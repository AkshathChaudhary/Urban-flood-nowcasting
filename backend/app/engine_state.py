"""
Shared state and helpers for FloodEngine API endpoints.
"""

import threading
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

_engine_lock = threading.Lock()
_engine_instance: Optional[FloodEngine] = None
_current_scenario: str = "moderate"


def get_engine() -> FloodEngine:
    """Returns the singleton FloodEngine instance, initializing default if needed."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            drainage_graph = None
            try:
                from backend.app.api.drainage import get_drainage_graph
                drainage_graph = get_drainage_graph()
            except Exception as e:
                print(f"[ENGINE_STATE] Notice: DrainageGraph loading deferred or optional ({e})")

            _engine_instance = FloodEngine.from_default_data(drainage_graph=drainage_graph)
            # Warm up default forecast
            _engine_instance.run_forecast(scenario=_current_scenario, horizon_minutes=180)
        return _engine_instance


def set_engine(engine: FloodEngine, scenario: str = "moderate") -> None:
    """Sets the active FloodEngine instance and scenario tag."""
    global _engine_instance, _current_scenario
    with _engine_lock:
        _engine_instance = engine
        _current_scenario = scenario


def get_current_scenario() -> str:
    global _current_scenario
    with _engine_lock:
        return _current_scenario


def compute_summary(depth_grid: np.ndarray, horizon: int, cell_size_m: Optional[float] = None) -> FloodSummary:
    """Calculates dashboard KPI metrics for a given water depth array."""
    if cell_size_m is None:
        # Deduce from grid shape: (300, 160) is Kolkata (35.0m resolution); (200, 200) is Mumbai (10.0m)
        if depth_grid.shape == (300, 160):
            cell_size_m = 35.0
        else:
            cell_size_m = float(CELL_SIZE_M)

    cell_area = cell_size_m * cell_size_m
    max_d = float(np.max(depth_grid)) if depth_grid.size > 0 else 0.0
    mean_d = float(np.mean(depth_grid)) if depth_grid.size > 0 else 0.0
    flooded_15 = int(np.sum(depth_grid > 0.15))
    flooded_30 = int(np.sum(depth_grid > 0.30))
    vol_m3 = float(np.sum(depth_grid) * cell_area)

    return FloodSummary(
        horizon_minutes=horizon,
        max_depth_m=round(max_d, 3),
        mean_depth_m=round(mean_d, 3),
        flooded_cells_15cm=flooded_15,
        flooded_cells_30cm=flooded_30,
        surface_water_volume_m3=round(vol_m3, 1),
    )


def lat_lon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    """
    Maps (lat, lon) coordinates to 200x200 grid (row, col).
    10m cell corresponds to approximately 0.00009 degrees latitude.
    """
    deg_per_cell_lat = 10.0 / 111320.0
    deg_per_cell_lon = 10.0 / (111320.0 * np.cos(np.radians(ORIGIN_LAT)))

    # Inverted row: row 0 is top (North), row 199 is bottom (South)
    row = int(GRID_ROWS - 1 - (lat - ORIGIN_LAT) / deg_per_cell_lat)
    col = int((lon - ORIGIN_LON) / deg_per_cell_lon)

    row = max(0, min(GRID_ROWS - 1, row))
    col = max(0, min(GRID_COLS - 1, col))
    return row, col


def grid_to_lat_lon(row: int, col: int) -> Tuple[float, float]:
    """
    Maps 200x200 grid (row, col) back to (lat, lon).
    """
    deg_per_cell_lat = 10.0 / 111320.0
    deg_per_cell_lon = 10.0 / (111320.0 * np.cos(np.radians(ORIGIN_LAT)))

    lat = ORIGIN_LAT + (GRID_ROWS - 1 - row + 0.5) * deg_per_cell_lat
    lon = ORIGIN_LON + (col + 0.5) * deg_per_cell_lon
    return float(lat), float(lon)
