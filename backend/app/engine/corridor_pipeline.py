"""
Unified Multi-Model Corridor Pipeline
=====================================

Connects all 3 research models across any two geographic locations:
  1. Model 1 (Pair A - Drainage): Subterranean pipe hydraulics, inlet absorption & manhole surcharge
  2. Model 2 (Pair B - Flood): 2D Saint-Venant overland runoff, depression ponding & rainfall nowcasting
  3. Model 3 (Pair C - Routing): Dynamic flood-resilient A* routing with vehicle wading clearance physics

Supports:
  - Instant loading (<0.2s) for pre-cached corridors (Mumbai BKC, Kolkata EM Bypass)
  - Dynamic on-the-fly provisioning for arbitrary locations globally via OSM Overpass & Nominatim
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np

from backend.app.engine.flood_engine import FloodEngine
from backend.app.models.drainage import DrainageGraph
from backend.app.models.location import (
    CITY_CONFIGS,
    KOLKATA_LANDMARKS,
    STUDY_AREA_LANDMARKS,
    is_inside_study_area,
)
from backend.app.models.routing import RoutingEngine, VEHICLE_THRESHOLDS

WORKSPACE_DIR = Path(__file__).resolve().parents[3]
CITIES_DATA_DIR = WORKSPACE_DIR / "backend" / "data" / "cities"


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Computes great-circle distance between two coordinates in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def geocode_location(query: str) -> Tuple[float, float, str]:
    """
    Resolves any landmark name, coordinate string, or address to (lon, lat, name).
    Checks local catalogs first (instant), then queries Nominatim for arbitrary global locations.
    """
    clean = query.strip()
    lower = clean.lower()

    # 1. Check Mumbai Landmarks
    for k, coords in STUDY_AREA_LANDMARKS.items():
        if k in lower or lower in k:
            return coords[0], coords[1], f"{k.title()} (Mumbai)"

    # 2. Check Kolkata Landmarks
    for k, coords in KOLKATA_LANDMARKS.items():
        if k in lower or lower in k:
            return coords[0], coords[1], f"{k.title()} (Kolkata)"

    # 3. Check Coordinate String "lat, lon"
    if "," in clean:
        parts = [p.strip() for p in clean.split(",")]
        if len(parts) == 2:
            try:
                v1, v2 = float(parts[0]), float(parts[1])
                if (8.0 <= v1 <= 38.0) and (65.0 <= v2 <= 100.0):
                    return v2, v1, f"Coordinates [{v1:.4f}° N, {v2:.4f}° E]"
                elif (65.0 <= v1 <= 100.0) and (8.0 <= v2 <= 38.0):
                    return v1, v2, f"Coordinates [{v2:.4f}° N, {v1:.4f}° E]"
                return v2, v1, f"Coordinates [{v1:.4f}, {v2:.4f}]"
            except ValueError:
                pass

    # 4. Global Geocoding via Nominatim API
    print(f"  🔍 Geocoding '{query}' via OpenStreetMap Nominatim...")
    try:
        encoded = urllib.parse.quote(clean)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "UrbanFloodCorridorPipeline/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                item = data[0]
                lat = float(item["lat"])
                lon = float(item["lon"])
                disp_name = item.get("display_name", clean).split(",")[0]
                return lon, lat, f"{disp_name} (Geocoded)"
    except Exception as e:
        print(f"  ⚠️ Geocoding request failed: {e}")

    # Fallback to Kestopur if Kolkata keyword present, otherwise BKC
    if any(w in lower for w in ["kolkata", "calcutta", "bengal", "ruby", "salt"]):
        return 88.4230, 22.5930, f"Kestopur (Fallback for '{query}')"
    return 72.8545, 19.0665, f"BKC (Fallback for '{query}')"


def resolve_corridor_assets(
    src: Tuple[float, float], dst: Tuple[float, float]
) -> Dict[str, Any]:
    """
    Identifies or builds the corridor package for the given origin and destination.
    Returns paths to DEM, road graph, and drainage files, plus spatial grid dimensions.
    """
    src_lon, src_lat = src
    dst_lon, dst_lat = dst

    # Check if both inside Kolkata corridor
    k_min_lat, k_max_lat, k_min_lon, k_max_lon = CITY_CONFIGS["kolkata"]["bbox"]
    if (k_min_lat <= src_lat <= k_max_lat and k_min_lon <= src_lon <= k_max_lon and
        k_min_lat <= dst_lat <= k_max_lat and k_min_lon <= dst_lon <= k_max_lon):
        return {
            "name": "Kolkata — EM Bypass Corridor (12 km)",
            "city_slug": "kolkata",
            "dem_npy": WORKSPACE_DIR / "backend" / "data" / "cities" / "kolkata" / "dem" / "elevation_grid.npy",
            "roads_graph": WORKSPACE_DIR / "backend" / "data" / "cities" / "kolkata" / "roads" / "road_graph.json",
            "roads_geojson": WORKSPACE_DIR / "backend" / "data" / "cities" / "kolkata" / "roads" / "road_network.geojson",
            "drainage_nodes": WORKSPACE_DIR / "backend" / "data" / "cities" / "kolkata" / "drainage" / "drainage_nodes.geojson",
            "drainage_edges": WORKSPACE_DIR / "backend" / "data" / "cities" / "kolkata" / "drainage" / "drainage_edges.geojson",
            "grid": (300, 160, 35.0),
            "bbox": (k_min_lat, k_max_lat, k_min_lon, k_max_lon),
        }

    # Check if both inside Mumbai study area
    m_min_lat, m_max_lat, m_min_lon, m_max_lon = CITY_CONFIGS["mumbai"]["bbox"]
    if (m_min_lat <= src_lat <= m_max_lat and m_min_lon <= src_lon <= m_max_lon and
        m_min_lat <= dst_lat <= m_max_lat and m_min_lon <= dst_lon <= m_max_lon):
        return {
            "name": "Mumbai — BKC / Kurla Basin (2x2 km Pilot)",
            "city_slug": "mumbai",
            "dem_npy": WORKSPACE_DIR / "backend" / "data" / "dem" / "elevation_grid.npy",
            "roads_graph": WORKSPACE_DIR / "backend" / "data" / "roads" / "road_graph.json",
            "roads_geojson": WORKSPACE_DIR / "backend" / "data" / "roads" / "road_network.geojson",
            "drainage_nodes": WORKSPACE_DIR / "backend" / "data" / "drainage" / "drainage_nodes.geojson",
            "drainage_edges": WORKSPACE_DIR / "backend" / "data" / "drainage" / "drainage_edges.geojson",
            "grid": (200, 200, 10.0),
            "bbox": (m_min_lat, m_max_lat, m_min_lon, m_max_lon),
        }

    # For any arbitrary location: determine bounding box and cache dir
    from build_any_corridor_assets import (
        compute_bbox,
        corridor_cache_dir,
        build_corridor,
        _compile_corridor_rainfall_assets,
    )
    bbox = compute_bbox((src_lon, src_lat), (dst_lon, dst_lat))
    corridor_hash, custom_dir = corridor_cache_dir(bbox)
    min_lat, max_lat, min_lon, max_lon = bbox

    # Check if custom corridor is already cached
    cached_graph = custom_dir / "roads" / "road_graph.json"
    cached_dem = custom_dir / "dem" / "elevation_grid.npy"
    cached_drainage = custom_dir / "drainage" / "drainage_nodes.geojson"
    cached_rainfall = custom_dir / "rainfall" / "rainfall_metadata.json"

    if not (cached_graph.exists() and cached_dem.exists() and cached_drainage.exists()):
        print(f"\n  ⚡ Corridor '{corridor_hash}' not cached. Building complete domain assets on-the-fly...")
        try:
            build_corridor(
                origin=f"{src_lat:.5f}, {src_lon:.5f}",
                destination=f"{dst_lat:.5f}, {dst_lon:.5f}",
                force=False,
            )
        except Exception as exc:
            print(f"  ⚠️ Dynamic corridor build failed: {exc}. Mapping to nearest verified corridor.")
            dist_to_kolkata = haversine_m(src_lon, src_lat, 88.40, 22.55)
            dist_to_mumbai = haversine_m(src_lon, src_lat, 72.85, 19.07)
            if dist_to_kolkata < dist_to_mumbai:
                return resolve_corridor_assets((88.4230, 22.5930), (88.4030, 22.5135))
            else:
                return resolve_corridor_assets((72.8545, 19.0665), (72.8660, 19.0740))

    # Read calibrated grid resolution from metadata
    grid = (200, 200, 25.0)
    meta_path = custom_dir / "dem" / "dem_metadata.json"
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                grid = (meta.get("rows", 200), meta.get("cols", 200), meta.get("cell_size_m", 25.0))
        except Exception:
            pass

    # Ensure rainfall assets exist for this corridor
    if not cached_rainfall.exists():
        dem_grid = np.load(cached_dem)
        _compile_corridor_rainfall_assets(
            out_dir=custom_dir,
            center_lat=(min_lat + max_lat) / 2.0,
            center_lon=(min_lon + max_lon) / 2.0,
            grid_rows=grid[0],
            grid_cols=grid[1],
            cell_size_m=grid[2],
            dem_grid=dem_grid,
            bbox_hash=corridor_hash,
            active_scenario="heavy",
        )

    return {
        "name": f"Dynamic Corridor ({corridor_hash})",
        "city_slug": f"corridor_{corridor_hash}",
        "dem_npy": cached_dem,
        "roads_graph": cached_graph,
        "roads_geojson": custom_dir / "roads" / "road_network.geojson",
        "drainage_nodes": cached_drainage,
        "drainage_edges": custom_dir / "drainage" / "drainage_edges.geojson",
        "rainfall_dir": custom_dir / "rainfall",
        "grid": grid,
        "bbox": (min_lat, max_lat, min_lon, max_lon),
    }


def run_unified_corridor_pipeline(
    src_input: str = "Kestopur",
    dst_input: str = "Ruby Hospital",
    scenario: str = "heavy",
    vehicle_type: str = "car",
    horizon_minutes: int = 60,
    dt_seconds: float = 300.0,
    date_str: Optional[str] = None,
    live_radar: bool = False,
) -> Dict[str, Any]:
    """
    Executes the complete tri-model pipeline:
    1. Geocodes origin and destination
    2. Model 1 (Drainage): Loads subterranean pipe hydraulics
    3. Model 2 (Flood): Runs 2D hydrodynamic overland runoff coupled with drainage absorption
    4. Model 3 (Routing): Routes vehicle with A* avoidance of submerged streets
    """
    print("=" * 80)
    print(" 🌊 URBAN FLOOD NOWCASTING & RESILIENT NAVIGATION — UNIFIED PIPELINE")
    print("=" * 80)

    # 1. Geocode Origin & Destination
    print("\n[Step 1/4] Geocoding Route Coordinates...")
    src_lon, src_lat, src_name = geocode_location(src_input)
    dst_lon, dst_lat, dst_name = geocode_location(dst_input)
    print(f"  Origin     : {src_name} [{src_lat:.5f}° N, {src_lon:.5f}° E]")
    print(f"  Destination: {dst_name} [{dst_lat:.5f}° N, {dst_lon:.5f}° E]")

    # 2. Resolve Corridor Assets
    corridor = resolve_corridor_assets((src_lon, src_lat), (dst_lon, dst_lat))
    rows, cols, cell_size_m = corridor["grid"]
    print(f"\n[Step 2/4] Initializing Domain Assets for '{corridor['name']}'...")
    print(f"  Grid Resolution: {rows} x {cols} cells @ {cell_size_m:.1f}m cell size")

    # 3. Model 1: Subterranean Drainage Graph
    print("\n[Step 3A/4] Initializing Model 1 (Subterranean Storm Drainage Network)...")
    drainage = DrainageGraph(
        nodes_path=corridor["drainage_nodes"],
        edges_path=corridor["drainage_edges"],
        cell_size_m=cell_size_m,
    )
    drainage_summary = drainage.get_network_summary()
    print(f"  Total Inlets & Junctions : {drainage_summary['total_nodes']:,} nodes")
    print(f"  Total Underground Pipes  : {drainage_summary['total_edges']:,} conduits")
    print(f"  Active Outfalls to River : {drainage_summary.get('outfall_nodes', 0)} outfalls")

    # 4. Model 2: 2D Hydrodynamic Surface Flood Engine coupled with Universal Rainfall Provider
    print(f"\n[Step 3B/4] Initializing Model 2 (2D Hydrodynamic Surface Flood Engine)...")
    dem = np.load(corridor["dem_npy"]).astype(np.float32)

    # Detect lowest elevation sink in domain to focus convective thunderstorm cells
    sink_idx = np.unravel_index(np.argmin(dem), dem.shape)
    sink_r, sink_c = int(sink_idx[0]), int(sink_idx[1])
    center_lat = (corridor["bbox"][0] + corridor["bbox"][1]) / 2.0
    center_lon = (corridor["bbox"][2] + corridor["bbox"][3]) / 2.0

    from backend.data.rainfall.provider import CorridorRainfallProvider
    active_scenario = "live" if live_radar else scenario.lower()
    rainfall_provider = CorridorRainfallProvider(
        lat=center_lat,
        lon=center_lon,
        grid_shape=(rows, cols),
        cell_size_m=cell_size_m,
        scenario=active_scenario,
        date_str=date_str,
        hotspot_row=sink_r,
        hotspot_col=sink_c,
    )

    cur_rain = rainfall_provider.get_current_rainfall()
    print(f"  Topography Elevation Range  : {float(np.min(dem)):.2f}m to {float(np.max(dem)):.2f}m MSL")
    print(f"  Atmospheric Rainfall Engine : CorridorRainfallProvider [{active_scenario.upper()}]")
    print(f"  Corridor Atmospheric Center : [{center_lat:.4f}° N, {center_lon:.4f}° E]")
    print(f"  Topographic Sink Core       : Cell [{sink_r}, {sink_c}] (MSL: {float(np.min(dem)):.2f}m)")
    print(f"  Instantaneous Rain Rate     : {cur_rain:.2f} mm/hr")
    if active_scenario == "live":
        radar_frames = rainfall_provider.get_radar_frames(limit=3)
        print(f"  Doppler Radar Satellite     : {len(radar_frames)} live frames tracked (RainViewer)")
    elif active_scenario == "historical" or date_str:
        print(f"  Historical Replay Event     : {date_str or 'Calibrated storm'}")

    flood_engine = FloodEngine(
        dem=dem,
        drainage_graph=drainage,
        rainfall_provider=rainfall_provider,
        cell_size_m=cell_size_m,
    )
    print(f"  Simulating {horizon_minutes}-minute '{active_scenario.upper()}' storm scenario...")

    forecast_grids = flood_engine.run_forecast(
        scenario=active_scenario,
        horizon_minutes=horizon_minutes,
        dt=dt_seconds,
    )
    target_depth_grid = forecast_grids[horizon_minutes]
    max_depth = float(np.max(target_depth_grid))
    mean_depth = float(np.mean(target_depth_grid))
    flooded_cells_15cm = int(np.sum(target_depth_grid >= 0.15))
    flooded_cells_30cm = int(np.sum(target_depth_grid >= 0.30))

    print(f"\n  📊 Flood Simulation Physics Summary (at T+{horizon_minutes} min):")
    print(f"     • Total Rain Influx       : {flood_engine.total_rain_volume_m3:12.1f} m³")
    print(f"     • Soil Infiltration Loss   : {flood_engine.total_infiltrated_volume_m3:12.1f} m³")
    print(f"     • Absorbed by Storm Drains : {flood_engine.total_absorbed_volume_m3:12.1f} m³")
    print(f"     • Peak Standing Water Depth: {max_depth * 100:12.1f} cm")
    print(f"     • Street Cells > 15 cm     : {flooded_cells_15cm:12,d} cells")
    print(f"     • Street Cells > 30 cm     : {flooded_cells_30cm:12,d} cells")

    # 5. Model 3: Flood-Resilient Vehicle Routing Engine
    print(f"\n[Step 4/4] Running Model 3 (Flood-Resilient Routing Engine)...")
    clearance_m = VEHICLE_THRESHOLDS.get(vehicle_type.lower(), 0.30)
    print(f"  Selected Vehicle Class : {vehicle_type.capitalize()} (Wading Limit: {int(clearance_m*100)} cm)")
    print(f"  Overlaying simulated hydrodynamic depth matrix onto street graph...")

    routing_engine = RoutingEngine(
        geojson_path=corridor["roads_geojson"],
        graph_path=corridor["roads_graph"],
    )

    routes = routing_engine.find_alternative_routes(
        src=(src_lon, src_lat),
        dst=(dst_lon, dst_lat),
        vehicle_type=vehicle_type,
        depth_grid=target_depth_grid,
        max_alternatives=2,
    )

    if not routes or not routes[0].get("route_found"):
        print("\n❌ NO SAFE ROUTE FOUND:")
        print(f"  All available street corridors between {src_name} and {dst_name} exceed {int(clearance_m*100)} cm water depth.")
        print("  Recommendation: Dispatch high-clearance rescue truck or hold until drainage recession.")
        return {"status": "NO_SAFE_ROUTE", "corridor": corridor["name"]}

    primary = routes[0]
    dist_km = primary["distance_m"] / 1000.0
    travel_time = primary["travel_time_min"]
    max_flood_experienced = primary["max_flood_depth_m"] * 100.0
    safety_rating = primary["flood_risk"]
    avoided_roads = primary.get("roads_avoided", [])
    traversed_roads = primary.get("roads_traversed", [])

    print("\n" + "=" * 80)
    print(f" ✅ OPTIMAL SAFE NAVIGATION FOUND ({corridor['name'].upper()})")
    print("=" * 80)
    print(f"  Origin Landmark          : {src_name}")
    print(f"  Destination Landmark     : {dst_name}")
    print(f"  Total Travel Distance    : {primary['distance_m']:.1f} m ({dist_km:.2f} km)")
    print(f"  Estimated Travel Time    : {travel_time:.1f} minutes")
    print(f"  Maximum Water Encountered: {max_flood_experienced:.1f} cm (Limit: {int(clearance_m*100)} cm)")
    print(f"  Corridor Safety Level    : {safety_rating}")
    print(f"  Street Segments Safely Avoided: {len(avoided_roads)} submerged segments")

    if traversed_roads:
        print("\n  📍 Key Corridors Traversed:")
        seen = []
        for r in traversed_roads:
            name = r.get("name", "Unnamed Street")
            if not seen or seen[-1] != name:
                seen.append(name)
        for i, nm in enumerate(seen[:10], 1):
            print(f"     {i}. {nm}")
        if len(seen) > 10:
            print(f"     ... and {len(seen) - 10} additional connecting streets")

    if avoided_roads:
        print("\n  🚫 Submerged Street Chokepoints Avoided by Resilient Routing:")
        avoided_unique = list(set(r.get("name", "Street") for r in avoided_roads[:6]))
        for au in avoided_unique:
            print(f"     • {au}")

    if len(routes) > 1:
        print("\n  🔀 Alternative Safe Detours:")
        for idx, alt in enumerate(routes[1:], 1):
            print(f"     Detour {idx}: {alt['distance_m']/1000:.2f} km | {alt['travel_time_min']:.1f} min | Risk: {alt['flood_risk']}")

    # Export unified GeoJSON
    out_file = WORKSPACE_DIR / "live_corridor_navigation.geojson"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(primary["geojson"], f, indent=2)
    print(f"\n  💾 Exported Live Route Vector Layer: {out_file}")
    print("=" * 80)

    return {
        "status": "SUCCESS",
        "corridor": corridor["name"],
        "distance_km": dist_km,
        "travel_time_min": travel_time,
        "max_depth_cm": max_flood_experienced,
        "flood_absorbed_m3": flood_engine.total_absorbed_volume_m3,
        "avoided_segments": len(avoided_roads),
    }
