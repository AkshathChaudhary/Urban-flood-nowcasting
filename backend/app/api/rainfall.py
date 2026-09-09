"""
API Router: /api/rainfall endpoints for Doppler radar and rainfall nowcasts.
"""
from typing import Dict, List, Optional
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
    get_current_scenario,
    get_engine,
    grid_to_lat_lon,
    lat_lon_to_grid,
)
from backend.app.models.rainfall import (
    PointRainfallResponse,
    RadarFrameInfo,
    RainfallGridResponse,
    RainfallOverviewResponse,
    RainfallSummary,
)
from backend.data.rainfall.provider import RainfallProvider

router = APIRouter(prefix="/api/rainfall", tags=["rainfall-radar"])


def _compute_rainfall_summary(rain_grid: np.ndarray, horizon: int) -> RainfallSummary:
    """Calculates rainfall & radar intensity KPI metrics for a given rain rate array."""
    max_rate = float(np.max(rain_grid)) if rain_grid.size > 0 else 0.0
    mean_rate = float(np.mean(rain_grid)) if rain_grid.size > 0 else 0.0

    # Marshall-Palmer dBZ conversion
    dbz_grid = RainfallProvider.rain_rate_to_dbz(rain_grid)
    max_dbz = float(np.max(dbz_grid)) if dbz_grid.size > 0 else 0.0
    mean_dbz = float(np.mean(dbz_grid)) if dbz_grid.size > 0 else 0.0

    return RainfallSummary(
        horizon_minutes=horizon,
        max_rate_mmh=round(max_rate, 2),
        mean_rate_mmh=round(mean_rate, 3),
        max_reflectivity_dbz=round(max_dbz, 1),
        mean_reflectivity_dbz=round(mean_dbz, 1),
        is_raining=bool(max_rate > 0.1),
    )


@router.get("/overview", response_model=RainfallOverviewResponse)
@router.get("/nowcast", response_model=RainfallOverviewResponse)
def get_rainfall_overview():
    """
    Returns high-resolution rainfall nowcast overview across all forecast horizons (0 to 180 min),
    including current domain rain rate, peak rates, Doppler radar reflectivity stats, and radar frames.
    """
    engine = get_engine()
    scenario = get_current_scenario()
    provider = engine.rainfall_provider

    # If rain_nowcast not populated yet, populate from provider
    if not engine.rain_nowcast:
        engine.rain_nowcast = provider.generate_nowcast(scenario=scenario, horizon_minutes=180)

    horizons = sorted(engine.rain_nowcast.keys())
    summaries = {
        h: _compute_rainfall_summary(engine.rain_nowcast[h], h) for h in horizons
    }

    curr_rate = provider.get_current_rainfall()
    api_source = getattr(provider, "api_source_used", type(provider).__name__)

    # Fetch live Doppler radar frames if supported
    raw_frames = provider.get_radar_frames(limit=6)
    radar_frames = [
        RadarFrameInfo(
            time=f.get("time", 0),
            tile_url=f.get("tile_url", ""),
            relative_time=f.get("relative_time", ""),
            rain_rate_mmh=round(float(f.get("rain_rate_mmh", 0.0)), 2),
            reflectivity_dbz=round(float(f.get("reflectivity_dbz", 0.0)), 1),
        )
        for f in raw_frames
    ]

    return RainfallOverviewResponse(
        scenario=scenario,
        current_rain_rate_mmh=round(curr_rate, 2),
        api_source=api_source,
        horizons=horizons,
        summaries=summaries,
        radar_frames=radar_frames,
    )


