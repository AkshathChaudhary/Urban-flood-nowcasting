"""
C1.4 — Road Data Engineer: Road-to-DEM Grid Mapping Utilities
Urban Flood Nowcast Project

This module provides reusable coordinate conversion and geometry rasterization
utilities to map geographic road vector features (EPSG:4326) onto the project's
standard 200 x 200 DEM grid (B2 convention).

Coordinate & Grid Specification:
- Study Area: Mumbai (~2 km x 2 km)
- Coordinate Reference System: WGS84 / EPSG:4326
- Grid Dimensions: 200 rows x 200 columns (total 40,000 cells)
- Nominal Cell Size: 10 m x 10 m
- SW Origin (Bounding Box Minimum):
    Latitude  = 19.0600° N
    Longitude = 72.8500° E
- NE Bound (Bounding Box Maximum):
    Latitude  = 19.0782° N (delta = 0.0182° ≈ 2014.7 m)
    Longitude = 72.8688° E (delta = 0.0188° ≈ 1977.8 m)
- Geographic Cell Resolutions:
    d_lat = 0.0182° / 200 = 0.0000910° ≈ 10.07 m
    d_lon = 0.0188° / 200 = 0.0000940° ≈ 9.89 m
"""

import math
from typing import List, Tuple, Union, Optional
from shapely.geometry import LineString, MultiLineString, Point


# -------------------------------------------------------------------------
# CONSTANTS (B2 DEM / GRID CONVENTION)
# -------------------------------------------------------------------------

ORIGIN_LAT: float = 19.0600
ORIGIN_LON: float = 72.8500
MAX_LAT: float = 19.0782
MAX_LON: float = 72.8688

GRID_ROWS: int = 200
GRID_COLS: int = 200
CELL_SIZE_M: float = 10.0

# Geographic increments per cell
DLAT: float = (MAX_LAT - ORIGIN_LAT) / GRID_ROWS  # ~0.000091 deg
DLON: float = (MAX_LON - ORIGIN_LON) / GRID_COLS  # ~0.000094 deg

# Mean Earth Radius in meters
EARTH_RADIUS_M: float = 6371000.0


# -------------------------------------------------------------------------
# DISTANCE & COORDINATE UTILITIES
# -------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two geographic points in meters
    using the Haversine formula.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c


def is_in_bounds(lat: float, lon: float) -> bool:
    """
    Checks if a geographic coordinate (lat, lon) falls strictly inside
    the DEM bounding box [ORIGIN_LAT, MAX_LAT] and [ORIGIN_LON, MAX_LON].
    """
    return (ORIGIN_LAT <= lat <= MAX_LAT) and (ORIGIN_LON <= lon <= MAX_LON)


def latlon_to_grid(lat: float, lon: float, clamp: bool = False) -> Tuple[int, int]:
    """
    Converts geographic coordinates (WGS84 EPSG:4326) into DEM grid indices (row, col).

    Parameters:
    -----------
    lat : float
        Latitude in decimal degrees.
    lon : float
        Longitude in decimal degrees.
    clamp : bool, default=False
        If True, clamps row and col to [0, GRID_ROWS - 1] and [0, GRID_COLS - 1].
        If False, calculates exact integer cell index (may be < 0 or >= 200 if out of bounds).

    Returns:
    --------
    Tuple[int, int]
        (row, col) corresponding to the DEM 200x200 grid cell.
    """
    norm_y = (lat - ORIGIN_LAT) / (MAX_LAT - ORIGIN_LAT)
    norm_x = (lon - ORIGIN_LON) / (MAX_LON - ORIGIN_LON)

    row = int(math.floor(norm_y * GRID_ROWS))
    col = int(math.floor(norm_x * GRID_COLS))

    if clamp:
        row = max(0, min(GRID_ROWS - 1, row))
        col = max(0, min(GRID_COLS - 1, col))

    return row, col


def grid_to_latlon(row: int, col: int) -> Tuple[float, float]:
    """
    Converts a DEM grid cell index (row, col) to the geographic center
    coordinates (lat, lon) of that cell.

    Parameters:
    -----------
    row : int
        Grid row index (0 to GRID_ROWS - 1).
    col : int
        Grid column index (0 to GRID_COLS - 1).

    Returns:
    --------
    Tuple[float, float]
        (latitude, longitude) of the cell center.
    """
    lat = ORIGIN_LAT + (row + 0.5) * DLAT
    lon = ORIGIN_LON + (col + 0.5) * DLON
    return lat, lon


# -------------------------------------------------------------------------
# GEOMETRY SAMPLING & RASTERIZATION
# -------------------------------------------------------------------------

def sample_linestring_to_cells(
    geom: Union[LineString, MultiLineString],
    sample_step_m: float = 5.0,
    keep_only_in_bounds: bool = True
) -> List[Tuple[int, int]]:
    """
    Discretizes a Shapely LineString / MultiLineString geometry by sampling points
    along its length at high spatial resolution (default 5.0 meters) and mapping
    each sample to its corresponding (row, col) grid cell.

    Consecutive duplicate cells are removed while preserving the traversal order
    and full connectivity of the road segment across the 2D grid.

    Parameters:
    -----------
    geom : LineString or MultiLineString
        Shapely geometric object in EPSG:4326 coordinates (lon, lat).
    sample_step_m : float, default=5.0
        Sampling step interval in meters. Using 5m guarantees multiple samples
        per 10m cell, preventing any diagonal cell skipping.
    keep_only_in_bounds : bool, default=True
        Whether to filter out cells that fall outside the 200x200 DEM grid.

    Returns:
    --------
    List[Tuple[int, int]]
        Ordered list of unique grid cells (row, col) traversed by the road.
    """
    if geom is None or geom.is_empty:
        return []

    lines: List[LineString] = []
    if isinstance(geom, LineString):
        lines = [geom]
    elif isinstance(geom, MultiLineString):
        lines = list(geom.geoms)
    else:
        return []

    sampled_cells: List[Tuple[int, int]] = []
    seen_cells_set = set()

    for line in lines:
        coords = list(line.coords)
        if len(coords) < 2:
            continue

        # Iterate through line segments
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i][0], coords[i][1]
            lon2, lat2 = coords[i+1][0], coords[i+1][1]

            seg_len_m = haversine_distance(lat1, lon1, lat2, lon2)
            num_steps = max(1, int(math.ceil(seg_len_m / sample_step_m)))

            for step in range(num_steps + 1):
                fraction = step / float(num_steps)
                lat = lat1 + fraction * (lat2 - lat1)
                lon = lon1 + fraction * (lon2 - lon1)

                row, col = latlon_to_grid(lat, lon, clamp=False)

                if keep_only_in_bounds:
                    if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
                        cell = (row, col)
                        if cell not in seen_cells_set:
                            seen_cells_set.add(cell)
                            sampled_cells.append(cell)
                else:
                    cell = (row, col)
                    if cell not in seen_cells_set:
                        seen_cells_set.add(cell)
                        sampled_cells.append(cell)

    return sampled_cells
