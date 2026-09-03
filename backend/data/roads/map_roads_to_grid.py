"""
C1.4 — Road Data Engineer: Road-to-DEM Grid Mapping Pipeline
Urban Flood Nowcast Project

This script maps the normalized C1 road network (from GraphML) onto the
standard 200 x 200 B2 DEM elevation and hydrological grid.

Pipeline Outputs:
- backend/data/roads/road_grid_mapping.csv
    Cell-level mapping table linking each road segment to its traversed DEM grid cells
    with cell-specific elevation, imperviousness, infiltration, and hydrological attributes.
- backend/data/roads/road_grid_mapping.geojson
    Road-level GeoJSON preserving original geometry and metadata, enriched with
    traversed grid cell arrays and aggregated terrain metrics.
- backend/data/roads/road_grid_validation.png
    Diagnostic visualization verifying alignment of roads against the DEM grid.
"""

import sys
import os
import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np
import networkx as nx
from shapely import wkt
from shapely.geometry import LineString, MultiLineString, mapping
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Ensure backend package resolution
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.roads.grid_mapping import (
    ORIGIN_LAT,
    ORIGIN_LON,
    MAX_LAT,
    MAX_LON,
    GRID_ROWS,
    GRID_COLS,
    CELL_SIZE_M,
    sample_linestring_to_cells,
    grid_to_latlon,
    latlon_to_grid,
    is_in_bounds,
)


# -------------------------------------------------------------------------
# DEFAULT FILE PATHS
# -------------------------------------------------------------------------

DEFAULT_INPUT_ROADS = CURRENT_DIR / "raw" / "osm_roads_mumbai_attributes.graphml"
DEFAULT_DEM_DIR = PROJECT_ROOT / "backend" / "data" / "dem"
DEFAULT_OUTPUT_CSV = CURRENT_DIR / "road_grid_mapping.csv"
DEFAULT_OUTPUT_GEOJSON = CURRENT_DIR / "road_grid_mapping.geojson"
DEFAULT_OUTPUT_PLOT = CURRENT_DIR / "road_grid_validation.png"


# -------------------------------------------------------------------------
# HYDROLOGICAL RASTER RESAMPLING & EXTRACTION HELPERS
# -------------------------------------------------------------------------

def load_or_resample_raster(
    tif_path: Path,
    target_shape: Tuple[int, int] = (GRID_ROWS, GRID_COLS),
    is_categorical: bool = False
) -> Optional[np.ndarray]:
    """
    Loads a GeoTIFF raster and resamples it to target 200x200 grid shape
    matching the DEM array orientation.
    """
    if not tif_path.exists():
        return None

    try:
        import rasterio
        from rasterio.enums import Resampling

        resample_method = Resampling.nearest if is_categorical else Resampling.bilinear

        with rasterio.open(tif_path) as src:
            data = src.read(
                1,
                out_shape=target_shape,
                resampling=resample_method
            ).astype(np.float32)

            # Mask standard nodata values
            nodata_val = src.nodata
            if nodata_val is not None:
                invalid_mask = np.isclose(data, nodata_val) | (data <= -9000)
                data[invalid_mask] = np.nan
            else:
                invalid_mask = data <= -9000
                data[invalid_mask] = np.nan

            return data

    except Exception as e:
        print(f"[WARN] Could not resample {tif_path.name}: {e}")
        return None


# -------------------------------------------------------------------------
# MAIN ROAD-TO-GRID MAPPING PIPELINE
# -------------------------------------------------------------------------

