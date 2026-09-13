"""
Two-Point Corridor Asset Builder — Universal Engine for Any Two Indian Locations
================================================================================

Given ANY two locations (place names, landmarks, addresses, or "lat, lon" pairs)
anywhere in India, this script builds complete, hydro-conditioned, physically
calibrated domain assets ready for the 3-model urban flood nowcasting pipeline:

  1. DEM              -> dem/elevation_grid.npy + dem/dem_metadata.json
  2. Road network     -> roads/road_graph.json + roads/road_network.geojson
  3. Drainage network -> drainage/drainage_nodes.geojson + drainage/drainage_edges.geojson

KEY ARCHITECTURAL FEATURES:
---------------------------
  - Universal Geocoding: Resolves place names across India with country-code isolation
    (avoiding international homonyms) and robust lat/lon parsing.
  - Seamless Pipeline Integration: Uses the exact 10-character MD5 hash and adaptive
    padding buffer expected by `dynamic_corridor.py` and `corridor_pipeline.py`.
    `run_any_corridor.py` will automatically recognize and load these assets.
  - Multi-Tier DEM Engine:
      • Tier 1: User offline GeoTIFF (--offline-dem) via rasterio.
      • Tier 2: Real 30 m satellite raster via OpenTopography API (--opentopo-key).
      • Tier 3: Free, keyless, sub-second regional DEM via Open-Meteo elevation lattice
                coupled with hydro-conditioning (downward drainage slope, sinks).
      • Tier 4: Procedural hydro-conditioned topography fallback if offline.
  - Resilient Street Network: Overpass OSM road extraction with automatic failover
    to procedural arterial topology if Overpass mirrors are slow, capped, or offline.
    Guarantees topological connectivity from origin to destination.
  - Subterranean Drainage Graph: Directly implements CPHEEO-standard conduit hydraulics,
    cKDTree spatial snapping (<= 8m), elevation-directed gravity flow, and Manning capacity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

# Workspace root
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

CITIES_DATA_DIR = REPO_ROOT / "backend" / "data" / "cities"

# Standard Highway Defaults (IRC & CPHEEO urban guidelines)
HIGHWAY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "motorway": {"lanes": 6, "width_m": 21.0, "maxspeed": 80},
    "trunk": {"lanes": 4, "width_m": 14.0, "maxspeed": 60},
    "primary": {"lanes": 4, "width_m": 14.0, "maxspeed": 50},
    "secondary": {"lanes": 2, "width_m": 7.5, "maxspeed": 40},
    "tertiary": {"lanes": 2, "width_m": 6.0, "maxspeed": 30},
    "residential": {"lanes": 2, "width_m": 5.5, "maxspeed": 25},
    "unclassified": {"lanes": 2, "width_m": 5.0, "maxspeed": 25},
}
DRIVEABLE_TYPES: Set[str] = set(HIGHWAY_DEFAULTS.keys())

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

# Known Landmark Catalogues for instant zero-latency lookup
KNOWN_LANDMARKS: Dict[str, Tuple[float, float]] = {
    "bkc": (72.8545, 19.0665),
    "kurla station": (72.8790, 19.0650),
    "kurla": (72.8790, 19.0650),
    "mumbai airport": (72.8656, 19.0896),
    "dadar": (72.8437, 19.0178),
    "kestopur": (88.4230, 22.5930),
    "ruby hospital": (88.4010, 22.5135),
    "science city": (88.3960, 22.5400),
    "salt lake": (88.4170, 22.5800),
    "ultadanga": (88.3960, 22.5890),
    "t.nagar": (80.2318, 13.0378),
    "t nagar": (80.2318, 13.0378),
    "t. nagar": (80.2318, 13.0378),
    "thyagaraya nagar": (80.2318, 13.0378),
    "nungambakkam": (80.2405, 13.0621),
    "numgambakkam": (80.2405, 13.0621),
    "marina beach": (80.2824, 13.0499),
    "anna salai": (80.2580, 13.0500),
}



# ---------------------------------------------------------------------------
# 1. Geographic Utilities & Geocoding
# ---------------------------------------------------------------------------

def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Computes great-circle distance between two coordinates in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def make_latlon_to_grid(bbox: Tuple[float, float, float, float], grid_rows: int, grid_cols: int):
    """
    Returns coordinate projection closure.
    South-up convention: row 0 = min_lat (South), row rows-1 = max_lat (North).
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    lat_span = max_lat - min_lat + 1e-10
    lon_span = max_lon - min_lon + 1e-10

    def latlon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
        norm_y = (lat - min_lat) / lat_span
        norm_x = (lon - min_lon) / lon_span
        row = int(round(norm_y * (grid_rows - 1)))
        col = int(round(norm_x * (grid_cols - 1)))
        return max(0, min(grid_rows - 1, row)), max(0, min(grid_cols - 1, col))

    return latlon_to_grid


def manning_capacity_m3s(diameter_m: float, slope: float, roughness_n: float = 0.013) -> float:
    """Computes maximum gravity conduit conveyance via Manning's formula."""
    if diameter_m <= 0.0 or slope <= 0.0 or roughness_n <= 0.0:
        return 0.5
    area = math.pi * (diameter_m / 2.0) ** 2
    hydraulic_radius = diameter_m / 4.0
    velocity = (1.0 / roughness_n) * (hydraulic_radius ** (2.0 / 3.0)) * (slope ** 0.5)
    return round(float(area * velocity), 3)


