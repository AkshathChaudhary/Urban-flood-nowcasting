"""
DEM and Surface Raster Loader
=============================

Loads digital elevation models (.npy or GeoTIFF) and associated surface rasters
(imperviousness, infiltration, water bodies, retention ponds).
"""

from pathlib import Path
from typing import Optional, Tuple, Union
import numpy as np

from backend.app.config import (
    DEM_ELEVATION_FILE,
    DEM_IMPERVIOUSNESS_FILE,
    DEM_INFILTRATION_FILE,
    DEM_RETENTION_POND_MASK_FILE,
    DEM_WATER_BODY_MASK_FILE,
    GRID_COLS,
    GRID_ROWS,
)


def load_dem(
    path: Optional[Union[str, Path]] = None,
    expected_shape: Tuple[int, int] = (GRID_ROWS, GRID_COLS),
) -> np.ndarray:
    """
    Loads DEM elevation grid as a 2D float32 numpy array.
    Validates array dimensions and handles .npy format.
    """
    dem_path = Path(path) if path else DEM_ELEVATION_FILE
    if not dem_path.exists():
        raise FileNotFoundError(f"DEM raster file not found at: {dem_path}")

    dem = np.load(dem_path).astype(np.float32)
    if dem.shape != expected_shape:
        raise ValueError(f"DEM shape mismatch: expected {expected_shape}, got {dem.shape}")
    return dem


def load_surface_rasters(
    expected_shape: Tuple[int, int] = (GRID_ROWS, GRID_COLS),
) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Loads complete set of micro-topography and land surface rasters:
    (elevation, imperviousness, infiltration, water_body_mask, retention_pond_mask).
    """
    dem = load_dem(expected_shape=expected_shape)
    imp = np.load(DEM_IMPERVIOUSNESS_FILE).astype(np.float32) if DEM_IMPERVIOUSNESS_FILE.exists() else None
    inf = np.load(DEM_INFILTRATION_FILE).astype(np.float32) if DEM_INFILTRATION_FILE.exists() else None
    wb = np.load(DEM_WATER_BODY_MASK_FILE).astype(bool) if DEM_WATER_BODY_MASK_FILE.exists() else None
    pond = np.load(DEM_RETENTION_POND_MASK_FILE).astype(bool) if DEM_RETENTION_POND_MASK_FILE.exists() else None

    return dem, imp, inf, wb, pond