def map_roads_to_grid(
    input_roads_path: Path = DEFAULT_INPUT_ROADS,
    dem_dir: Path = DEFAULT_DEM_DIR,
    output_csv_path: Path = DEFAULT_OUTPUT_CSV,
    output_geojson_path: Path = DEFAULT_OUTPUT_GEOJSON,
    output_plot_path: Path = DEFAULT_OUTPUT_PLOT,
    sample_step_m: float = 5.0,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Executes the complete Road-to-DEM grid mapping pipeline.
    """
    print("=================================================================")
    print("C1.4: Road-to-DEM Grid Mapping Pipeline")
    print("=================================================================")
    print(f"Road Input Graph    : {input_roads_path}")
    print(f"DEM Directory       : {dem_dir}")
    print(f"Output CSV Table    : {output_csv_path}")
    print(f"Output GeoJSON      : {output_geojson_path}")
    print(f"Output Validation   : {output_plot_path}")
    print("-----------------------------------------------------------------")

    # 1. VERIFY INPUT FILES EXISTENCE
    if not input_roads_path.exists():
        raise FileNotFoundError(f"Input road graphml file not found: {input_roads_path}")

    elev_file = dem_dir / "elevation_grid.npy"
    imperv_file = dem_dir / "imperviousness.npy"
    infil_file = dem_dir / "infiltration.npy"

    for f in [elev_file, imperv_file, infil_file]:
        if not f.exists():
            raise FileNotFoundError(f"Required DEM grid file missing: {f}")

    # 2. LOAD DEM & HYDROLOGICAL ARRAYS
    print("[STAGE 1/5] Loading DEM arrays and hydrological rasters...")
    elev_grid = np.load(elev_file).astype(np.float32)
    imperv_grid = np.load(imperv_file).astype(np.float32)
    infil_grid = np.load(infil_file).astype(np.float32)

    # Validate DEM Shapes
    assert elev_grid.shape == (GRID_ROWS, GRID_COLS), f"Elevation grid shape mismatch: {elev_grid.shape}"
    assert imperv_grid.shape == (GRID_ROWS, GRID_COLS), f"Imperviousness grid shape mismatch: {imperv_grid.shape}"
    assert infil_grid.shape == (GRID_ROWS, GRID_COLS), f"Infiltration grid shape mismatch: {infil_grid.shape}"
    print(f"  -> DEM shape: {elev_grid.shape}, Elev min/max: {np.nanmin(elev_grid):.2f}m / {np.nanmax(elev_grid):.2f}m")

    # Load optional hydrological rasters (resampled to 200x200)
    flow_accum_grid = load_or_resample_raster(dem_dir / "raw" / "D8_Flow_Accumulation.tif", is_categorical=False)
    flow_dir_grid = load_or_resample_raster(dem_dir / "raw" / "D8_Flow_Direction.tif", is_categorical=True)
    twi_grid = load_or_resample_raster(dem_dir / "raw" / "TWI.tif", is_categorical=False)
    slope_grid = load_or_resample_raster(dem_dir / "raw" / "viz" / "viz.be_slope.tif", is_categorical=False)

    print("  -> Loaded hydrological rasters: " + ", ".join(
        [k for k, v in [
            ("FlowAccum", flow_accum_grid),
            ("FlowDir", flow_dir_grid),
            ("TWI", twi_grid),
            ("Slope", slope_grid)
        ] if v is not None]
    ))

    # 3. LOAD ROAD GRAPH & PARSE ATTRIBUTES
    print("[STAGE 2/5] Loading road network graph...")
    G = nx.read_graphml(input_roads_path)
    total_edges = len(G.edges)
    print(f"  -> Total road segments in graph: {total_edges}")

    # 4. DISCRETIZE ROADS & MAP TO GRID CELLS
    print(f"[STAGE 3/5] Discretizing road geometries (step={sample_step_m}m) & mapping to cells...")

    csv_rows = []
    geojson_features = []

    total_roads = 0
    roads_mapped = 0
    roads_outside = 0
    invalid_geoms = 0
    missing_ids = 0

    unique_grid_cells_covered: Set[Tuple[int, int]] = set()
    cell_road_density = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.int32)

    # Sort edges deterministically
    sorted_edges = sorted(G.edges(keys=True, data=True), key=lambda x: (str(x[0]), str(x[1]), x[2]))

    for idx, (u, v, k, data) in enumerate(sorted_edges, start=1):
        total_roads += 1
        road_id = data.get("id")
        if not road_id:
            road_id = f"R-{idx:03d}" if idx < 1000 else f"R-{idx}"
            missing_ids += 1

        road_name = data.get("name", "")
        if road_name is None or str(road_name).lower() in ["none", "nan", "null"]:
            road_name = ""

        highway_type = data.get("highway_type") or data.get("highway") or "unclassified"
        lanes = int(data.get("lanes", 2))
        width_m = float(data.get("width_m", 6.0))
        length_m = float(data.get("length_m") or data.get("length") or 0.0)
        maxspeed_kmh = int(data.get("maxspeed_kmh", 30))
        lanes_src = data.get("lanes_source", "estimated")
        width_src = data.get("width_source", "estimated")
        speed_src = data.get("speed_source", "estimated")

        # Parse geometry
        geom = None
        if "geometry" in data and data["geometry"]:
            try:
                geom = wkt.loads(data["geometry"]) if isinstance(data["geometry"], str) else data["geometry"]
            except Exception:
                geom = None
        
        if geom is None:
            # Fallback to straight line between nodes u and v
            try:
                u_node = G.nodes[u]
                v_node = G.nodes[v]
                x1, y1 = float(u_node["x"]), float(u_node["y"])
                x2, y2 = float(v_node["x"]), float(v_node["y"])
                geom = LineString([(x1, y1), (x2, y2)])
            except Exception:
                geom = None

        if geom is None or geom.is_empty:
            invalid_geoms += 1
            continue

        # Sample grid cells along geometry
        cells = sample_linestring_to_cells(geom, sample_step_m=sample_step_m, keep_only_in_bounds=True)

        if len(cells) == 0:
            roads_outside += 1
            is_inside = False
        else:
            roads_mapped += 1
            is_inside = True

        # Extract cell-level attributes
        cell_elevations = []
        cell_imperv = []
        cell_infil = []
        cell_slope = []
        cell_twi = []
        cell_accum = []

        for r, c in cells:
            unique_grid_cells_covered.add((r, c))
            cell_road_density[r, c] += 1

            # Grid values
            elev_val = float(elev_grid[r, c])
            imp_val = float(imperv_grid[r, c])
            inf_val = float(infil_grid[r, c])

            fa_val = float(flow_accum_grid[r, c]) if flow_accum_grid is not None and not np.isnan(flow_accum_grid[r, c]) else None
            fd_val = int(flow_dir_grid[r, c]) if flow_dir_grid is not None and not np.isnan(flow_dir_grid[r, c]) else None
            twi_val = float(twi_grid[r, c]) if twi_grid is not None and not np.isnan(twi_grid[r, c]) else None
            slope_val = float(slope_grid[r, c]) if slope_grid is not None and not np.isnan(slope_grid[r, c]) else None

            cell_elevations.append(elev_val)
            cell_imperv.append(imp_val)
            cell_infil.append(inf_val)
            if slope_val is not None:
                cell_slope.append(slope_val)
            if twi_val is not None:
                cell_twi.append(twi_val)
            if fa_val is not None:
                cell_accum.append(fa_val)

            csv_rows.append({
                "road_id": road_id,
                "grid_row": r,
                "grid_col": c,
                "road_length_m": round(length_m, 2),
                "road_class": highway_type,
                "road_name": road_name,
                "lanes": lanes,
                "width_m": round(width_m, 2),
                "maxspeed_kmh": maxspeed_kmh,
                "lanes_source": lanes_src,
                "width_source": width_src,
                "speed_source": speed_src,
                "elevation_m": round(elev_val, 2),
                "imperviousness": round(imp_val, 3),
                "infiltration_mm_hr": round(inf_val, 2),
                "flow_accumulation": round(fa_val, 2) if fa_val is not None else "",
                "flow_direction": fd_val if fd_val is not None else "",
                "twi": round(twi_val, 3) if twi_val is not None else "",
                "slope_deg": round(slope_val, 2) if slope_val is not None else "",
            })

        # Construct GeoJSON feature
        feature_props = {
            "road_id": road_id,
            "name": road_name,
            "highway_type": highway_type,
            "lanes": lanes,
            "width_m": round(width_m, 2),
            "length_m": round(length_m, 2),
            "maxspeed_kmh": maxspeed_kmh,
            "lanes_source": lanes_src,
            "width_source": width_src,
            "speed_source": speed_src,
            "inside_grid": is_inside,
            "cell_count": len(cells),
            "grid_cells": [[r, c] for r, c in cells],
            "min_elevation_m": round(float(np.min(cell_elevations)), 2) if cell_elevations else None,
            "max_elevation_m": round(float(np.max(cell_elevations)), 2) if cell_elevations else None,
            "mean_elevation_m": round(float(np.mean(cell_elevations)), 2) if cell_elevations else None,
            "mean_imperviousness": round(float(np.mean(cell_imperv)), 3) if cell_imperv else None,
            "mean_infiltration_mm_hr": round(float(np.mean(cell_infil)), 2) if cell_infil else None,
            "mean_slope_deg": round(float(np.mean(cell_slope)), 2) if cell_slope else None,
            "mean_twi": round(float(np.mean(cell_twi)), 3) if cell_twi else None,
            "max_flow_accum": round(float(np.max(cell_accum)), 2) if cell_accum else None,
        }

        geojson_features.append({
            "type": "Feature",
            "id": road_id,
            "properties": feature_props,
            "geometry": mapping(geom)
        })

    # 5. WRITE CSV & GEOJSON OUTPUTS
    print("[STAGE 4/5] Writing output datasets...")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

    csv_fieldnames = [
        "road_id", "grid_row", "grid_col", "road_length_m", "road_class",
        "road_name", "lanes", "width_m", "maxspeed_kmh", "lanes_source",
        "width_source", "speed_source", "elevation_m", "imperviousness",
        "infiltration_mm_hr", "flow_accumulation", "flow_direction", "twi", "slope_deg"
    ]

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"  -> Saved CSV mapping table: {output_csv_path} ({len(csv_rows):,} rows)")

    geojson_collection = {
        "type": "FeatureCollection",
        "name": "mumbai_roads_dem_grid_mapping",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": geojson_features
    }

    with open(output_geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_collection, f, indent=2)
    print(f"  -> Saved GeoJSON dataset: {output_geojson_path} ({len(geojson_features):,} features)")

    # 6. GENERATE VALIDATION VISUALIZATION
    print("[STAGE 5/5] Generating validation visualization...")
    generate_validation_plot(
        elev_grid=elev_grid,
        imperv_grid=imperv_grid,
        density_grid=cell_road_density,
        geojson_features=geojson_features,
        csv_rows=csv_rows,
        output_plot_path=output_plot_path
    )

    # 7. SUMMARY REPORT
    report = {
        "total_roads": total_roads,
        "roads_mapped": roads_mapped,
        "roads_outside_grid": roads_outside,
        "invalid_geometries": invalid_geoms,
        "missing_ids": missing_ids,
        "unique_grid_cells_covered": len(unique_grid_cells_covered),
        "total_grid_cells": GRID_ROWS * GRID_COLS,
        "grid_coverage_pct": round((len(unique_grid_cells_covered) / (GRID_ROWS * GRID_COLS)) * 100, 2),
        "total_road_cell_records": len(csv_rows),
        "output_csv": str(output_csv_path),
        "output_geojson": str(output_geojson_path),
        "output_plot": str(output_plot_path),
    }

    print("=================================================================")
    print("MAPPING VALIDATION SUMMARY")
    print("=================================================================")
    print(f"Total Roads Evaluated          : {report['total_roads']:,}")
    print(f"Roads Successfully Mapped      : {report['roads_mapped']:,} ({report['roads_mapped']/report['total_roads']*100:.1f}%)")
    print(f"Roads Outside DEM Grid Extent  : {report['roads_outside_grid']:,}")
    print(f"Invalid Geometries             : {report['invalid_geometries']}")
    print(f"Unique Grid Cells Covered      : {report['unique_grid_cells_covered']:,} / {report['total_grid_cells']:,} ({report['grid_coverage_pct']}%)")
    print(f"Total Road-Grid Cell Records   : {report['total_road_cell_records']:,}")
    print("=================================================================")

    return report


def generate_validation_plot(
    elev_grid: np.ndarray,
    imperv_grid: np.ndarray,
    density_grid: np.ndarray,
    geojson_features: List[Dict[str, Any]],
    csv_rows: List[Dict[str, Any]],
    output_plot_path: Path
):
    """
    Renders a multi-panel diagnostic figure validating road network alignment
    with the 200x200 DEM grid.
    """
    output_plot_path.parent.mkdir(parents=True, exist_ok=True)

    plt.style.use('dark_background')
    fig, axes = plt.subplots(2, 2, figsize=(18, 16), dpi=160)
    fig.patch.set_facecolor('#0d1117')
    for ax in axes.flat:
        ax.set_facecolor('#161b22')

    # PANEL 1: DEM Elevation with Road Network Overlay
    ax1 = axes[0, 0]
    im1 = ax1.imshow(elev_grid, cmap='terrain', origin='lower', extent=[ORIGIN_LON, MAX_LON, ORIGIN_LAT, MAX_LAT])
    cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
    cbar1.set_label('DEM Elevation (m ASL)', color='white')
    cbar1.ax.tick_params(colors='white')

    # Overlay road lines
    hw_colors = {
        "motorway": "#ff4757",
        "trunk": "#ff6b81",
        "primary": "#ffa502",
        "secondary": "#eccc68",
        "tertiary": "#70a1ff",
        "residential": "#2ed573",
        "unclassified": "#a4b0be",
    }

    plotted_classes = set()
    for feat in geojson_features:
        geom = feat["geometry"]
        hw = feat["properties"]["highway_type"]
        color = hw_colors.get(hw, "#5352ed")
        label = hw.capitalize() if hw not in plotted_classes else None
        if label:
            plotted_classes.add(hw)

        if geom["type"] == "LineString":
            coords = geom["coordinates"]
            xs, ys = [c[0] for c in coords], [c[1] for c in coords]
            ax1.plot(xs, ys, color=color, linewidth=1.2, alpha=0.85, label=label)

    ax1.set_xlim(ORIGIN_LON - 0.001, MAX_LON + 0.001)
    ax1.set_ylim(ORIGIN_LAT - 0.001, MAX_LAT + 0.001)
    ax1.plot([ORIGIN_LON, MAX_LON, MAX_LON, ORIGIN_LON, ORIGIN_LON],
             [ORIGIN_LAT, ORIGIN_LAT, MAX_LAT, MAX_LAT, ORIGIN_LAT],
             color='#ffffff', linestyle='--', linewidth=1.5, label='DEM Bounding Box')

    ax1.set_title("1. Road Network Overlaid on 200×200 DEM Elevation", fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
    ax1.set_xlabel("Longitude (°E)", color='#8b949e')
    ax1.set_ylabel("Latitude (°N)", color='#8b949e')
    ax1.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d', fontsize=8)
    ax1.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    # PANEL 2: Grid Cell Road Density (Rasterized Cells)
    ax2 = axes[0, 1]
    masked_density = np.ma.masked_where(density_grid == 0, density_grid)
    im2_bg = ax2.imshow(elev_grid, cmap='gray', origin='lower', extent=[0, 200, 0, 200], alpha=0.35)
    im2 = ax2.imshow(masked_density, cmap='plasma', origin='lower', extent=[0, 200, 0, 200], interpolation='nearest')
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.set_label('Road Segments / Cell', color='white')
    cbar2.ax.tick_params(colors='white')

    ax2.set_title(f"2. Rasterized Road Cell Density ({np.count_nonzero(density_grid):,} Active Cells)", fontsize=13, fontweight='bold', color='#f0883e', pad=10)
    ax2.set_xlabel("DEM Grid Column (0-199)", color='#8b949e')
    ax2.set_ylabel("DEM Grid Row (0-199)", color='#8b949e')
    ax2.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    # PANEL 3: Imperviousness with Road Footprint Overlay
    ax3 = axes[1, 0]
    im3 = ax3.imshow(imperv_grid, cmap='inferno', origin='lower', extent=[0, 200, 0, 200])
    cbar3 = fig.colorbar(im3, ax=ax3, fraction=0.046, pad=0.04)
    cbar3.set_label('Imperviousness Index (0 to 1)', color='white')
    cbar3.ax.tick_params(colors='white')

    # Overlay sampled cells
    cell_cols = [r["grid_col"] for r in csv_rows]
    cell_rows = [r["grid_row"] for r in csv_rows]
    ax3.scatter(cell_cols, cell_rows, s=1, c='#00d2ff', alpha=0.3, label='Mapped Road Cells')

    ax3.set_title("3. Road Cell Overlay on Imperviousness Surface", fontsize=13, fontweight='bold', color='#3fb950', pad=10)
    ax3.set_xlabel("DEM Grid Column (0-199)", color='#8b949e')
    ax3.set_ylabel("DEM Grid Row (0-199)", color='#8b949e')
    ax3.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d', fontsize=8)
    ax3.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    # PANEL 4: Road Cell Elevation & Slope Distribution
    ax4 = axes[1, 1]
    road_elevations = [r["elevation_m"] for r in csv_rows if r["elevation_m"] is not None]
    road_slopes = [r["slope_deg"] for r in csv_rows if r["slope_deg"] != ""]

    ax4.hist(elev_grid.flatten(), bins=40, density=True, color='#58a6ff', alpha=0.4, label='Entire DEM Elevation')
    ax4.hist(road_elevations, bins=40, density=True, color='#ffa502', alpha=0.6, label='Road Network Cells')

    ax4.set_title("4. Elevation Distribution: Road Cells vs Full DEM", fontsize=13, fontweight='bold', color='#d2a8ff', pad=10)
    ax4.set_xlabel("Elevation (m ASL)", color='#8b949e')
    ax4.set_ylabel("Probability Density", color='#8b949e')
    ax4.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d', fontsize=9)
    ax4.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    plt.suptitle("C1.4 ROAD-TO-DEM GRID MAPPING VALIDATION SUITE (200×200 EPSG:4326)", fontsize=16, fontweight='heavy', color='#ffffff', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    plt.savefig(output_plot_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
    print(f"  -> Saved validation plot: {output_plot_path}")
    plt.close()


# -------------------------------------------------------------------------
# CLI ENTRY POINT
# -------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Map C1 road network onto the 200x200 B2 DEM grid.")
    parser.add_argument("--input-roads", type=Path, default=DEFAULT_INPUT_ROADS, help="Path to input road graphml file")
    parser.add_argument("--dem-dir", type=Path, default=DEFAULT_DEM_DIR, help="Path to DEM directory")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV, help="Path to output CSV table")
    parser.add_argument("--output-geojson", type=Path, default=DEFAULT_OUTPUT_GEOJSON, help="Path to output GeoJSON")
    parser.add_argument("--output-plot", type=Path, default=DEFAULT_OUTPUT_PLOT, help="Path to output validation plot")
    parser.add_argument("--sample-step-m", type=float, default=5.0, help="LineString sample step in meters")
    parser.add_argument("--force", action="store_true", help="Force overwrite of existing files")

    args = parser.parse_args()

    map_roads_to_grid(
        input_roads_path=args.input_roads,
        dem_dir=args.dem_dir,
        output_csv_path=args.output_csv,
        output_geojson_path=args.output_geojson,
        output_plot_path=args.output_plot,
        sample_step_m=args.sample_step_m,
        force=args.force,
    )


if __name__ == "__main__":
    main()
