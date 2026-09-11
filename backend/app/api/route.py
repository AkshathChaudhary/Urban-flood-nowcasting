"""
FastAPI Dynamic Routing Router (Pair C - Task C2.7)
===================================================

Exposes REST API endpoints for computing flood-resilient routes, evaluating
alternative detours, checking vehicle water clearance tolerances, and simulating
flood ponding scenarios.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import numpy as np

from backend.app.models.routing import RoutingEngine, VEHICLE_THRESHOLDS
from backend.app.models.location import (
    get_live_location,
    resolve_destination,
    STUDY_AREA_LANDMARKS,
    DESTINATIONS_CATALOG,
    ENTRY_GATEWAYS,
    MIN_LAT,
    MAX_LAT,
    MIN_LON,
    MAX_LON,
)
from backend.app.api.roads import get_routing_engine
from backend.app.engine_state import get_engine

router = APIRouter(prefix="/api/route", tags=["Flood-Resilient Routing"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    src_lon: float = Field(..., ge=-180.0, le=180.0, description="Starting longitude (WGS84, e.g. 72.855)")
    src_lat: float = Field(..., ge=-90.0, le=90.0, description="Starting latitude (WGS84, e.g. 19.065)")
    dst_lon: float = Field(..., ge=-180.0, le=180.0, description="Destination longitude (WGS84, e.g. 72.865)")
    dst_lat: float = Field(..., ge=-90.0, le=90.0, description="Destination latitude (WGS84, e.g. 19.075)")
    vehicle_type: str = Field(
        "car",
        description="Vehicle type: 'pedestrian', 'car', 'suv', 'ambulance', or 'truck'."
    )
    time_horizon_min: int = Field(
        0,
        ge=0,
        le=180,
        description="Forecast horizon in minutes (0 = current, 30, 60, 90, 120, 180)."
    )
    include_alternatives: bool = Field(
        True,
        description="Whether to calculate up to 2 distinct safe alternative routes."
    )
    blocked_road_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of road IDs to manually treat as impassable (e.g. debris or police blockades)."
    )


class FloodSimulationRouteRequest(RouteRequest):
    simulated_flood_depth_m: float = Field(
        0.35,
        ge=0.0,
        le=2.0,
        description="Uniform or localized simulated flood depth applied to low-elevation hotspots in meters."
    )
    hotspot_only: bool = Field(
        True,
        description="If True, only low-elevation flood hotspots receive flood depth. If False, applied to low-lying roads."
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/destinations")
@router.get("/landmarks")
def get_destinations_catalog():
    """
    Returns curated study area destinations, popular landmarks, and peripheral entry gateways.
    Used by frontend UI to populate origin/destination dropdowns, destination cards,
    and interactive map pins within the 2x2 km Mumbai pilot sector.
    """
    return {
        "city": "Mumbai",
        "pilot_basin": "Kurla - BKC - Mithi River Floodplain (2km x 2km)",
        "bounds": {
            "min_lat": MIN_LAT,
            "max_lat": MAX_LAT,
            "min_lon": MIN_LON,
            "max_lon": MAX_LON,
        },
        "destinations": DESTINATIONS_CATALOG,
        "entry_gateways": ENTRY_GATEWAYS,
        "total_destinations": len(DESTINATIONS_CATALOG),
    }


@router.get("/vehicles")
def get_vehicle_specs():
    """
    Returns supported vehicle classes and their maximum water wading clearance depths.
    """
    return {
        "vehicle_types": list(VEHICLE_THRESHOLDS.keys()),
        "clearance_thresholds_m": VEHICLE_THRESHOLDS,
        "clearance_thresholds_cm": {k: int(v * 100) for k, v in VEHICLE_THRESHOLDS.items()},
        "routing_priorities": {
            "ambulance": "High priority: emergency vehicle lane clearing on primary corridors (15% speed bonus).",
            "truck": "High clearance: 60cm wading depth for rescue operations.",
            "suv": "Moderate clearance: 45cm wading depth.",
            "car": "Standard urban sedan: 30cm clearance limit.",
            "pedestrian": "Critical vulnerability: 15cm wading limit.",
        },
    }


@router.post("")
def calculate_flood_route(req: RouteRequest):
    """
    Calculates the safest, fastest driving route between origin and destination coordinates.
    Dynamically routes around submerged or flooded streets based on vehicle wading limits
    and active simulation depth grid at the specified time horizon.
    """
    engine = get_routing_engine()
    vtype = req.vehicle_type.lower()
    if vtype not in VEHICLE_THRESHOLDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid vehicle type '{req.vehicle_type}'. Supported: {list(VEHICLE_THRESHOLDS.keys())}"
        )

    src = (req.src_lon, req.src_lat)
    dst = (req.dst_lon, req.dst_lat)

    # Check if FloodEngine has depth grids available for this horizon
    depth_grid = None
    try:
        flood_eng = get_engine()
        if hasattr(flood_eng, "get_street_depth_grid"):
            depth_grid = flood_eng.get_street_depth_grid(req.time_horizon_min)
        elif hasattr(flood_eng, "forecast_grids") and req.time_horizon_min in flood_eng.forecast_grids:
            depth_grid = flood_eng.forecast_grids[req.time_horizon_min]
    except Exception:
        depth_grid = None

    if req.blocked_road_ids:
        engine.apply_flood_weights(
            depth_grid=depth_grid,
            vehicle_type=vtype,
            blocked_road_ids=req.blocked_road_ids,
        )

    if req.include_alternatives:
        routes = engine.find_alternative_routes(
            src=src,
            dst=dst,
            vehicle_type=vtype,
            depth_grid=depth_grid,
            max_alternatives=2,
        )
        if not routes or not routes[0].get("route_found"):
            return {
                "route_found": False,
                "message": "No passable route available for this vehicle due to flooded or closed roads.",
                "vehicle_type": vtype,
                "alternatives_count": 0,
                "routes": routes,
            }
        return {
            "route_found": True,
            "vehicle_type": vtype,
            "time_horizon_min": req.time_horizon_min,
            "primary_route": routes[0],
            "alternatives": routes[1:],
            "alternatives_count": len(routes) - 1,
        }
    else:
        route = engine.find_route(
            src=src,
            dst=dst,
            vehicle_type=vtype,
            depth_grid=depth_grid,
        )
        return {
            "route_found": route.get("route_found", False),
            "vehicle_type": vtype,
            "time_horizon_min": req.time_horizon_min,
            "primary_route": route,
            "alternatives": [],
            "alternatives_count": 0,
        }


@router.post("/simulate-flood")
def simulate_flood_route(req: FloodSimulationRouteRequest):
    """
    Simulates a flood scenario by flooding low-elevation roads/hotspots to `simulated_flood_depth_m`
    and computes the rerouted path, demonstrating dynamic flood evasion in real-time.
    """
    engine = get_routing_engine()
    vtype = req.vehicle_type.lower()
    if vtype not in VEHICLE_THRESHOLDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid vehicle type '{req.vehicle_type}'."
        )

    # Synthesize 200x200 flood grid based on DEM elevation low-points
    mock_depth_grid = np.zeros((200, 200), dtype=np.float32)

    # Inundate grid cells corresponding to road midpoints with elevation <= 3.8m
    flooded_edges_count = 0
    for edge in engine.edge_attributes.values():
        if edge.get("elevation_m", 10.0) <= 3.8:
            r = edge.get("midpoint_grid_row", 0)
            c = edge.get("midpoint_grid_col", 0)
            mock_depth_grid[r, c] = req.simulated_flood_depth_m
            flooded_edges_count += 1

    src = (req.src_lon, req.src_lat)
    dst = (req.dst_lon, req.dst_lat)

    routes = engine.find_alternative_routes(
        src=src,
        dst=dst,
        vehicle_type=vtype,
        depth_grid=mock_depth_grid,
        max_alternatives=2,
    )

    return {
        "simulation_applied": {
            "simulated_water_depth_m": req.simulated_flood_depth_m,
            "flooded_segments_affected": flooded_edges_count,
            "vehicle_clearance_limit_m": VEHICLE_THRESHOLDS[vtype],
        },
        "route_found": routes[0].get("route_found", False) if routes else False,
        "primary_route": routes[0] if routes else None,
        "alternatives": routes[1:] if len(routes) > 1 else [],
    }


class NavigateRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=100, description="Destination landmark name (e.g. 'Kurla Station', 'BKC', 'LBS Marg') or coordinates 'lat, lon'")
    src_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Optional manual origin lon. If omitted, automatically acquires live user location.")
    src_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Optional manual origin lat. If omitted, automatically acquires live user location.")
    vehicle_type: str = Field("car", description="Vehicle type: 'car', 'suv', 'ambulance', 'truck', 'pedestrian'")
    simulated_flood_depth_m: Optional[float] = Field(None, ge=0.0, le=3.0, description="Optional flood depth in meters (e.g. 0.35) to simulate in real-time.")
    include_alternatives: bool = Field(True, description="Whether to include safe alternative detour options.")


@router.get("/current-location")
def get_user_live_location():
    """
    Acquires the user's real live location via GPS/IP and validates whether it falls
    inside the 2x2 km Mumbai study area. If outside, safely clamps to the BKC/CST Road entry point.
    """
    return get_live_location()


@router.post("/navigate")
def live_navigate(req: NavigateRequest):
    """
    High-level live navigation endpoint:
    - Auto-acquires live user location if src_lon/src_lat are not provided.
    - Resolves natural-language destination landmarks or coordinates.
    - Computes flood-resilient A* route avoiding submerged streets for the selected vehicle.
    """
    engine = get_routing_engine()
    vtype = req.vehicle_type.lower()
    if vtype not in VEHICLE_THRESHOLDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid vehicle type '{req.vehicle_type}'. Supported: {list(VEHICLE_THRESHOLDS.keys())}"
        )

    # 1. Determine Origin
    if req.src_lon is not None and req.src_lat is not None:
        src = (req.src_lon, req.src_lat)
        origin_desc = f"Custom origin ({req.src_lat:.4f}, {req.src_lon:.4f})"
    else:
        live = get_live_location()
        src = (live["lon"], live["lat"])
        origin_desc = live["location_name"]

    # 2. Resolve Destination
    dst_lon, dst_lat, dest_name = resolve_destination(req.destination)
    dst = (dst_lon, dst_lat)

    # 3. Simulate Flood if requested
    mock_depth_grid = None
    if req.simulated_flood_depth_m is not None and req.simulated_flood_depth_m > 0.0:
        mock_depth_grid = np.zeros((200, 200), dtype=np.float32)
        for edge in engine.edge_attributes.values():
            if edge.get("elevation_m", 10.0) <= 3.8:
                r = edge.get("midpoint_grid_row", 0)
                c = edge.get("midpoint_grid_col", 0)
                mock_depth_grid[r, c] = req.simulated_flood_depth_m

    # 4. Route Calculation
    routes = engine.find_alternative_routes(
        src=src,
        dst=dst,
        vehicle_type=vtype,
        depth_grid=mock_depth_grid,
        max_alternatives=2 if req.include_alternatives else 0,
    )

    if not routes or not routes[0].get("route_found"):
        return {
            "route_found": False,
            "origin": {"name": origin_desc, "lon": src[0], "lat": src[1]},
            "destination": {"name": dest_name, "lon": dst_lon, "lat": dst_lat},
            "vehicle_type": vtype,
            "message": "All paths to destination are submerged or impassable for your vehicle.",
        }

    return {
        "route_found": True,
        "origin": {"name": origin_desc, "lon": src[0], "lat": src[1]},
        "destination": {"name": dest_name, "lon": dst_lon, "lat": dst_lat},
        "vehicle_type": vtype,
        "clearance_limit_cm": int(VEHICLE_THRESHOLDS[vtype] * 100),
        "primary_route": routes[0],
        "alternatives": routes[1:] if len(routes) > 1 else [],
        "alternatives_count": len(routes) - 1,
    }
