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

# Singleton instance of RoutingEngine
_routing_engine: Optional[RoutingEngine] = None


def get_routing_engine() -> RoutingEngine:
    """Lazy-initializes or returns the active RoutingEngine instance."""
    global _routing_engine
    if _routing_engine is None:
        geojson_p = ROADS_DIR / "road_network.geojson" if (ROADS_DIR / "road_network.geojson").exists() else ROAD_GEOJSON_PATH
        graph_p = ROADS_DIR / "road_graph.json" if (ROADS_DIR / "road_graph.json").exists() else ROAD_GRAPH_PATH
        if not graph_p.exists() and not geojson_p.exists():
            raise RuntimeError(
                f"Road data files not found at {geojson_p} or {graph_p}. Run clean_roads.py to build them."
            )
        _routing_engine = RoutingEngine(geojson_p, graph_p)
    return _routing_engine


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
def get_roads_summary():
    """
    Returns aggregated metrics of the road network: node count, directed edges,
    total highway network length in km, classification breakdown, and vehicle thresholds.
    """
    engine = get_routing_engine()
    return engine.get_network_summary()


@router.get("/network")
def get_road_network_geojson(
    highway_type: Optional[str] = Query(None, description="Filter by highway type, e.g. 'primary', 'residential', 'trunk'")
):
    """
    Returns the complete road network formatted as a GeoJSON FeatureCollection of LineStrings.
    Optional query parameter to filter by highway classification.
    """
    geojson_path = ROADS_DIR / "road_network.geojson" if (ROADS_DIR / "road_network.geojson").exists() else ROAD_GEOJSON_PATH
    if not geojson_path.exists():
        raise HTTPException(status_code=404, detail="Road network GeoJSON not found on server.")

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if highway_type:
        ht_clean = highway_type.lower().strip()
        filtered_features = [
            f for f in data.get("features", [])
            if f.get("properties", {}).get("highway_type") == ht_clean
        ]
        return {
            "type": "FeatureCollection",
            "metadata": {
                **data.get("metadata", {}),
                "filter_applied": ht_clean,
                "filtered_count": len(filtered_features),
            },
            "features": filtered_features,
        }

    return data


@router.get("/hotspots")
def get_flood_hotspots():
    """
    Returns identified flood-vulnerable road intersections and low-elevation
    crossings (z <= 4.0m) as a GeoJSON FeatureCollection of Points.
    """
    hotspots_path = ROADS_DIR / "flood_hotspots.geojson" if (ROADS_DIR / "flood_hotspots.geojson").exists() else HOTSPOTS_GEOJSON_PATH
    if not hotspots_path.exists():
        raise HTTPException(status_code=404, detail="Flood hotspots GeoJSON not found on server.")

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
