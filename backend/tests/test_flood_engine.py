"""
Unit and benchmark tests for FloodEngine orchestrator and forecast generation.
"""

import time
import unittest
import numpy as np

from backend.app.engine.flood_engine import FloodEngine
from backend.data.rainfall.provider import DemoRainfallProvider


class TestFloodEngine(unittest.TestCase):
    def setUp(self):
        # Load engine with default Mumbai DEM and terrain grids
        self.engine = FloodEngine.from_default_data()

    def test_flood_engine_initialization(self):
        """Engine should initialize with 200x200 grids and precomputed flow directions."""
        self.assertEqual(self.engine.water_depth.shape, (200, 200))
        self.assertEqual(self.engine.flow_directions.shape, (200, 200))
        self.assertEqual(self.engine.sinks_mask.shape, (200, 200))
        self.assertEqual(float(np.sum(self.engine.water_depth)), 0.0)

    def test_apply_rainfall_with_infiltration(self):
        """Precipitation below infiltration rate should be absorbed into soil on land."""
        engine = FloodEngine.from_default_data()
        dt = 3600.0  # 1 hour

        # Light rain: 1.0 mm/hr (well below minimum infiltration of ~1.5 mm/hr)
        light_rain = np.full((200, 200), 1.0, dtype=np.float32)
        added = engine.apply_rainfall(dt, light_rain)

        # Net added water on land should be zero (fully absorbed by soil)
        land_added = added[~engine.water_body_mask]
        self.assertAlmostEqual(float(np.max(land_added)), 0.0, places=5)
        self.assertAlmostEqual(float(np.max(engine.water_depth[~engine.water_body_mask])), 0.0, places=5)
        # On water body cells (open water), direct rainfall is preserved (1mm = 0.001m)
        water_added = added[engine.water_body_mask]
        self.assertAlmostEqual(float(np.mean(water_added)), 0.001, places=5)

        # Heavy rain: 50 mm/hr (significantly exceeds infiltration)
        heavy_rain = np.full((200, 200), 50.0, dtype=np.float32)
        added_heavy = engine.apply_rainfall(dt, heavy_rain)

        self.assertGreater(float(np.mean(added_heavy)), 0.04)  # ~45mm = 0.045m
        self.assertGreater(float(np.mean(engine.water_depth)), 0.04)

    def test_negative_elevation_land_flooding(self):
        """Verify that land cells with elevation < 0 m accumulate flood depth and are not black holes."""
        engine = FloodEngine.from_default_data()
        neg_elev_land = (engine.dem < 0.0) & (~engine.water_body_mask)
        self.assertGreater(int(neg_elev_land.sum()), 500, "Expected >500 low-elevation land cells")

        # Infiltration rate on negative-elevation land should be normal soil rate (~1.5 to 8 mm/hr), NOT 9999
        self.assertTrue(np.all(engine.infiltration[neg_elev_land] < 20.0))
        self.assertTrue(np.all(engine.imperviousness[neg_elev_land] > 0.5))

        # Apply moderate rain: 30 mm/hr for 1 hour
        rain = np.full((200, 200), 30.0, dtype=np.float32)
        engine.simulate_timestep(3600.0, rain)

        # Negative elevation land cells MUST have accumulated flood water
        neg_depths = engine.water_depth[neg_elev_land]
        self.assertTrue(np.all(neg_depths > 0.0), "All low-elevation land cells must hold flood water")
        self.assertGreater(float(np.mean(neg_depths)), 0.03, "Expected mean depth > 3cm on low-elevation land")

    def test_shared_contract_interfaces(self):
        """Test methods exposed for Pair A (Drainage) and Pair C (Routing)."""
        engine = FloodEngine.from_default_data()

        # Pair A: get_depth_at_cell
        depth_before = engine.get_depth_at_cell(50, 50)
        self.assertEqual(depth_before, 0.0)

        # Pair A: add_overflow_at_cell (volume in m^3)
        # 100 m^3 on a 10m x 10m cell (area = 100 m^2) adds exactly 1.0 m depth
        engine.add_overflow_at_cell(50, 50, volume_m3=100.0)
        depth_after = engine.get_depth_at_cell(50, 50)
        self.assertAlmostEqual(depth_after, 1.0, places=4)

        # Out of bounds safety
        self.assertEqual(engine.get_depth_at_cell(-1, 0), 0.0)
        self.assertEqual(engine.get_depth_at_cell(250, 250), 0.0)

    def test_simulate_single_timestep(self):
        """Simulate one 5-minute timestep and verify returned metrics."""
        engine = FloodEngine.from_default_data()
        dt = 300.0
        rain = np.full((200, 200), 30.0, dtype=np.float32)  # 30 mm/hr

        metrics = engine.simulate_timestep(dt, rain)

        self.assertIn("max_depth_m", metrics)
        self.assertIn("mean_depth_m", metrics)
        self.assertIn("surface_water_volume_m3", metrics)
        self.assertGreater(metrics["surface_water_volume_m3"], 0.0)
        self.assertTrue(np.all(engine.water_depth >= 0.0))

    def test_run_forecast_cloudburst(self):
        """Run complete 180-minute forecast and verify multi-horizon snapshots."""
        engine = FloodEngine.from_default_data()

        # Run cloudburst scenario
        snapshots = engine.run_forecast(scenario="cloudburst", horizon_minutes=180, dt=300.0)

        # Expected horizons: 0, 30, 60, 90, 120, 180
        for h in [0, 30, 60, 90, 120, 180]:
            self.assertIn(h, snapshots)
            self.assertEqual(snapshots[h].shape, (200, 200))
            self.assertTrue(np.all(snapshots[h] >= 0.0))

        # T=0 is dry, T=30 has significant localized flood depth
        self.assertEqual(float(np.max(snapshots[0])), 0.0)
        self.assertGreater(float(np.max(snapshots[30])), 0.02)

        # Pair C contract: get_forecast_grids
        grids = engine.get_forecast_grids()
        self.assertEqual(len(grids), 6)

    def test_timestep_performance_benchmark(self):
        """Timestep execution on 200x200 grid must run well under 0.5s (B2.14 target)."""
        engine = FloodEngine.from_default_data()
        dt = 300.0
        rain = np.full((200, 200), 40.0, dtype=np.float32)

        # Warm up
        engine.simulate_timestep(dt, rain)

        # Time 5 consecutive timesteps
        t0 = time.perf_counter()
        steps = 5
        for _ in range(steps):
            engine.simulate_timestep(dt, rain)
        t1 = time.perf_counter()

        avg_time = (t1 - t0) / steps
        print(f"\n[BENCHMARK] Average timestep duration on 200x200 grid: {avg_time * 1000:.2f} ms")

        # Must be < 0.5 seconds (500 ms)
        self.assertLess(avg_time, 0.5, f"Timestep took {avg_time:.3f}s which exceeds 0.5s limit!")

    def test_historical_mumbai_2023_july26(self):
        """Replay real Mumbai storm from July 26, 2023 via HistoricalRainfallProvider."""
        from backend.data.rainfall.provider import get_rainfall_provider

        hist_provider = get_rainfall_provider(
            mode="historical", lat=19.07, lon=72.85, date_str="2023-07-26", start_hour=11
        )
        engine = FloodEngine.from_default_data(rainfall_provider=hist_provider)

        snapshots = engine.run_forecast(scenario="historical", horizon_minutes=180, dt=300.0)

        # Verify all horizons captured
        for h in [0, 30, 60, 90, 120, 180]:
            self.assertIn(h, snapshots)

        # Real historical precipitation must accumulate water
        peak_depth = float(np.max(snapshots[180]))
        mean_depth = float(np.mean(snapshots[180]))
        self.assertGreater(peak_depth, 0.5, "Expected peak depth > 0.5m in Mumbai depressions")
        self.assertGreater(mean_depth, 0.01, "Expected average surface water > 1 cm")

        # Verify strict water mass conservation over total domain
        expected_surface = (
            engine.total_rain_volume_m3
            + engine.total_upstream_inflow_m3
            + engine.initial_river_storage_m3
            + engine.total_overflow_volume_m3
            + engine.total_surge_intrusion_m3
            - engine.total_infiltrated_volume_m3
            - engine.total_absorbed_volume_m3
            - engine.total_river_drain_volume_m3
            - engine.total_pumped_volume_m3
            - engine.total_boundary_outflow_m3
            - engine.retention_pond_storage_m3
        )
        actual_surface = float(np.sum(engine.water_depth) * engine.cell_area)
        self.assertAlmostEqual(expected_surface, actual_surface, places=1)

        # Land surface mass conservation
        expected_land_surface = expected_surface - engine.river_storage_m3
        actual_land_surface = float(np.sum(engine.water_depth[~engine.water_body_mask]) * engine.cell_area)
        self.assertAlmostEqual(expected_land_surface, actual_land_surface, places=1)

    def test_river_bankfull_overflow_and_spill(self):
        """Test that river overflows onto adjacent bank cells when storage exceeds bankfull capacity."""
        temp_engine = FloodEngine.from_default_data()
        cap = temp_engine.river_bankfull_capacity_m3
        init_storage = cap - 20000.0

        engine = FloodEngine.from_default_data(
            upstream_river_inflow_m3_s=50.0,   # 50 m3/s from upstream Powai/Vihar lakes
            tidal_lock=True,                    # High tide blocking downstream outflow
            initial_river_storage_m3=init_storage,
        )

        self.assertGreater(cap, 150000.0)

        # Before simulation: river has init_storage, land surface is dry
        self.assertEqual(engine.river_storage_m3, init_storage)
        self.assertEqual(float(np.sum(engine.water_depth[~engine.water_body_mask])), 0.0)

        # Step 1: Upstream inflow adds 50 m3/s * 300s = 15,000 m3 -> (< cap, no spill)
        rain_zero = np.zeros((engine.rows, engine.cols), dtype=np.float32)
        engine.simulate_timestep(300.0, rain_zero)
        self.assertEqual(engine.river_storage_m3, init_storage + 15000.0)
        self.assertEqual(engine.total_river_overflow_m3, 0.0)

        # Step 2 & 3: Add 30,000 m3 more -> exceeds cap -> Spill!
        engine.simulate_timestep(300.0, rain_zero)
        engine.simulate_timestep(300.0, rain_zero)

        # River MUST have spilled
        self.assertGreater(engine.total_river_overflow_m3, 0.0)
        self.assertEqual(engine.river_storage_m3, cap)

        # Water must now be present on river bank breach cells
        bank_depths = engine.water_depth[engine.river_bank_mask]
        self.assertTrue(np.any(bank_depths > 0.0), "River bank breach cells must have received spillover depth")
        self.assertGreater(float(np.sum(bank_depths)), 0.0)

        # Verify strict mass conservation
        total_in = (
            engine.total_rain_volume_m3
            + engine.total_upstream_inflow_m3
            + engine.initial_river_storage_m3
            + engine.total_overflow_volume_m3
        )
        total_out = (
            engine.total_infiltrated_volume_m3
            + engine.total_absorbed_volume_m3
            + engine.total_river_drain_volume_m3
        )
        expected_surface = total_in - total_out
        actual_surface = float(np.sum(engine.water_depth) * engine.cell_area)
        self.assertAlmostEqual(expected_surface, actual_surface, places=1)

    def test_soil_saturation_blocks_infiltration(self):
        """Precipitation should produce 100% direct runoff once soil moisture capacity is full."""
        # 1. Start with 100% pre-saturated soil
        engine_saturated = FloodEngine.from_default_data(antecedent_saturation_fraction=1.0)
        dt = 3600.0  # 1 hour
        light_rain = np.full((200, 200), 5.0, dtype=np.float32)  # 5 mm/hr

        added = engine_saturated.apply_rainfall(dt, light_rain)

        # Soil should absorb ZERO water on land because it is already completely saturated
        self.assertAlmostEqual(engine_saturated.total_infiltrated_volume_m3, 0.0, places=5)
        # All 5mm rain (0.005m) must become direct surface flood depth
        land = ~engine_saturated.water_body_mask
        self.assertAlmostEqual(float(np.mean(added[land])), 0.005, places=5)

        # 2. Compare with dry soil: dry soil absorbs the light rain
        engine_dry = FloodEngine.from_default_data(antecedent_saturation_fraction=0.0)
        added_dry = engine_dry.apply_rainfall(dt, light_rain)
        self.assertGreater(engine_dry.total_infiltrated_volume_m3, 0.0)
        self.assertLess(float(np.mean(added_dry[land])), 0.005)

    def test_drain_blockage_reduces_absorption(self):
        """Debris blockage should scale down drainage absorption proportionally."""
        class MockDrainage:
            def absorb_surface_water(self, depth_grid, dt):
                return np.full_like(depth_grid, 0.02)  # absorbs 2 cm everywhere

        # Case A: 100% clear (blockage factor = 1.0)
        engine_clear = FloodEngine.from_default_data(
            drainage_graph=MockDrainage(),
            drain_blockage_factor=1.0
        )
        engine_clear.water_depth[~engine_clear.water_body_mask] = 0.10
        vol_clear = engine_clear.calculate_drainage_absorption(300.0)

        # Case B: 65% capacity (blockage factor = 0.65)
        engine_blocked = FloodEngine.from_default_data(
            drainage_graph=MockDrainage(),
            drain_blockage_factor=0.65
        )
        engine_blocked.water_depth[~engine_blocked.water_body_mask] = 0.10
        vol_blocked = engine_blocked.calculate_drainage_absorption(300.0)

        # Blocked volume should be exactly 65% of clear volume
        self.assertAlmostEqual(vol_blocked / vol_clear, 0.65, places=4)

    def test_retention_pond_captures_runoff(self):
        """Stormwater retention ponds buffer surface runoff up to capacity."""
        engine = FloodEngine.from_default_data(
            enable_retention_ponds=True,
            retention_pond_capacity_m3=10000.0
        )
        self.assertGreater(int(engine.retention_pond_mask.sum()), 0)

        # Place 0.5m of surface water directly on pond cells
        engine.water_depth[engine.retention_pond_mask] = 0.50
        initial_pond_surface_vol = float(np.sum(engine.water_depth[engine.retention_pond_mask]) * engine.cell_area)

        # Step drain_retention_ponds
        engine.drain_retention_ponds(300.0)

        # Water should be transferred from surface into retention pond storage
        self.assertGreater(engine.retention_pond_storage_m3, 0.0)
        self.assertLess(float(np.sum(engine.water_depth[engine.retention_pond_mask]) * engine.cell_area), initial_pond_surface_vol)

    def test_pump_station_removes_water(self):
        """Pump stations should withdraw stormwater from specified cells and discharge out of domain."""
        pump_stations = [
            {"row": 100, "col": 100, "capacity_m3_s": 2.0, "operational": True},
            {"row": 120, "col": 120, "capacity_m3_s": 5.0, "operational": False},  # Failed pump
        ]
        engine = FloodEngine.from_default_data(pump_stations=pump_stations)

        # Place 1.0m of water on both pump station cells (100 m² cell area -> 100 m³ available)
        engine.water_depth[100, 100] = 1.0
        engine.water_depth[120, 120] = 1.0

        dt = 20.0  # 20 seconds
        pumped = engine.apply_pump_stations(dt)

        # Station 1: 2.0 m3/s * 20s = 40 m3 pumped
        self.assertAlmostEqual(pumped, 40.0, places=4)
        self.assertAlmostEqual(engine.total_pumped_volume_m3, 40.0, places=4)
        # Depth at (100, 100) reduced by 40 m³ / 100 m² = 0.4 m -> 0.6 m remains
        self.assertAlmostEqual(engine.water_depth[100, 100], 0.6, places=4)

        # Station 2: Failed pump removed 0 m³ -> depth remains 1.0 m
        self.assertAlmostEqual(engine.water_depth[120, 120], 1.0, places=4)

    def test_surface_porosity_and_street_depth(self):
        """Surface porosity must be in [0.35, 1.0] and get_street_depth >= water_depth."""
        engine = FloodEngine.from_default_data()
        self.assertTrue(np.all(engine.surface_porosity >= 0.35))
        self.assertTrue(np.all(engine.surface_porosity <= 1.0))
        # Water bodies and retention ponds have porosity 1.0
        self.assertTrue(np.all(engine.surface_porosity[engine.water_body_mask] == 1.0))
        if np.any(engine.retention_pond_mask):
            self.assertTrue(np.all(engine.surface_porosity[engine.retention_pond_mask] == 1.0))

        # Test get_street_depth
        engine.water_depth.fill(0.20)
        street_depth = engine.get_street_depth()
        self.assertTrue(np.all(street_depth >= engine.water_depth))
        # Dense land with imperviousness ~0.85 has porosity ~0.49 -> street depth ~0.40m
        dense_mask = engine.imperviousness > 0.80
        if np.any(dense_mask):
            self.assertGreater(float(np.mean(street_depth[dense_mask])), 0.35)

    def test_convective_disaggregation_volume_conservation(self):
        """Convective hyetograph multiplier must average to 1.0 across an hour (conserves 100% volume)."""
        from backend.data.rainfall.provider import compute_convective_hyetograph_multiplier
        multipliers = [compute_convective_hyetograph_multiplier(m) for m in range(60)]
        mean_mult = sum(multipliers) / 60.0
        self.assertAlmostEqual(mean_mult, 1.0, places=5)
        # Peak must occur near 22 min with intensity ~1.9x
        self.assertGreater(max(multipliers), 1.8)

    def test_mdd_gentle_slope_mass_conservation(self):
        """MDD routing on flat terrain must preserve 100% of water mass."""
        from backend.app.engine.surface_flow import route_surface_water
        # Create nearly flat terrain (slopes < 0.005)
        elev = np.zeros((30, 30), dtype=np.float32)
        for r in range(30):
            for c in range(30):
                elev[r, c] = 5.0 - 0.001 * (r + c)
        depth = np.zeros((30, 30), dtype=np.float32)
        depth[10:15, 10:15] = 0.50  # 5x5 puddle
        init_vol = float(np.sum(depth))

        routed, outflow = route_surface_water(
            elevation=elev,
            water_depth=depth,
            dt=60.0,
            cell_size_m=10.0,
            sub_passes=4,
            boundary_condition="closed",
        )
        final_vol = float(np.sum(routed))
        self.assertAlmostEqual(init_vol, final_vol, places=4)

    def test_all_subsystems_mass_conservation(self):
        """Verify strict water mass conservation when all subsystems (surge, pumps, ponds, upstream inflow) are active."""
        # Create a pond mask on dry land
        pond_mask = np.zeros((200, 200), dtype=bool)
        pond_mask[50:55, 50:55] = True

        pump_stations = [
            {"row": 80, "col": 80, "capacity_m3_s": 2.0, "radius_cells": 1, "operational": True}
        ]

        engine = FloodEngine.from_default_data(
            retention_pond_mask=pond_mask,
            retention_pond_capacity_m3=5000.0,
            pump_stations=pump_stations,
            storm_surge_m=1.0,
            upstream_river_inflow_m3_s=10.0,
        )

        dt = 300.0
        # Rain grid: 20 mm/hr
        rain_grid = np.full((200, 200), 20.0, dtype=np.float32)

        for _ in range(5):
            engine.simulate_timestep(dt, rain_grid)

        # Check that subsystems actually engaged
        self.assertGreater(engine.total_rain_volume_m3, 0.0)
        self.assertGreater(engine.total_upstream_inflow_m3, 0.0)
        self.assertGreater(engine.total_infiltrated_volume_m3, 0.0)
        self.assertGreater(engine.total_surge_intrusion_m3, 0.0)
        self.assertGreater(engine.total_pumped_volume_m3, 0.0)
        self.assertGreater(engine.total_pond_storage_inflow_m3, 0.0)

        # Full mass conservation across all active components
        expected_surface = (
            engine.total_rain_volume_m3
            + engine.total_upstream_inflow_m3
            + engine.initial_river_storage_m3
            + engine.total_overflow_volume_m3
            + engine.total_surge_intrusion_m3
            - engine.total_infiltrated_volume_m3
            - engine.total_absorbed_volume_m3
            - engine.total_river_drain_volume_m3
            - engine.total_pumped_volume_m3
            - engine.total_boundary_outflow_m3
            - engine.retention_pond_storage_m3
        )
        actual_surface = float(np.sum(engine.water_depth) * engine.cell_area)
        self.assertAlmostEqual(expected_surface, actual_surface, places=1)

    def test_robust_horizon_capture(self):
        """Verify that all forecast horizons are captured even with non-standard dt values (B5 fix)."""
        engine = FloodEngine.from_default_data()
        # dt = 420s (7 min) which does not evenly divide 30, 60, 90 min
        snapshots = engine.run_forecast(scenario="moderate", horizon_minutes=180, dt=420.0)
        for h in [0, 30, 60, 90, 120, 180]:
            self.assertIn(h, snapshots, f"Horizon {h} min missing with dt=420s")


if __name__ == "__main__":
    unittest.main()