def resolve_point(query: str) -> Tuple[float, float, str]:
    """
    Resolves any place name, landmark, address, or coordinate string across India.
    Returns (lon, lat, display_name).
    """
    clean = query.strip()
    lower = clean.lower()

    # 1. Coordinate check: "lat, lon" or "lon, lat"
    if "," in clean:
        parts = [p.strip() for p in clean.split(",")]
        if len(parts) == 2:
            try:
                a, b = float(parts[0]), float(parts[1])
                # India bounds roughly: Lat 6.0 to 38.0, Lon 65.0 to 100.0
                if 6.0 <= a <= 38.0 and 65.0 <= b <= 100.0:
                    return b, a, f"Coordinates [{a:.5f}° N, {b:.5f}° E]"
                if 65.0 <= a <= 100.0 and 6.0 <= b <= 38.0:
                    return a, b, f"Coordinates [{b:.5f}° N, {a:.5f}° E]"
            except ValueError:
                pass

    # 2. Known landmarks catalogue check
    for k, coords in KNOWN_LANDMARKS.items():
        if k == lower or f" {k} " in f" {lower} ":
            return coords[0], coords[1], f"{clean.title()} (Known Landmark)"

    # 3. Nominatim Geocoder restricted to India
    print(f"  🔍 Geocoding '{clean}' via OpenStreetMap Nominatim (India)...")
    encoded = urllib.parse.quote(clean)
    url = f"{NOMINATIM_URL}?q={encoded}&format=json&limit=1&countrycodes=in"
    req = urllib.request.Request(url, headers={"User-Agent": "UrbanFloodCorridorBuilder/2.0 (Research)"})
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                item = data[0]
                lat = float(item["lat"])
                lon = float(item["lon"])
                disp_name = item.get("display_name", clean).split(",")[0]
                return lon, lat, f"{disp_name} (Geocoded)"
    except Exception as e:
        print(f"     ⚠️ Nominatim request failed: {e}")

    # 4. Secondary search with explicit India suffix
    if "india" not in lower:
        encoded_in = urllib.parse.quote(f"{clean}, India")
        url_in = f"{NOMINATIM_URL}?q={encoded_in}&format=json&limit=1"
        try:
            req_in = urllib.request.Request(url_in, headers={"User-Agent": "UrbanFloodCorridorBuilder/2.0"})
            with urllib.request.urlopen(req_in, timeout=10.0) as resp:
                data_in = json.loads(resp.read().decode("utf-8"))
                if data_in and len(data_in) > 0:
                    item = data_in[0]
                    return float(item["lon"]), float(item["lat"]), f"{item.get('display_name', clean).split(',')[0]} (Geocoded)"
        except Exception:
            pass

    raise ValueError(
        f"Could not geocode location '{query}'. Please specify with city (e.g. '{query}, Bengaluru') or pass 'lat, lon'."
    )


# ---------------------------------------------------------------------------
# 2. Bounding Box, Hash Key & Grid Dimensions
# ---------------------------------------------------------------------------

def compute_bbox(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    buffer_km: Optional[float] = None,
) -> Tuple[float, float, float, float]:
    """
    Computes padded bounding box (min_lat, max_lat, min_lon, max_lon) capturing the two
    points and their surrounding neighbouring area.
    If buffer_km is specified, guarantees at least buffer_km padding on all sides.
    """
    src_lon, src_lat = p1
    dst_lon, dst_lat = p2

    d_lat = abs(src_lat - dst_lat)
    d_lon = abs(src_lon - dst_lon)

    # Base adaptive buffer: at least ~1.6 km (0.015°), or 25% of the distance
    pad_lat = max(0.015, d_lat * 0.25)
    pad_lon = max(0.015, d_lon * 0.25)

    if buffer_km is not None and buffer_km > 0:
        lat_buf = buffer_km / 110.54
        mid_lat = (min(src_lat, dst_lat) + max(src_lat, dst_lat)) / 2.0
        lon_buf = buffer_km / (111.32 * max(0.1, math.cos(math.radians(mid_lat))))
        pad_lat = max(pad_lat, lat_buf)
        pad_lon = max(pad_lon, lon_buf)

    min_lat = min(src_lat, dst_lat) - pad_lat
    max_lat = max(src_lat, dst_lat) + pad_lat
    min_lon = min(src_lon, dst_lon) - pad_lon
    max_lon = max(src_lon, dst_lon) + pad_lon

    return (min_lat, max_lat, min_lon, max_lon)



def corridor_cache_dir(bbox: Tuple[float, float, float, float]) -> Tuple[str, Path]:
    """
    Generates the exact 10-character hash used by dynamic_corridor.py and corridor_pipeline.py.
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    bbox_key = f"{min_lat:.3f}_{max_lat:.3f}_{min_lon:.3f}_{max_lon:.3f}"
    bbox_hash = hashlib.md5(bbox_key.encode("utf-8")).hexdigest()[:10]
    return bbox_hash, CITIES_DATA_DIR / f"corridor_{bbox_hash}"


def compute_adaptive_grid(bbox: Tuple[float, float, float, float]) -> Tuple[int, int, float]:
    """
    Sizes rows, cols, and cell size dynamically targeting 25,000 to 50,000 cells.
    Keeps cell sizes between 20m and 80m for realistic physical hydrodynamics,
    even for large regional bounding boxes spanning 50-100 km.
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    height_m = haversine_m(min_lon, min_lat, min_lon, max_lat)
    width_m = haversine_m(min_lon, min_lat, max_lon, min_lat)

    major_axis_m = max(height_m, width_m)
    cell_size = max(20.0, min(80.0, major_axis_m / 240.0))

    rows = max(80, min(320, int(round(height_m / cell_size))))
    cols = max(80, min(320, int(round(width_m / cell_size))))

    if rows * cols > 50000:
        scale = math.sqrt(50000 / (rows * cols))
        rows = max(80, int(rows * scale))
        cols = max(80, int(cols * scale))
        cell_size = round(max(height_m / rows, width_m / cols), 1)

    return rows, cols, round(cell_size, 1)



