"""
Unit & Integration Tests for Drainage Model (Pair A)
=====================================================

Tests hydraulic physics, Manning's equation, surface water absorption,
gravity flow propagation, debris blockage effects, surcharge overflow,
and FastAPI endpoint responses.
"""

import math
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import numpy as np

from backend.main import app
from backend.models.drainage import DrainageGraph

NODES_PATH = Path("backend/data/drainage/drainage_nodes.geojson")
EDGES_PATH = Path("backend/data/drainage/drainage_edges.geojson")


class TestDrainageModelPhysics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Instantiate graph once for physics validation."""
        cls.graph = DrainageGraph(NODES_PATH, EDGES_PATH, cell_size_m=10.0)

    def setUp(self):
        """Reset state before each test."""
        self.graph.reset_state()
        self.graph.set_global_blockage(0.0)

    def test_manning_equation_calculation(self):
        """
        Validates Manning's equation against an exact analytical calculation:
        Q = (1/n) * A * R^(2/3) * S^(1/2)
        """
        edge_id = list(self.graph.edge_data.keys())[0]
        edge = self.graph.edge_data[edge_id]

        d = edge["diameter_m"]
        n = edge["roughness_n"]
        s = edge["slope"]

        # Analytical hand-calculation
        area = math.pi * ((d / 2.0) ** 2)
        r = d / 4.0
        expected_q = (1.0 / n) * area * (r ** (2.0 / 3.0)) * math.sqrt(s)

        computed_q = self.graph.compute_pipe_capacity(edge_id)
        self.assertAlmostEqual(computed_q, expected_q, places=4)

    def test_blockage_effect(self):
        """
        Verifies that a 40% blockage reduces effective pipe capacity by exactly 40%.
        """
        edge_id = list(self.graph.edge_data.keys())[0]
        cap_clean = self.graph.compute_pipe_capacity(edge_id)

        # Apply 40% blockage
        self.graph.set_blockage(edge_id, 0.40)
        cap_blocked = self.graph.compute_pipe_capacity(edge_id)

        self.assertAlmostEqual(cap_blocked, cap_clean * 0.60, places=4)

    def test_absorption_constraints(self):
        """
        Verifies surface water absorption constraints:
        1. Cannot absorb more water than is present on the surface.
        2. Cannot absorb more water than the inlet capacity allows in dt.
        """
        depth_grid = np.zeros((200, 200), dtype=np.float32)

        # Find first inlet node
        inlet_node = next(n for n in self.graph.node_data.values() if n["type"] == "inlet")
        r, c = inlet_node["grid_row"], inlet_node["grid_col"]
        cap = inlet_node["capacity_m3s"]
        dt = 300.0  # 5 minutes

        # Sub-test 1: Very shallow puddle (0.01m = 1 cm)
        depth_grid[r, c] = 0.01
        absorbed = self.graph.absorb_surface_water(depth_grid, dt=dt)
        # Should absorb exactly 0.01m (entire puddle)
        self.assertAlmostEqual(float(absorbed[r, c]), 0.01, places=4)

        # Sub-test 2: Deep flood exceeding inlet capacity
        # Inlet cap * dt / cell_area = cap * 300 / 100 = 3 * cap meters
        self.graph.reset_state()
        depth_grid[r, c] = 100.0  # extreme flood
        absorbed = self.graph.absorb_surface_water(depth_grid, dt=dt)
        expected_absorbed_depth = (cap * dt) / 100.0
        self.assertAlmostEqual(float(absorbed[r, c]), expected_absorbed_depth, places=3)

    def test_flow_propagation_and_discharge(self):
        """
        Tests water propagating downstream and discharging through outfalls.
        """
        # Inject water into a high-elevation node
        high_node_id = max(
            self.graph.node_data.keys(),
            key=lambda nid: self.graph.node_data[nid]["elevation_m"],
        )
        test_volume = 100.0  # 100 m³
        self.graph.current_water_m3[high_node_id] = test_volume

        # Propagate flow
        self.graph.propagate_flow(dt=300.0)

        summary = self.graph.get_network_summary()
        # Conservation of water: stored + discharged must equal initial injected volume
        total_remaining = summary["current_water_stored_m3"] + summary["total_discharged_m3"]
        self.assertAlmostEqual(total_remaining, test_volume, places=1)

    def test_overflow_surcharge(self):
        """
        Tests overflow detection when a node receives water exceeding its holding capacity.
        """
        inlet_node = next(n for n in self.graph.node_data.values() if n["type"] == "inlet")
        node_id = inlet_node["id"]
        dt = 300.0
        max_cap = inlet_node["capacity_m3s"] * dt

        # Inject 3x the allowable capacity
        self.graph.current_water_m3[node_id] = max_cap * 3.0

        overflow = self.graph.compute_overflow(dt=dt)
        self.assertIn(node_id, overflow)
        self.assertAlmostEqual(overflow[node_id], max_cap * 2.0, places=2)
        # Node volume should now be capped at max_cap
        self.assertAlmostEqual(self.graph.current_water_m3[node_id], max_cap, places=2)


class TestPairBIntegrationContract(unittest.TestCase):
    def test_simulation_cycle(self):
        """
        Simulates the interaction between Pair B (FloodEngine) and Pair A (DrainageGraph).
        Verifies:
        1. FloodEngine supplies surface depth grid.
        2. DrainageGraph absorbs surface water and returns absorption grid.
        3. DrainageGraph propagates pipe flow.
        4. DrainageGraph computes overflow and returns surcharge coordinates.
        """
        graph = DrainageGraph(NODES_PATH, EDGES_PATH, cell_size_m=10.0)
        dt = 300.0

        # Simulate 200x200 flood surface with 0.15m water depth across the city
        surface_depth = np.full((200, 200), 0.15, dtype=np.float32)
        initial_surface_water = surface_depth.sum()

        # Step 1: Absorb
        absorbed_grid = graph.absorb_surface_water(surface_depth, dt=dt)
        surface_depth -= absorbed_grid
        self.assertLess(surface_depth.sum(), initial_surface_water)

        # Step 2: Propagate
        discharged_m3 = graph.propagate_flow(dt=dt)
        self.assertGreater(discharged_m3, 0.0)

        # Step 3: Check overflow
        overflow = graph.compute_overflow(dt=dt)
        for node_id, vol_m3 in overflow.items():
            r, c = graph.get_node_cell(node_id)
            # Re-inject overflow onto surface
            surface_depth[r, c] += vol_m3 / graph.cell_area_m2


class TestFastAPIDrainageEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_summary_endpoint(self):
        res = self.client.get("/api/drainage/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_nodes"], 1000)
        self.assertGreater(data["total_edges"], 1000)

    def test_nodes_endpoint(self):
        res = self.client.get("/api/drainage/nodes?node_type=inlet")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertTrue(len(data["features"]) > 0)
        self.assertEqual(data["features"][0]["properties"]["type"], "inlet")

    def test_edges_endpoint(self):
        res = self.client.get("/api/drainage/edges")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertIn("effective_capacity_m3s", data["features"][0]["properties"])

    def test_blockage_update(self):
        res = self.client.post("/api/drainage/blockage", json={"blockage_pct": 0.4})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")


if __name__ == "__main__":
    unittest.main()
