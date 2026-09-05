import math
from pathlib import Path
import numpy as np

import json
from PIL import Image, ImageDraw

# Project Grid Parameters (From developer_assignments.md)
GRID_ROWS = 200
GRID_COLS = 200
CELL_SIZE_M = 10.0
# Domain bounds (matching Hydro_Conditioned_DEM.tif)
MIN_LAT_DEFAULT = 19.06013888888332
MAX_LAT_DEFAULT = 19.07819444443888
MIN_LON_DEFAULT = 72.84986111114458
MAX_LON_DEFAULT = 72.86875000003347

def rasterize_osm_waterbodies(
    osm_path: Path,
    grid_rows: int = 200,
    grid_cols: int = 200,
    min_lat: float = MIN_LAT_DEFAULT,
    max_lat: float = MAX_LAT_DEFAULT,
    min_lon: float = MIN_LON_DEFAULT,
    max_lon: float = MAX_LON_DEFAULT,
) -> np.ndarray:
    """
    Rasterize OpenStreetMap water bodies and waterways onto the study area grid.
    Uses OpenStreetMap data EXCLUSIVELY:
    - Multipolygon relations (e.g. Mithi River): renders outer polygon, cuts inner island holes
    - Closed polygons: lakes, ponds, basins, reservoirs, natural=water
    - Linear waterways: streams, canals, drains, rivers
    """
    with open(osm_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = {e["id"]: (e["lat"], e["lon"]) for e in data.get("elements", []) if e.get("type") == "node"}
    ways = {e["id"]: e for e in data.get("elements", []) if e.get("type") == "way"}
    relations = [e for e in data.get("elements", []) if e.get("type") == "relation"]

    def latlon_to_xy(lat: float, lon: float):
        # x corresponds to columns (West to East)
        # y corresponds to rows (North to South, row 0 is top / max_lat)
        x = (lon - min_lon) / (max_lon - min_lon) * (grid_cols - 1)
        y = (max_lat - lat) / (max_lat - min_lat) * (grid_rows - 1)
        return (x, y)

    img = Image.new("1", (grid_cols, grid_rows), 0)
    draw = ImageDraw.Draw(img)

    # 1. Relations (multipolygons: river channels, tidal water bodies)
    for rel in relations:
        # Sort so outer boundaries are filled first, then inner island holes are cut out
        members = sorted(rel.get("members", []), key=lambda m: 0 if m.get("role") == "outer" else 1)
        for m in members:
            role = m.get("role")
            w_id = m.get("ref")
            w = ways.get(w_id)
            if not w:
                continue
            coords = []
            if "geometry" in w:
                coords = [latlon_to_xy(pt["lat"], pt["lon"]) for pt in w["geometry"]]
            elif "nodes" in w:
                coords = [latlon_to_xy(nodes[nid][0], nodes[nid][1]) for nid in w["nodes"] if nid in nodes]

            if len(coords) >= 3:
                fill_val = 1 if role == "outer" else 0
                draw.polygon(coords, fill=fill_val)

    # 2. Standalone ways
    for w_id, w in ways.items():
        tags = w.get("tags") or {}
        # Skip relation member outer ways that have no independent tags
        is_rel_member = any(m.get("ref") == w_id for rel in relations for m in rel.get("members", []))
        if is_rel_member and not tags:
            continue

        coords = []
        if "geometry" in w:
            coords = [latlon_to_xy(pt["lat"], pt["lon"]) for pt in w["geometry"]]
        elif "nodes" in w:
            coords = [latlon_to_xy(nodes[nid][0], nodes[nid][1]) for nid in w["nodes"] if nid in nodes]

        if not coords:
            continue

        is_closed = (
            coords[0] == coords[-1]
            or (len(coords) > 2 and math.hypot(coords[0][0] - coords[-1][0], coords[0][1] - coords[-1][1]) < 2.0)
        )
        natural = tags.get("natural")
        water = tags.get("water")
        landuse = tags.get("landuse")
        waterway = tags.get("waterway")

        if is_closed and (
            natural == "water"
            or landuse in ("basin", "reservoir")
            or water in ("river", "canal", "basin", "pond")
        ):
            draw.polygon(coords, fill=1)
        else:
            # Linear waterway: canal/river/Vakola Nala width=3 (~30m), streams/drains width=2 (~20m)
            width = 3 if waterway in ("canal", "river") or tags.get("name") == "Vakola Nala" else 2
            draw.line(coords, fill=1, width=width)

    return np.array(img, dtype=bool)


def rasterize_osm_retention_ponds(
    osm_path: Path,
    grid_rows: int = 200,
    grid_cols: int = 200,
    min_lat: float = MIN_LAT_DEFAULT,
    max_lat: float = MAX_LAT_DEFAULT,
    min_lon: float = MIN_LON_DEFAULT,
    max_lon: float = MAX_LON_DEFAULT,
) -> np.ndarray:
    """
    Rasterize OpenStreetMap retention ponds and detention basins onto the study area grid.
    Identifies enclosed water bodies / detention basins (e.g. Vidyapeeth Pond, university reservoirs)
    that act as stormwater buffering storage rather than open-draining river channels.
    """
    with open(osm_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = {e["id"]: (e["lat"], e["lon"]) for e in data.get("elements", []) if e.get("type") == "node"}
    ways = {e["id"]: e for e in data.get("elements", []) if e.get("type") == "way"}

    def latlon_to_xy(lat: float, lon: float):
        x = (lon - min_lon) / (max_lon - min_lon) * (grid_cols - 1)
        y = (max_lat - lat) / (max_lat - min_lat) * (grid_rows - 1)
        return (x, y)

    img = Image.new("1", (grid_cols, grid_rows), 0)
    draw = ImageDraw.Draw(img)

    for w_id, w in ways.items():
        tags = w.get("tags") or {}
        coords = []
        if "geometry" in w:
            coords = [latlon_to_xy(pt["lat"], pt["lon"]) for pt in w["geometry"]]
        elif "nodes" in w:
            coords = [latlon_to_xy(nodes[nid][0], nodes[nid][1]) for nid in w["nodes"] if nid in nodes]

        if not coords:
            continue

        is_closed = (
            coords[0] == coords[-1]
            or (len(coords) > 2 and math.hypot(coords[0][0] - coords[-1][0], coords[0][1] - coords[-1][1]) < 2.0)
        )
        natural = tags.get("natural")
        water = tags.get("water")
        landuse = tags.get("landuse")
        name = tags.get("name", "")

        # Ponds, reservoirs, and detention basins
        if is_closed and (
            name == "Vidyapeeth Pond"
            or landuse in ("basin", "reservoir")
            or water in ("basin", "pond", "reservoir")
            or (natural == "water" and water not in ("river", "canal") and tags.get("waterway") is None and tags.get("source") != "Yahoo")
        ):
            draw.polygon(coords, fill=1)

    return np.array(img, dtype=bool)


def hydro_enforce_channels(elevation_grid: np.ndarray, water_body_mask: np.ndarray) -> np.ndarray:
    """
    Hydro-enforces the DEM by burning bridge openings and culverts through
    elevated road/rail berms in the river channel.
    Satellite DEMs capture bridge decks (e.g. LBS Marg Bridge, Central Railway tracks)
    as 5-9m high artificial dams across the Mithi River. Hydro-enforcement carves the
    channel bed beneath these bridges down to the natural riverbed profile.
    """
    enforced = elevation_grid.copy()
    if np.any(water_body_mask):
        river_elevs = enforced[water_body_mask]
        baseline_bed = float(np.percentile(river_elevs, 25))
        bridge_spikes = water_body_mask & (enforced > 3.0)
        # Carve bridge decks down to local channel bed level
        enforced[bridge_spikes] = np.clip(enforced[bridge_spikes] - 4.5, baseline_bed, 2.8)
    return enforced


def process_dem_rasters(dem_dir: str):
    dem_path = Path(dem_dir)
    hydro_dem_file = dem_path / "raw" / "Hydro_Conditioned_DEM.tif"
    if not hydro_dem_file.exists():
        hydro_dem_file = dem_path / "raw" / "output_be.tif"

    min_lat, max_lat = MIN_LAT_DEFAULT, MAX_LAT_DEFAULT
    min_lon, max_lon = MIN_LON_DEFAULT, MAX_LON_DEFAULT

    try:
        import rasterio
        from rasterio.enums import Resampling

        with rasterio.open(hydro_dem_file) as src:
            min_lon = src.bounds.left
            max_lon = src.bounds.right
            min_lat = src.bounds.bottom
            max_lat = src.bounds.top

            # Resample to exactly 200x200 grid
            data = src.read(
                1,
                out_shape=(GRID_ROWS, GRID_COLS),
                resampling=Resampling.bilinear
            ).astype(np.float32)

            # Replace NoData/invalid values if any with minimum valid elevation
            valid_mask = (data > -100) & (data < 1000)
            if not np.all(valid_mask):
                min_valid = np.nanmin(data[valid_mask]) if np.any(valid_mask) else 5.0
                data[~valid_mask] = min_valid

            elevation_grid = data
            print(f"Loaded DEM via rasterio. Shape: {elevation_grid.shape}, Min: {elevation_grid.min():.2f}m, Max: {elevation_grid.max():.2f}m")

    except ImportError:
        # Fallback using PIL / pure numpy if rasterio is not installed
        im = Image.open(hydro_dem_file)
        im_resized = im.resize((GRID_COLS, GRID_ROWS), Image.BILINEAR)
        elevation_grid = np.array(im_resized, dtype=np.float32)
        print(f"Loaded DEM via PIL. Shape: {elevation_grid.shape}, Min: {elevation_grid.min():.2f}m, Max: {elevation_grid.max():.2f}m")

    # 1. Save standard 200x200 elevation grid
    elev_out = dem_path / "elevation_grid.npy"
    np.save(elev_out, elevation_grid)
    print(f" -> Saved {elev_out}")

    # 2. Detect pre-existing water bodies (rivers, channels) and retention ponds (basins)
    osm_water_file = dem_path.parent / "osm_waterbodies.json"
    if not osm_water_file.exists():
        osm_water_file = dem_path.parent / "drainage" / "raw" / "osm_drainage_mumbai.json"

    water_body_mask = np.zeros((GRID_ROWS, GRID_COLS), dtype=bool)
    retention_pond_mask = np.zeros((GRID_ROWS, GRID_COLS), dtype=bool)

    if osm_water_file.exists():
        try:
            water_body_mask = rasterize_osm_waterbodies(
                osm_water_file,
                grid_rows=GRID_ROWS,
                grid_cols=GRID_COLS,
                min_lat=min_lat,
                max_lat=max_lat,
                min_lon=min_lon,
                max_lon=max_lon,
            )
            retention_pond_mask = rasterize_osm_retention_ponds(
                osm_water_file,
                grid_rows=GRID_ROWS,
                grid_cols=GRID_COLS,
                min_lat=min_lat,
                max_lat=max_lat,
                min_lon=min_lon,
                max_lon=max_lon,
            )
            print(f"Loaded OpenStreetMap water bodies from {osm_water_file.name}: {int(water_body_mask.sum())} water cells, {int(retention_pond_mask.sum())} retention pond cells.")
        except Exception as e:
            print(f"Warning: Failed to rasterize OSM water bodies ({e}), initializing empty masks.")
            water_body_mask = np.zeros((GRID_ROWS, GRID_COLS), dtype=bool)
            retention_pond_mask = np.zeros((GRID_ROWS, GRID_COLS), dtype=bool)
    else:
        print("OSM water body dataset not found. Initializing empty water body mask.")

    water_body_out = dem_path / "water_body_mask.npy"
    np.save(water_body_out, water_body_mask)
    n_water = int(water_body_mask.sum())
    print(f" -> Saved {water_body_out} ({n_water} OpenStreetMap water cells = {n_water/GRID_ROWS/GRID_COLS*100:.2f}% of domain)")

    pond_out = dem_path / "retention_pond_mask.npy"
    np.save(pond_out, retention_pond_mask)
    n_pond = int(retention_pond_mask.sum())
    print(f" -> Saved {pond_out} ({n_pond} OpenStreetMap retention pond cells)")

    # 2b. Hydro-enforce river channel by burning culverts and bridge deck openings
    elevation_grid = hydro_enforce_channels(elevation_grid, water_body_mask)
    elev_out = dem_path / "elevation_grid.npy"
    np.save(elev_out, elevation_grid)
    print(f" -> Saved hydro-enforced {elev_out} (Min: {elevation_grid.min():.2f}m, Max: {elevation_grid.max():.2f}m)")

    # 3. Generate Imperviousness grid
    elev_norm = (elevation_grid - elevation_grid.min()) / (elevation_grid.max() - elevation_grid.min() + 1e-5)
    imperviousness = 0.85 - (0.35 * elev_norm)
    imperviousness = np.clip(imperviousness, 0.20, 0.95).astype(np.float32)
    imperviousness[water_body_mask] = 0.0
    imperviousness[retention_pond_mask] = 0.0

    imp_out = dem_path / "imperviousness.npy"
    np.save(imp_out, imperviousness)
    print(f" -> Saved {imp_out} (water body & pond imperviousness = 0.0; land < 0 m retained urban imperviousness)")

    # 4. Generate Infiltration grid (mm/hr): base_rate * (1 - imperviousness)
    base_infiltration_rate = 10.0  # mm/hr for typical urban soil
    infiltration = base_infiltration_rate * (1.0 - imperviousness)
    infiltration[water_body_mask] = 0.0  # Saturated riverbed: no soil infiltration loss
    infiltration[retention_pond_mask] = 0.0  # Retention pond basin: no soil infiltration loss

    inf_out = dem_path / "infiltration.npy"
    np.save(inf_out, infiltration)
    print(f" -> Saved {inf_out} (water body & pond infiltration = 0.0 mm/hr; land < 0 m retains soil infiltration)")


if __name__ == "__main__":
    process_dem_rasters("backend/data/dem")