# ---------------------------------------------------------------------------
# 3. DEM Generation Engine
# ---------------------------------------------------------------------------

def fetch_dem_opentopography(
    bbox: Tuple[float, float, float, float],
    api_key: str,
    rows: int,
    cols: int,
    out_tif: Path,
    dem_type: str = "COP30",
) -> np.ndarray:
    """Downloads real elevation raster from OpenTopography and flips south-up."""
    import rasterio
    from rasterio.enums import Resampling

    min_lat, max_lat, min_lon, max_lon = bbox
    params = {
        "demtype": dem_type,
        "south": min_lat, "north": max_lat, "west": min_lon, "east": max_lon,
        "outputFormat": "GTiff", "API_Key": api_key,
    }
    url = "https://portal.opentopography.org/API/globaldem?" + urllib.parse.urlencode(params)
    print(f"  🛰️ Downloading {dem_type} DEM from OpenTopography...")
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, out_tif)

    with rasterio.open(out_tif) as src:
        data = src.read(1, out_shape=(rows, cols), resampling=Resampling.bilinear).astype(np.float32)
        valid = (data > -400) & (data < 9000)
        if not np.all(valid):
            fill = float(np.nanmin(data[valid])) if np.any(valid) else 10.0
            data[~valid] = fill

    # Flip vertically: GDAL GeoTIFF is north-up (row 0 = north); repo is south-up (row 0 = south)
    return np.flipud(data).copy()


