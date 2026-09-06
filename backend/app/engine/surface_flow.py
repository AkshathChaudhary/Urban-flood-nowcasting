"""
D8 Surface Flow Routing and Hydrological Analysis.

Implements:
- Vectorized D8 steepest descent computation (B2.4)
- Sink and local depression identification (B2.6)
- Stable 2D overland flow routing with strict mass conservation (B2.8, B2.14)
"""

import math
from typing import Dict, List, Optional, Tuple
import numpy as np


# 8 neighbor directions: (dr, dc)
# Order: East, Southeast, South, Southwest, West, Northwest, North, Northeast
D8_OFFSETS: List[Tuple[int, int]] = [
    (0, 1),    # 0: E
    (1, 1),    # 1: SE
    (1, 0),    # 2: S
    (1, -1),   # 3: SW
    (0, -1),   # 4: W
    (-1, -1),  # 5: NW
    (-1, 0),   # 6: N
    (-1, 1),   # 7: NE
]

D8_NAMES = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]


def compute_d8_flow_directions(
    dem: np.ndarray,
    cell_size_m: float = 10.0
) -> np.ndarray:
    """
    Computes D8 flow direction code for each cell in the DEM.

    Returns:
        np.ndarray of shape (rows, cols), dtype int32:
        - 0 to 7: Index of neighbor receiving flow (see D8_OFFSETS)
        - -1: Sink / depression / flat cell with no downhill neighbor
    """
    rows, cols = dem.shape
    slopes = np.full((8, rows, cols), -np.inf, dtype=np.float32)

    diag_dist = math.sqrt(2.0) * cell_size_m
    distances = [
        cell_size_m, diag_dist, cell_size_m, diag_dist,
        cell_size_m, diag_dist, cell_size_m, diag_dist
    ]

    for k, ((dr, dc), dist) in enumerate(zip(D8_OFFSETS, distances)):
        # Overlapping slices between center and neighbor
        r_src_start = max(0, -dr)
        r_src_end = rows - max(0, dr)
        c_src_start = max(0, -dc)
        c_src_end = cols - max(0, dc)

        r_nbr_start = max(0, dr)
        r_nbr_end = rows - max(0, -dr)
        c_nbr_start = max(0, dc)
        c_nbr_end = cols - max(0, -dc)

        center_elev = dem[r_src_start:r_src_end, c_src_start:c_src_end]
        nbr_elev = dem[r_nbr_start:r_nbr_end, c_nbr_start:c_nbr_end]

        slopes[k, r_src_start:r_src_end, c_src_start:c_src_end] = (
            center_elev - nbr_elev
        ) / dist

    max_slope_idx = np.argmax(slopes, axis=0).astype(np.int32)
    max_slope_val = np.take_along_axis(
        slopes, np.expand_dims(max_slope_idx, axis=0), axis=0
    ).squeeze(axis=0)

    # If maximum slope <= 0, no downhill neighbor exists (sink or flat)
    flow_dirs = np.where(max_slope_val > 0.0, max_slope_idx, -1).astype(np.int32)
    return flow_dirs


def identify_sinks(
    dem: np.ndarray,
    flow_directions: Optional[np.ndarray] = None,
    cell_size_m: float = 10.0
) -> np.ndarray:
    """
    Identifies depression / sink cells (local minima where water ponds).

    Returns:
        np.ndarray of shape (rows, cols), dtype bool: True if cell is a sink.
    """
    if flow_directions is None:
        flow_directions = compute_d8_flow_directions(dem, cell_size_m)
    return flow_directions == -1


