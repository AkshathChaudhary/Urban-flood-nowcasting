"""
FloodEngine — Core Hydrological & Hydrodynamic Simulation Orchestrator.

Implements:
- Initialization & terrain coupling (B2.5, B2.6)
- Infiltration-corrected rainfall deposition (B2.7)
- 2D surface routing dispatch (B2.8, B2.14)
- Drainage absorption and overflow coupling (B2.9, B2.10)
- Timestep simulation loop (B2.11)
- Multi-horizon forecast execution (B2.12)
- Interface contracts for Pair A (Drainage) and Pair C (Routing)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from backend.app.config import (
    CELL_AREA_M2,
    CELL_SIZE_M,
    DEM_ELEVATION_FILE,
    DEM_IMPERVIOUSNESS_FILE,
    DEM_INFILTRATION_FILE,
    DEM_WATER_BODY_MASK_FILE,
    DT_SECONDS,
    FLOW_SUB_PASSES,
    FORECAST_HORIZONS,
    GRID_COLS,
    GRID_ROWS,
)
from backend.app.engine.surface_flow import (
    compute_d8_flow_directions,
    identify_sinks,
    route_surface_water,
)
from backend.data.rainfall.provider import DemoRainfallProvider, RainfallProvider


class FloodEngine:
    """
    Central computational engine for urban flood nowcasting.

    Maintains 2D elevation, imperviousness, infiltration, and dynamic water depth.
    Simulates overland runoff propagation, interaction with subterranean drainage,
    and produces nowcast depth grids across forecast horizons.
    """

    def __init__(
        self,
        dem: np.ndarray,
        imperviousness: Optional[np.ndarray] = None,
        infiltration: Optional[np.ndarray] = None,
        water_body_mask: Optional[np.ndarray] = None,
        rainfall_provider: Optional[RainfallProvider] = None,
        drainage_graph: Optional[Any] = None,
        cell_size_m: float = CELL_SIZE_M,
        boundary_condition: str = "closed",
        upstream_river_inflow_m3_s: float = 0.0,
        tidal_lock: bool = False,
        initial_river_storage_m3: float = 0.0,
    ):
        """
        Initialize the FloodEngine.

        Args:
            dem: 2D numpy array of elevations in meters (shape: rows, cols)
            imperviousness: 2D numpy array (0.0 to 1.0)
            infiltration: 2D numpy array of soil infiltration rates in mm/hr
            water_body_mask: Boolean 2D array — True for cells that are pre-existing
                             rivers/channels/lakes. These cells do not accumulate
                             surface flood water — runoff reaching them drains away.
            rainfall_provider: RainfallProvider instance
            drainage_graph: Optional DrainageGraph instance (Pair A interface)
            cell_size_m: Grid cell spatial resolution (default 10.0 m)
            boundary_condition: "closed" or "outflow"
        """
        self.dem = dem.astype(np.float32)
        self.rows, self.cols = self.dem.shape
        self.cell_size = float(cell_size_m)
        self.cell_area = self.cell_size * self.cell_size
        self.boundary_condition = boundary_condition

        # Water body mask: rivers, channels, tidal zones that must not accumulate flood depth.
        # These cells act as natural drains — any water reaching them is removed from the
        # surface water budget (it enters the waterway and flows downstream out of the domain).
        if water_body_mask is not None:
            self.water_body_mask = water_body_mask.astype(bool)
        else:
            # Fallback: infer from negative-elevation DEM cells
            self.water_body_mask = dem < 0.0

        # Default or assigned imperviousness (0.0: permeable soil -> 1.0: concrete)
        if imperviousness is not None:
            self.imperviousness = np.clip(imperviousness.astype(np.float32), 0.0, 1.0)
        else:
            self.imperviousness = np.full((self.rows, self.cols), 0.75, dtype=np.float32)
        # Enforce: water body cells have zero imperviousness (open water surface)
        self.imperviousness[self.water_body_mask] = 0.0

        # Infiltration capacity grid (mm/hr)
        if infiltration is not None:
            self.infiltration = np.maximum(infiltration.astype(np.float32), 0.0)
        else:
            base_rate = 5.0  # mm/hr
            self.infiltration = base_rate * (1.0 - self.imperviousness)
        # Water body cells drain instantly: effectively infinite infiltration
        self.infiltration[self.water_body_mask] = 9999.0

        # Providers and graph references
        self.rainfall_provider = rainfall_provider or DemoRainfallProvider(
            grid_shape=(self.rows, self.cols), cell_size_m=self.cell_size
        )
        self.drainage_graph = drainage_graph

        # Simulation state arrays
        self.water_depth = np.zeros((self.rows, self.cols), dtype=np.float32)
        self.cumulative_rain_m = np.zeros((self.rows, self.cols), dtype=np.float32)
        self.cumulative_infiltrated_m = np.zeros((self.rows, self.cols), dtype=np.float32)

        # River boundary conditions & states
        self.upstream_river_inflow_m3_s = float(upstream_river_inflow_m3_s)
        self.tidal_lock = bool(tidal_lock)
        self.initial_river_storage_m3 = float(initial_river_storage_m3)
        self.total_upstream_inflow_m3 = 0.0

        # Mass balance counters (m^3)
        self.total_rain_volume_m3 = 0.0
        self.total_infiltrated_volume_m3 = 0.0
        self.total_absorbed_volume_m3 = 0.0
        self.total_overflow_volume_m3 = 0.0
        self.total_boundary_outflow_m3 = 0.0
        self.total_river_drain_volume_m3 = 0.0   # water that exited downstream
        self.total_river_overflow_m3 = 0.0       # water spilled from river onto land

        # Output snapshots {minutes: depth_grid}
        self.forecast_grids: Dict[int, np.ndarray] = {}

        # Precompute static terrain properties
        self.initialize()

    def initialize(self) -> None:
        """
        Precompute static hydrological properties from DEM and zero dynamic states.
        """
        self.flow_directions = compute_d8_flow_directions(self.dem, self.cell_size)
        self.sinks_mask = identify_sinks(self.dem, self.flow_directions, self.cell_size)

        # Precompute river bank cells: land cells directly adjacent (4-connected) to
        # any water body cell. These receive overflow when the river exceeds bankfull.
        self.river_bank_mask = self._compute_river_bank_mask()

        # Bankfull capacity of all river/channel cells (m³).
        # Based on assumed average bankfull depth for the Mithi River / urban channels.
        # Mithi River main channel: ~2.5m bankfull; smaller channels: ~1.0m.
        # Conservative combined estimate: 1.8m average across all 1569 water body cells.
        BANKFULL_DEPTH_M = 1.8
        n_water_cells = int(self.water_body_mask.sum())
        self.river_bankfull_capacity_m3 = max(
            n_water_cells * self.cell_area * BANKFULL_DEPTH_M, 1.0
        )

        self.reset_state()

    def reset_state(self) -> None:
        """Resets all water depths and mass accumulation counters."""
        self.water_depth.fill(0.0)
        self.cumulative_rain_m.fill(0.0)
        self.cumulative_infiltrated_m.fill(0.0)
        self.total_rain_volume_m3 = 0.0
        self.total_infiltrated_volume_m3 = 0.0
        self.total_absorbed_volume_m3 = 0.0
        self.total_overflow_volume_m3 = 0.0
        self.total_boundary_outflow_m3 = 0.0
        self.total_river_drain_volume_m3 = 0.0
        self.total_river_overflow_m3 = 0.0
        self.total_upstream_inflow_m3 = 0.0
        self.river_storage_m3 = min(self.initial_river_storage_m3, self.river_bankfull_capacity_m3)
        self.forecast_grids.clear()

    # =========================================================================
    # Simulation Step Sub-methods
    # =========================================================================

    def apply_rainfall(self, dt: float, rain_rate_grid: np.ndarray) -> np.ndarray:
        """
        Apply rainfall deposition and subtract soil infiltration.

        Effective runoff addition:
            Δd = max(rain_rate * dt/3600 - infiltration * dt/3600, 0) / 1000  (m)

        Args:
            dt: Timestep in seconds
            rain_rate_grid: Rainfall intensity grid in mm/hr

        Returns:
            np.ndarray: Net water depth added across grid (meters)
        """
        dt_hr = dt / 3600.0

        # Total gross rainfall in meters
        gross_rain_m = (rain_rate_grid.astype(np.float32) * dt_hr) / 1000.0

        # Maximum soil infiltration capacity for this timestep in meters
        max_infil_m = (self.infiltration * dt_hr) / 1000.0

        # Actual infiltrated water (cannot exceed gross rain)
        actual_infil_m = np.minimum(gross_rain_m, max_infil_m)

        # Net effective precipitation reaching surface
        net_addition_m = np.maximum(gross_rain_m - actual_infil_m, 0.0)

        # Water body cells (rivers/channels) do not accumulate surface flood depth.
        # Rain falling directly on them enters the waterway immediately.
        net_addition_m[self.water_body_mask] = 0.0

        # Update grid state
        self.water_depth += net_addition_m
        self.cumulative_rain_m += gross_rain_m
        self.cumulative_infiltrated_m += actual_infil_m

        # Update mass balance totals (count rainfall over land only for surface budget)
        land_mask = ~self.water_body_mask
        self.total_rain_volume_m3 += float(np.sum(gross_rain_m[land_mask]) * self.cell_area)
        self.total_infiltrated_volume_m3 += float(np.sum(actual_infil_m[land_mask]) * self.cell_area)

        return net_addition_m

    def calculate_surface_flow(
        self, dt: float, sub_passes: int = FLOW_SUB_PASSES
    ) -> float:
        """
        Execute 2D overland water routing based on hydraulic head gradients.

        Args:
            dt: Timestep in seconds
            sub_passes: Number of sub-iterations for stability

        Returns:
            float: Volume of water exited past boundary in m^3
        """
        self.water_depth, boundary_outflow = route_surface_water(
            elevation=self.dem,
            water_depth=self.water_depth,
            dt=dt,
            cell_size_m=self.cell_size,
            sub_passes=sub_passes,
            boundary_condition=self.boundary_condition,
        )
        self.total_boundary_outflow_m3 += boundary_outflow
        return boundary_outflow

    def calculate_drainage_absorption(self, dt: float) -> float:
        """
        Interface: Pair B calls Pair A's absorb_surface_water method.
        Deducts absorbed water from the surface water depth.

        Returns:
            float: Total volume absorbed by drainage network in m^3
        """
        if self.drainage_graph is None or not hasattr(
            self.drainage_graph, "absorb_surface_water"
        ):
            return 0.0

        absorbed_depth_grid = self.drainage_graph.absorb_surface_water(
            self.water_depth, dt
        )
        # Limit absorption to what water actually exists on the surface
        actual_absorbed = np.minimum(absorbed_depth_grid, self.water_depth)
        self.water_depth -= actual_absorbed

        absorbed_vol_m3 = float(np.sum(actual_absorbed) * self.cell_area)
        self.total_absorbed_volume_m3 += absorbed_vol_m3
        return absorbed_vol_m3

    def calculate_overflow(self) -> float:
        """
        Interface: Pair B queries Pair A's compute_overflow method.
        Puts overflowing sewer water back onto surface cells.

        Returns:
            float: Total overflow volume added back to surface in m^3
        """
        if self.drainage_graph is None or not hasattr(
            self.drainage_graph, "compute_overflow"
        ):
            return 0.0

        overflow_records = self.drainage_graph.compute_overflow()
        total_overflow_vol = 0.0

        if isinstance(overflow_records, dict):
            for node_id, vol_m3 in overflow_records.items():
                if vol_m3 <= 0.0:
                    continue
                if hasattr(self.drainage_graph, "get_node_cell"):
                    r, c = self.drainage_graph.get_node_cell(node_id)
                    self.add_overflow_at_cell(r, c, vol_m3)
                    total_overflow_vol += vol_m3

        self.total_overflow_volume_m3 += total_overflow_vol
        return total_overflow_vol

    def _compute_river_bank_mask(self) -> np.ndarray:
        """
        Identifies land cells immediately adjacent (4-connected) to water body cells.
        These are the river bank cells that receive overflow when the river floods.
        """
        wb = self.water_body_mask
        bank = np.zeros(wb.shape, dtype=bool)
        bank[:-1, :] |= wb[1:, :]   # cell above a water body
        bank[1:, :]  |= wb[:-1, :]  # cell below a water body
        bank[:, :-1] |= wb[:, 1:]   # cell left of a water body
        bank[:, 1:]  |= wb[:, :-1]  # cell right of a water body
        return bank & ~wb  # exclude water body cells themselves

    def _spill_river_overflow(self, overflow_vol_m3: float) -> None:
        """
        Distributes river overflow volume evenly across all river bank land cells.
        In reality overflow is non-uniform (elevation-dependent), but this conservative
        approximation correctly puts water on the right spatial region.
        """
        n_bank = int(self.river_bank_mask.sum())
        if n_bank == 0 or overflow_vol_m3 <= 0.0:
            return
        depth_per_cell_m = overflow_vol_m3 / (n_bank * self.cell_area)
        self.water_depth[self.river_bank_mask] += depth_per_cell_m

    def drain_water_bodies(self, dt: float = DT_SECONDS) -> float:
        """
        Implements river/channel water level dynamics each timestep:

        Step 0 — Upstream inflow: external catchment water enters river channel.
        Step A — Collect runoff: any surface water that has routed onto water body cells
                 is absorbed into the river channel (it enters the waterway).
        Step B — Downstream outflow: a fraction of current river storage exits the domain
                 each timestep (simplified kinematic routing). Under tidal lock, outflow is blocked.
        Step C — Bankfull overflow: if river storage exceeds channel capacity, the excess
                 is spilled back onto adjacent land cells as riverine flood water.
                 This is the primary flood mechanism for low-lying BKC / Mithi basin.

        Returns:
            float: Volume spilled onto land from river overflow this timestep (m³).
        """
        # 0. Upstream river inflow entering from upstream catchment (e.g. Powai / Vihar lakes)
        if self.upstream_river_inflow_m3_s > 0.0:
            up_vol = self.upstream_river_inflow_m3_s * dt
            self.river_storage_m3 += up_vol
            self.total_upstream_inflow_m3 += up_vol

        # A. Collect surface runoff that reached river cells
        inflow_vol = float(np.sum(self.water_depth[self.water_body_mask]) * self.cell_area)
        self.water_depth[self.water_body_mask] = 0.0
        self.river_storage_m3 += inflow_vol

        # B. Natural downstream outflow via simplified kinematic routing.
        # Under tidal lock (high spring tide in Arabian Sea), outflow is blocked/restricted.
        outflow_rate = 0.0 if self.tidal_lock else 0.12
        natural_outflow = min(self.river_storage_m3 * outflow_rate, self.river_storage_m3)
        self.river_storage_m3 -= natural_outflow
        self.total_river_drain_volume_m3 += natural_outflow

        # C. Bankfull overflow: river exceeds channel capacity -> spill onto land
        spilled_vol = 0.0
        if self.river_storage_m3 > self.river_bankfull_capacity_m3:
            spilled_vol = self.river_storage_m3 - self.river_bankfull_capacity_m3
            self.river_storage_m3 = self.river_bankfull_capacity_m3
            self._spill_river_overflow(spilled_vol)
            self.total_river_overflow_m3 += spilled_vol

        return spilled_vol

    def simulate_timestep(
        self, dt: float, rain_rate_grid: np.ndarray, sub_passes: int = FLOW_SUB_PASSES
    ) -> Dict[str, float]:
        """
        Advances the simulation by dt seconds:
            1. Apply rainfall & subtract infiltration
            2. Compute overland 2D surface routing
            3. Absorb water into drainage inlets
            4. Add pipe overflow back to surface
            5. Drain water body cells (rivers/channels)

        Returns:
            Dict containing timestep summary metrics.
        """
        # 1. Rainfall
        self.apply_rainfall(dt, rain_rate_grid)

        # 2. Surface Flow
        self.calculate_surface_flow(dt, sub_passes=sub_passes)

        # 3. Drainage Absorption
        absorbed_m3 = self.calculate_drainage_absorption(dt)

        # 4. Sewer Overflow
        overflow_m3 = self.calculate_overflow()

        # 5. River/Channel Drain: remove any water that flowed into water body cells
        self.drain_water_bodies(dt)

        # Stats are reported over land cells only (exclude water bodies from flood metrics)
        land_depth = np.where(~self.water_body_mask, self.water_depth, 0.0)
        current_vol_m3 = float(np.sum(land_depth) * self.cell_area)
        max_depth = float(np.max(land_depth))
        mean_depth = float(np.mean(land_depth))
        flooded_cells = int(np.sum(land_depth > 0.05))  # cells > 5 cm

        return {
            "max_depth_m": max_depth,
            "mean_depth_m": mean_depth,
            "surface_water_volume_m3": current_vol_m3,
            "flooded_cells_count": flooded_cells,
            "absorbed_volume_m3": absorbed_m3,
            "overflow_volume_m3": overflow_m3,
        }

    # =========================================================================
    # Multi-Horizon Forecast Runner
    # =========================================================================

    def run_forecast(
        self,
        scenario: str = "moderate",
        horizon_minutes: int = 180,
        dt: float = DT_SECONDS,
        sub_passes: int = FLOW_SUB_PASSES,
    ) -> Dict[int, np.ndarray]:
        """
        Executes a complete forecast simulation from T=0 to T=horizon_minutes.
        Captures depth grids at each defined horizon marker [0, 30, 60, 90, 120, 180].

        Args:
            scenario: Name of rainfall scenario ("moderate", "heavy", "cloudburst", etc.)
            horizon_minutes: Forecast horizon length in minutes (default 180)
            dt: Timestep in seconds (default 300 s / 5 min)
            sub_passes: Stability passes per timestep

        Returns:
            Dict[int, np.ndarray]: {minutes: water_depth_grid (200, 200)}
        """
        # Fetch rainfall nowcast grids from provider
        rain_nowcast = self.rainfall_provider.generate_nowcast(
            scenario=scenario, horizon_minutes=horizon_minutes
        )

        self.reset_state()

        # Target capture timestamps in minutes
        capture_horizons = sorted([h for h in FORECAST_HORIZONS if h <= horizon_minutes])
        if 0 not in capture_horizons:
            capture_horizons.insert(0, 0)

        # Snapshot at T=0
        self.forecast_grids[0] = self.water_depth.copy()

        total_steps = int(round((horizon_minutes * 60.0) / dt))
        next_capture_idx = 1 if len(capture_horizons) > 1 else None

        # Sorted rainfall horizon marks available from provider
        rain_time_keys = sorted(rain_nowcast.keys())

        for step in range(1, total_steps + 1):
            current_time_min = (step * dt) / 60.0

            # Determine the appropriate rainfall grid for current minute
            # Use most recent available forecast grid without looking into the future
            active_rain_key = rain_time_keys[0]
            for rk in rain_time_keys:
                if rk <= current_time_min:
                    active_rain_key = rk
                else:
                    break

            rain_grid = rain_nowcast[active_rain_key]

            # Step forward
            self.simulate_timestep(dt=dt, rain_rate_grid=rain_grid, sub_passes=sub_passes)

            # Check if this step aligns with a capture horizon
            if next_capture_idx is not None and next_capture_idx < len(capture_horizons):
                target_min = capture_horizons[next_capture_idx]
                if abs(current_time_min - target_min) < (dt / 120.0):
                    self.forecast_grids[target_min] = self.water_depth.copy()
                    next_capture_idx += 1

        # Fill any missing horizon with latest depth
        for h in capture_horizons:
            if h not in self.forecast_grids:
                self.forecast_grids[h] = self.water_depth.copy()

        return self.forecast_grids

    # =========================================================================
    # Shared Interface Contracts
    # =========================================================================

    def get_depth_at_cell(self, row: int, col: int) -> float:
        """
        Interface for Pair A (Drainage) & Pair C (Routing).
        Returns flood depth at specific DEM cell in meters.
        """
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return float(self.water_depth[row, col])
        return 0.0

    def add_overflow_at_cell(self, row: int, col: int, volume_m3: float) -> None:
        """
        Interface for Pair A (Drainage).
        Adds overflowing volume in m^3 back to the specified cell.
        """
        if 0 <= row < self.rows and 0 <= col < self.cols and volume_m3 > 0.0:
            depth_increase = volume_m3 / self.cell_area
            self.water_depth[row, col] += depth_increase

    def get_forecast_grids(self) -> Dict[int, np.ndarray]:
        """
        Interface for Pair C (Routing).
        Returns {minutes: depth_grid} for all forecast horizons.
        """
        return self.forecast_grids

    # =========================================================================
    # Factory Helper
    # =========================================================================

    @classmethod
    def from_default_data(
        cls,
        rainfall_provider: Optional[RainfallProvider] = None,
        drainage_graph: Optional[Any] = None,
        boundary_condition: str = "closed",
        upstream_river_inflow_m3_s: float = 0.0,
        tidal_lock: bool = False,
        initial_river_storage_m3: float = 0.0,
    ) -> "FloodEngine":
        """
        Instantiates FloodEngine loading the preprocessed Mumbai DEM,
        imperviousness, infiltration, and water body mask rasters from backend/data/dem/.
        """
        if not DEM_ELEVATION_FILE.exists():
            raise FileNotFoundError(
                f"DEM elevation file not found at {DEM_ELEVATION_FILE}. "
                "Run backend/data/dem/process_dem.py first."
            )

        dem = np.load(DEM_ELEVATION_FILE)
        imp = np.load(DEM_IMPERVIOUSNESS_FILE) if DEM_IMPERVIOUSNESS_FILE.exists() else None
        inf = np.load(DEM_INFILTRATION_FILE) if DEM_INFILTRATION_FILE.exists() else None
        # Load pre-existing water body mask; fall back to negative-elevation detection
        wb_mask = np.load(DEM_WATER_BODY_MASK_FILE) if DEM_WATER_BODY_MASK_FILE.exists() else None

        return cls(
            dem=dem,
            imperviousness=imp,
            infiltration=inf,
            water_body_mask=wb_mask,
            rainfall_provider=rainfall_provider,
            drainage_graph=drainage_graph,
            cell_size_m=CELL_SIZE_M,
            boundary_condition=boundary_condition,
            upstream_river_inflow_m3_s=upstream_river_inflow_m3_s,
            tidal_lock=tidal_lock,
            initial_river_storage_m3=initial_river_storage_m3,
        )
