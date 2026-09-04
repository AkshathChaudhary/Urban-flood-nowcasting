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
        """Precipitation below infiltration rate should be absorbed into soil."""
        engine = FloodEngine.from_default_data()
        dt = 3600.0  # 1 hour

        # Light rain: 1.0 mm/hr (well below minimum infiltration of ~1.5 mm/hr)
        light_rain = np.full((200, 200), 1.0, dtype=np.float32)
        added = engine.apply_rainfall(dt, light_rain)

        # Net added water should be zero or negligible
        self.assertAlmostEqual(float(np.max(added)), 0.0, places=5)
        self.assertAlmostEqual(float(np.max(engine.water_depth)), 0.0, places=5)

        # Heavy rain: 50 mm/hr (significantly exceeds infiltration)
        heavy_rain = np.full((200, 200), 50.0, dtype=np.float32)
        added_heavy = engine.apply_rainfall(dt, heavy_rain)

        self.assertGreater(float(np.mean(added_heavy)), 0.04)  # ~45mm = 0.045m
        self.assertGreater(float(np.mean(engine.water_depth)), 0.04)

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

        # Verify strict water mass conservation (including drainage and river dynamics)
        expected_surface = (
            engine.total_rain_volume_m3
            + engine.total_upstream_inflow_m3
            + engine.initial_river_storage_m3
            - engine.total_infiltrated_volume_m3
            - engine.total_absorbed_volume_m3
            + engine.total_overflow_volume_m3
            - engine.total_river_drain_volume_m3
            - engine.river_storage_m3
        )
        actual_surface = float(np.sum(engine.water_depth) * engine.cell_area)
        self.assertAlmostEqual(expected_surface, actual_surface, places=1)

    def test_river_bankfull_overflow_and_spill(self):
        """Test that river overflows onto adjacent bank cells when storage exceeds bankfull capacity."""
        engine = FloodEngine.from_default_data(
            upstream_river_inflow_m3_s=50.0,   # 50 m3/s from upstream Powai/Vihar lakes
            tidal_lock=True,                    # High tide blocking downstream outflow
            initial_river_storage_m3=250000.0,  # 88% full initially
        )

        cap = engine.river_bankfull_capacity_m3
        self.assertGreater(cap, 200000.0)

        # Before simulation: river has 250,000 m3, land surface is dry
        self.assertEqual(engine.river_storage_m3, 250000.0)
        self.assertEqual(float(np.sum(engine.water_depth)), 0.0)

        # Step 1: Upstream inflow adds 50 m3/s * 300s = 15,000 m3 -> 265,000 m3 (< cap, no spill)
        rain_zero = np.zeros((engine.rows, engine.cols), dtype=np.float32)
        engine.simulate_timestep(300.0, rain_zero)
        self.assertEqual(engine.river_storage_m3, 265000.0)
        self.assertEqual(engine.total_river_overflow_m3, 0.0)

        # Step 2 & 3: Add 30,000 m3 more -> 295,000 m3 > cap (282,420 m3) -> Spill!
        engine.simulate_timestep(300.0, rain_zero)
        engine.simulate_timestep(300.0, rain_zero)

        # River MUST have spilled
        self.assertGreater(engine.total_river_overflow_m3, 0.0)
        self.assertEqual(engine.river_storage_m3, cap)

        # Water must now be present on river bank cells
        bank_depths = engine.water_depth[engine.river_bank_mask]
        self.assertTrue(np.all(bank_depths > 0.0), "All river bank cells must have received spillover depth")

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
        expected_surface = total_in - total_out - engine.river_storage_m3
        actual_surface = float(np.sum(engine.water_depth) * engine.cell_area)
        self.assertAlmostEqual(expected_surface, actual_surface, places=1)


if __name__ == "__main__":
    unittest.main()
