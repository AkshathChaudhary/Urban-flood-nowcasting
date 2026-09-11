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
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable
import numpy as np

from backend.app.config import (
    CELL_AREA_M2,
    CELL_SIZE_M,
    DEM_ELEVATION_FILE,
    DEM_IMPERVIOUSNESS_FILE,
    DEM_INFILTRATION_FILE,
    DEM_WATER_BODY_MASK_FILE,
    DEM_RETENTION_POND_MASK_FILE,
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

@runtime_checkable
class DrainageInterface(Protocol):
    """Formal interface protocol for Pair A (Drainage) integration."""
    def absorb_surface_water(self, depth_grid: np.ndarray, dt: float) -> np.ndarray: ...
    def compute_overflow(self) -> Dict[str, float]: ...


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
        tidal_tailwater_stage_m: float = 0.5,
        tidal_cycle_start_hour: float = 14.0,
        antecedent_saturation_fraction: float = 0.0,
        drain_blockage_factor: float = 1.0,
        retention_pond_mask: Optional[np.ndarray] = None,
        retention_pond_capacity_m3: float = 25000.0,
        storm_surge_m: float = 0.0,
        pump_stations: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize the FloodEngine.

        Args:
            dem: 2D numpy array of elevations in meters (shape: rows, cols)
            imperviousness: 2D numpy array (0.0 to 1.0)
            infiltration: 2D numpy array of soil infiltration rates in mm/hr
            water_body_mask: Boolean 2D array — True for cells that are pre-existing
                             rivers/channels/lakes.
            rainfall_provider: RainfallProvider instance
            drainage_graph: Optional DrainageGraph instance (Pair A interface)
            cell_size_m: Grid cell spatial resolution (default 10.0 m)
            boundary_condition: "closed" or "outflow"
            antecedent_saturation_fraction: Pre-existing soil saturation (0.0 to 1.0)
            drain_blockage_factor: Street inlet blockage (0.0 = fully blocked, 1.0 = clear)
            retention_pond_mask: Boolean 2D array for stormwater retention basins
            retention_pond_capacity_m3: Maximum pond detention capacity (m³)
            storm_surge_m: Coastal storm surge sea level rise (m)
            pump_stations: List of dicts specifying pump stations
        """
        self.dem = dem.astype(np.float32)
        self.rows, self.cols = self.dem.shape
        self.cell_size = float(cell_size_m)
        self.cell_area = self.cell_size * self.cell_size
        self.boundary_condition = boundary_condition

        # Water body mask: true rivers, channels, and tidal zones.
        if water_body_mask is not None:
            self.water_body_mask = water_body_mask.astype(bool)
        else:
            self.water_body_mask = np.zeros((self.rows, self.cols), dtype=bool)

        # Retention pond mask (enclosed basins/ponds buffering overland runoff)
        if retention_pond_mask is not None:
            self.retention_pond_mask = retention_pond_mask.astype(bool)
            # Separate: remove retention pond cells from river channel mask so they don't drain via river tidal outflow
            self.water_body_mask = self.water_body_mask & ~self.retention_pond_mask
        else:
            self.retention_pond_mask = np.zeros((self.rows, self.cols), dtype=bool)

        # Default or assigned imperviousness (0.0: permeable soil -> 1.0: concrete)
        if imperviousness is not None:
            self.imperviousness = np.clip(imperviousness.astype(np.float32), 0.0, 1.0)
        else:
            self.imperviousness = np.full((self.rows, self.cols), 0.75, dtype=np.float32)
        # Open water surfaces have zero imperviousness
        self.imperviousness[self.water_body_mask] = 0.0
        self.imperviousness[self.retention_pond_mask] = 0.0

        # Effective surface porosity (void space fraction in urban streetscapes)
        # Buildings occupy 40-65% of land area in dense Kurla/BKC blocks.
        # Overland flood water is squeezed into streets/alleys, increasing physical depth.
        self.surface_porosity = np.clip(1.0 - 0.60 * self.imperviousness, 0.35, 1.0).astype(np.float32)
        self.surface_porosity[self.water_body_mask] = 1.0
        self.surface_porosity[self.retention_pond_mask] = 1.0

        # Infiltration capacity grid (mm/hr)
        if infiltration is not None:
            self.infiltration = np.maximum(infiltration.astype(np.float32), 0.0)
        else:
            base_rate = 5.0  # mm/hr
            self.infiltration = base_rate * (1.0 - self.imperviousness)
        # Saturated riverbed and retention basins have zero infiltration loss
        self.infiltration[self.water_body_mask] = 0.0
        self.infiltration[self.retention_pond_mask] = 0.0

        # Soil saturation feedback (Horton infiltration capacity store)
        self.antecedent_saturation_fraction = float(antecedent_saturation_fraction)
        # Permeable soil holds ~80 mm (0.080 m) water before reaching field capacity
        self.soil_saturation_capacity_m = (0.080 * (1.0 - self.imperviousness)).astype(np.float32)
        self.soil_saturation_capacity_m[self.water_body_mask] = 0.0
        self.soil_saturation_capacity_m[self.retention_pond_mask] = 0.0
        self.soil_moisture_m = np.zeros((self.rows, self.cols), dtype=np.float32)

        # Drainage blockage factor
        self.drain_blockage_factor = float(drain_blockage_factor)

        # Retention pond storage tracking
        self.retention_pond_capacity_m3 = float(retention_pond_capacity_m3)
        self.retention_pond_storage_m3 = 0.0
        self.total_pond_storage_inflow_m3 = 0.0
        self.total_pond_spill_m3 = 0.0

        # Storm surge / seawater intrusion
        self.storm_surge_m = float(storm_surge_m)
        self.total_surge_intrusion_m3 = 0.0

        # Municipal pump stations
        self.pump_stations = pump_stations or []
        self.total_pumped_volume_m3 = 0.0

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
        self.tidal_tailwater_stage_m = float(tidal_tailwater_stage_m)
        self.tidal_cycle_start_hour = float(tidal_cycle_start_hour)
        self.total_upstream_inflow_m3 = 0.0
        self._elapsed_sim_seconds = 0.0

        # Mass balance counters (m^3)
        self.total_rain_volume_m3 = 0.0
        self.total_infiltrated_volume_m3 = 0.0
        self.total_absorbed_volume_m3 = 0.0
        self.total_overflow_volume_m3 = 0.0
        self.total_boundary_outflow_m3 = 0.0
        self.total_river_drain_volume_m3 = 0.0   # water that exited downstream
        self.total_river_overflow_m3 = 0.0       # water spilled from river onto land
        self.total_pipe_discharged_volume_m3 = 0.0  # water safely drained via subterranean pipes

        # Output snapshots {minutes: depth_grid}
        self.forecast_grids: Dict[int, np.ndarray] = {}
        # Rainfall nowcast grids {minutes: rain_rate_grid (mm/hr)}
        self.rain_nowcast: Dict[int, np.ndarray] = {}

        # Precompute static terrain properties
        self.initialize()

    def initialize(self) -> None:
        """
        Precompute static hydrological properties from DEM and zero dynamic states.
        """
        self.flow_directions = compute_d8_flow_directions(self.dem, self.cell_size)
        self.sinks_mask = identify_sinks(self.dem, self.flow_directions, self.cell_size)

        # Precompute river bank cells and retention pond bank cells
        self.river_bank_mask = self._compute_river_bank_mask()
        self.retention_pond_bank_mask = self._compute_retention_pond_bank_mask()

        # Bankfull capacity of river/channel cells (m³).
        BANKFULL_DEPTH_M = 1.8
        n_water_cells = int(self.water_body_mask.sum())
        self.river_bankfull_capacity_m3 = max(
            n_water_cells * self.cell_area * BANKFULL_DEPTH_M, 1.0
        )

        # Cache static river bed mean elevation (P3)
        if np.any(self.water_body_mask):
            self._river_bed_elev = float(np.mean(self.dem[self.water_body_mask]))
        else:
            self._river_bed_elev = float(np.min(self.dem))

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
        self.total_pipe_discharged_volume_m3 = 0.0
        self.total_upstream_inflow_m3 = 0.0
        self.total_surge_intrusion_m3 = 0.0
        self.total_pumped_volume_m3 = 0.0
        self.retention_pond_storage_m3 = 0.0
        self.total_pond_storage_inflow_m3 = 0.0
        self.total_pond_spill_m3 = 0.0

        # Reset soil moisture store based on antecedent saturation fraction
        self.soil_moisture_m = np.clip(
            self.soil_saturation_capacity_m * self.antecedent_saturation_fraction,
            0.0,
            self.soil_saturation_capacity_m,
        )

        self.river_storage_m3 = min(self.initial_river_storage_m3, self.river_bankfull_capacity_m3)
        n_water_cells = int(self.water_body_mask.sum())
        if n_water_cells > 0 and self.river_storage_m3 > 0.0:
            init_channel_depth = self.river_storage_m3 / (n_water_cells * self.cell_area)
            self.water_depth[self.water_body_mask] = init_channel_depth
        self.forecast_grids.clear()
        # Reset tidal clock — simulation always starts at tidal_cycle_start_hour phase
        self._elapsed_sim_seconds = 0.0

    # =========================================================================
    # Simulation Step Sub-methods
    # =========================================================================

    def apply_rainfall(self, dt: float, rain_rate_grid: np.ndarray) -> np.ndarray:
        """
        Apply rainfall deposition and subtract soil infiltration.
        Infiltration is constrained by both the soil infiltration rate and
        remaining pore space capacity (soil saturation feedback).

        Args:
            dt: Timestep in seconds
            rain_rate_grid: Rainfall intensity grid in mm/hr

        Returns:
            np.ndarray: Net effective precipitation grid in meters (gross rain minus infiltration).
                        Land cells are added to self.water_depth; open water body cells
                        are routed directly to self.river_storage_m3.
        """
        dt_hr = dt / 3600.0

        # Total gross rainfall in meters
        gross_rain_m = (rain_rate_grid.astype(np.float32) * dt_hr) / 1000.0

        # Maximum soil infiltration rate capacity for this timestep in meters
        max_infil_m = (self.infiltration * dt_hr) / 1000.0

        # Remaining soil moisture pore capacity before saturation (m)
        remaining_capacity_m = np.maximum(self.soil_saturation_capacity_m - self.soil_moisture_m, 0.0)

        # Actual infiltrated water (cannot exceed gross rain, rate capacity, or pore space)
        actual_infil_m = np.minimum(gross_rain_m, np.minimum(max_infil_m, remaining_capacity_m))

        # Update soil moisture store
        self.soil_moisture_m += actual_infil_m

        # Net effective precipitation reaching surface
        net_addition_m = np.maximum(gross_rain_m - actual_infil_m, 0.0)

        # Track direct rain on open water -> river storage (B1/R1)
        if np.any(self.water_body_mask):
            direct_rain_on_river = float(
                np.sum(net_addition_m[self.water_body_mask]) * self.cell_area
            )
            self.river_storage_m3 += direct_rain_on_river

        # Zero out water body contribution from grid (channel stage set by drain_water_bodies)
        net_addition_m_land = net_addition_m.copy()
        net_addition_m_land[self.water_body_mask] = 0.0

        # Update grid state (land cells only)
        self.water_depth += net_addition_m_land
        self.cumulative_rain_m += gross_rain_m
        self.cumulative_infiltrated_m += actual_infil_m

        # Update mass balance totals (entire domain)
        self.total_rain_volume_m3 += float(np.sum(gross_rain_m) * self.cell_area)
        self.total_infiltrated_volume_m3 += float(np.sum(actual_infil_m) * self.cell_area)

        return net_addition_m

    def calculate_surface_flow(
        self, dt: float, sub_passes: int = FLOW_SUB_PASSES
    ) -> float:
        """
        Execute 2D overland water routing based on hydraulic head gradients.

        Water inside river channels is physically confined by channel banks;
        overland runoff routing onto river cells enters the channel.

        Args:
            dt: Timestep in seconds
            sub_passes: Number of sub-iterations for stability

        Returns:
            float: Volume of water exited past boundary in m^3
        """
        # Separate overland water from confined channel water
        land_water = np.where(~self.water_body_mask, self.water_depth, 0.0)
        routed_depth, boundary_outflow = route_surface_water(
            elevation=self.dem,
            water_depth=land_water,
            dt=dt,
            cell_size_m=self.cell_size,
            sub_passes=sub_passes,
            boundary_condition=self.boundary_condition,
        )
        self.total_boundary_outflow_m3 += boundary_outflow

        # Overland runoff that reached channel cells enters the river
        runoff_into_channel = float(np.sum(routed_depth[self.water_body_mask]) * self.cell_area)
        self.river_storage_m3 += runoff_into_channel

        # Update overland depth on land cells
        self.water_depth[~self.water_body_mask] = routed_depth[~self.water_body_mask]

        return boundary_outflow

    def calculate_drainage_absorption(self, dt: float) -> float:
        """
        Interface: Pair B calls Pair A's absorb_surface_water method.
        Deducts absorbed water from the surface water depth.
        Inlets absorb overland street runoff on land.

        Returns:
            float: Total volume absorbed by drainage network in m^3
        """
        if self.drainage_graph is None or not hasattr(
            self.drainage_graph, "absorb_surface_water"
        ):
            return 0.0

        # Submergence feedback: inform drainage network of downstream river stage
        if hasattr(self.drainage_graph, "set_river_submergence"):
            n_water = max(int(self.water_body_mask.sum()), 1)
            stage_m = self.river_storage_m3 / (n_water * self.cell_area)
            self.drainage_graph.set_river_submergence(stage_m, self.water_depth)

        # Inlets absorb overland street runoff on land
        land_depth = np.where(~self.water_body_mask, self.water_depth, 0.0)
        absorbed_depth_grid = self.drainage_graph.absorb_surface_water(
            land_depth, dt
        )
        # Apply drain blockage factor (debris/plastic clogging)
        absorbed_depth_grid = absorbed_depth_grid * self.drain_blockage_factor

        # Limit absorption to what overland water exists on the land surface
        actual_absorbed = np.minimum(absorbed_depth_grid, land_depth)
        self.water_depth[~self.water_body_mask] -= actual_absorbed[~self.water_body_mask]

        absorbed_vol_m3 = float(np.sum(actual_absorbed) * self.cell_area)
        self.total_absorbed_volume_m3 += absorbed_vol_m3
        return absorbed_vol_m3

    def calculate_overflow(self) -> float:
        """
        Interface: Pair B queries Pair A's compute_overflow method.
        Puts overflowing sewer water back onto surface cells.

        Returns:
            float: Total volume added to surface from overflows in m^3
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
                pos = None
                if hasattr(self.drainage_graph, "get_node_cell"):
                    pos = self.drainage_graph.get_node_cell(node_id)
                elif hasattr(self.drainage_graph, "get_node_grid_position"):
                    pos = self.drainage_graph.get_node_grid_position(node_id)
                if pos is not None:
                    r, c = pos
                    if 0 <= r < self.rows and 0 <= c < self.cols:
                        depth_add = vol_m3 / self.cell_area
                        self.water_depth[r, c] += depth_add
                        total_overflow_vol += vol_m3
                        # If node is inside channel, also account in river storage
                        if self.water_body_mask[r, c]:
                            self.river_storage_m3 += vol_m3

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

    def _compute_retention_pond_bank_mask(self) -> np.ndarray:
        """
        Identifies land cells immediately adjacent (4-connected) to retention pond cells.
        """
        rp = self.retention_pond_mask
        bank = np.zeros(rp.shape, dtype=bool)
        bank[:-1, :] |= rp[1:, :]
        bank[1:, :]  |= rp[:-1, :]
        bank[:, :-1] |= rp[:, 1:]
        bank[:, 1:]  |= rp[:, :-1]
        return bank & ~rp & ~self.water_body_mask


    def _spill_river_overflow(self, overflow_vol_m3: float) -> None:
        """
        Distributes river overflow volume across river bank land cells based on
        broad-crested weir overtopping hydraulics:
            Q_breach ~ w * (H_channel - Z_bank)^1.5
        Low-elevation bank segments (e.g. Kranti Nagar / Kurla West) breach earliest
        and receive the deepest flooding, matching physical flood observations.
        Mass conservation is strictly preserved: sum of added volume == overflow_vol_m3.
        """
        if overflow_vol_m3 <= 0.0 or not np.any(self.river_bank_mask):
            return

        n_water = max(int(self.water_body_mask.sum()), 1)
        # Channel water surface elevation prior to spill: bed elevation + stage (P3 cached)
        river_bed_elev = self._river_bed_elev

        # Peak stage depth in channel driving the overtopping
        peak_stage_m = (self.river_bankfull_capacity_m3 + overflow_vol_m3) / (n_water * self.cell_area)
        h_channel = river_bed_elev + peak_stage_m

        bank_elev = self.dem[self.river_bank_mask]
        # Overtopping hydraulic head above bank crest
        dh = np.maximum(h_channel - bank_elev, 0.0)
        # Broad-crested weir flux proportional to dh^1.5
        weir_weights = dh ** 1.5
        sum_w = float(np.sum(weir_weights))

        if sum_w > 0.0:
            norm_weights = (weir_weights / sum_w).astype(np.float64)
        else:
            # Fallback if channel stage is lower than bank crests (overflow triggered by volume):
            # Spill breaches through the lowest 20% elevation bank cells (B3 fix)
            p20 = float(np.percentile(bank_elev, 20))
            low_bank_mask = bank_elev <= p20
            min_z = float(np.min(bank_elev))
            inv_dist = np.where(low_bank_mask, 1.0 / (bank_elev - min_z + 0.1), 0.0)
            sum_inv = float(np.sum(inv_dist))
            if sum_inv > 1e-12:
                norm_weights = (inv_dist / sum_inv).astype(np.float64)
            else:
                n_low = int(np.sum(low_bank_mask))
                if n_low > 0:
                    norm_weights = np.where(low_bank_mask, 1.0 / n_low, 0.0).astype(np.float64)
                else:
                    norm_weights = np.full_like(bank_elev, 1.0 / max(len(bank_elev), 1), dtype=np.float64)

        # Distribute overflow volume onto bank cells according to hydraulic weir weighting
        added_depth_m = (overflow_vol_m3 * norm_weights) / self.cell_area
        self.water_depth[self.river_bank_mask] += added_depth_m.astype(np.float32)

    def get_street_depth(self) -> np.ndarray:
        """
        Returns physical water depth in streets and alleys accounting for building volume displacement.
            d_street = d_grid / surface_porosity
        where surface_porosity = 1 - 0.60 * imperviousness in [0.35, 1.0].
        In open channels or parks (porosity = 1.0), d_street == water_depth.
        In dense urban blocks (porosity ~ 0.50), d_street is ~2.0x grid water_depth,
        correcting the systematic 40-60% underestimation of street flood marks.
        """
        return (self.water_depth / self.surface_porosity).astype(np.float32)


    def _tidal_outflow_rate(self) -> float:
        """
        Compute dynamic tidal outflow rate based on current simulation time.

        Mumbai experiences semi-diurnal tides with ~12.4-hour period.
        The outflow rate is modulated by the tidal phase:
        - At low tide: max outflow (gravity drainage freely exits to Mahim Bay)
        - At high tide: near-zero outflow (sea backs up into estuary, blocking discharge)

        Returns:
            float: fractional outflow rate per timestep (0.0 = fully blocked, 0.12 = free drain)
        """
        if self.tidal_lock:
            return 0.0

        # Elapsed simulation time in hours from start
        elapsed_hours = self._elapsed_sim_seconds / 3600.0
        # Tidal phase in radians: 0 = low tide, pi = high tide
        # tidal_cycle_start_hour encodes where in the tidal cycle the simulation begins
        # (14:00 IST on July 26 2023 = approximately 2 hrs after high tide in Mumbai)
        TIDAL_PERIOD_HOURS = 12.4
        phase_rad = 2.0 * np.pi * elapsed_hours / TIDAL_PERIOD_HOURS
        # Shift by starting phase (0=low tide, pi=high tide)
        # For a starting offset of e.g. 2h after high tide: start_phase = pi + 2*pi*2/12.4
        start_phase = np.pi + 2.0 * np.pi * (self.tidal_cycle_start_hour % TIDAL_PERIOD_HOURS) / TIDAL_PERIOD_HOURS
        tidal_height = 0.5 * (1.0 + np.cos(phase_rad + start_phase))  # 0=low tide, 1=high tide

        # At low tide (tidal_height=0): outflow_rate = 0.12 (free gravity drain)
        # At high tide (tidal_height=1): outflow_rate = 0.0 (fully blocked)
        MAX_FREE_DRAIN_RATE = 0.12
        return MAX_FREE_DRAIN_RATE * (1.0 - tidal_height)

    def drain_water_bodies(self, dt: float = DT_SECONDS) -> float:
        """
        Implements river/channel water level dynamics each timestep:

        Step 0 — Upstream inflow: external catchment water (Powai/Vihar lakes) enters river.
        Step 1 — Downstream outflow: modulated by dynamic tidal cycle (semi-diurnal 12.4-hr).
                 Outflow is restricted at high tide and free at low tide.
                 A sea-level tailwater floor prevents the channel draining below
                 the minimum tidal stage depth (e.g. 0.5m base depth representing
                 permanent tidal standing water in Mithi River estuary).
        Step 2 — Bankfull overflow: if river storage exceeds channel capacity, the excess
                 is spilled back onto adjacent land cells as riverine flood water.
        Step 3 — Retain channel depth: water bodies retain actual water depth proportional
                 to current channel storage rather than being zeroed out.

        Returns:
            float: Volume spilled onto land from river overflow this timestep (m³).
        """
        n_water = int(self.water_body_mask.sum())
        if n_water == 0:
            self._elapsed_sim_seconds += dt
            return 0.0

        # 0. Upstream river inflow entering from upstream catchment (Powai/Vihar lakes)
        if self.upstream_river_inflow_m3_s > 0.0:
            up_vol = self.upstream_river_inflow_m3_s * dt
            self.river_storage_m3 += up_vol
            self.total_upstream_inflow_m3 += up_vol

        # 1. Sea-level tailwater floor: the minimum volume the channel always holds.
        # Even at low tide, tidal backwater keeps ~tidal_tailwater_stage_m of standing depth.
        # The channel cannot drain below this volume via gravity.
        tailwater_min_storage = n_water * self.cell_area * self.tidal_tailwater_stage_m

        # Dynamic tidal outflow rate: 0.0 at high tide -> 0.12 at low tide
        outflow_rate = self._tidal_outflow_rate()

        # Only the storage ABOVE the tailwater floor can drain downstream.
        drainable_storage = max(self.river_storage_m3 - tailwater_min_storage, 0.0)
        natural_outflow = min(drainable_storage * outflow_rate, drainable_storage)
        self.river_storage_m3 -= natural_outflow
        self.total_river_drain_volume_m3 += natural_outflow

        # 2. Bankfull overflow: river exceeds channel capacity -> spill onto land
        spilled_vol = 0.0
        if self.river_storage_m3 > self.river_bankfull_capacity_m3:
            spilled_vol = self.river_storage_m3 - self.river_bankfull_capacity_m3
            self.river_storage_m3 = self.river_bankfull_capacity_m3
            self._spill_river_overflow(spilled_vol)
            self.total_river_overflow_m3 += spilled_vol

        # 3. Retain physical channel stage depth in the water depth grid
        channel_depth = self.river_storage_m3 / (n_water * self.cell_area)
        self.water_depth[self.water_body_mask] = channel_depth

        # Advance elapsed simulation clock
        self._elapsed_sim_seconds += dt

        return spilled_vol

    def drain_retention_ponds(self, dt: float) -> float:
        """
        Buffers overland runoff arriving on retention pond cells up to
        retention_pond_capacity_m3, with controlled slow release spillway flow.

        Returns:
            float: Volume spilled from retention pond back onto land (m³).
        """
        n_pond = int(self.retention_pond_mask.sum())
        if n_pond == 0:
            return 0.0

        # 1. Inflow: overland water pooling on pond cells enters detention storage
        free_cap = max(self.retention_pond_capacity_m3 - self.retention_pond_storage_m3, 0.0)
        depth_on_ponds = self.water_depth[self.retention_pond_mask]
        avail_vol = float(np.sum(depth_on_ponds) * self.cell_area)
        inflow_vol = min(avail_vol, free_cap)
        if avail_vol > 0.0 and inflow_vol > 0.0:
            frac = inflow_vol / avail_vol
            self.water_depth[self.retention_pond_mask] -= depth_on_ponds * frac
            self.retention_pond_storage_m3 += inflow_vol
            self.total_pond_storage_inflow_m3 += inflow_vol

        # 2. Controlled slow release spillway: release ~1% per 5-min timestep to adjacent land
        spilled_vol = 0.0
        if self.retention_pond_storage_m3 > 0.0:
            n_bank = int(self.retention_pond_bank_mask.sum())
            if n_bank > 0:
                SLOW_RELEASE_FRAC = 0.01
                release_vol = min(self.retention_pond_storage_m3 * SLOW_RELEASE_FRAC, self.retention_pond_storage_m3)
                self.retention_pond_storage_m3 -= release_vol
                depth_add = release_vol / (n_bank * self.cell_area)
                self.water_depth[self.retention_pond_bank_mask] += depth_add
                self.total_pond_spill_m3 += release_vol
                spilled_vol = release_vol

        return spilled_vol

    def apply_storm_surge(self, dt: float) -> float:
        """
        Simulates tidal storm surge / seawater intrusion.
        When storm_surge_m > 0, pushes seawater onto estuary-adjacent low-lying cells (DEM < surge).

        Returns:
            float: Seawater volume added this timestep in m³.
        """
        if self.storm_surge_m <= 0.0:
            return 0.0

        surge_mask = self.river_bank_mask & (self.dem < self.storm_surge_m)
        if not np.any(surge_mask):
            return 0.0

        target_depth = self.storm_surge_m - self.dem[surge_mask]
        current_depth = self.water_depth[surge_mask]
        deficit = np.maximum(target_depth - current_depth, 0.0)

        intrusion_depth = np.minimum(deficit, 0.10)  # gradual surge intrusion up to 10cm/step
        added_vol = float(np.sum(intrusion_depth) * self.cell_area)
        if added_vol > 0.0:
            self.water_depth[surge_mask] += intrusion_depth
            self.total_surge_intrusion_m3 += added_vol

        return added_vol

    def apply_pump_stations(self, dt: float) -> float:
        """
        Removes stormwater via operational municipal stormwater pumping stations.
        If radius_cells > 0 (default 0), pumps draw from the surrounding wet well sump basin.

        Returns:
            float: Total volume pumped out of domain this timestep in m³.
        """
        if not self.pump_stations:
            return 0.0

        pumped_this_step = 0.0
        for ps in self.pump_stations:
            if not ps.get("operational", True):
                continue
            r, c = ps["row"], ps["col"]
            radius = int(ps.get("radius_cells", 0))
            cap_rate = float(ps.get("capacity_m3_s", 5.0))
            max_vol = cap_rate * dt

            if radius == 0:
                if 0 <= r < self.rows and 0 <= c < self.cols:
                    avail_vol = float(self.water_depth[r, c] * self.cell_area)
                    rem_vol = min(max_vol, avail_vol)
                    if rem_vol > 0.0:
                        self.water_depth[r, c] -= rem_vol / self.cell_area
                        pumped_this_step += rem_vol
            else:
                r_min, r_max = max(0, r - radius), min(self.rows, r + radius + 1)
                c_min, c_max = max(0, c - radius), min(self.cols, c + radius + 1)
                patch = self.water_depth[r_min:r_max, c_min:c_max]
                avail_vol = float(np.sum(patch) * self.cell_area)
                rem_vol = min(max_vol, avail_vol)
                if rem_vol > 0.0 and avail_vol > 0.0:
                    frac = rem_vol / avail_vol
                    self.water_depth[r_min:r_max, c_min:c_max] -= patch * frac
                    pumped_this_step += rem_vol

        self.total_pumped_volume_m3 += pumped_this_step
        return pumped_this_step

    def simulate_timestep(
        self, dt: float, rain_rate_grid: np.ndarray, sub_passes: int = FLOW_SUB_PASSES
    ) -> Dict[str, float]:
        """
        Advances the simulation by dt seconds:
            1. Apply rainfall & subtract infiltration (soil saturation capped)
            2. Compute overland 2D surface routing
            3. Absorb water into drainage inlets (blockage factor applied)
            4. Municipal pump stations
            5. Stormwater retention basins / ponds
            6. Add sewer pipe overflow back to surface
            7. Storm surge seawater intrusion
            8. Drain water body cells (rivers/channels with tidal dynamics)

        Returns:
            Dict containing timestep summary metrics.
        """
        # 1. Rainfall
        self.apply_rainfall(dt, rain_rate_grid)

        # 2. Surface Flow
        self.calculate_surface_flow(dt, sub_passes=sub_passes)

        # 3. Drainage Absorption
        absorbed_m3 = self.calculate_drainage_absorption(dt)

        # 3b. Subterranean Pipe Flow Propagation (Pair A pipe conveyance to outfalls)
        discharged_pipe_m3 = 0.0
        if self.drainage_graph is not None and hasattr(self.drainage_graph, "propagate_flow"):
            discharged_pipe_m3 = float(self.drainage_graph.propagate_flow(dt))
            self.total_pipe_discharged_volume_m3 += discharged_pipe_m3

        # 4. Municipal Pump Stations
        pumped_m3 = self.apply_pump_stations(dt)

        # 5. Retention Ponds
        pond_spill_m3 = self.drain_retention_ponds(dt)

        # 6. Sewer Overflow
        overflow_m3 = self.calculate_overflow()

        # 7. Storm Surge Intrusion
        surge_m3 = self.apply_storm_surge(dt)

        # 8. River/Channel Drain: update storage, outflow, spill, and channel stage
        river_spill_m3 = self.drain_water_bodies(dt)

        # Stats are reported over land cells (for hazard/flooding alerts) as well as total domain:
        land_depth = np.where(~self.water_body_mask, self.water_depth, 0.0)
        current_vol_m3 = float(np.sum(self.water_depth) * self.cell_area)
        land_vol_m3 = float(np.sum(land_depth) * self.cell_area)
        max_depth = float(np.max(land_depth))
        mean_depth = float(np.mean(land_depth))
        flooded_cells = int(np.sum(land_depth > 0.05))  # land cells > 5 cm

        return {
            "max_depth_m": max_depth,
            "mean_depth_m": mean_depth,
            "surface_water_volume_m3": current_vol_m3,
            "land_water_volume_m3": land_vol_m3,
            "river_storage_volume_m3": self.river_storage_m3,
            "retention_pond_storage_volume_m3": self.retention_pond_storage_m3,
            "flooded_cells_count": flooded_cells,
            "absorbed_volume_m3": absorbed_m3,
            "pipe_discharged_volume_m3": discharged_pipe_m3,
            "overflow_volume_m3": overflow_m3,
            "pumped_volume_m3": pumped_m3,
            "storm_surge_volume_m3": surge_m3,
            "river_spill_volume_m3": river_spill_m3,
            "pond_spill_volume_m3": pond_spill_m3,
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
        self.rain_nowcast = rain_nowcast

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
            # Use continuous dynamic provider hook if supported, otherwise step-down interpolation
            dynamic_grid = None
            if hasattr(self.rainfall_provider, "get_rain_rate_grid"):
                dynamic_grid = self.rainfall_provider.get_rain_rate_grid(
                    current_time_min, scenario=scenario
                )

            if dynamic_grid is not None:
                rain_grid = dynamic_grid
            else:
                active_rain_key = rain_time_keys[0]
                for rk in rain_time_keys:
                    if rk <= current_time_min:
                        active_rain_key = rk
                    else:
                        break
                rain_grid = rain_nowcast[active_rain_key]

            # Step forward
            self.simulate_timestep(dt=dt, rain_rate_grid=rain_grid, sub_passes=sub_passes)

            # Check if this step aligns with a capture horizon (B5/R2 robust capture)
            while (
                next_capture_idx is not None
                and next_capture_idx < len(capture_horizons)
                and current_time_min >= capture_horizons[next_capture_idx] - 1e-6
            ):
                target_min = capture_horizons[next_capture_idx]
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

    def get_street_depth_grid(self, horizon_minutes: int = 0) -> np.ndarray:
        """
        Interface for Pair C (Roads & Routing).
        Returns physical street water depth in meters, applying urban building porosity displacement:
            d_street = d_grid / porosity
        Buildings occupy 40-65% of city blocks in dense urban areas (Kurla/BKC), squeezing overland flow into streets.
        """
        if horizon_minutes in self.forecast_grids:
            grid = self.forecast_grids[horizon_minutes]
        else:
            grid = self.water_depth

        porosity = np.maximum(self.surface_porosity, 0.1)
        street_depth = grid / porosity
        street_depth[self.water_body_mask] = grid[self.water_body_mask]
        return street_depth.astype(np.float32)

    def get_street_depth(
        self,
        row: Optional[int] = None,
        col: Optional[int] = None,
        horizon_minutes: int = 0,
    ) -> Union[float, np.ndarray]:
        """
        Interface for road midpoint query or full street depth grid.
        - If row and col are provided, returns float depth at (row, col) in meters.
        - If row and col are None, returns the entire 2D street depth array (shape: rows, cols).
        """
        street_grid = self.get_street_depth_grid(horizon_minutes)
        if row is not None and col is not None:
            if 0 <= row < self.rows and 0 <= col < self.cols:
                return float(street_grid[row, col])
            return 0.0
        return street_grid

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
        tidal_tailwater_stage_m: float = 0.5,
        tidal_cycle_start_hour: float = 14.0,
        antecedent_saturation_fraction: float = 0.0,
        drain_blockage_factor: float = 1.0,
        enable_retention_ponds: bool = False,
        retention_pond_mask: Optional[np.ndarray] = None,
        retention_pond_capacity_m3: float = 25000.0,
        storm_surge_m: float = 0.0,
        pump_stations: Optional[List[Dict[str, Any]]] = None,
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
        wb_mask = np.load(DEM_WATER_BODY_MASK_FILE) if DEM_WATER_BODY_MASK_FILE.exists() else None
        if retention_pond_mask is None and enable_retention_ponds and DEM_RETENTION_POND_MASK_FILE.exists():
            retention_pond_mask = np.load(DEM_RETENTION_POND_MASK_FILE)


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
            tidal_tailwater_stage_m=tidal_tailwater_stage_m,
            tidal_cycle_start_hour=tidal_cycle_start_hour,
            antecedent_saturation_fraction=antecedent_saturation_fraction,
            drain_blockage_factor=drain_blockage_factor,
            retention_pond_mask=retention_pond_mask,
            retention_pond_capacity_m3=retention_pond_capacity_m3,
            storm_surge_m=storm_surge_m,
            pump_stations=pump_stations,
        )