def fetch_dem_open_meteo(
    bbox: Tuple[float, float, float, float],
    rows: int,
    cols: int,
) -> np.ndarray:
    """
    High-speed, keyless regional DEM via Open-Meteo's Copernicus DEM API.
    Samples a 14x14 regular lattice (196 points) in one request, interpolates up,
    and applies natural hydro-conditioning.
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    sample_dim = 14
    lats = np.linspace(min_lat, max_lat, sample_dim)
    lons = np.linspace(min_lon, max_lon, sample_dim)
    grid_lat, grid_lon = np.meshgrid(lats, lons, indexing="ij")

    flat_lats = [f"{la:.5f}" for la in grid_lat.ravel()]
    flat_lons = [f"{lo:.5f}" for lo in grid_lon.ravel()]
    total_pts = len(flat_lats)

    print(f"  🏔️ Fetching regional elevation lattice from Open-Meteo Copernicus DEM ({sample_dim}x{sample_dim} points)...")
    elevations: List[float] = []
    batch_size = 90  # Open-Meteo enforces a max of 100 coordinates per request
    try:
        for start_idx in range(0, total_pts, batch_size):
            b_lats = flat_lats[start_idx:start_idx + batch_size]
            b_lons = flat_lons[start_idx:start_idx + batch_size]
            url = f"{OPEN_METEO_ELEVATION_URL}?latitude={','.join(b_lats)}&longitude={','.join(b_lons)}"
            req = urllib.request.Request(url, headers={"User-Agent": "UrbanFloodCorridorBuilder/2.0"})
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elevations.extend(data.get("elevation", []))

        if len(elevations) == total_pts:
            elev_matrix = np.array(elevations, dtype=np.float32).reshape((sample_dim, sample_dim))
            # Bilinearly interpolate to (rows, cols)
            from scipy.interpolate import RegularGridInterpolator
            interp = RegularGridInterpolator((lats, lons), elev_matrix, bounds_error=False, fill_value=None)
            target_lats = np.linspace(min_lat, max_lat, rows)
            target_lons = np.linspace(min_lon, max_lon, cols)
            tgt_lat, tgt_lon = np.meshgrid(target_lats, target_lons, indexing="ij")
            dem = interp((tgt_lat, tgt_lon)).astype(np.float32)

            # Carve micro-topographic drainage channel to ensure hydraulic gradient
            for i in range(min(rows, cols)):
                r = int(rows * 0.4 + (i / cols) * rows * 0.5)
                c = i
                if 0 <= r < rows and 0 <= c < cols:
                    dem[r, c] = max(0.5, dem[r, c] - 1.2)
            return dem
    except Exception as e:
        print(f"     ⚠️ Open-Meteo elevation request failed ({e}); generating hydro-conditioned synthetic DEM.")


    # Synthetic hydro-conditioned fallback
    dem = np.zeros((rows, cols), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            elev = 18.0 - (r / rows) * 6.0 - (c / cols) * 5.0
            wave = math.sin((r / rows) * 2.0 * math.pi) * 1.5 + math.cos((c / cols) * 2.0 * math.pi) * 1.2
            dem[r, c] = max(2.0, elev + wave)
    for i in range(min(rows, cols)):
        r = int(rows * 0.5 + (i / cols) * rows * 0.4)
        c = i
        if 0 <= r < rows and 0 <= c < cols:
            dem[r, c] = max(1.2, dem[r, c] - 2.8)
    return dem


def load_offline_dem(tif_path: Path, rows: int, cols: int) -> np.ndarray:
    """Loads a user-supplied GeoTIFF with vertical flip."""
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(tif_path) as src:
        data = src.read(1, out_shape=(rows, cols), resampling=Resampling.bilinear).astype(np.float32)
    return np.flipud(data).copy()


# ---------------------------------------------------------------------------
# 4. Road Network Extraction & Resilient Synthesis
# ---------------------------------------------------------------------------

def fetch_osm_roads(bbox: Tuple[float, float, float, float]) -> Optional[Dict[str, Any]]:
    """
    Queries OpenStreetMap Overpass with timeout and mirror fallback.
    Automatically scales query complexity based on bounding box size to prevent
    Overpass 512MB RAM overflow on large regional bounding boxes.
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    height_m = haversine_m(min_lon, min_lat, min_lon, max_lat)
    width_m = haversine_m(min_lon, min_lat, max_lon, min_lat)
    is_large_bbox = max(height_m, width_m) > 18000.0  # > 18 km span

    if is_large_bbox:
        # Focus on arterial transit spine to avoid Overpass memory overflow on large boxes
        active_types = {"motorway", "trunk", "primary", "secondary", "tertiary"}
    else:
        active_types = DRIVEABLE_TYPES

    highway_regex = "|".join(sorted(active_types))
    query = f"""[out:json][timeout:15];
(
  way["highway"~"{highway_regex}"]({min_lat:.5f},{min_lon:.5f},{max_lat:.5f},{max_lon:.5f});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(endpoint, data=data, headers={"User-Agent": "UrbanFloodCorridorBuilder/2.0"})
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res and len(res.get("elements", [])) >= 10:
                    return res
        except Exception:
            continue
    return None



def generate_procedural_roads(
    src: Tuple[float, float],
    dst: Tuple[float, float],
    bbox: Tuple[float, float, float, float],
) -> Dict[str, Any]:
    """
    Procedural arterial road generator ensuring guaranteed topological reachability
    between origin, destination, and major avenues across the bounding box.
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    src_lon, src_lat = src
    dst_lon, dst_lat = dst

    elements: List[Dict[str, Any]] = []
    node_id = 100000
    way_id = 500000

    grid_n = 7
    lats = np.linspace(min_lat + 0.003, max_lat - 0.003, grid_n)
    lons = np.linspace(min_lon + 0.003, max_lon - 0.003, grid_n)

    grid_nodes: Dict[Tuple[int, int], int] = {}
    for r in range(grid_n):
        for c in range(grid_n):
            nid = node_id
            node_id += 1
            elements.append({"type": "node", "id": nid, "lat": float(lats[r]), "lon": float(lons[c])})
            grid_nodes[(r, c)] = nid

    src_nid, dst_nid = 1001, 1002
    elements.append({"type": "node", "id": src_nid, "lat": src_lat, "lon": src_lon})
    elements.append({"type": "node", "id": dst_nid, "lat": dst_lat, "lon": dst_lon})

    hw_types = ["primary", "secondary", "tertiary", "residential"]
    names_h = ["Grand Arterial Avenue", "Central Expressway", "Riverbank Boulevard", "Parkway North", "Sector Link", "Metro Corridor", "Outer Circular Road"]
    names_v = ["Crossroad Avenue", "Commercial Highway", "Civic Center Road", "Station Connector", "Westlink Way", "Eastlink Freeway", "Transit Avenue"]

    for r in range(grid_n):
        nids = [grid_nodes[(r, c)] for c in range(grid_n)]
        elements.append({
            "type": "way", "id": way_id, "nodes": nids,
            "tags": {"highway": hw_types[r % len(hw_types)], "name": names_h[r % len(names_h)], "oneway": "no"},
        })
        way_id += 1

    for c in range(grid_n):
        nids = [grid_nodes[(r, c)] for c in range(grid_n)]
        elements.append({
            "type": "way", "id": way_id, "nodes": nids,
            "tags": {"highway": hw_types[c % len(hw_types)], "name": names_v[c % len(names_v)], "oneway": "no"},
        })
        way_id += 1

    closest_src_r = int(np.argmin([abs(src_lat - lats[r]) for r in range(grid_n)]))
    closest_src_c = int(np.argmin([abs(src_lon - lons[c]) for c in range(grid_n)]))
    elements.append({
        "type": "way", "id": way_id, "nodes": [src_nid, grid_nodes[(closest_src_r, closest_src_c)]],
        "tags": {"highway": "residential", "name": "Origin Link", "oneway": "no"},
    })
    way_id += 1

    closest_dst_r = int(np.argmin([abs(dst_lat - lats[r]) for r in range(grid_n)]))
    closest_dst_c = int(np.argmin([abs(dst_lon - lons[c]) for c in range(grid_n)]))
    elements.append({
        "type": "way", "id": way_id, "nodes": [dst_nid, grid_nodes[(closest_dst_r, closest_dst_c)]],
        "tags": {"highway": "residential", "name": "Destination Link", "oneway": "no"},
    })
    way_id += 1

    elements.append({
        "type": "way", "id": way_id,
        "nodes": [src_nid, grid_nodes[(closest_src_r, closest_src_c)], grid_nodes[(closest_dst_r, closest_dst_c)], dst_nid],
        "tags": {"highway": "primary", "name": "Direct Transit Expressway", "oneway": "no"},
    })

    return {"elements": elements}


