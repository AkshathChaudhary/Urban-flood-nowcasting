"""
Unit & Integration Tests for Road Graph & Dynamic Routing Engine (Pair C)
========================================================================

Tests:
1. Road graph loading, schema adherence, and spatial indexing.
2. A* flood-resilient shortest path calculation.
3. Penalty weighting rules (2x for 5-15cm, 5x for 15-30cm, inf for >= clearance).
4. Vehicle clearance tolerances (pedestrian, car, SUV, truck, ambulance).
5. Dynamic route avoidance of submerged streets.
6. Alternative safe routes generation.
7. FastAPI REST endpoints for roads and routing.
"""

import math
import unittest
from pathlib import Path
import numpy as np
import httpx

from backend.main import app
from backend.models.routing import RoutingEngine, VEHICLE_THRESHOLDS

ROAD_GEOJSON = Path("backend/data/roads/road_network.geojson")
ROAD_GRAPH = Path("backend/data/roads/road_graph.json")


class TestRoutingEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Instantiate RoutingEngine once for tests."""
        cls.engine = RoutingEngine(ROAD_GEOJSON, ROAD_GRAPH)
        cls.node_ids = list(cls.engine.node_positions.keys())

    def setUp(self):
        """Reset weights to dry conditions before each test."""
        self.engine.apply_flood_weights(depth_grid=None, vehicle_type="car")

    def test_graph_structure_and_counts(self):
        """Validates that nodes and edges are populated with valid attributes."""
        summary = self.engine.get_network_summary()
        self.assertGreater(summary["total_nodes"], 500)
        self.assertGreater(summary["total_directed_edges"], 1000)
        self.assertGreater(summary["total_length_km"], 50.0)
        self.assertIn("residential", summary["highway_type_breakdown"])

    def test_snap_to_nearest_node(self):
        """Verifies vectorized nearest node snapping for arbitrary coordinates."""
        # Query near Kurla station / Mithi River
        test_lon, test_lat = 72.8624, 19.0764
        nid = self.engine.snap_to_nearest_node(test_lon, test_lat)
        self.assertIn(nid, self.engine.node_positions)
        node_lon, node_lat = self.engine.node_positions[nid]
        # Snap should be within reasonable distance (< 200m)
        diff_deg = math.sqrt((test_lon - node_lon)**2 + (test_lat - node_lat)**2)
        self.assertLess(diff_deg, 0.005)

    def test_dry_weather_routing(self):
        """Verifies baseline A* shortest path between two points under dry conditions."""
        src = self.engine.node_positions[self.node_ids[5]]
        dst = self.engine.node_positions[self.node_ids[80]]

        route = self.engine.find_route(src, dst, vehicle_type="car")
        self.assertTrue(route["route_found"])
        self.assertGreater(route["distance_m"], 0.0)
        self.assertGreater(route["travel_time_min"], 0.0)
        self.assertEqual(route["flood_risk"], "SAFE")
        self.assertEqual(route["geojson"]["type"], "Feature")

    def test_penalty_weight_rules(self):
        """
        Validates penalty weighting:
        - 0.05m - 0.15m: 2x base weight
        - 0.15m - 0.30m: 5x base weight
        - >= 0.30m: infinite weight (impassable for car)
        """
        mock_depth = np.zeros((200, 200), dtype=np.float32)
        sample_edge = list(self.engine.edge_attributes.values())[0]
        r, c = sample_edge["midpoint_grid_row"], sample_edge["midpoint_grid_col"]
        base_w = sample_edge["base_weight"]

        # 1. Depth = 0.08m (moderate) -> 2.0x weight
        mock_depth[r, c] = 0.08
        self.engine.apply_flood_weights(mock_depth, vehicle_type="car")
        self.assertAlmostEqual(sample_edge["weight"], base_w * 2.0, places=2)
        self.assertEqual(sample_edge["status"], "CAUTION")

        # 2. Depth = 0.20m (severe) -> 5.0x weight
        mock_depth[r, c] = 0.20
        self.engine.apply_flood_weights(mock_depth, vehicle_type="car")
        self.assertAlmostEqual(sample_edge["weight"], base_w * 5.0, places=2)
        self.assertEqual(sample_edge["status"], "HIGH_RISK")

        # 3. Depth = 0.35m (above 0.30m car threshold) -> inf weight
        mock_depth[r, c] = 0.35
        self.engine.apply_flood_weights(mock_depth, vehicle_type="car")
        self.assertTrue(math.isinf(sample_edge["weight"]))
        self.assertEqual(sample_edge["status"], "BLOCKED")

    def test_vehicle_clearance_differences(self):
        """
        Tests that an identical 0.35m flood blocks a sedan (threshold 0.30m)
        but remains passable for an SUV (threshold 0.45m) and truck (0.60m).
        """
        mock_depth = np.zeros((200, 200), dtype=np.float32)
        sample_edge = list(self.engine.edge_attributes.values())[0]
        r, c = sample_edge["midpoint_grid_row"], sample_edge["midpoint_grid_col"]
        mock_depth[r, c] = 0.35

        # Car: Blocked
        res_car = self.engine.apply_flood_weights(mock_depth, vehicle_type="car")
        self.assertTrue(math.isinf(sample_edge["weight"]))

        # SUV: Passable with heavy delay
        res_suv = self.engine.apply_flood_weights(mock_depth, vehicle_type="suv")
        self.assertFalse(math.isinf(sample_edge["weight"]))
        self.assertEqual(sample_edge["status"], "HIGH_RISK")

        # Truck: Passable with heavy delay
        res_truck = self.engine.apply_flood_weights(mock_depth, vehicle_type="truck")
        self.assertFalse(math.isinf(sample_edge["weight"]))

        # Pedestrian: Blocked (threshold 0.15m)
        res_ped = self.engine.apply_flood_weights(mock_depth, vehicle_type="pedestrian")
        self.assertTrue(math.isinf(sample_edge["weight"]))

    def test_ambulance_priority_bonus(self):
        """Tests that ambulance gets priority travel time bonus on primary corridors."""
        # Find a primary edge
        primary_edges = [
            e for e in self.engine.edge_attributes.values()
            if e["highway_type"] in ["primary", "trunk", "motorway"]
        ]
        if primary_edges:
            edge = primary_edges[0]
            base_w = edge["base_weight"]

            self.engine.apply_flood_weights(None, vehicle_type="car")
            car_weight = edge["weight"]

            self.engine.apply_flood_weights(None, vehicle_type="ambulance")
            amb_weight = edge["weight"]

            self.assertAlmostEqual(amb_weight, car_weight * 0.85, places=2)

    def test_route_avoidance_of_flooded_corridor(self):
        """
        Verifies that when a corridor along the primary route is submerged,
        the routing engine detours around it and reports the avoided road.
        """
        src = self.engine.node_positions[self.node_ids[10]]
        dst = self.engine.node_positions[self.node_ids[60]]

        # Dry route
        dry_route = self.engine.find_route(src, dst, vehicle_type="car")
        self.assertTrue(dry_route["route_found"])
        traversed = dry_route["roads_traversed"]

        if len(traversed) >= 3:
            # Flood the middle road segment to 0.50m (deep flood)
            mid_road_id = traversed[len(traversed) // 2]["id"]
            road_data = self.engine.roads_by_id[mid_road_id]
            r, c = road_data["midpoint_grid_row"], road_data["midpoint_grid_col"]

            mock_depth = np.zeros((200, 200), dtype=np.float32)
            mock_depth[r, c] = 0.50

            flood_route = self.engine.find_route(src, dst, vehicle_type="car", depth_grid=mock_depth)
            
            # If an alternative path exists, verify it doesn't traverse the blocked road
            if flood_route["route_found"]:
                flood_traversed_ids = [e["id"] for e in flood_route["roads_traversed"]]
                self.assertNotIn(mid_road_id, flood_traversed_ids)

    def test_alternative_routes_generation(self):
        """Verifies generation of distinct alternative routes."""
        src = self.engine.node_positions[self.node_ids[10]]
        dst = self.engine.node_positions[self.node_ids[90]]

        alts = self.engine.find_alternative_routes(src, dst, vehicle_type="car", max_alternatives=2)
        self.assertGreaterEqual(len(alts), 1)
        self.assertTrue(alts[0]["route_found"])

    def test_routing_under_complete_inundation(self):
        """All edges flooded to 2.0m; verify graceful impassability without exceptions."""
        deep_flood = np.full((200, 200), 2.0, dtype=np.float32)
        src = self.engine.node_positions[self.node_ids[10]]
        dst = self.engine.node_positions[self.node_ids[90]]
        res = self.engine.find_route(src, dst, vehicle_type="car", depth_grid=deep_flood)
        self.assertFalse(res["route_found"])
        self.assertIn("roads_avoided", res)
        self.assertGreater(len(res["roads_avoided"]), 0)

    def test_identical_origin_destination(self):
        """Verify routing from point A to point A returns zero distance cleanly."""
        src = self.engine.node_positions[self.node_ids[10]]
        res = self.engine.find_route(src, src, vehicle_type="car")
        self.assertTrue(res["route_found"])
        self.assertEqual(res["distance_m"], 0.0)
        self.assertEqual(res["travel_time_min"], 0.0)

    def test_thread_safe_independent_vehicle_queries(self):
        """
        Tests that querying with pedestrian (15cm limit) under 25cm flood does NOT
        pollute subsequent or concurrent truck queries (60cm limit).
        """
        mock_depth = np.full((200, 200), 0.25, dtype=np.float32)
        src = self.engine.node_positions[self.node_ids[10]]
        dst = self.engine.node_positions[self.node_ids[60]]

        # Pedestrian query: should be blocked
        res_ped = self.engine.find_route(src, dst, vehicle_type="pedestrian", depth_grid=mock_depth)
        self.assertFalse(res_ped["route_found"])

        # Truck query on the same engine instance: should be passable
        res_truck = self.engine.find_route(src, dst, vehicle_type="truck", depth_grid=mock_depth)
        self.assertTrue(res_truck["route_found"])


class SyncASGIClient:
    def __init__(self, app):
        self.app = app
        self.transport = httpx.ASGITransport(app=app)

    def get(self, url, **kwargs):
        import asyncio
        async def _req():
            async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as c:
                return await c.get(url, **kwargs)
        return asyncio.run(_req())

    def post(self, url, **kwargs):
        import asyncio
        async def _req():
            async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as c:
                return await c.post(url, **kwargs)
        return asyncio.run(_req())


class TestRoutingAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = SyncASGIClient(app)

    def test_get_roads_summary(self):
        resp = self.client.get("/api/roads/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_nodes", data)
        self.assertIn("total_length_km", data)

    def test_get_roads_network_geojson(self):
        resp = self.client.get("/api/roads/network?highway_type=residential")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertGreater(len(data["features"]), 0)

    def test_get_flood_hotspots(self):
        resp = self.client.get("/api/roads/hotspots")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertGreater(len(data["features"]), 0)

    def test_get_individual_road(self):
        resp = self.client.get("/api/roads/R-0001")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], "R-0001")
        self.assertIn("passability", data)

    def test_get_vehicle_specs(self):
        resp = self.client.get("/api/route/vehicles")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("vehicle_types", data)
        self.assertIn("ambulance", data["vehicle_types"])

    def test_calculate_flood_route_endpoint(self):
        payload = {
            "src_lon": 72.8624,
            "src_lat": 19.0764,
            "dst_lon": 72.8556,
            "dst_lat": 19.0635,
            "vehicle_type": "suv",
            "include_alternatives": True,
        }
        resp = self.client.post("/api/route", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("route_found"))
        self.assertIn("primary_route", data)

    def test_current_location_endpoint(self):
        resp = self.client.get("/api/route/current-location")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("lon", data)
        self.assertIn("lat", data)
        self.assertIn("location_name", data)

    def test_live_navigate_endpoint(self):
        payload = {
            "destination": "Kurla Station",
            "vehicle_type": "car",
            "include_alternatives": True,
        }
        resp = self.client.post("/api/route/navigate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("route_found"))
        self.assertIn("primary_route", data)
        self.assertIn("destination", data)


if __name__ == "__main__":
    unittest.main()
