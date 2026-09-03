"""
API Router: /api/simulate endpoint.
"""

from fastapi import APIRouter, HTTPException
from backend.app.engine_state import (
    compute_summary,
    get_engine,
    set_engine,
)
from backend.app.models.flood import FloodForecastOverview, SimulateRequest
from backend.data.rainfall.provider import get_rainfall_provider

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulate", response_model=FloodForecastOverview)
def run_simulation(req: SimulateRequest):
    """
    Triggers an on-demand flood simulation run.
    Recomputes water accumulation, overland flow routing, and nowcast snapshots.
    Updates the active server state with the new forecast.
    """
    engine = get_engine()

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

        engine.rainfall_provider = provider
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")