def route_surface_water(
    elevation: np.ndarray,
    water_depth: np.ndarray,
    dt: float,
    cell_size_m: float = 10.0,
    sub_passes: int = 4,
    manning_n: float = 0.035,
    boundary_condition: str = "closed"
) -> Tuple[np.ndarray, float]:
    """
    Vectorized dynamic 2D surface water routing.

    Routes water downhill driven by total water head:
        H = elevation + water_depth

    Water depth is updated in multiple sub-passes per timestep to maintain
    strict numerical stability without oscillation.

    Args:
        elevation: 2D array of ground elevations (meters)
        water_depth: 2D array of current surface water depths (meters)
        dt: Time step in seconds
        cell_size_m: Grid cell resolution (default 10.0 m)
        sub_passes: Number of sub-iterations per timestep (default 4)
        manning_n: Manning roughness coefficient for urban terrain
        boundary_condition: "closed" (retains water within domain) or
                            "outflow" (water flows out of boundary)

    Returns:
        Tuple of:
            new_depth (np.ndarray): updated water depth array (meters)
            boundary_outflow_m3 (float): total volume exited off boundaries (m^3)
    """
    rows, cols = elevation.shape
    depth = np.maximum(water_depth, 0.0).copy()
    dt_sub = dt / float(sub_passes)
    cell_area = cell_size_m * cell_size_m

    diag_dist = math.sqrt(2.0) * cell_size_m
    distances = [
        cell_size_m, diag_dist, cell_size_m, diag_dist,
        cell_size_m, diag_dist, cell_size_m, diag_dist
    ]

    total_boundary_outflow_m3 = 0.0

    for _ in range(sub_passes):
        # Total hydraulic head
        head = elevation + depth

        # Slopes to 8 neighbors
        slopes = np.full((8, rows, cols), -np.inf, dtype=np.float32)

        for k, ((dr, dc), dist) in enumerate(zip(D8_OFFSETS, distances)):
            r_src_start = max(0, -dr)
            r_src_end = rows - max(0, dr)
            c_src_start = max(0, -dc)
            c_src_end = cols - max(0, dc)

            r_nbr_start = max(0, dr)
            r_nbr_end = rows - max(0, -dr)
            c_nbr_start = max(0, dc)
            c_nbr_end = cols - max(0, -dc)

            center_head = head[r_src_start:r_src_end, c_src_start:c_src_end]
            nbr_head = head[r_nbr_start:r_nbr_end, c_nbr_start:c_nbr_end]

            # Positive slope means center head is higher than neighbor head
            slopes[k, r_src_start:r_src_end, c_src_start:c_src_end] = (
                center_head - nbr_head
            ) / dist

        # Find direction of steepest hydraulic descent
        best_dir = np.argmax(slopes, axis=0)
        best_slope = np.take_along_axis(
            slopes, np.expand_dims(best_dir, axis=0), axis=0
        ).squeeze(axis=0)

        # Active flow cells: must have positive slope and non-negligible water (>0.1 mm)
        active_mask = (best_slope > 1e-4) & (depth > 1e-4)

        if not np.any(active_mask):
            break

        # Calculate outflow depth for each active cell
        outflow_grid = np.zeros((8, rows, cols), dtype=np.float32)

        # Simplified kinematic wave velocity approximation:
        # v = (1 / n) * R^(2/3) * S^(1/2), where hydraulic radius R ~ depth
        eff_depth = np.maximum(depth, 1e-4)
        v = (1.0 / manning_n) * (eff_depth ** (2.0 / 3.0)) * np.sqrt(np.maximum(best_slope, 0.0))
        # Limit velocity to physically realistic urban overland max (3.0 m/s)
        v = np.clip(v, 0.0, 3.0)

        # Courant-Friedrichs-Lewy (CFL) stable fraction
        # Flux cannot exceed available depth or half of head difference (to avoid gradient reversal)
        max_dist_step = v * dt_sub
        flux_fraction = np.clip(max_dist_step / cell_size_m, 0.0, 0.5)

        # Maximum depth that can be transferred without overshooting
        # Half of (head difference) is the hydrostatic leveling limit
        head_diff = best_slope * cell_size_m
        flux_depth = np.minimum(depth * flux_fraction, head_diff * 0.5)
        flux_depth = np.where(active_mask, flux_depth, 0.0).astype(np.float32)

        # Multi-Directional Distribution (MDD) on gentle urban terrain (< 1% slope):
        # Eliminates artificial D8 single-cell ray striping on flat urban floodplains.
        pos_slopes = np.maximum(slopes, 0.0)
        sum_pos_slopes = np.sum(pos_slopes, axis=0)  # shape (rows, cols)

        # Cells with gentle slope where multi-directional spreading applies
        gentle_mask = active_mask & (best_slope < 0.01) & (sum_pos_slopes > 1e-6)
        steep_mask = active_mask & ~gentle_mask

        for k in range(8):
            # Steep cells: 100% of flux routed to steepest descent direction (D8)
            mask_steep_k = steep_mask & (best_dir == k) & (flux_depth > 0.0)
            outflow_grid[k, mask_steep_k] = flux_depth[mask_steep_k]

            # Gentle cells: flux proportionally distributed across all downhill neighbors
            if np.any(gentle_mask):
                k_fraction = pos_slopes[k, gentle_mask] / sum_pos_slopes[gentle_mask]
                outflow_grid[k, gentle_mask] = (flux_depth[gentle_mask] * k_fraction).astype(np.float32)

        # Deduct total outflow from source cells
        total_outflow = np.sum(outflow_grid, axis=0)
        depth -= total_outflow

        # Accumulate inflow into target cells
        inflow = np.zeros((rows, cols), dtype=np.float32)

        for k, (dr, dc) in enumerate(D8_OFFSETS):
            flow_k = outflow_grid[k]

            r_src_start = max(0, -dr)
            r_src_end = rows - max(0, dr)
            c_src_start = max(0, -dc)
            c_src_end = cols - max(0, dc)

            r_nbr_start = max(0, dr)
            r_nbr_end = rows - max(0, -dr)
            c_nbr_start = max(0, dc)
            c_nbr_end = cols - max(0, -dc)

            # Target cells within domain receive the water
            inflow[r_nbr_start:r_nbr_end, c_nbr_start:c_nbr_end] += flow_k[
                r_src_start:r_src_end, c_src_start:c_src_end
            ]

            # Water directed off-boundary
            if boundary_condition == "outflow":
                # Compute total leaving grid boundary
                all_leaving = np.sum(flow_k) - np.sum(
                    flow_k[r_src_start:r_src_end, c_src_start:c_src_end]
                )
                if all_leaving > 0:
                    total_boundary_outflow_m3 += float(all_leaving) * cell_area
            else:
                # Closed boundary: bounce boundary outflow back into source cells
                # Mask out-of-bounds boundary cells from leaving
                leaving_water = flow_k.copy()
                leaving_water[r_src_start:r_src_end, c_src_start:c_src_end] = 0.0
                depth += leaving_water

        depth += inflow
        depth = np.maximum(depth, 0.0)

    return depth, total_boundary_outflow_m3
