"""
FastAPI Roads Router (Pair C - Task C2.8)
=========================================

Exposes REST API endpoints for road network metadata, GeoJSON vector layers,
flood-prone low-elevation hotspots, and individual road segment diagnostics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.config import ROADS_DIR
from backend.app.engine_state import get_engine
from backend.app.models.routing import RoutingEngine, VEHICLE_THRESHOLDS

router = APIRouter(prefix="/api/roads", tags=["Road Network & Flood Hotspots"])

# Default Asset Paths
ROAD_GEOJSON_PATH = ROADS_DIR / "road_network.geojson" if (ROADS_DIR / "road_network.geojson").exists() else Path("backend/data/roads/road_network.geojson")
ROAD_GRAPH_PATH = ROADS_DIR / "road_graph.json" if (ROADS_DIR / "road_graph.json").exists() else Path("backend/data/roads/road_graph.json")
HOTSPOTS_GEOJSON_PATH = ROADS_DIR / "flood_hotspots.geojson" if (ROADS_DIR / "flood_hotspots.geojson").exists() else Path("backend/data/roads/flood_hotspots.geojson")

# Cache of RoutingEngines by city
_routing_engines: Dict[str, RoutingEngine] = {}


def get_routing_engine(city: str = "mumbai") -> RoutingEngine:
    """Lazy-initializes or returns the active RoutingEngine instance for the specified city."""
    global _routing_engines
    c = (city or "mumbai").lower().strip()
    if c not in _routing_engines:
        if c == "kolkata":
            geojson_p = Path("backend/data/cities/kolkata/roads/road_network.geojson")
            graph_p = Path("backend/data/cities/kolkata/roads/road_graph.json")
        else:
            geojson_p = ROADS_DIR / "road_network.geojson" if (ROADS_DIR / "road_network.geojson").exists() else ROAD_GEOJSON_PATH
            graph_p = ROADS_DIR / "road_graph.json" if (ROADS_DIR / "road_graph.json").exists() else ROAD_GRAPH_PATH
        if not graph_p.exists() and not geojson_p.exists():
            raise RuntimeError(
                f"Road data files not found at {geojson_p} or {graph_p}."
            )
        _routing_engines[c] = RoutingEngine(geojson_p, graph_p)
    return _routing_engines[c]


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class RoadSummaryResponse(BaseModel):
    total_nodes: int
    total_directed_edges: int
    total_unique_road_segments: int
    total_length_km: float
    highway_type_breakdown: Dict[str, int]
    vehicle_clearance_specs_m: Dict[str, float]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=RoadSummaryResponse)
def get_roads_summary(city: Optional[str] = Query("mumbai")):
    """
    Returns aggregated metrics of the road network for the specified city.
    """
    c = str(getattr(city, "default", city) or "mumbai").lower().strip()
    engine = get_routing_engine(c)
    return engine.get_network_summary()


@router.get("/network")
def get_road_network_geojson(
    city: Optional[str] = Query("mumbai", description="City context: 'mumbai' or 'kolkata'"),
    highway_type: Optional[str] = Query(None, description="Filter by highway type, e.g. 'primary', 'residential', 'trunk'")
):
    """
    Returns the complete road network formatted as a GeoJSON FeatureCollection of LineStrings.
    Optional query parameter to filter by highway classification or city.
    """
    c = str(getattr(city, "default", city) or "mumbai").lower().strip()
    if c == "kolkata":
        geojson_path = Path("backend/data/cities/kolkata/roads/road_network.geojson")
    else:
        geojson_path = ROADS_DIR / "road_network.geojson" if (ROADS_DIR / "road_network.geojson").exists() else ROAD_GEOJSON_PATH

    if not geojson_path.exists():
        raise HTTPException(status_code=404, detail=f"Road network GeoJSON not found for city '{c}'.")

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    if c == "kolkata":
        for feat in features:
            p = feat.setdefault("properties", {})
            if "highway_type" not in p and "highway" in p:
                p["highway_type"] = p["highway"]
        ht_val = getattr(highway_type, "default", highway_type)
        if not (isinstance(ht_val, str) and ht_val.strip()):
            major = [f for f in features if any(t in str(f.get("properties", {}).get("highway_type", "")).lower() for t in ["primary", "secondary", "tertiary", "trunk", "motorway"])]
            if major:
                features = major

    ht_raw = getattr(highway_type, "default", highway_type)
    if isinstance(ht_raw, str) and ht_raw.strip():
        ht_clean = ht_raw.lower().strip()
        features = [
            f for f in features
            if ht_clean in str(f.get("properties", {}).get("highway_type", "")).lower()
        ]

    return {
        "type": "FeatureCollection",
        "metadata": {
            **data.get("metadata", {}),
            "city": c,
            "total_count": len(features),
        },
        "features": features,
    }


@router.get("/hotspots")
def get_flood_hotspots(city: Optional[str] = Query("mumbai")):
    """
    Returns identified flood-vulnerable road intersections and low-elevation
    crossings (z <= 4.0m) as a GeoJSON FeatureCollection of Points.
    """
    c = str(getattr(city, "default", city) or "mumbai").lower().strip()
    if c == "kolkata":
        hotspots_path = Path("backend/data/cities/kolkata/roads/flood_hotspots.geojson")
    else:
        hotspots_path = ROADS_DIR / "flood_hotspots.geojson" if (ROADS_DIR / "flood_hotspots.geojson").exists() else HOTSPOTS_GEOJSON_PATH

    if not hotspots_path.exists():
        return {"type": "FeatureCollection", "features": []}

    with open(hotspots_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/corridors/passability")
def get_corridor_passability(
    time_horizon_min: int = Query(0, ge=0, le=180, description="Forecast horizon in minutes (0, 30, 60, 90, 120, 180)")
):
    """
    Evaluates passability across all road corridors for the specified forecast horizon:
    - CLEAR: depth < 10 cm (< 0.10 m)
    - CAUTION: 10 cm <= depth < 30 cm (0.10 - 0.30 m)
    - IMPASSABLE: depth >= 30 cm (>= 0.30 m)
    """
    engine = get_routing_engine()
    depth_grid = None
    h_min = int(getattr(time_horizon_min, "default", time_horizon_min) or 0)
    try:
        flood_eng = get_engine()
        if hasattr(flood_eng, "get_street_depth_grid"):
            depth_grid = flood_eng.get_street_depth_grid(h_min)
        elif hasattr(flood_eng, "forecast_grids") and h_min in flood_eng.forecast_grids:
            depth_grid = flood_eng.forecast_grids[h_min]
    except Exception:
        depth_grid = None

    result = engine.classify_corridors(depth_grid=depth_grid)
    result["time_horizon_min"] = h_min
    return result


@router.get("/passability-grid")
@router.get("/network/passability")
def get_road_network_passability(
    city: Optional[str] = Query("mumbai"),
    time_horizon_min: int = Query(0, ge=0, le=180),
    vehicle_type: Optional[str] = Query("ambulance"),
    traffic_mode: Optional[str] = Query("peak_monsoon")
):
    """
    Evaluates dynamic road passability (OPEN, RESTRICTED, CLOSED) for each road segment
    in the city network by coupling hydrodynamic street flood depth with the selected
    vehicle's wading clearance limit and traffic conditions.
    """
    c = str(getattr(city, "default", city) or "mumbai").lower().strip()
    vtype = str(getattr(vehicle_type, "default", vehicle_type) or "ambulance").lower().strip()
    v_thresh = VEHICLE_THRESHOLDS.get(vtype, 0.45)
    tmode = str(getattr(traffic_mode, "default", traffic_mode) or "peak_monsoon").lower().strip()
    
    h_param = getattr(time_horizon_min, "default", time_horizon_min)
    h_min = int(h_param) if h_param is not None else 0

    engine = get_routing_engine(c)
    depth_grid = None
    try:
        if c == "kolkata":
            from backend.app.api.flood import get_kolkata_forecast
            _, k_grids = get_kolkata_forecast()
            depth_grid = k_grids.get(h_min)
        else:
            flood_eng = get_engine()
            if hasattr(flood_eng, "get_street_depth_grid"):
                depth_grid = flood_eng.get_street_depth_grid(h_min)
            elif hasattr(flood_eng, "forecast_grids") and h_min in flood_eng.forecast_grids:
                depth_grid = flood_eng.forecast_grids[h_min]
    except Exception:
        depth_grid = None

    from backend.app.services.traffic import traffic_service

    roads_status: Dict[str, Any] = {}
    open_count = 0
    restricted_count = 0
    closed_count = 0
    traffic_cache: Dict[Tuple[float, float, float], Dict[str, Any]] = {}

    # For Kolkata, match the rendered major network for lightning speed and responsiveness
    candidate_roads = engine.roads_by_id
    if c == "kolkata":
        candidate_roads = {
            rid: r for rid, r in engine.roads_by_id.items()
            if any(t in str(r.get("highway_type", r.get("highway", ""))).lower() for t in ["primary", "secondary", "tertiary", "trunk", "motorway"])
        }

    for road_id, road in candidate_roads.items():
        depth = 0.0
        if depth_grid is not None:
            r = road.get("midpoint_grid_row", 0)
            col = road.get("midpoint_grid_col", 0)
            if 0 <= r < depth_grid.shape[0] and 0 <= col < depth_grid.shape[1]:
                # Street depth with street porosity calibration (1 / 0.8)
                depth = float(depth_grid[r, col]) / 0.8

        # Clearance comparison:
        # depth < 0.6 * v_thresh: OPEN (Free Flow)
        # 0.6 * v_thresh <= depth < v_thresh: RESTRICTED (Caution)
        # depth >= v_thresh: CLOSED (Impassable)
        if depth >= v_thresh:
            status = "CLOSED"
            closed_count += 1
        elif depth >= 0.6 * v_thresh:
            status = "RESTRICTED"
            restricted_count += 1
        else:
            status = "OPEN"
            open_count += 1

        # Quick passability for all 6 vehicle types
        all_pass = {
            vt: depth < th
            for vt, th in VEHICLE_THRESHOLDS.items()
        }

        # Midpoint coordinates for traffic lookup with local spatial caching
        coords = road.get("coordinates", [])
        mid_lon, mid_lat = (coords[len(coords) // 2] if coords else (72.85, 19.07))
        speed_lim = float(road.get("maxspeed_kmh", 40.0) or 40.0)
        cache_key = (round(mid_lat, 2), round(mid_lon, 2), speed_lim)
        if cache_key in traffic_cache:
            tflow = traffic_cache[cache_key]
        else:
            tflow = traffic_service.get_flow_for_point(mid_lat, mid_lon, speed_lim, tmode, allow_network=False)
            traffic_cache[cache_key] = tflow

        roads_status[road_id] = {
            "status": status,
            "depth_cm": round(depth * 100, 1),
            "passability": all_pass,
            "speed_kmh": round(tflow.get("current_speed_kmh", speed_lim), 1),
            "congestion": tflow.get("congestion_level", "FREE_FLOW"),
            "delay_mult": round(tflow.get("delay_multiplier", 1.0), 2)
        }

    return {
        "city": c,
        "time_horizon_min": h_min,
        "selected_vehicle": vtype,
        "clearance_cm": int(v_thresh * 100),
        "total_roads": len(roads_status),
        "open_count": open_count,
        "restricted_count": restricted_count,
        "closed_count": closed_count,
        "roads": roads_status
    }



@router.get("/waypoints")
def get_city_waypoints(city: Optional[str] = Query("mumbai")):
    """Returns list of popular navigation landmarks/waypoints for the city."""
    from backend.app.models.location import STUDY_AREA_LANDMARKS, KOLKATA_LANDMARKS
    c = (city or "mumbai").lower().strip()
    landmarks_dict = KOLKATA_LANDMARKS if c == "kolkata" else STUDY_AREA_LANDMARKS
    waypoints = []
    seen = set()
    for name, (lon, lat) in landmarks_dict.items():
        coords_key = (round(lat, 4), round(lon, 4))
        if coords_key in seen:
            continue
        seen.add(coords_key)
        waypoints.append({
            "name": name.title(),
            "lat": lat,
            "lon": lon,
            "id": name.lower().replace(" ", "_"),
        })
    return {"city": c, "waypoints": waypoints}


@router.get("/route")
def get_safe_route(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lon: float = Query(..., description="Origin longitude"),
    dest_lat: float = Query(..., description="Destination latitude"),
    dest_lon: float = Query(..., description="Destination longitude"),
    city: Optional[str] = Query("mumbai"),
    vehicle_type: Optional[str] = Query("car"),
    time_horizon_min: Optional[int] = Query(0),
):
    """GET endpoint alias for calculating flood-resilient route between two points."""
    from backend.app.api.route import calculate_flood_route, RouteRequest
    req = RouteRequest(
        src_lat=origin_lat,
        src_lon=origin_lon,
        dst_lat=dest_lat,
        dst_lon=dest_lon,
        vehicle_type=vehicle_type or "car",
        time_horizon_min=time_horizon_min or 0,
        include_alternatives=True,
    )
    res = calculate_flood_route(req)
    primary = res.get("primary_route", {})
    return {
        "city": city,
        "status": "success",
        "distance_m": primary.get("distance_m", 0),
        "duration_min": primary.get("duration_min", 0),
        "flood_risk": primary.get("flood_risk", "LOW"),
        "max_water_depth_m": primary.get("max_water_depth_m", 0.0),
        "alternatives": res.get("alternatives", []),
        "primary_route": primary,
    }


@router.get("/{road_id}")
def get_road_by_id(
    road_id: str,
    time_horizon_min: int = Query(0, ge=0, le=180, description="Forecast horizon in minutes (0, 30, 60, 90, 120, 180)")
):
    """
    Retrieves physical attributes, topological nodes, DEM elevation,
    dynamic street flood depth, and vehicle passability matrix for a specific road ID.
    """
    engine = get_routing_engine()
    depth_grid = None
    try:
        flood_eng = get_engine()
        if hasattr(flood_eng, "get_street_depth_grid"):
            depth_grid = flood_eng.get_street_depth_grid(time_horizon_min)
        elif hasattr(flood_eng, "forecast_grids") and time_horizon_min in flood_eng.forecast_grids:
            depth_grid = flood_eng.forecast_grids[time_horizon_min]
    except Exception:
        depth_grid = None

    road = engine.get_road_details(road_id.upper(), depth_grid=depth_grid)
    if not road:
        road = engine.get_road_details(road_id, depth_grid=depth_grid)
    if not road:
        raise HTTPException(status_code=404, detail=f"Road segment with ID '{road_id}' not found.")
    road["time_horizon_min"] = time_horizon_min
    return road

