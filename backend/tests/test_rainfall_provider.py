"""
Unit tests for RainfallProvider implementations, synthetic scenarios,
One Weather API nowcasting, and Doppler radar integration (B1.13).
"""

import unittest
import numpy as np

from backend.data.rainfall.provider import (
    RainfallProvider,
    DemoRainfallProvider,
    OneWeatherRadarNowcastProvider,
    LiveRainfallProvider,
    HistoricalRainfallProvider,
    SpatialHistoricalProvider,
    get_rainfall_provider,
)


class TestRainfallProvider(unittest.TestCase):
    def setUp(self):
        self.provider = DemoRainfallProvider(grid_shape=(200, 200), cell_size_m=10.0)

    def test_forecast_horizons_and_shapes(self):
        """All scenarios must produce grids of shape (200, 200) for standard horizons."""
        scenarios = ["moderate", "heavy", "extreme", "cloudburst", "extreme_blocked"]
        expected_horizons = [0, 30, 60, 90, 120, 180]

        for sc in scenarios:
            forecast = self.provider.generate_nowcast(scenario=sc, horizon_minutes=180)
            self.assertEqual(sorted(list(forecast.keys())), expected_horizons)
            for h in expected_horizons:
                grid = forecast[h]
                self.assertEqual(grid.shape, (200, 200), f"Mismatch in {sc} at T+{h}")
                self.assertTrue(np.all(grid >= 0.0), f"Negative rain rate in {sc} at T+{h}")

    def test_moderate_scenario_ramping(self):
        """Moderate scenario ramps up to peak around T=60 then ramps down."""
        forecast = self.provider.generate_nowcast(scenario="moderate")
        # Peak at T=60 should be ~10 mm/hr
        self.assertAlmostEqual(float(np.mean(forecast[60])), 10.0, places=1)
        # T=0 and T=120 should be lower than peak
        self.assertLess(float(np.mean(forecast[0])), 10.0)
        self.assertLess(float(np.mean(forecast[180])), 5.0)

    def test_cloudburst_scenario_intensity(self):
        """Cloudburst must reach 120 mm/hr in a concentrated zone during initial 30 min."""
        forecast = self.provider.generate_nowcast(scenario="cloudburst")
        self.assertAlmostEqual(float(np.max(forecast[0])), 120.0, places=1)
        self.assertAlmostEqual(float(np.max(forecast[30])), 120.0, places=1)
        # Stops after 30 min
        self.assertEqual(float(np.max(forecast[60])), 0.0)

    def test_marshall_palmer_conversion(self):
        """Validates Doppler radar reflectivity Marshall-Palmer conversion (Z = 200 * R^1.6)."""
        # 30 dBZ -> ~2.73 mm/hr
        rate_30 = RainfallProvider.dbz_to_rain_rate(30.0)
        self.assertAlmostEqual(rate_30, 2.734, places=2)

        # 50 dBZ -> ~48.64 mm/hr
        rate_50 = RainfallProvider.dbz_to_rain_rate(50.0)
        self.assertAlmostEqual(rate_50, 48.64, places=1)

        # Non-positive / very low reflectivity -> 0.0
        self.assertEqual(RainfallProvider.dbz_to_rain_rate(0.0), 0.0)
        self.assertEqual(RainfallProvider.rain_rate_to_dbz(0.0), 0.0)

        # Invertibility: round-trip consistency
        recovered_dbz = RainfallProvider.rain_rate_to_dbz(rate_30)
        self.assertAlmostEqual(recovered_dbz, 30.0, places=1)

        # Vectorized numpy array support
        dbz_arr = np.array([0.0, 20.0, 30.0, 50.0], dtype=np.float32)
        rates_arr = RainfallProvider.dbz_to_rain_rate(dbz_arr)
        self.assertEqual(rates_arr.shape, (4,))
        self.assertAlmostEqual(float(rates_arr[2]), 2.734, places=2)

    def test_one_weather_radar_nowcast_provider(self):
        """Tests high-resolution nowcast generation with radar integration."""
        provider = OneWeatherRadarNowcastProvider(
            lat=19.07,
            lon=72.85,
            grid_shape=(200, 200),
            cell_size_m=10.0,
            use_radar=True,
            demo_fallback=True,
        )
        forecast = provider.generate_nowcast(horizon_minutes=180)
        expected_horizons = [0, 30, 60, 90, 120, 180]
        self.assertEqual(sorted(list(forecast.keys())), expected_horizons)

        for h in expected_horizons:
            grid = forecast[h]
            self.assertEqual(grid.shape, (200, 200))
            self.assertTrue(np.all(grid >= 0.0))

        # Continuous rain rate grid
        rate_grid = provider.get_rain_rate_grid(minute=45.0)
        self.assertIsNotNone(rate_grid)
        self.assertEqual(rate_grid.shape, (200, 200))

        # Reflectivity grid
        dbz_grid = provider.get_radar_reflectivity_grid(minute=0.0)
        self.assertIsNotNone(dbz_grid)
        self.assertEqual(dbz_grid.shape, (200, 200))
        self.assertTrue(np.all(dbz_grid >= 0.0))

        # Current rainfall
        current_rain = provider.get_current_rainfall()
        self.assertIsInstance(current_rain, float)
        self.assertGreaterEqual(current_rain, 0.0)

    def test_radar_frames_retrieval(self):
        """Tests radar frames metadata retrieval."""
        provider = OneWeatherRadarNowcastProvider(lat=19.07, lon=72.85)
        frames = provider.get_radar_frames(limit=3)
        self.assertIsInstance(frames, list)
        self.assertGreater(len(frames), 0)
        frame = frames[0]
        self.assertIn("timestamp", frame)
        self.assertIn("tile_url", frame)
        self.assertIn("estimated_peak_dbz", frame)
        self.assertIn("estimated_rain_rate_mmh", frame)

    def test_historical_provider_preserved(self):
        """Verifies HistoricalRainfallProvider and SpatialHistoricalProvider remain intact."""
        hist = HistoricalRainfallProvider(
            lat=19.07,
            lon=72.85,
            date_str="2023-07-26",
            start_hour=10,
            grid_shape=(200, 200),
            cell_size_m=10.0,
        )
        nowcast = hist.generate_nowcast(horizon_minutes=60)
        self.assertIn(0, nowcast)
        self.assertEqual(nowcast[0].shape, (200, 200))

        spatial_hist = SpatialHistoricalProvider(
            lat=19.07,
            lon=72.85,
            date_str="2023-07-26",
            start_hour=10,
            grid_shape=(200, 200),
            cell_size_m=10.0,
        )
        sp_nowcast = spatial_hist.generate_nowcast(horizon_minutes=60)
        self.assertIn(0, sp_nowcast)
        self.assertEqual(sp_nowcast[0].shape, (200, 200))

    def test_factory_function(self):
        """Factory helper returns correct provider instance for all supported modes."""
        demo = get_rainfall_provider("demo")
        self.assertIsInstance(demo, DemoRainfallProvider)

        one_weather = get_rainfall_provider("one_weather", lat=19.07, lon=72.85)
        self.assertIsInstance(one_weather, OneWeatherRadarNowcastProvider)

        radar = get_rainfall_provider("radar", lat=19.07, lon=72.85)
        self.assertIsInstance(radar, OneWeatherRadarNowcastProvider)

        live = get_rainfall_provider("live", lat=19.07, lon=72.85)
        self.assertIsInstance(live, OneWeatherRadarNowcastProvider)

        hist = get_rainfall_provider("historical", lat=19.07, lon=72.85, date_str="2023-07-26")
        self.assertIsInstance(hist, HistoricalRainfallProvider)

        spatial = get_rainfall_provider("spatial_historical", lat=19.07, lon=72.85, date_str="2023-07-26")
        self.assertIsInstance(spatial, SpatialHistoricalProvider)


if __name__ == "__main__":
    unittest.main()
