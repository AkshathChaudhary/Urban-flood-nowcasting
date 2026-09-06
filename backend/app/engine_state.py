"""
Shared state and helpers for FloodEngine API endpoints.
"""

from typing import Dict, Optional, Tuple
import numpy as np

from backend.app.config import (
    CELL_AREA_M2,
    CELL_SIZE_M,
    GRID_COLS,
    GRID_ROWS,
    ORIGIN_LAT,
    ORIGIN_LON,
)
from backend.app.engine.flood_engine import FloodEngine
from backend.app.models.flood import FloodSummary

_engine_instance: Optional[FloodEngine] = None
_current_scenario: str = "moderate"


def get_engine() -> FloodEngine:
    """Returns the singleton FloodEngine instance, initializing default if needed."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = FloodEngine.from_default_data()
        # Warm up default forecast
        _engine_instance.run_forecast(scenario=_current_scenario, horizon_minutes=180)
    return _engine_instance


def set_engine(engine: FloodEngine, scenario: str = "moderate") -> None:
    """Sets the active FloodEngine instance and scenario tag."""
    global _engine_instance, _current_scenario
    _engine_instance = engine
    _current_scenario = scenario


def get_current_scenario() -> str:
    global _current_scenario
    return _current_scenario


def compute_summary(depth_grid: np.ndarray, horizon: int) -> FloodSummary:
    """Calculates dashboard KPI metrics for a given water depth array."""
    max_d = float(np.max(depth_grid)) if depth_grid.size > 0 else 0.0
    mean_d = float(np.mean(depth_grid)) if depth_grid.size > 0 else 0.0
    flooded_15 = int(np.sum(depth_grid > 0.15))
    flooded_30 = int(np.sum(depth_grid > 0.30))
    vol_m3 = float(np.sum(depth_grid) * CELL_AREA_M2)

    return FloodSummary(
        horizon_minutes=horizon,
        max_depth_m=round(max_d, 3),
        mean_depth_m=round(mean_d, 4),
        flooded_cells_15cm=flooded_15,
        flooded_cells_30cm=flooded_30,
        surface_water_volume_m3=round(vol_m3, 1),
    )


def lat_lon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    """
    Converts latitude/longitude to grid (row, col) indices.
    Assumes 10m cells projected locally from ORIGIN_LAT, ORIGIN_LON (SW corner).
    1 degree latitude ~ 111,000 m.
    1 degree longitude ~ 111,000 * cos(lat) m ~ 105,000 m at Mumbai.
    """
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(np.radians(ORIGIN_LAT))

    d_north_m = (lat - ORIGIN_LAT) * meters_per_deg_lat
    d_east_m = (lon - ORIGIN_LON) * meters_per_deg_lon

    # Grid row 0 is top (North), row 199 is bottom (South)
    total_height_m = GRID_ROWS * CELL_SIZE_M
    row = int((total_height_m - d_north_m) / CELL_SIZE_M)
    col = int(d_east_m / CELL_SIZE_M)

    row = max(0, min(row, GRID_ROWS - 1))
    col = max(0, min(col, GRID_COLS - 1))
    return row, col
