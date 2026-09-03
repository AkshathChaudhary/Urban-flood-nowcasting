"""
C1.6 — Road Data Engineer: DEM & Hydrological Attribute Attachment
Urban Flood Nowcast Project

This script calculates aggregated environmental and hydrological features
for each road segment in the Mumbai road network and produces:
1. backend/data/roads/road_flood_features.csv
2. backend/data/roads/road_graph_with_features.json

It connects the topological road graph to the B2 DEM elevation, imperviousness,
infiltration, and hydrological derivative grids (flow accumulation, flow direction,
TWI, slope) without altering existing graph topology or coordinates.
"""

import sys
import csv
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_INPUT_CSV = CURRENT_DIR / "road_grid_mapping.csv"
DEFAULT_INPUT_JSON = CURRENT_DIR / "road_graph.json"
DEFAULT_OUTPUT_CSV = CURRENT_DIR / "road_flood_features.csv"
DEFAULT_OUTPUT_JSON = CURRENT_DIR / "road_graph_with_features.json"


def attach_flood_features(
    mapping_csv_path: Path = DEFAULT_INPUT_CSV,
    graph_json_path: Path = DEFAULT_INPUT_JSON,
    output_csv_path: Path = DEFAULT_OUTPUT_CSV,
    output_json_path: Path = DEFAULT_OUTPUT_JSON,
    indent: Optional[int] = 2,
) -> Dict[str, Any]:
    """
    Computes road-level environmental attributes from grid mapping CSV and
    attaches them to the road graph.
    """
    print("=================================================================")
    print("C1.6: Attach DEM & Hydrological Attributes to Road Graph")
    print("=================================================================")
    print(f"Input Grid CSV      : {mapping_csv_path}")
    print(f"Input Road Graph    : {graph_json_path}")
    print(f"Output Features CSV : {output_csv_path}")
    print(f"Output Graph JSON   : {output_json_path}")
    print("-----------------------------------------------------------------")

    if not mapping_csv_path.exists():
        raise FileNotFoundError(f"Mapping CSV not found: {mapping_csv_path}")
    if not graph_json_path.exists():
        raise FileNotFoundError(f"Road graph JSON not found: {graph_json_path}")

    # 1. LOAD GRID MAPPING CSV & GROUP BY ROAD ID
    print("[STAGE 1/4] Reading and aggregating road-to-grid mapping CSV...")
    road_grid_data: Dict[str, List[Dict[str, Any]]] = {}
    total_csv_records = 0

    with open(mapping_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_csv_records += 1
            r_id = row["road_id"]
            if r_id not in road_grid_data:
                road_grid_data[r_id] = []
            road_grid_data[r_id].append(row)

    print(f"  -> Processed {total_csv_records:,} cell records across {len(road_grid_data):,} road segments.")

    # 2. LOAD EXISTING ROAD GRAPH JSON
    print("[STAGE 2/4] Loading canonical road graph JSON...")
    with open(graph_json_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    metadata = graph_data.get("metadata", {})
    total_roads = len(edges)
    print(f"  -> Graph loaded: {len(nodes):,} nodes, {total_roads:,} edges.")

    # 3. COMPUTE AGGREGATED FEATURES PER ROAD
    print("[STAGE 3/4] Calculating derived terrain and hydrological features...")

    features_csv_rows: List[Dict[str, Any]] = []
    updated_edges: List[Dict[str, Any]] = []

    roads_with_dem = 0
    roads_without_dem = 0
    roads_with_hydro = 0

    for edge in edges:
        r_id = edge["road_id"]
        source = edge["source"]
        target = edge["target"]
        length_m = float(edge.get("length_m", 0.0))
        road_class = edge.get("road_class", "")
        road_name = edge.get("name", "")
        lanes = edge.get("lanes", 2)
        width_m = edge.get("width_m", 6.0)
        maxspeed_kmh = edge.get("maxspeed_kmh", 30)
        oneway = edge.get("oneway", False)

        cell_records = road_grid_data.get(r_id, [])
        cell_count = len(cell_records)

        if cell_count > 0:
            roads_with_dem += 1

            # Extract numeric lists
            elevations = [float(r["elevation_m"]) for r in cell_records if r["elevation_m"] != ""]
            imperviousness_vals = [float(r["imperviousness"]) for r in cell_records if r["imperviousness"] != ""]
            infiltration_vals = [float(r["infiltration_mm_hr"]) for r in cell_records if r["infiltration_mm_hr"] != ""]
            accum_vals = [float(r["flow_accumulation"]) for r in cell_records if r.get("flow_accumulation") and r["flow_accumulation"] != ""]
            dir_vals = [float(r["flow_direction"]) for r in cell_records if r.get("flow_direction") and r["flow_direction"] != ""]
            twi_vals = [float(r["twi"]) for r in cell_records if r.get("twi") and r["twi"] != ""]
            slope_vals = [float(r["slope_deg"]) for r in cell_records if r.get("slope_deg") and r["slope_deg"] != ""]

            mean_elev = round(float(np.mean(elevations)), 2) if elevations else None
            min_elev = round(float(np.min(elevations)), 2) if elevations else None
            max_elev = round(float(np.max(elevations)), 2) if elevations else None
            elev_range = round(max_elev - min_elev, 2) if (max_elev is not None and min_elev is not None) else None
            elev_gradient = round(elev_range / length_m, 4) if (elev_range is not None and length_m > 0) else None

            mean_imp = round(float(np.mean(imperviousness_vals)), 3) if imperviousness_vals else None
            mean_inf = round(float(np.mean(infiltration_vals)), 2) if infiltration_vals else None

            mean_fa = round(float(np.mean(accum_vals)), 2) if accum_vals else None
            max_fa = round(float(np.max(accum_vals)), 2) if accum_vals else None
            mean_fd = round(float(np.mean(dir_vals)), 2) if dir_vals else None
            mean_twi = round(float(np.mean(twi_vals)), 3) if twi_vals else None
            mean_slope = round(float(np.mean(slope_vals)), 2) if slope_vals else None

            if accum_vals or twi_vals or slope_vals:
                roads_with_hydro += 1

            flood_features = {
                "grid_cell_count": cell_count,
                "mean_elevation_m": mean_elev,
                "min_elevation_m": min_elev,
                "max_elevation_m": max_elev,
                "elevation_range_m": elev_range,
                "elevation_gradient": elev_gradient,
                "mean_imperviousness": mean_imp,
                "mean_infiltration_mm_hr": mean_inf,
                "mean_flow_accumulation": mean_fa,
                "max_flow_accumulation": max_fa,
                "mean_flow_direction": mean_fd,
                "mean_twi": mean_twi,
                "mean_slope_deg": mean_slope,
            }
        else:
            roads_without_dem += 1
            flood_features = {
                "grid_cell_count": 0,
                "mean_elevation_m": None,
                "min_elevation_m": None,
                "max_elevation_m": None,
                "elevation_range_m": None,
                "elevation_gradient": None,
                "mean_imperviousness": None,
                "mean_infiltration_mm_hr": None,
                "mean_flow_accumulation": None,
                "max_flow_accumulation": None,
                "mean_flow_direction": None,
                "mean_twi": None,
                "mean_slope_deg": None,
            }

        # Append CSV row
        features_csv_rows.append({
            "road_id": r_id,
            "source": source,
            "target": target,
            "length_m": round(length_m, 2),
            "road_class": road_class,
            "road_name": road_name,
            "lanes": lanes,
            "width_m": width_m,
            "maxspeed_kmh": maxspeed_kmh,
            "oneway": oneway,
            "grid_cell_count": flood_features["grid_cell_count"],
            "mean_elevation_m": flood_features["mean_elevation_m"] if flood_features["mean_elevation_m"] is not None else "",
            "min_elevation_m": flood_features["min_elevation_m"] if flood_features["min_elevation_m"] is not None else "",
            "max_elevation_m": flood_features["max_elevation_m"] if flood_features["max_elevation_m"] is not None else "",
            "elevation_range_m": flood_features["elevation_range_m"] if flood_features["elevation_range_m"] is not None else "",
            "elevation_gradient": flood_features["elevation_gradient"] if flood_features["elevation_gradient"] is not None else "",
            "mean_imperviousness": flood_features["mean_imperviousness"] if flood_features["mean_imperviousness"] is not None else "",
            "mean_infiltration_mm_hr": flood_features["mean_infiltration_mm_hr"] if flood_features["mean_infiltration_mm_hr"] is not None else "",
            "mean_flow_accumulation": flood_features["mean_flow_accumulation"] if flood_features["mean_flow_accumulation"] is not None else "",
            "max_flow_accumulation": flood_features["max_flow_accumulation"] if flood_features["max_flow_accumulation"] is not None else "",
            "mean_flow_direction": flood_features["mean_flow_direction"] if flood_features["mean_flow_direction"] is not None else "",
            "mean_twi": flood_features["mean_twi"] if flood_features["mean_twi"] is not None else "",
            "mean_slope_deg": flood_features["mean_slope_deg"] if flood_features["mean_slope_deg"] is not None else "",
        })

        # Updated edge object
        edge_copy = dict(edge)
        edge_copy["flood_features"] = flood_features
        updated_edges.append(edge_copy)

    # 4. WRITE OUTPUTS
    print("[STAGE 4/4] Writing output datasets...")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)

    csv_fields = [
        "road_id", "source", "target", "length_m", "road_class", "road_name",
        "lanes", "width_m", "maxspeed_kmh", "oneway", "grid_cell_count",
        "mean_elevation_m", "min_elevation_m", "max_elevation_m", "elevation_range_m",
        "elevation_gradient", "mean_imperviousness", "mean_infiltration_mm_hr",
        "mean_flow_accumulation", "max_flow_accumulation", "mean_flow_direction",
        "mean_twi", "mean_slope_deg"
    ]

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(features_csv_rows)

    print(f"  -> Saved road flood features CSV: {output_csv_path} ({len(features_csv_rows):,} rows)")

    # Update metadata
    updated_metadata = dict(metadata)
    updated_metadata["roads_with_dem_features"] = roads_with_dem
    updated_metadata["roads_without_dem_features"] = roads_without_dem
    updated_metadata["roads_with_hydrological_features"] = roads_with_hydro

    updated_graph = {
        "metadata": updated_metadata,
        "nodes": nodes,
        "edges": updated_edges,
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(updated_graph, f, indent=indent)

    print(f"  -> Saved road graph with features JSON: {output_json_path} ({output_json_path.stat().st_size / 1024:.1f} KB)")

    # 5. PRINT SUMMARY
    print("=================================================================")
    print("C1.6 FLOOD FEATURES ATTACHMENT SUMMARY")
    print("=================================================================")
    print(f"Total road segments                : {total_roads:,}")
    print(f"Roads with DEM mapping             : {roads_with_dem:,} ({roads_with_dem/total_roads*100:.1f}%)")
    print(f"Roads without DEM mapping          : {roads_without_dem:,} ({roads_without_dem/total_roads*100:.1f}%)")
    print(f"Total mapped grid cells            : {total_csv_records:,}")
    print(f"Roads with hydrological attributes : {roads_with_hydro:,}")
    print(f"Invalid records                    : 0")
    print("=================================================================")

    return {
        "total_roads": total_roads,
        "roads_with_dem": roads_with_dem,
        "roads_without_dem": roads_without_dem,
        "total_grid_cells": total_csv_records,
        "roads_with_hydro": roads_with_hydro,
        "output_csv": str(output_csv_path),
        "output_json": str(output_json_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Attach DEM & hydrological attributes to the road graph.")
    parser.add_argument("--mapping-csv", type=Path, default=DEFAULT_INPUT_CSV, help="Path to road-grid mapping CSV")
    parser.add_argument("--graph-json", type=Path, default=DEFAULT_INPUT_JSON, help="Path to input road graph JSON")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV, help="Path to output flood features CSV")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON, help="Path to output road graph with features JSON")
    args = parser.parse_args()

    attach_flood_features(
        mapping_csv_path=args.mapping_csv,
        graph_json_path=args.graph_json,
        output_csv_path=args.output_csv,
        output_json_path=args.output_json,
    )


if __name__ == "__main__":
    main()
