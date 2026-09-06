"""
Unit tests for RainfallProvider implementations and synthetic scenarios (B1.13).
"""

import unittest
import numpy as np

from backend.data.rainfall.provider import (
    DemoRainfallProvider,
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

    def test_factory_function(self):
        """Factory helper returns correct provider instance."""
        demo = get_rainfall_provider("demo")
        self.assertIsInstance(demo, DemoRainfallProvider)


if __name__ == "__main__":
    unittest.main()
