"""
API Router: /api/simulate endpoint.
"""

from fastapi import APIRouter, HTTPException
from backend.app.engine_state import (
    compute_summary,
    get_engine,
    set_engine,
)
from backend.app.engine.flood_engine import FloodEngine
from backend.app.models.flood import FloodForecastOverview, SimulateRequest
from backend.data.rainfall.provider import get_rainfall_provider

import logging

router = APIRouter(prefix="/api", tags=["simulation"])
logger = logging.getLogger(__name__)


@router.post("/simulate", response_model=FloodForecastOverview)
def run_simulation(req: SimulateRequest):
    """
    Triggers an on-demand flood simulation run.
    Recomputes water accumulation, overland flow routing, and nowcast snapshots.
    Updates the active server state with the new forecast.
    """
    try:
        # Resolve provider based on mode
        if req.scenario == "live":
            provider = get_rainfall_provider(
                mode="live", lat=req.lat or 19.07, lon=req.lon or 72.85
            )
        elif req.scenario == "historical":
            provider = get_rainfall_provider(
                mode="historical",
                lat=req.lat or 19.07,
                lon=req.lon or 72.85,
                date_str=req.date_str or "2023-07-26",
                start_hour=req.start_hour or 11,
            )
        else:
            # Demo scenarios: moderate, heavy, extreme, cloudburst, extreme_blocked
            provider = get_rainfall_provider(mode="demo")

        # Instantiate a fresh engine to avoid race conditions and mutating active server state
        current_engine = get_engine()
        drainage_graph = getattr(current_engine, "drainage_graph", None)

        drain_blockage = 0.5 if req.scenario == "extreme_blocked" else 1.0
        engine = FloodEngine.from_default_data(
            rainfall_provider=provider,
            drainage_graph=drainage_graph,
            drain_blockage_factor=drain_blockage,
        )
        engine.run_forecast(
            scenario=req.scenario,
            horizon_minutes=req.horizon_minutes,
            dt=req.dt_seconds,
        )

        set_engine(engine, scenario=req.scenario)

        horizons = sorted(engine.forecast_grids.keys())
        summaries = {
            h: compute_summary(engine.forecast_grids[h], h) for h in horizons
        }

        return FloodForecastOverview(
            scenario=req.scenario,
            horizons=horizons,
            summaries=summaries,
            total_rain_volume_m3=round(engine.total_rain_volume_m3, 1),
            total_infiltrated_volume_m3=round(engine.total_infiltrated_volume_m3, 1),
            total_absorbed_volume_m3=round(engine.total_absorbed_volume_m3, 1),
            total_overflow_volume_m3=round(engine.total_overflow_volume_m3, 1),
        )

    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Simulation parameter error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during simulation run")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")
