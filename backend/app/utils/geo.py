"""
Geographic and CRS Coordinate Transformation Utilities
=======================================================

Provides:
- Haversine great-circle distance
- WGS84 (EPSG:4326) <-> Grid (row, col) conversions
- Bounding box containment checking
"""

import math
from typing import Tuple
import numpy as np

from backend.app.config import (
    CELL_SIZE_M,
    GRID_COLS,
    GRID_ROWS,
    ORIGIN_LAT,
    ORIGIN_LON,
)


def haversine_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Computes great-circle distance between two (lon, lat) points in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def lat_lon_to_grid_cell(
    lat: float,
    lon: float,
    origin_lat: float = ORIGIN_LAT,
    origin_lon: float = ORIGIN_LON,
    cell_size_m: float = CELL_SIZE_M,
    rows: int = GRID_ROWS,
    cols: int = GRID_COLS,
) -> Tuple[int, int]:
    """Converts WGS84 (lat, lon) to discrete 2D raster grid cell index (row, col)."""
    deg_per_cell_lat = cell_size_m / 111320.0
    deg_per_cell_lon = cell_size_m / (111320.0 * np.cos(np.radians(origin_lat)))

    # Inverted row: row 0 is top (North), row rows-1 is bottom (South)
    row = int(rows - 1 - (lat - origin_lat) / deg_per_cell_lat)
    col = int((lon - origin_lon) / deg_per_cell_lon)

    row = max(0, min(rows - 1, row))
    col = max(0, min(cols - 1, col))
    return row, col


def grid_cell_to_lat_lon(
    row: int,
    col: int,
    origin_lat: float = ORIGIN_LAT,
    origin_lon: float = ORIGIN_LON,
    cell_size_m: float = CELL_SIZE_M,
    rows: int = GRID_ROWS,
) -> Tuple[float, float]:
    """Converts 2D raster grid cell index (row, col) to WGS84 (lat, lon) cell center."""
    deg_per_cell_lat = cell_size_m / 111320.0
    deg_per_cell_lon = cell_size_m / (111320.0 * np.cos(np.radians(origin_lat)))

    lat = origin_lat + (rows - 1 - row + 0.5) * deg_per_cell_lat
    lon = origin_lon + (col + 0.5) * deg_per_cell_lon
    return float(lat), float(lon)


def is_within_bounds(
    lat: float,
    lon: float,
    min_lat: float = 19.0600,
    max_lat: float = 19.0782,
    min_lon: float = 72.8498,
    max_lon: float = 72.8688,
) -> bool:
    """Checks if a point (lat, lon) lies strictly within the study area bounding box."""
    return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