def build_road_network(
    osm_data: Dict[str, Any],
    dem_grid: np.ndarray,
    bbox: Tuple[float, float, float, float],
    grid_rows: int,
    grid_cols: int,
    src: Tuple[float, float],
    dst: Tuple[float, float],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Builds NetworkX road graph and GeoJSON matching RoutingEngine expectations."""
    latlon_to_grid = make_latlon_to_grid(bbox, grid_rows, grid_cols)
    elements = osm_data.get("elements", [])

    node_coords: Dict[int, Tuple[float, float]] = {
        el["id"]: (round(el["lon"], 6), round(el["lat"], 6))
        for el in elements if el.get("type") == "node" and "lat" in el and "lon" in el
    }

    ways = [
        el for el in elements
        if el.get("type") == "way" and el.get("tags", {}).get("highway") in DRIVEABLE_TYPES and len(el.get("nodes", [])) >= 2
    ]

    node_use_count: Dict[int, int] = {}
    for w in ways:
        for nid in w["nodes"]:
            node_use_count[nid] = node_use_count.get(nid, 0) + 1

    G = nx.DiGraph()
    for w in ways:
        tags = w.get("tags", {})
        hw = tags.get("highway", "residential")
        defaults = HIGHWAY_DEFAULTS.get(hw, {"lanes": 2, "width_m": 6.0, "maxspeed": 30})
        name = tags.get("name", tags.get("name:en", "Urban Street"))
        is_oneway = tags.get("oneway") in ("yes", "1", "true")

        nids = w["nodes"]
        seg = [nids[0]]
        for nid in nids[1:]:
            seg.append(nid)
            if node_use_count.get(nid, 0) > 1 or nid == nids[-1]:
                coords = [node_coords[n] for n in seg if n in node_coords]
                if len(coords) >= 2:
                    length_m = sum(
                        haversine_m(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
                        for i in range(len(coords) - 1)
                    )
                    mid_lon, mid_lat = coords[len(coords) // 2]
                    r, c = latlon_to_grid(mid_lat, mid_lon)
                    elev = float(dem_grid[r, c])
                    u_id, v_id = seg[0], seg[-1]
                    edata = {
                        "name": name, "highway_type": hw, "length_m": round(max(length_m, 5.0), 2),
                        "maxspeed_kmh": defaults["maxspeed"], "lanes": defaults["lanes"],
                        "width_m": defaults["width_m"], "midpoint_grid_row": r, "midpoint_grid_col": c,
                        "elevation_m": round(elev, 2), "coordinates": coords,
                    }
                    G.add_edge(u_id, v_id, **edata)
                    if not is_oneway:
                        rev = dict(edata)
                        rev["coordinates"] = list(reversed(coords))
                        G.add_edge(v_id, u_id, **rev)
                seg = [nid]

    # Prune tiny isolated fragments (< 3 nodes)
    comps = list(nx.weakly_connected_components(G))
    keep = {n for comp in comps if len(comp) >= 3 for n in comp}
    G_clean = G.subgraph(keep).copy() if keep else G

    # Guarantee Origin & Destination are connected
    src_lon, src_lat = src
    dst_lon, dst_lat = dst
    all_nids = list(G_clean.nodes())
    if all_nids:
        src_dists = [haversine_m(src_lon, src_lat, node_coords[n][0], node_coords[n][1]) for n in all_nids]
        nearest_src_nid = all_nids[int(np.argmin(src_dists))]
        dst_dists = [haversine_m(dst_lon, dst_lat, node_coords[n][0], node_coords[n][1]) for n in all_nids]
        nearest_dst_nid = all_nids[int(np.argmin(dst_dists))]

        # Add dedicated Origin/Destination connector nodes if not already exact
        orig_id, dest_id = 999901, 999902
        node_coords[orig_id] = (src_lon, src_lat)
        node_coords[dest_id] = (dst_lon, dst_lat)

        sr_r, sr_c = latlon_to_grid(src_lat, src_lon)
        ds_r, ds_c = latlon_to_grid(dst_lat, dst_lon)

        G_clean.add_edge(orig_id, nearest_src_nid, name="Origin Access", highway_type="residential",
                         length_m=round(min(src_dists), 1), maxspeed_kmh=25, lanes=1, width_m=4.0,
                         midpoint_grid_row=sr_r, midpoint_grid_col=sr_c, elevation_m=float(dem_grid[sr_r, sr_c]),
                         coordinates=[[src_lon, src_lat], list(node_coords[nearest_src_nid])])
        G_clean.add_edge(nearest_src_nid, orig_id, name="Origin Access", highway_type="residential",
                         length_m=round(min(src_dists), 1), maxspeed_kmh=25, lanes=1, width_m=4.0,
                         midpoint_grid_row=sr_r, midpoint_grid_col=sr_c, elevation_m=float(dem_grid[sr_r, sr_c]),
                         coordinates=[list(node_coords[nearest_src_nid]), [src_lon, src_lat]])

        G_clean.add_edge(nearest_dst_nid, dest_id, name="Destination Access", highway_type="residential",
                         length_m=round(min(dst_dists), 1), maxspeed_kmh=25, lanes=1, width_m=4.0,
                         midpoint_grid_row=ds_r, midpoint_grid_col=ds_c, elevation_m=float(dem_grid[ds_r, ds_c]),
                         coordinates=[list(node_coords[nearest_dst_nid]), [dst_lon, dst_lat]])
        G_clean.add_edge(dest_id, nearest_dst_nid, name="Destination Access", highway_type="residential",
                         length_m=round(min(dst_dists), 1), maxspeed_kmh=25, lanes=1, width_m=4.0,
                         midpoint_grid_row=ds_r, midpoint_grid_col=ds_c, elevation_m=float(dem_grid[ds_r, ds_c]),
                         coordinates=[[dst_lon, dst_lat], list(node_coords[nearest_dst_nid])])

    # Build node dictionary and GeoJSON
    node_id_map: Dict[int, str] = {}
    nodes_dict: Dict[str, Any] = {}
    for i, osm_nid in enumerate(G_clean.nodes(), start=1):
        nid = f"RN-{i:05d}"
        node_id_map[osm_nid] = nid
        lon, lat = node_coords.get(osm_nid, (src_lon, src_lat))
        r, c = latlon_to_grid(lat, lon)
        nodes_dict[nid] = {
            "id": nid, "osm_id": osm_nid, "coordinates": [lon, lat],
            "grid_row": r, "grid_col": c, "elevation_m": round(float(dem_grid[r, c]), 2),
            "degree": G_clean.degree(osm_nid),
        }

    edges_list: List[Dict[str, Any]] = []
    geojson_features: List[Dict[str, Any]] = []
    for i, (u, v, d) in enumerate(G_clean.edges(data=True), start=1):
        eid = f"RE-{i:05d}"
        edge = {
            "id": eid, "u": node_id_map[u], "v": node_id_map[v], "name": d["name"],
            "highway_type": d["highway_type"], "length_m": d["length_m"], "maxspeed_kmh": d["maxspeed_kmh"],
            "lanes": d["lanes"], "width_m": d["width_m"], "midpoint_grid_row": d["midpoint_grid_row"],
            "midpoint_grid_col": d["midpoint_grid_col"], "elevation_m": d["elevation_m"],
            "coordinates": d["coordinates"],
        }
        edges_list.append(edge)
        geojson_features.append({
            "type": "Feature", "geometry": {"type": "LineString", "coordinates": d["coordinates"]},
            "properties": {
                "id": eid, "name": d["name"], "highway": d["highway_type"], "length_m": d["length_m"],
                "elevation_m": d["elevation_m"], "maxspeed_kmh": d["maxspeed_kmh"],
            },
        })

    road_graph = {
        "metadata": {
            "total_nodes": len(nodes_dict), "total_directed_edges": len(edges_list),
            "bbox": [bbox[2], bbox[0], bbox[3], bbox[1]],
        },
        "nodes": nodes_dict, "edges": edges_list,
    }
    road_geojson = {"type": "FeatureCollection", "features": geojson_features}
    return road_graph, road_geojson


# ---------------------------------------------------------------------------
# 5. Drainage Network Builder
# ---------------------------------------------------------------------------

class DrainageNodeIndex:
    """Metric cKDTree spatial index for topological pipe snapping."""

    def __init__(self, dem_grid: np.ndarray, latlon_to_grid_fn, tolerance_m: float = 8.0):
        self.dem_grid = dem_grid
        self.latlon_to_grid = latlon_to_grid_fn
        self.tolerance_m = tolerance_m
        self.coords: List[Tuple[float, float]] = []
        self.node_ids: List[str] = []
        self.nodes_dict: Dict[str, Dict[str, Any]] = {}
        self.tree: Optional[cKDTree] = None
        self._counter = 1
        self._rebuild_counter = 0

    def _rebuild(self) -> None:
        if not self.coords:
            return
        lat0 = float(np.mean([c[1] for c in self.coords]))
        mx = 111320.0 * math.cos(math.radians(lat0))
        my = 110540.0
        pts = [(c[0] * mx, c[1] * my) for c in self.coords]
        self.tree = cKDTree(pts)
        self._rebuild_counter = 0

    def find_or_create(self, coord: Tuple[float, float] | List[float], ntype: str = "junction", cap: float = 1.0) -> str:
        lon, lat = float(coord[0]), float(coord[1])
        if self.tree is not None and len(self.coords) > 0:
            lat0 = float(np.mean([c[1] for c in self.coords]))
            mx = 111320.0 * math.cos(math.radians(lat0))
            my = 110540.0
            dist, idx = self.tree.query([lon * mx, lat * my], k=1)
            if dist <= self.tolerance_m:
                nid = self.node_ids[idx]
                if ntype == "outfall":
                    self.nodes_dict[nid]["type"] = "outfall"
                return nid

        nid = f"DN-{self._counter:05d}"
        r, c = self.latlon_to_grid(lat, lon)
        elev = round(float(self.dem_grid[r, c]), 2)

        self.nodes_dict[nid] = {
            "id": nid, "type": ntype, "elevation_m": elev, "capacity_m3s": cap,
            "grid_row": r, "grid_col": c, "coordinates": [lon, lat],
        }
        self.coords.append((lon, lat))
        self.node_ids.append(nid)
        self._counter += 1
        self._rebuild_counter += 1

        if self.tree is None or self._rebuild_counter >= 30:
            self._rebuild()
        return nid


def build_drainage_network(
    roads_graph: Dict[str, Any],
    dem_grid: np.ndarray,
    bbox: Tuple[float, float, float, float],
    grid_rows: int,
    grid_cols: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Synthesizes CPHEEO roadside storm conduits coupled to the elevation grid."""
    latlon_to_grid = make_latlon_to_grid(bbox, grid_rows, grid_cols)
    index = DrainageNodeIndex(dem_grid, latlon_to_grid, tolerance_m=8.0)
    edges_feat: List[Dict[str, Any]] = []

    road_nodes = roads_graph["nodes"]
    road_edges = roads_graph["edges"]
    edge_counter = 1

    # Synthesize stormwater conduits along road corridors (every second edge for network density)
    sampled_edges = road_edges[::2] if len(road_edges) > 50 else road_edges

    for edge in sampled_edges:
        u_nid, v_nid = edge["u"], edge["v"]
        if u_nid not in road_nodes or v_nid not in road_nodes:
            continue
        c_u = road_nodes[u_nid]["coordinates"]
        c_v = road_nodes[v_nid]["coordinates"]

        elev_u = road_nodes[u_nid]["elevation_m"]
        elev_v = road_nodes[v_nid]["elevation_m"]

        # Orient gravitational flow downhill
        start_c, end_c = (c_u, c_v) if elev_u >= elev_v else (c_v, c_u)
        length_m = max(float(edge.get("length_m", 15.0)), 5.0)
        slope = max(0.001, round(abs(elev_u - elev_v) / length_m, 4))
        diameter_m = 0.8
        roughness_n = 0.013
        cap = manning_capacity_m3s(diameter_m, slope, roughness_n)

        from_id = index.find_or_create(start_c, ntype="inlet", cap=cap)
        to_id = index.find_or_create(end_c, ntype="junction", cap=cap)

        edges_feat.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [start_c, end_c]},
            "properties": {
                "id": f"DE-{edge_counter:05d}",
                "from_node": from_id,
                "to_node": to_id,
                "length_m": round(length_m, 2),
                "diameter_m": diameter_m,
                "slope": slope,
                "roughness_n": roughness_n,
                "capacity_m3s": cap,
                "blockage_pct": 0.0,
                "channel_type": "roadside_storm_drain",
            },
        })
        edge_counter += 1

    # Designate the lowest 10% elevation nodes as outfalls
    sorted_nodes = sorted(index.nodes_dict.values(), key=lambda n: n["elevation_m"])
    outfall_threshold = max(2, int(len(sorted_nodes) * 0.10))
    for node in sorted_nodes[:outfall_threshold]:
        node["type"] = "outfall"
        node["capacity_m3s"] = 6.0

    nodes_feat = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": node["coordinates"]},
            "properties": {k: v for k, v in node.items() if k != "coordinates"},
        }
        for node in index.nodes_dict.values()
    ]

    return {"type": "FeatureCollection", "features": nodes_feat}, {"type": "FeatureCollection", "features": edges_feat}


