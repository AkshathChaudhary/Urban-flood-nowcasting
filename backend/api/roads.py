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

from backend.models.routing import RoutingEngine, VEHICLE_THRESHOLDS

router = APIRouter(prefix="/api/roads", tags=["Road Network & Flood Hotspots"])

# Default Asset Paths
ROAD_GEOJSON_PATH = Path("backend/data/roads/road_network.geojson")
ROAD_GRAPH_PATH = Path("backend/data/roads/road_graph.json")
HOTSPOTS_GEOJSON_PATH = Path("backend/data/roads/flood_hotspots.geojson")

# Singleton instance of RoutingEngine
_routing_engine: Optional[RoutingEngine] = None


def get_routing_engine() -> RoutingEngine:
    """Lazy-initializes or returns the active RoutingEngine instance."""
    global _routing_engine
    if _routing_engine is None:
        if not ROAD_GRAPH_PATH.exists() and not ROAD_GEOJSON_PATH.exists():
            raise RuntimeError(
                f"Road data files not found. Run clean_roads.py to build them."
            )
        _routing_engine = RoutingEngine(ROAD_GEOJSON_PATH, ROAD_GRAPH_PATH)
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
    if not ROAD_GEOJSON_PATH.exists():
        raise HTTPException(status_code=404, detail="Road network GeoJSON not found on server.")

    with open(ROAD_GEOJSON_PATH, "r", encoding="utf-8") as f:
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
    if not HOTSPOTS_GEOJSON_PATH.exists():
        raise HTTPException(status_code=404, detail="Flood hotspots GeoJSON not found on server.")

    with open(HOTSPOTS_GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/{road_id}")
def get_road_by_id(road_id: str):
    """
    Retrieves physical attributes, topological nodes, DEM elevation,
    current flood depth, and vehicle passability matrix for a specific road ID (e.g. 'R-0001').
    """
    engine = get_routing_engine()
    road = engine.get_road_details(road_id.upper())
    if not road:
        # Try finding by lowercase or original string
        road = engine.get_road_details(road_id)
    if not road:
        raise HTTPException(status_code=404, detail=f"Road segment with ID '{road_id}' not found.")
    return road
