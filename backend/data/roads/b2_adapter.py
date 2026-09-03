"""
C1.8 — Road Data Engineer: B2 Flood Simulation Engine Adapter
Urban Flood Nowcast Project

This module provides the integration adapter between B2's 2D hydraulic flood
depth prediction grids and the C1 road network.

Standard B2 Shared Contract:
- Grid dimensions: 200 rows x 200 columns (matching B2 DEM / EPSG:4326)
- Cell resolution: 10 m x 10 m
- Variable: water_depth / flood_depth (units: meters)
- Values: float32, non-negative (0.0 m = dry, >0.0 m = inundated)
- Time horizons: T+0, T+30, T+60, T+90, T+120, T+180 min (or ISO timestamps)
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
import numpy as np


GRID_ROWS = 200
GRID_COLS = 200
CELL_SIZE_M = 10.0


class B2PredictionFrame:
    """Represents a single timestamp prediction frame from B2."""

    def __init__(
        self,
        timestamp: str,
        depth_grid: np.ndarray,
        units: str = "meters",
        horizon_minutes: Optional[int] = None,
        source_description: str = "B2 FloodEngine"
    ):
        if depth_grid.shape != (GRID_ROWS, GRID_COLS):
            raise ValueError(f"Depth grid shape {depth_grid.shape} does not match expected ({GRID_ROWS}, {GRID_COLS})")

        self.timestamp: str = timestamp
        self.depth_grid: np.ndarray = depth_grid.astype(np.float32)
        self.units: str = units
        self.horizon_minutes: Optional[int] = horizon_minutes
        self.source_description: str = source_description

    def get_depth_at(self, row: int, col: int) -> float:
        """Returns flood depth at (row, col) in meters."""
        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
            return float(self.depth_grid[row, col])
        return 0.0


class B2Adapter:
    """
    Adapter to ingest and normalize B2 flood depth predictions into standard
    time-series frames for road risk evaluation.
    """

    @staticmethod
    def load_from_dict(
        forecast_dict: Dict[Union[int, str], np.ndarray],
        base_timestamp: str = "T+0min"
    ) -> List[B2PredictionFrame]:
        """
        Loads B2 forecast dictionary {horizon_min: 200x200 depth_array}
        matching FloodEngine.get_forecast_grids() contract.
        """
        frames: List[B2PredictionFrame] = []
        for horizon, grid in forecast_dict.items():
            if isinstance(horizon, int):
                ts_label = f"T+{horizon}min"
                h_min = horizon
            else:
                ts_label = str(horizon)
                h_min = None

            frame = B2PredictionFrame(
                timestamp=ts_label,
                depth_grid=grid,
                units="meters",
                horizon_minutes=h_min,
                source_description="B2 Forecast Dict"
            )
            frames.append(frame)
        return frames

    @staticmethod
    def load_from_directory(
        directory_path: Path
    ) -> List[B2PredictionFrame]:
        """
        Scans a directory for B2 .npy or .npz depth grid files.
        """
        frames: List[B2PredictionFrame] = []
        dir_p = Path(directory_path)
        if not dir_p.exists():
            return frames

        # Check for individual .npy files
        npy_files = sorted(list(dir_p.glob("*.npy")))
        for f in npy_files:
            try:
                arr = np.load(f)
                if arr.shape == (GRID_ROWS, GRID_COLS):
                    ts = f.stem.replace("depth_", "").replace("flood_", "")
                    frames.append(B2PredictionFrame(
                        timestamp=ts,
                        depth_grid=arr,
                        units="meters",
                        source_description=f"File: {f.name}"
                    ))
            except Exception as e:
                print(f"[WARN] Could not load B2 file {f.name}: {e}")

        return frames

    @staticmethod
    def generate_reference_scenario_frames(
        scenario_name: str = "heavy_rain",
        dem_grid: Optional[np.ndarray] = None
    ) -> List[B2PredictionFrame]:
        """
        Generates deterministic benchmark flood-depth forecast time-series
        (T+0, T+30, T+60, T+90, T+120, T+180) adhering strictly to B2 physics contracts
        when live external simulation runs are not being executed.
        """
        horizons = [0, 30, 60, 90, 120, 180]
        frames: List[B2PredictionFrame] = []

        # Use actual elevation topology to guide realistic hydraulic depression accumulation
        if dem_grid is None:
            dem_file = Path("backend/data/dem/elevation_grid.npy")
            if dem_file.exists():
                dem_grid = np.load(dem_file)
            else:
                dem_grid = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)

        # Normalize elevation depression factor (lower elevation -> higher potential accumulation)
        elev_min, elev_max = float(np.min(dem_grid)), float(np.max(dem_grid))
        depression_factor = 1.0 - np.clip((dem_grid - elev_min) / (elev_max - elev_min + 1e-5), 0.0, 1.0)
        # Lowland core mask
        lowland_accumulation = np.power(depression_factor, 2.5)

        for h in horizons:
            # Temporal storm evolution profile: peak around 60-90 min, then recession
            if h == 0:
                depth = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)
            elif h == 30:
                depth = (lowland_accumulation * 0.18).astype(np.float32)
            elif h == 60:
                depth = (lowland_accumulation * 0.45).astype(np.float32)
            elif h == 90:
                depth = (lowland_accumulation * 0.58).astype(np.float32)
            elif h == 120:
                depth = (lowland_accumulation * 0.38).astype(np.float32)
            elif h == 180:
                depth = (lowland_accumulation * 0.15).astype(np.float32)
            else:
                depth = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float32)

            frames.append(B2PredictionFrame(
                timestamp=f"T+{h}min",
                depth_grid=depth,
                units="meters",
                horizon_minutes=h,
                source_description=f"B2 Reference Scenario ({scenario_name})"
            ))

        return frames
