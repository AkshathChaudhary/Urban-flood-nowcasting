"""
API Router: /api/flood-forecast endpoints.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import numpy as np

from backend.app.config import (
    CELL_SIZE_M,
    GRID_COLS,
    GRID_ROWS,
    ORIGIN_LAT,
    ORIGIN_LON,
)
from backend.app.engine_state import (
    compute_summary,
    get_current_scenario,
    get_engine,
    lat_lon_to_grid,
)
from backend.app.models.flood import (
    FloodForecastOverview,
    FloodGridResponse,
    PointDepthResponse,
)

router = APIRouter(prefix="/api", tags=["flood-forecast"])


@router.get("/flood-forecast", response_model=FloodForecastOverview)
def get_flood_forecast_overview():
    """
    Returns an overview of the current flood forecast across all time horizons (0 to 180 min).
    Provides KPI summary stats (max depth, mean depth, flooded cell count) for each horizon.
    """
    engine = get_engine()
    scenario = get_current_scenario()
    horizons = sorted(engine.forecast_grids.keys())

    summaries = {
        h: compute_summary(engine.forecast_grids[h], h) for h in horizons
    }

    return FloodForecastOverview(
        scenario=scenario,
        horizons=horizons,
        summaries=summaries,
        total_rain_volume_m3=round(engine.total_rain_volume_m3, 1),
        total_infiltrated_volume_m3=round(engine.total_infiltrated_volume_m3, 1),
        total_absorbed_volume_m3=round(engine.total_absorbed_volume_m3, 1),
        total_overflow_volume_m3=round(engine.total_overflow_volume_m3, 1),
    )


@router.get("/flood-forecast/{minutes}", response_model=FloodGridResponse)
def get_flood_forecast_grid(minutes: int):
    """
    Returns the complete 200x200 water depth grid (in meters) for a specific time horizon.
    Ideal for GIS heatmap visualization in MapLibre / Leaflet.
    """
    engine = get_engine()
    if minutes not in engine.forecast_grids:
        available = sorted(engine.forecast_grids.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Horizon {minutes} min not found. Available horizons: {available}",
        )

    grid = engine.forecast_grids[minutes]
    summary = compute_summary(grid, minutes)

    return FloodGridResponse(
        scenario=get_current_scenario(),
        horizon_minutes=minutes,
        rows=GRID_ROWS,
        cols=GRID_COLS,
        cell_size_m=CELL_SIZE_M,
        origin_lat=ORIGIN_LAT,
        origin_lon=ORIGIN_LON,
        summary=summary,
        depth_grid=np.round(grid, 3).tolist(),
    )


@router.get("/flood-forecast/point/query", response_model=PointDepthResponse)
def query_point_depth(
    row: Optional[int] = Query(None, ge=0, lt=GRID_ROWS),
    col: Optional[int] = Query(None, ge=0, lt=GRID_COLS),
    lat: Optional[float] = Query(None, ge=18.0, le=20.0),
    lon: Optional[float] = Query(None, ge=72.0, le=74.0),
):
    """
    Query flood depth progression at a specific coordinate or grid cell.
    Returns water depth at T+0 through T+180 min and road hazard status.
    """
    engine = get_engine()

    if row is None or col is None:
        if lat is not None and lon is not None:
            row, col = lat_lon_to_grid(lat, lon)
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either (row, col) or (lat, lon) coordinates.",
            )

    elevation = float(engine.dem[row, col])
    porosity = float(engine.surface_porosity[row, col]) if hasattr(engine, "surface_porosity") else 1.0

    depth_at_horizons = {
        h: round(float(engine.forecast_grids[h][row, col]), 3)
        for h in sorted(engine.forecast_grids.keys())
    }

    street_depth_at_horizons = {
        h: round(float(engine.forecast_grids[h][row, col] / max(porosity, 0.1)), 3)
        for h in sorted(engine.forecast_grids.keys())
    }

    # Hazard level determined by physical street water depth
    max_street_depth = max(street_depth_at_horizons.values()) if street_depth_at_horizons else 0.0

    if max_street_depth > 0.30:
        hazard = "IMPASSABLE"
    elif max_street_depth > 0.10:
        hazard = "CAUTION"
    else:
        hazard = "CLEAR"

    return PointDepthResponse(
        lat=lat,
        lon=lon,
        row=row,
        col=col,
        elevation_m=round(elevation, 2),
        depth_m_at_horizon=depth_at_horizons,
        street_depth_m_at_horizon=street_depth_at_horizons,
        porosity=round(porosity, 3),
        hazard_level=hazard,
    )