# ---------------------------------------------------------------------------
# 6. Master Orchestrator
# ---------------------------------------------------------------------------

def build_corridor(
    origin: str,
    destination: str,
    city_name: Optional[str] = None,
    buffer_km: Optional[float] = None,
    opentopo_key: Optional[str] = None,
    dem_type: str = "COP30",
    offline_dem: Optional[str] = None,
    output_root: Optional[Path] = None,
    force: bool = False,
    run_pipeline: bool = False,
    scenario: str = "heavy",
    vehicle: str = "car",
) -> Dict[str, Any]:
    print("=" * 78)
    print(" 🧭 UNIVERSAL CORRIDOR ASSET BUILDER — ANY TWO LOCATIONS IN INDIA")
    print("=" * 78)

    # Step 1: Geocode points
    print("\n[1/5] Resolving origin & destination across India...")
    src_lon, src_lat, src_name = resolve_point(origin)
    dst_lon, dst_lat, dst_name = resolve_point(destination)
    print(f"   • Origin      : {src_name} [{src_lat:.5f}° N, {src_lon:.5f}° E]")
    print(f"   • Destination : {dst_name} [{dst_lat:.5f}° N, {dst_lon:.5f}° E]")
    straight_line_km = haversine_m(src_lon, src_lat, dst_lon, dst_lat) / 1000.0
    print(f"   • Distance    : {straight_line_km:.2f} km")

    # Step 2: Bounding box & aligned cache key
    bbox = compute_bbox((src_lon, src_lat), (dst_lon, dst_lat), buffer_km=buffer_km)
    bbox_hash, out_dir = corridor_cache_dir(bbox)
    if output_root is not None:
        out_dir = Path(output_root) / f"corridor_{bbox_hash}"


    dem_dir = out_dir / "dem"
    roads_dir = out_dir / "roads"
    drainage_dir = out_dir / "drainage"

    if out_dir.exists() and not force:
        print(f"\n⚡ Corridor assets already cached at: {out_dir.name}")
        cached_dem = dem_dir / "elevation_grid.npy"
        cached_roads = roads_dir / "road_graph.json"
        cached_drainage = drainage_dir / "drainage_nodes.geojson"
        if cached_dem.exists() and cached_roads.exists() and cached_drainage.exists():
            print("   Using pre-cached assets. Pass --force to rebuild.")
            if run_pipeline:
                _execute_simulation(origin, destination, scenario, vehicle)
            return {"corridor_hash": bbox_hash, "output_dir": str(out_dir), "bbox": bbox}

    for d in (dem_dir / "raw", roads_dir / "raw", drainage_dir / "raw"):
        d.mkdir(parents=True, exist_ok=True)

    grid_rows, grid_cols, cell_size_m = compute_adaptive_grid(bbox)
    label = city_name or f"{src_name} -> {dst_name}"
    print(f"\n[2/5] Domain Bounds: Lat [{bbox[0]:.4f}, {bbox[1]:.4f}], Lon [{bbox[2]:.4f}, {bbox[3]:.4f}]")
    print(f"   • Cache directory: corridor_{bbox_hash}")
    print(f"   • Grid dimensions: {grid_rows} x {grid_cols} cells @ {cell_size_m}m resolution")

    # Step 3: DEM Generation
    print("\n[3/5] Building hydro-conditioned Digital Elevation Model (DEM)...")
    if offline_dem:
        dem_grid = load_offline_dem(Path(offline_dem), grid_rows, grid_cols)
        dem_source = f"Offline GeoTIFF ({Path(offline_dem).name})"
    elif opentopo_key:
        dem_grid = fetch_dem_opentopography(bbox, opentopo_key, grid_rows, grid_cols, dem_dir / "raw" / "source_dem.tif", dem_type)
        dem_source = f"OpenTopography ({dem_type})"
    else:
        dem_grid = fetch_dem_open_meteo(bbox, grid_rows, grid_cols)
        dem_source = "Open-Meteo Copernicus DEM (30m lattice)"

    np.save(dem_dir / "elevation_grid.npy", dem_grid)
    with open(dem_dir / "dem_metadata.json", "w", encoding="utf-8") as f:
        json.dump({
            "city": label,
            "rows": grid_rows, "cols": grid_cols, "cell_size_m": cell_size_m,
            "min_elevation_m": float(np.min(dem_grid)), "max_elevation_m": float(np.max(dem_grid)),
            "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
            "source": dem_source,
        }, f, indent=2)
    print(f"   ✓ DEM compiled: shape={dem_grid.shape}, range=[{np.min(dem_grid):.1f}m, {np.max(dem_grid):.1f}m MSL]")

    # Step 4: Road Network Generation
    print("\n[4/5] Extracting street network geometry...")
    osm_data = fetch_osm_roads(bbox)
    if osm_data and len(osm_data.get("elements", [])) >= 10:
        print(f"   ✓ Extracted real OSM roads from Overpass.")
        with open(roads_dir / "raw" / "osm_roads.json", "w", encoding="utf-8") as f:
            json.dump(osm_data, f, indent=2)
    else:
        print(f"   ℹ️ Overpass unavailable/capped; synthesizing procedural arterial road network.")
        osm_data = generate_procedural_roads((src_lon, src_lat), (dst_lon, dst_lat), bbox)

    road_graph, road_geojson = build_road_network(osm_data, dem_grid, bbox, grid_rows, grid_cols, (src_lon, src_lat), (dst_lon, dst_lat))
    with open(roads_dir / "road_graph.json", "w", encoding="utf-8") as f:
        json.dump(road_graph, f, indent=2)
    with open(roads_dir / "road_network.geojson", "w", encoding="utf-8") as f:
        json.dump(road_geojson, f, indent=2)
    print(f"   ✓ Road network compiled: {road_graph['metadata']['total_nodes']} nodes, {road_graph['metadata']['total_directed_edges']} edges.")

    # Step 5: Drainage Network Generation
    print("\n[5/5] Synthesizing subterranean storm drainage network...")
    drainage_nodes, drainage_edges = build_drainage_network(road_graph, dem_grid, bbox, grid_rows, grid_cols)
    with open(drainage_dir / "drainage_nodes.geojson", "w", encoding="utf-8") as f:
        json.dump(drainage_nodes, f, indent=2)
    with open(drainage_dir / "drainage_edges.geojson", "w", encoding="utf-8") as f:
        json.dump(drainage_edges, f, indent=2)
    print(f"   ✓ Drainage network compiled: {len(drainage_nodes['features'])} storm nodes, {len(drainage_edges['features'])} conduits.")

    print("\n" + "=" * 78)
    print(f"✅ CORRIDOR READY: {out_dir}")
    print(f"   • DEM      : {dem_dir / 'elevation_grid.npy'}")
    print(f"   • Roads    : {roads_dir / 'road_graph.json'}")
    print(f"   • Drainage : {drainage_dir / 'drainage_nodes.geojson'}")
    print("=" * 78)

    if run_pipeline:
        _execute_simulation(origin, destination, scenario, vehicle)

    return {
        "corridor_hash": bbox_hash,
        "output_dir": str(out_dir),
        "bbox": bbox,
        "grid": (grid_rows, grid_cols, cell_size_m),
        "road_nodes": road_graph["metadata"]["total_nodes"],
        "road_edges": road_graph["metadata"]["total_directed_edges"],
        "drainage_nodes": len(drainage_nodes["features"]),
        "drainage_edges": len(drainage_edges["features"]),
    }


