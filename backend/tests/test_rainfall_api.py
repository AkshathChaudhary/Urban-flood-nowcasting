"""
Integration tests for /api/rainfall endpoints.
"""
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app


class TestRainfallAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_rainfall_overview(self):
        """Test GET /api/rainfall/overview returns horizons, summaries, and radar frames."""
        res = self.client.get("/api/rainfall/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("scenario", data)
        self.assertIn("current_rain_rate_mmh", data)
        self.assertIn("api_source", data)
        self.assertIn("horizons", data)
        self.assertIn("summaries", data)
        self.assertEqual(data["horizons"], [0, 30, 60, 90, 120, 180])

        summary_0 = data["summaries"]["0"]
        self.assertIn("max_rate_mmh", summary_0)
        self.assertIn("max_reflectivity_dbz", summary_0)
        self.assertIn("is_raining", summary_0)

    def test_get_rainfall_grid_by_horizon(self):
        """Test GET /api/rainfall/nowcast/{minutes} returns full 200x200 rain and reflectivity grids."""
        res = self.client.get("/api/rainfall/nowcast/30")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["horizon_minutes"], 30)
        self.assertEqual(data["rows"], 200)
        self.assertEqual(data["cols"], 200)
        self.assertEqual(len(data["rain_rate_grid"]), 200)
        self.assertEqual(len(data["rain_rate_grid"][0]), 200)
        self.assertEqual(len(data["reflectivity_dbz_grid"]), 200)
        self.assertEqual(len(data["reflectivity_dbz_grid"][0]), 200)

        # Non-existent horizon
        bad_res = self.client.get("/api/rainfall/nowcast/999")
        self.assertEqual(bad_res.status_code, 404)

    def test_query_point_rainfall(self):
        """Test GET /api/rainfall/point/query by row/col and lat/lon."""
        # Query by cell indices
        res = self.client.get("/api/rainfall/point/query?row=100&col=100")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["row"], 100)
        self.assertEqual(data["col"], 100)
        self.assertIn("rain_rate_mmh_at_horizon", data)
        self.assertIn("reflectivity_dbz_at_horizon", data)
        self.assertIn(data["intensity_category"], ["NONE", "LIGHT", "MODERATE", "HEAVY", "CLOUDBURST"])

        # Query by lat/lon
        geo_res = self.client.get("/api/rainfall/point/query?lat=19.07&lon=72.85")
        self.assertEqual(geo_res.status_code, 200)

        # Missing params should be 400
        bad_res = self.client.get("/api/rainfall/point/query")
        self.assertEqual(bad_res.status_code, 400)

    def test_get_radar_frames(self):
        """Test GET /api/rainfall/radar/frames returns list of radar frames."""
        res = self.client.get("/api/rainfall/radar/frames?limit=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
