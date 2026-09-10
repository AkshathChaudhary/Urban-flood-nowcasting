"""
Automated Integration Tests for FastAPI Endpoints (Task B2.13).
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.main import app


class TestFastAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create test client with lifecycle context
        cls.client = TestClient(app)

    def test_root_and_health(self):
        """Test root info and healthcheck endpoints."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["domain"]["rows"], 200)
        self.assertEqual(data["domain"]["cols"], 200)

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "healthy")

    def test_get_flood_forecast_overview(self):
        """Test GET /api/flood-forecast returns multi-horizon overview."""
        res = self.client.get("/api/flood-forecast")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("horizons", data)
        self.assertIn("summaries", data)
        self.assertEqual(data["horizons"], [0, 30, 60, 90, 120, 180])

        # Check summary properties for T+60
        summary_60 = data["summaries"]["60"]
        self.assertIn("max_depth_m", summary_60)
        self.assertIn("flooded_cells_15cm", summary_60)
        self.assertIn("surface_water_volume_m3", summary_60)

    def test_get_flood_forecast_grid_by_horizon(self):
        """Test GET /api/flood-forecast/{minutes} returns full 200x200 grid."""
        res = self.client.get("/api/flood-forecast/60")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["horizon_minutes"], 60)
        self.assertEqual(data["rows"], 200)
        self.assertEqual(data["cols"], 200)
        self.assertEqual(len(data["depth_grid"]), 200)
        self.assertEqual(len(data["depth_grid"][0]), 200)

        # Invalid horizon test
        bad_res = self.client.get("/api/flood-forecast/999")
        self.assertEqual(bad_res.status_code, 404)

    def test_point_depth_query(self):
        """Test point inundation queries by grid cell and lat/lon."""
        # Query by cell indices
        res = self.client.get("/api/flood-forecast/point/query?row=50&col=50")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["row"], 50)
        self.assertEqual(data["col"], 50)
        self.assertIn("depth_m_at_horizon", data)
        self.assertIn("hazard_level", data)
        self.assertIn(data["hazard_level"], ["CLEAR", "CAUTION", "IMPASSABLE"])

        # Query by lat/lon coordinates
        geo_res = self.client.get("/api/flood-forecast/point/query?lat=19.065&lon=72.855")
        self.assertEqual(geo_res.status_code, 200)

        # Missing coordinates should return 400
        bad_res = self.client.get("/api/flood-forecast/point/query")
        self.assertEqual(bad_res.status_code, 400)

    def test_post_simulate(self):
        """Test POST /api/simulate triggering a custom on-demand scenario run."""
        payload = {
            "scenario": "cloudburst",
            "horizon_minutes": 180,
            "dt_seconds": 300.0,
        }
        res = self.client.post("/api/simulate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["scenario"], "cloudburst")
        self.assertEqual(data["horizons"], [0, 30, 60, 90, 120, 180])
        # Cloudburst must show positive water volume
        self.assertGreater(data["total_rain_volume_m3"], 0.0)


if __name__ == "__main__":
    unittest.main()