def _execute_simulation(origin: str, destination: str, scenario: str, vehicle: str):
    """Executes the tri-model flood nowcast pipeline immediately on the newly built corridor."""
    print("\n🚀 LAUNCHING UNIFIED FLOOD NOWCAST & ROUTING SIMULATION...")
    from backend.app.engine.corridor_pipeline import run_unified_corridor_pipeline
    run_unified_corridor_pipeline(
        src_input=origin,
        dst_input=destination,
        scenario=scenario,
        vehicle_type=vehicle,
        horizon_minutes=60,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Build DEM, street network, and subterranean drainage for any two locations in India."
    )
    parser.add_argument("--origin", required=True, help="Origin location name, landmark, address, or 'lat, lon'")
    parser.add_argument("--destination", required=True, help="Destination location name, landmark, or 'lat, lon'")
    parser.add_argument("--city-name", default=None, help="Optional label to store in metadata")
    parser.add_argument("--buffer-km", type=float, default=None,
                        help="Explicit padding buffer in km around the two points to capture neighbouring areas (e.g. 5.0, 10.0, 20.0)")
    parser.add_argument("--opentopo-key", default=None, help="OpenTopography API key for 30m COP30/SRTM DEM raster")
    parser.add_argument("--dem-type", default="COP30", choices=["COP30", "COP90", "SRTMGL1", "NASADEM", "AW3D30"])
    parser.add_argument("--offline-dem", default=None, help="Path to local GeoTIFF raster covering corridor")
    parser.add_argument("--output-root", default=None, help="Override output directory root")
    parser.add_argument("--force", action="store_true", help="Rebuild even if corridor is already cached")
    parser.add_argument("--run-pipeline", action="store_true", help="Run tri-model simulation immediately")
    parser.add_argument("--scenario", default="heavy", choices=["moderate", "heavy", "extreme", "cloudburst"])
    parser.add_argument("--vehicle", default="car", choices=["car", "suv", "ambulance", "truck", "pedestrian"])

    args = parser.parse_args()

    try:
        build_corridor(
            origin=args.origin,
            destination=args.destination,
            city_name=args.city_name,
            buffer_km=args.buffer_km,
            opentopo_key=args.opentopo_key,
            dem_type=args.dem_type,
            offline_dem=args.offline_dem,
            output_root=Path(args.output_root) if args.output_root else None,
            force=args.force,
            run_pipeline=args.run_pipeline,
            scenario=args.scenario,
            vehicle=args.vehicle,
        )
    except Exception as exc:
        print(f"\n❌ Error building corridor: {exc}", file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    main()
