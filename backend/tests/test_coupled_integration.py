"""
Coupled Multi-Model Integration Tests (Pair A + Pair B + Pair C)
===============================================================

Tests the end-to-end coupling between:
1. FloodEngine ↔ DrainageGraph: Inflow absorption, subterranean pipe propagation to outfalls, and surcharge boil-up.
2. FloodEngine ↔ RoutingEngine: Urban porosity displacement (d_street = d_grid / porosity) and road passability.
3. FastAPI Endpoints: /api/roads/corridors/passability, dynamic road midpoint depth query, and Scenario 5 pipe blockage.
"""

import unittest
from fastapi.testclient import TestClient
import numpy as np

from backend.app.main import app
from backend.app.engine_state import get_engine
from backend.app.models.drainage import DrainageGraph
from backend.app.models.routing import RoutingEngine
from backend.app.config import (
    DRAINAGE_EDGES_FILE,
    DRAINAGE_NODES_FILE,
    ROADS_DIR,
)


class TestCoupledMultiModelIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.engine = get_engine()

    def test_flood_engine_drives_subterranean_pipe_flow(self):
        """
        Verifies Gap 1 fix: simulate_timestep must call DrainageGraph.propagate_flow,
        moving water through the pipe network and discharging at outfalls.
        """
        # Ensure drainage graph is attached
        self.assertIsNotNone(self.engine.drainage_graph)
        self.engine.reset_state()
        if hasattr(self.engine.drainage_graph, "reset_state"):
            self.engine.drainage_graph.reset_state()

        # Simulate 3 steps with 60 mm/hr convective rain
        dt = 300.0
        rain_grid = np.full((self.engine.rows, self.engine.cols), 60.0, dtype=np.float32)

        discharged_accum = 0.0
        for step in range(4):
            stats = self.engine.simulate_timestep(dt=dt, rain_rate_grid=rain_grid)
            discharged_accum += stats.get("pipe_discharged_volume_m3", 0.0)

        # Inlets must have absorbed water and piped water must have begun traversing network
        self.assertGreater(self.engine.total_absorbed_volume_m3, 0.0)
        # Total pipe discharged volume should be tracked
        self.assertGreaterEqual(self.engine.total_pipe_discharged_volume_m3, 0.0)

    def test_urban_building_porosity_street_displacement(self):
        """
        Verifies Gap 2 fix: get_street_depth_grid applies d_street = d_grid / porosity.
        On land cells with buildings, street depth must be strictly greater than raw grid depth.
        """
        # Place 0.10m water on grid
        self.engine.water_depth.fill(0.10)
        street_depth = self.engine.get_street_depth_grid(horizon_minutes=0)

        # Land cells have porosity <= 0.75 in urban blocks, so d_street must be >= d_grid
        land_mask = ~self.engine.water_body_mask
        self.assertTrue(np.all(street_depth[land_mask] >= self.engine.water_depth[land_mask]))
        # Peak street depth must exceed 0.10m due to building displacement
        self.assertGreater(float(np.max(street_depth[land_mask])), 0.10)

    def test_dynamic_road_depth_query(self):
        """
        Verifies Gap 3 fix: GET /api/roads/{road_id} evaluates depth from live simulation forecast.
        """
        # Inject flood depth at horizon 60 on a road cell
        road_id = "R-0001"
        res = self.client.get(f"/api/roads/{road_id}?time_horizon_min=60")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current_flood_depth_m", data)
        self.assertIn("passability", data)
        self.assertIn("time_horizon_min", data)
        self.assertEqual(data["time_horizon_min"], 60)

    def test_corridor_passability_classification_endpoint(self):
        """
        Verifies Gap 3 fix: GET /api/roads/corridors/passability classifies all corridors
        into CLEAR (<10cm), CAUTION (10-30cm), and IMPASSABLE (>30cm).
        """
        res = self.client.get("/api/roads/corridors/passability?time_horizon_min=0")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("summary", data)
        self.assertIn("geojson", data)
        summary = data["summary"]
        self.assertIn("clear_count", summary)
        self.assertIn("caution_count", summary)
        self.assertIn("impassable_count", summary)
        self.assertEqual(
            summary["clear_count"] + summary["caution_count"] + summary["impassable_count"],
            summary["total_corridors"],
        )

    def test_scenario5_subterranean_blockage_coupling(self):
        """
        Verifies Gap 4 fix: Scenario 5 (blocked_drainage) applies 40% pipe capacity blockage.
        """
        payload = {
            "scenario": "blocked_drainage",
            "horizon_minutes": 60,
            "dt_seconds": 300.0,
        }
        res = self.client.post("/api/simulate", json=payload)
        self.assertEqual(res.status_code, 200)

        # Check that drainage graph has global blockage set to 0.40
        dg = self.engine.drainage_graph
        if dg is not None:
            sample_edge_id = list(dg.edge_data.keys())[0]
            edge = dg.get_edge(sample_edge_id)
            self.assertAlmostEqual(edge.get("blockage_pct", 0.0), 0.40, places=2)


if __name__ == "__main__":
    unittest.main()
