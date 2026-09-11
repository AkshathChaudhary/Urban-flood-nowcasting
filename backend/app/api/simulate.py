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


SUPPORTED_SCENARIOS = {
    "moderate": {
        "title": "Moderate Rainfall (10 mm/hr)",
        "description": "Baseline 10 mm/hr uniform rainfall over 2 hours with linear ramp-up and ramp-down.",
        "peak_intensity_mmh": 10.0,
        "mode": "demo",
    },
    "heavy": {
        "title": "Heavy Convective Storm (30 mm/hr)",
        "description": "30 mm/hr peak Gaussian rainstorm focused on low-elevation southeast Kurla sector.",
        "peak_intensity_mmh": 30.0,
        "mode": "demo",
    },
    "extreme": {
        "title": "Extreme Moving Storm Cell (60 mm/hr)",
        "description": "60 mm/hr intense storm cell traveling NW to SE across Mumbai at 20 km/h.",
        "peak_intensity_mmh": 60.0,
        "mode": "demo",
    },
    "cloudburst": {
        "title": "Severe Cloudburst (120 mm/hr)",
        "description": "120 mm/hr ultra-localized 500m-radius cloudburst event lasting 30 minutes.",
        "peak_intensity_mmh": 120.0,
        "mode": "demo",
    },
    "extreme_blocked": {
        "title": "Extreme Storm + 40% Drainage Blockage",
        "description": "60 mm/hr moving storm cell combined with severe debris clogging in subterranean stormwater pipes.",
        "peak_intensity_mmh": 60.0,
        "mode": "demo",
    },
    "blocked_drainage": {
        "title": "Extreme Storm + 40% Drainage Blockage (Alias)",
        "description": "60 mm/hr moving storm cell combined with severe debris clogging in subterranean stormwater pipes.",
        "peak_intensity_mmh": 60.0,
        "mode": "demo",
    },
    "live": {
        "title": "Live Radar Nowcast (OpenWeather + RainViewer)",
        "description": "Real-time minute-by-minute Doppler radar observations and nowcasts.",
        "peak_intensity_mmh": None,
        "mode": "live",
    },
    "historical": {
        "title": "Historical Reanalysis (July 26, 2023 Mumbai)",
        "description": "Replay of the verified July 26, 2023 Mumbai flooding event using ERA5 reanalysis data.",
        "peak_intensity_mmh": 50.9,
        "mode": "historical",
    },
}


@router.get("/scenarios")
@router.get("/simulate/scenarios")
def get_supported_scenarios():
    """
    Returns available simulation scenarios with descriptions, metadata, and peak intensities.
    Used by frontend UI dropdown selector.
    """
    return {
        "scenarios": list(SUPPORTED_SCENARIOS.keys()),
        "details": SUPPORTED_SCENARIOS,
    }


@router.post("/simulate", response_model=FloodForecastOverview)
def run_simulation(req: SimulateRequest):
    """
    Triggers an on-demand flood simulation run.
    Recomputes water accumulation, overland flow routing, and nowcast snapshots.
    Updates the active server state with the new forecast.
    """
    if req.scenario not in SUPPORTED_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario '{req.scenario}'. Supported scenarios: {sorted(SUPPORTED_SCENARIOS.keys())}",
        )

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

        # Reset and configure drainage graph for clean simulation isolation
        if drainage_graph is not None:
            if hasattr(drainage_graph, "reset_state"):
                drainage_graph.reset_state()
            if hasattr(drainage_graph, "set_global_blockage"):
                if req.scenario in ("extreme_blocked", "blocked_drainage"):
                    drainage_graph.set_global_blockage(0.40)  # Scenario 5: 40% pipe capacity reduction
                else:
                    drainage_graph.set_global_blockage(0.0)

        drain_blockage = 0.50 if req.scenario in ("extreme_blocked", "blocked_drainage") else 1.0
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
