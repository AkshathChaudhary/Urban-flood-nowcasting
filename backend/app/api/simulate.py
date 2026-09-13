"""
API Router: /api/simulate endpoint.
Coupled 2D Hydrodynamic runoff simulation for Mumbai & Kolkata.
Supports Live Doppler Radar Nowcasting, Real Historical Storm Replays, and Stress-Test Scenarios.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
import numpy as np

from backend.app.config import DATA_DIR
from backend.app.engine_state import (
    compute_summary,
    get_engine,
    set_engine,
)
from backend.app.engine.flood_engine import FloodEngine
from backend.app.models.flood import FloodForecastOverview, SimulateRequest
from backend.app.models.drainage import DrainageGraph
from backend.app.api.drainage import get_drainage_graph, invalidate_drainage_cache
from backend.app.api.flood import set_kolkata_engine
from backend.data.rainfall.provider import get_rainfall_provider

router = APIRouter(prefix="/api", tags=["simulation"])
logger = logging.getLogger(__name__)


SUPPORTED_SCENARIOS = {
    "live": {
        "title": "Live Radar Nowcast (OpenWeather / Open-Meteo Doppler)",
        "description": "Real-time Doppler radar observations and sub-hourly nowcasts for the selected city.",
        "peak_intensity_mmh": None,
        "mode": "live",
    },
    "historical": {
        "title": "Historical Storm Reanalysis (Open-Meteo Archive / ERA5)",
        "description": "Replay of verified real-world severe deluge events with calibrated sub-hourly convective hyetograph.",
        "peak_intensity_mmh": 50.9,
        "mode": "historical",
    },
    "cloudburst": {
        "title": "Severe Cloudburst (120 mm/hr)",
        "description": "120 mm/hr ultra-localized high-intensity burst (500m radius) lasting 30 minutes.",
        "peak_intensity_mmh": 120.0,
        "mode": "demo",
    },
    "extreme": {
        "title": "Extreme Moving Storm Cell (60 mm/hr)",
        "description": "60 mm/hr convective storm cell traveling across the urban corridor at 20 km/h.",
        "peak_intensity_mmh": 60.0,
        "mode": "demo",
    },
    "extreme_blocked": {
        "title": "Extreme Storm + 40% Drainage Blockage",
        "description": "60 mm/hr storm cell combined with severe subterranean stormwater conduit clogging.",
        "peak_intensity_mmh": 60.0,
        "mode": "demo",
    },
    "blocked_drainage": {
        "title": "Extreme Storm + 40% Drainage Blockage (Alias)",
        "description": "60 mm/hr storm cell combined with severe subterranean stormwater conduit clogging.",
        "peak_intensity_mmh": 60.0,
        "mode": "demo",
    },
    "heavy": {
        "title": "Heavy Convective Storm (30 mm/hr)",
        "description": "30 mm/hr peak Gaussian rainstorm focused over low-elevation urban depressions.",
        "peak_intensity_mmh": 30.0,
        "mode": "demo",
    },
    "moderate": {
        "title": "Moderate Steady Rainfall (10 mm/hr)",
        "description": "Baseline 10 mm/hr steady precipitation over 2 hours with ramp-up and ramp-down.",
        "peak_intensity_mmh": 10.0,
        "mode": "demo",
    },
}

HISTORICAL_PRESETS = {
    "mumbai": [
        {
            "id": "mumbai_2023_deluge",
            "date_str": "2023-07-26",
            "start_hour": 11,
            "title": "July 26, 2023 Monsoon Deluge",
            "description": "Verified Kurla/BKC flooding from ERA5 reanalysis (18.4 mm/hr peak at 11:00 UTC).",
            "peak_mmh": 50.9,
        },
        {
            "id": "mumbai_2005_cloudburst",
            "date_str": "2005-07-26",
            "start_hour": 14,
            "title": "July 26, 2005 Historic 944mm Storm",
            "description": "Century benchmark extreme cloudburst inundating entire Mithi River basin.",
            "peak_mmh": 120.0,
        },
        {
            "id": "mumbai_2019_monsoon",
            "date_str": "2019-07-02",
            "start_hour": 10,
            "title": "July 2, 2019 Malad & Kurla Floods",
            "description": "375mm 24-hour monsoon deluge causing widespread Mithi overflow and transit halt.",
            "peak_mmh": 45.0,
        },
    ],
    "kolkata": [
        {
            "id": "kolkata_2021_cloudburst",
            "date_str": "2021-09-20",
            "start_hour": 1,
            "title": "Sept 20, 2021 Night Cloudburst (142mm)",
            "description": "Midnight convective deluge submerging EM Bypass, Park Circus, and Salt Lake.",
            "peak_mmh": 65.0,
        },
        {
            "id": "kolkata_2020_amphan",
            "date_str": "2020-05-20",
            "start_hour": 17,
            "title": "May 20, 2020 Super Cyclone Amphan",
            "description": "Landfall peak eyewall gale with intense precipitation, storm surge, and drainage canal backflow (17:00-21:00 IST).",
            "peak_mmh": 80.0,
        },
        {
            "id": "kolkata_2021_depression",
            "date_str": "2021-09-29",
            "start_hour": 0,
            "title": "Sept 29, 2021 Cyclone Gulab Depression",
            "description": "140mm+ overnight deluge from remnant deep depression flooding Ultadanga, VIP Road, and EM Bypass.",
            "peak_mmh": 48.0,
        },
    ],
}

# Fast lookup for preset definitions by id
HISTORICAL_PRESETS_BY_ID: Dict[str, Dict[str, Any]] = {}
for city_key, p_list in HISTORICAL_PRESETS.items():
    for p in p_list:
        HISTORICAL_PRESETS_BY_ID[p["id"]] = {**p, "city": city_key}

# Add all preset IDs into SUPPORTED_SCENARIOS so clients can pass scenario="kolkata_2020_amphan" directly
for p_id, p_info in HISTORICAL_PRESETS_BY_ID.items():
    SUPPORTED_SCENARIOS[p_id] = {
        "title": p_info["title"],
        "description": p_info["description"],
        "peak_intensity_mmh": p_info["peak_mmh"],
        "mode": "historical",
    }


@router.get("/scenarios")
@router.get("/simulate/scenarios")
def get_supported_scenarios():
    """
    Returns available simulation scenarios with descriptions, metadata, and historical presets.
    Used by frontend UI dropdown selector and Simulation Modal.
    """
    return {
        "scenarios": list(SUPPORTED_SCENARIOS.keys()),
        "details": SUPPORTED_SCENARIOS,
        "historical_presets": HISTORICAL_PRESETS,
    }


@router.post("/simulate", response_model=FloodForecastOverview)
@router.get("/simulate", response_model=FloodForecastOverview)
@router.post("/flood/run-simulation", response_model=FloodForecastOverview)
@router.get("/flood/run-simulation", response_model=FloodForecastOverview)
def run_simulation(
    req: Optional[SimulateRequest] = Body(None),
    city: Optional[str] = Query(None),
    scenario: Optional[str] = Query(None),
    preset: Optional[str] = Query(None),
    date_str: Optional[str] = Query(None),
    start_hour: Optional[int] = Query(None),
):
    """
    Triggers an on-demand flood simulation run for either Mumbai or Kolkata.
    Recomputes water accumulation, overland flow routing, and nowcast snapshots.
    Updates the active server state with the new forecast.
    """
    if req is None:
        req = SimulateRequest(
            city=city or "mumbai",
            scenario=scenario or "moderate",
            preset=preset,
            date_str=date_str,
            start_hour=start_hour,
        )
    else:
        if city:
            req.city = city
        if scenario:
            req.scenario = scenario
        if preset:
            req.preset = preset
        if date_str:
            req.date_str = date_str
        if start_hour is not None:
            req.start_hour = start_hour

    # 0. Check and resolve historical preset if passed as scenario or in req.preset
    scenario_raw = (req.scenario or "moderate").strip()
    preset_id = req.preset or (scenario_raw if scenario_raw in HISTORICAL_PRESETS_BY_ID else None)
    preset_info = HISTORICAL_PRESETS_BY_ID.get(preset_id) if preset_id else None

    if preset_info:
        effective_scenario = "historical"
        scenario_title = preset_info["title"]
        active_preset = preset_info["id"]
        city = (req.city or preset_info["city"]).lower().strip()
        date_str = req.date_str or preset_info["date_str"]
        start_hour = req.start_hour if req.start_hour is not None else preset_info["start_hour"]
    else:
        effective_scenario = scenario_raw
        scenario_title = SUPPORTED_SCENARIOS.get(effective_scenario, {}).get("title", effective_scenario.capitalize())
        active_preset = None
        city = (req.city or "mumbai").lower().strip()
        date_str = req.date_str
        start_hour = req.start_hour

    if effective_scenario not in SUPPORTED_SCENARIOS and scenario_raw not in SUPPORTED_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario '{req.scenario}'. Supported scenarios: {sorted(SUPPORTED_SCENARIOS.keys())}",
        )

    is_kolkata = city == "kolkata"

    try:
        # 1. Resolve Rainfall Provider (Live, Historical, or Synthetic Demo)
        if effective_scenario == "live":
            default_lat = 22.5535 if is_kolkata else 19.0700
            default_lon = 88.4115 if is_kolkata else 72.8500
            grid_shape = (300, 160) if is_kolkata else (200, 200)
            cell_size = 35.0 if is_kolkata else 10.0

            provider = get_rainfall_provider(
                mode="live",
                lat=req.lat or default_lat,
                lon=req.lon or default_lon,
                grid_shape=grid_shape,
                cell_size_m=cell_size,
            )
        elif effective_scenario == "historical":
            default_lat = 22.5535 if is_kolkata else 19.0700
            default_lon = 88.4115 if is_kolkata else 72.8500
            default_date = "2021-09-20" if is_kolkata else "2023-07-26"
            default_start_hr = 1 if is_kolkata else 11
            grid_shape = (300, 160) if is_kolkata else (200, 200)
            cell_size = 35.0 if is_kolkata else 10.0

            provider = get_rainfall_provider(
                mode="historical",
                lat=req.lat or default_lat,
                lon=req.lon or default_lon,
                date_str=date_str or default_date,
                start_hour=start_hour if start_hour is not None else default_start_hr,
                grid_shape=grid_shape,
                cell_size_m=cell_size,
            )
        else:
            # Synthetic Demo scenarios
            grid_shape = (300, 160) if is_kolkata else (200, 200)
            cell_size = 35.0 if is_kolkata else 10.0
            provider = get_rainfall_provider(
                mode="demo",
                grid_shape=grid_shape,
                cell_size_m=cell_size,
            )

        # 2. Configure Subterranean Drainage Graph
        drainage_graph = get_drainage_graph(city)
        if drainage_graph is not None:
            if hasattr(drainage_graph, "reset_state"):
                drainage_graph.reset_state(reset_blockage=False)
            if hasattr(drainage_graph, "set_global_blockage"):
                if effective_scenario in ("extreme_blocked", "blocked_drainage"):
                    drainage_graph.set_global_blockage(0.40)  # 40% pipe capacity reduction
                    invalidate_drainage_cache(city)

        # Determine drainage conveyance factor from active network state
        avg_blockage = 0.0
        if drainage_graph is not None and hasattr(drainage_graph, "edge_data") and drainage_graph.edge_data:
            blockages = [e.get("blockage_pct", 0.0) for e in drainage_graph.edge_data.values()]
            if blockages:
                avg_blockage = float(np.mean(blockages))

        if effective_scenario in ("extreme_blocked", "blocked_drainage"):
            drain_blockage = 0.50
        elif avg_blockage > 0.0:
            drain_blockage = max(0.05, 1.0 - avg_blockage)
        else:
            drain_blockage = 1.0

        active_scenario_label = active_preset or effective_scenario

        # 3. Instantiate Engine & Run Forecast
        if is_kolkata:
            dem_path = DATA_DIR / "cities" / "kolkata" / "dem" / "elevation_grid.npy"
            if not dem_path.exists():
                raise FileNotFoundError(f"Kolkata DEM not found at {dem_path}")
            dem = np.load(dem_path).astype(np.float32)

            engine = FloodEngine(
                dem=dem,
                rainfall_provider=provider,
                drainage_graph=drainage_graph,
                cell_size_m=35.0,
                drain_blockage_factor=drain_blockage,
            )
            grids = engine.run_forecast(
                scenario=effective_scenario,
                horizon_minutes=req.horizon_minutes,
                dt=req.dt_seconds,
            )
            set_kolkata_engine(engine, grids, scenario=active_scenario_label, scenario_title=scenario_title)
            invalidate_drainage_cache(city)

            horizons = sorted(grids.keys())
            summaries = {
                h: compute_summary(grids[h], h, cell_size_m=35.0) for h in horizons
            }

            return FloodForecastOverview(
                scenario=active_scenario_label,
                scenario_title=scenario_title,
                horizons=horizons,
                summaries=summaries,
                total_rain_volume_m3=round(engine.total_rain_volume_m3, 1),
                total_infiltrated_volume_m3=round(engine.total_infiltrated_volume_m3, 1),
                total_absorbed_volume_m3=round(engine.total_absorbed_volume_m3, 1),
                total_overflow_volume_m3=round(engine.total_overflow_volume_m3, 1),
            )

        else:
            # Mumbai Engine
            engine = FloodEngine.from_default_data(
                rainfall_provider=provider,
                drainage_graph=drainage_graph,
                drain_blockage_factor=drain_blockage,
            )
            engine.run_forecast(
                scenario=effective_scenario,
                horizon_minutes=req.horizon_minutes,
                dt=req.dt_seconds,
            )

            set_engine(engine, scenario=active_scenario_label)
            invalidate_drainage_cache(city)

            horizons = sorted(engine.forecast_grids.keys())
            summaries = {
                h: compute_summary(engine.forecast_grids[h], h) for h in horizons
            }

            return FloodForecastOverview(
                scenario=active_scenario_label,
                scenario_title=scenario_title,
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