@router.get("/nowcast/{minutes}", response_model=RainfallGridResponse)
def get_rainfall_grid(minutes: int):
    """
    Returns the complete 200x200 rain rate grid (mm/hr) and Doppler radar reflectivity (dBZ)
    for a specific forecast horizon. Ideal for GIS precipitation overlays in MapLibre / Leaflet.
    """
    engine = get_engine()
    scenario = get_current_scenario()
    provider = engine.rainfall_provider

    if not engine.rain_nowcast:
        engine.rain_nowcast = provider.generate_nowcast(scenario=scenario, horizon_minutes=180)

    if minutes not in engine.rain_nowcast:
        available = sorted(engine.rain_nowcast.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Rainfall horizon {minutes} min not found. Available horizons: {available}",
        )

    rain_grid = engine.rain_nowcast[minutes]

    summary = _compute_rainfall_summary(rain_grid, minutes)
    dbz_grid = RainfallProvider.rain_rate_to_dbz(rain_grid)

    return RainfallGridResponse(
        scenario=scenario,
        horizon_minutes=minutes,
        rows=GRID_ROWS,
        cols=GRID_COLS,
        cell_size_m=CELL_SIZE_M,
        origin_lat=ORIGIN_LAT,
        origin_lon=ORIGIN_LON,
        summary=summary,
        rain_rate_grid=np.round(rain_grid, 2).tolist(),
        reflectivity_dbz_grid=np.round(dbz_grid, 1).tolist(),
    )


@router.get("/point/query", response_model=PointRainfallResponse)
def query_point_rainfall(
    row: Optional[int] = Query(None, ge=0, lt=GRID_ROWS),
    col: Optional[int] = Query(None, ge=0, lt=GRID_COLS),
    lat: Optional[float] = Query(None, ge=18.0, le=20.0),
    lon: Optional[float] = Query(None, ge=72.0, le=74.0),
):
    """
    Query rainfall intensity and radar reflectivity progression at a specific coordinate or grid cell.
    Returns rain rate (mm/hr) and dBZ at T+0 through T+180 min and meteorological intensity category.
    """
    engine = get_engine()
    scenario = get_current_scenario()
    provider = engine.rainfall_provider

    if row is None or col is None:
        if lat is not None and lon is not None:
            row, col = lat_lon_to_grid(lat, lon)
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either (row, col) grid indices or (lat, lon) coordinates.",
            )
    elif lat is None or lon is None:
        lat, lon = grid_to_lat_lon(row, col)

    if not engine.rain_nowcast:
        engine.rain_nowcast = provider.generate_nowcast(scenario=scenario, horizon_minutes=180)

    rates_at_horizon: Dict[int, float] = {}
    dbz_at_horizon: Dict[int, float] = {}

    for h, grid in engine.rain_nowcast.items():
        rate = float(grid[row, col])
        rates_at_horizon[h] = round(rate, 2)
        dbz = float(RainfallProvider.rain_rate_to_dbz(rate))
        dbz_at_horizon[h] = round(dbz, 1)

    peak_rate = max(rates_at_horizon.values()) if rates_at_horizon else 0.0
    if peak_rate <= 0.1:
        category = "NONE"
    elif peak_rate < 2.5:
        category = "LIGHT"
    elif peak_rate < 10.0:
        category = "MODERATE"
    elif peak_rate < 50.0:
        category = "HEAVY"
    else:
        category = "CLOUDBURST"

    return PointRainfallResponse(
        lat=lat,
        lon=lon,
        row=row,
        col=col,
        rain_rate_mmh_at_horizon=rates_at_horizon,
        reflectivity_dbz_at_horizon=dbz_at_horizon,
        intensity_category=category,
    )


@router.get("/radar/frames", response_model=List[RadarFrameInfo])
def get_radar_frames(limit: int = Query(10, ge=1, le=24)):
    """
    Returns available Doppler weather radar frames (RainViewer / IMD)
    with tile URLs and reflectivity dBZ for animation overlay on GIS dashboards.
    """
    engine = get_engine()
    provider = engine.rainfall_provider
    raw_frames = provider.get_radar_frames(limit=limit)

    return [
        RadarFrameInfo(
            time=f.get("time", 0),
            tile_url=f.get("tile_url", ""),
            relative_time=f.get("relative_time", ""),
            rain_rate_mmh=round(float(f.get("rain_rate_mmh", 0.0)), 2),
            reflectivity_dbz=round(float(f.get("reflectivity_dbz", 0.0)), 1),
        )
        for f in raw_frames
    ]
