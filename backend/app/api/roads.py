"""
FastAPI Roads Router (Pair C - Task C2.8)
=========================================

Exposes REST API endpoints for road network metadata, GeoJSON vector layers,
flood-prone low-elevation hotspots, and individual road segment diagnostics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
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
    engine = get_routing_engine(city or "mumbai")
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
    c = (city or "mumbai").lower().strip()
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
        if not highway_type:
            major = [f for f in features if any(t in str(f.get("properties", {}).get("highway_type", "")).lower() for t in ["primary", "secondary", "tertiary", "trunk", "motorway"])]
            if major:
                features = major

    if highway_type:
        ht_clean = highway_type.lower().strip()
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
    c = (city or "mumbai").lower().strip()
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
    try:
        flood_eng = get_engine()
        if hasattr(flood_eng, "get_street_depth_grid"):
            depth_grid = flood_eng.get_street_depth_grid(time_horizon_min)
        elif hasattr(flood_eng, "forecast_grids") and time_horizon_min in flood_eng.forecast_grids:
            depth_grid = flood_eng.forecast_grids[time_horizon_min]
    except Exception:
        depth_grid = None

    result = engine.classify_corridors(depth_grid=depth_grid)
    result["time_horizon_min"] = time_horizon_min
    return result


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
