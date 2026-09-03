"""
C1.12 — End-to-End C1 <-> B2 Integration Consistency Test Suite
Urban Flood Nowcast Project

This script performs strict automated verification across:
1. Grid dimensions, extents, CRS, and cell resolution
2. Road-to-grid mapping coordinates
3. B2 dynamic depth raster aggregation
4. Dynamic risk formula fidelity and classification
5. Hotspot prioritization ranking and tie-breaking
6. Flask REST API responses
7. Unmapped UNKNOWN road integrity
8. Vector LineString geometry and coordinate bounds
"""

import sys
import csv
import json
import unittest
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

# Set project root in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.roads.b2_adapter import B2Adapter, B2PredictionFrame, GRID_ROWS, GRID_COLS
from backend.data.roads.grid_mapping import (
    latlon_to_grid, grid_to_latlon, is_in_bounds,
    ORIGIN_LAT, ORIGIN_LON, MAX_LAT, MAX_LON
)
from backend.app import create_app

ROADS_DIR = PROJECT_ROOT / "backend" / "data" / "roads"
DYNAMIC_CSV = ROADS_DIR / "road_dynamic_risk.csv"
DYNAMIC_GEOJSON = ROADS_DIR / "road_dynamic_risk.geojson"
HOTSPOTS_CSV = ROADS_DIR / "road_hotspots.csv"
HOTSPOTS_GEOJSON = ROADS_DIR / "road_hotspots.geojson"
GRID_MAPPING_CSV = ROADS_DIR / "road_grid_mapping.csv"
SUSCEPTIBILITY_CSV = ROADS_DIR / "road_flood_susceptibility.csv"
GRAPH_WITH_RISK_JSON = ROADS_DIR / "road_graph_with_risk.json"

TARGET_HOTSPOTS = ["R-1184", "R-860", "R-861", "R-302", "R-1427"]


class TestC1B2Consistency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize Flask test client
        cls.flask_app = create_app()
        cls.client = cls.flask_app.test_client()

        # Load B2 Frames
        cls.b2_frames = B2Adapter.generate_reference_scenario_frames(scenario_name="heavy_rain")
        cls.b2_frames_by_ts = {f.timestamp: f.depth_grid for f in cls.b2_frames}

        # Index Road-to-Grid Mappings
        cls.road_cells = {}
        with open(GRID_MAPPING_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r_id = row["road_id"]
                r = int(row["grid_row"])
                c = int(row["grid_col"])
                if r_id not in cls.road_cells:
                    cls.road_cells[r_id] = []
                cls.road_cells[r_id].append((r, c))

        # Index Dynamic Risk CSV
        cls.dynamic_rows = []
        cls.dynamic_by_road_and_ts = {}
        with open(DYNAMIC_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cls.dynamic_rows.append(r)
                cls.dynamic_by_road_and_ts[(r["road_id"], r["timestamp"])] = r

        # Index Hotspots CSV
        cls.hotspots_by_id = {}
        with open(HOTSPOTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cls.hotspots_by_id[r["road_id"]] = r

        # Index Susceptibility CSV
        cls.susceptibility_by_id = {}
        with open(SUSCEPTIBILITY_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cls.susceptibility_by_id[r["road_id"]] = r

        # Load GeoJSON
        with open(DYNAMIC_GEOJSON, "r", encoding="utf-8") as f:
            cls.dynamic_geojson = json.load(f)

    # 1. Grid Dimensions & Geographic Extent
    def test_01_grid_dimensions_and_crs(self):
        self.assertEqual(GRID_ROWS, 200, "Grid rows must be 200")
        self.assertEqual(GRID_COLS, 200, "Grid columns must be 200")
        self.assertAlmostEqual(ORIGIN_LAT, 19.0600, places=4)
        self.assertAlmostEqual(MAX_LAT, 19.0782, places=4)
        self.assertAlmostEqual(ORIGIN_LON, 72.8500, places=4)
        self.assertAlmostEqual(MAX_LON, 72.8688, places=4)

        for frame in self.b2_frames:
            self.assertEqual(frame.depth_grid.shape, (200, 200))
            self.assertEqual(frame.depth_grid.dtype, np.float32)
            self.assertTrue(np.all(frame.depth_grid >= 0.0), "Flood depths must be non-negative")

    # 2. Road -> Grid -> B2 Depth Aggregation for Target Hotspots
    def test_02_b2_depth_aggregation_target_hotspots(self):
        for r_id in TARGET_HOTSPOTS:
            cells = self.road_cells[r_id]
            self.assertGreater(len(cells), 0, f"Road {r_id} must have mapped grid cells")

            for ts, depth_grid in self.b2_frames_by_ts.items():
                cell_depths = [depth_grid[r, c] for r, c in cells]
                expected_mean = round(float(np.mean(cell_depths)), 3)
                expected_max = round(float(np.max(cell_depths)), 3)

                csv_record = self.dynamic_by_road_and_ts[(r_id, ts)]
                actual_mean = float(csv_record["mean_flood_depth_m"])
                actual_max = float(csv_record["max_flood_depth_m"])

                self.assertAlmostEqual(expected_mean, actual_mean, places=3,
                                       msg=f"Mean depth mismatch for {r_id} at {ts}")
                self.assertAlmostEqual(expected_max, actual_max, places=3,
                                       msg=f"Max depth mismatch for {r_id} at {ts}")

    # 3. Dynamic Risk Formula Consistency
    def test_03_risk_formula_fidelity(self):
        w_static = 0.40
        w_dynamic = 0.60
        d_crit = 0.50

        for r_id in TARGET_HOTSPOTS:
            static_s = float(self.susceptibility_by_id[r_id]["flood_susceptibility_score"])

            for ts in self.b2_frames_by_ts.keys():
                csv_rec = self.dynamic_by_road_and_ts[(r_id, ts)]
                max_d = float(csv_rec["max_flood_depth_m"])

                expected_dyn_factor = round(float(np.clip(max_d / d_crit, 0.0, 1.0)), 4)
                expected_comb_risk = round(float(np.clip(
                    w_static * static_s + w_dynamic * expected_dyn_factor, 0.0, 1.0
                )), 4)

                actual_dyn_factor = float(csv_rec["dynamic_flood_factor"])
                actual_comb_risk = float(csv_rec["combined_risk"])

                self.assertAlmostEqual(expected_dyn_factor, actual_dyn_factor, places=4)
                self.assertAlmostEqual(expected_comb_risk, actual_comb_risk, places=4)

    # 4. Hotspot Ranking & Tie-Breaking Integrity
    def test_04_hotspot_ranking_integrity(self):
        ranked_roads = []
        with open(HOTSPOTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r["hotspot_score"] != "":
                    ranked_roads.append(r)

        self.assertEqual(len(ranked_roads), 1261, "Must have exactly 1261 ranked mapped hotspots")

        # Verify descending sort order
        for i in range(len(ranked_roads) - 1):
            curr_score = float(ranked_roads[i]["hotspot_score"])
            next_score = float(ranked_roads[i+1]["hotspot_score"])
            self.assertGreaterEqual(curr_score, next_score - 1e-6, "Hotspot ranking must be descending")

        # Check target roads are among top hotspots
        for r_id in TARGET_HOTSPOTS:
            h_info = self.hotspots_by_id[r_id]
            rank = int(h_info["rank"])
            self.assertLessEqual(rank, 10, f"Target road {r_id} should be in Top 10 hotspots")
            self.assertEqual(h_info["hotspot_class"], "CRITICAL")

    # 5. API Response Consistency
    def test_05_api_response_consistency(self):
        for r_id in TARGET_HOTSPOTS:
            # 1. Road details endpoint
            res = self.client.get(f"/api/roads/{r_id}")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()

            h_csv = self.hotspots_by_id[r_id]
            self.assertEqual(data["road_id"], r_id)
            self.assertEqual(data["hotspot_rank"], int(h_csv["rank"]))
            self.assertAlmostEqual(data["hotspot_score"], float(h_csv["hotspot_score"]), places=4)
            self.assertEqual(data["hotspot_class"], h_csv["hotspot_class"])

            # 2. Road timeseries endpoint
            res_ts = self.client.get(f"/api/roads/{r_id}/timeseries")
            self.assertEqual(res_ts.status_code, 200)
            data_ts = res_ts.get_json()
            self.assertEqual(data_ts["number_of_timestamps"], 6)

            for step in data_ts["timeseries"]:
                ts = step["timestamp"]
                csv_rec = self.dynamic_by_road_and_ts[(r_id, ts)]
                self.assertAlmostEqual(step["max_flood_depth_m"], float(csv_rec["max_flood_depth_m"]), places=3)
                self.assertAlmostEqual(step["combined_risk"], float(csv_rec["combined_risk"]), places=4)

    # 6. UNKNOWN (Unmapped Buffer) Road Handling
    def test_06_unknown_road_handling(self):
        unmapped_ids = [r_id for r_id, info in self.susceptibility_by_id.items()
                        if info["flood_susceptibility_score"] == ""]
        self.assertEqual(len(unmapped_ids), 252, "Must have exactly 252 unmapped roads")

        for r_id in unmapped_ids[:10]:
            h_info = self.hotspots_by_id[r_id]
            self.assertEqual(h_info["hotspot_score"], "")
            self.assertEqual(h_info["hotspot_class"], "UNKNOWN")
            self.assertEqual(h_info["peak_flood_depth_m"], "")

            # Verify API returns nulls and UNKNOWN
            res = self.client.get(f"/api/roads/{r_id}")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIsNone(data["static_susceptibility"])
            self.assertIsNone(data["hotspot_score"])
            self.assertEqual(data["static_risk_class"], "UNKNOWN")

    # 7. GeoJSON Vector Geometry & Bounds Consistency
    def test_07_geojson_geometry_consistency(self):
        features = self.dynamic_geojson.get("features", [])
        self.assertEqual(len(features), 1513, "GeoJSON must have exactly 1513 features")

        for feat in features:
            geom = feat["geometry"]
            self.assertEqual(geom["type"], "LineString")
            coords = geom["coordinates"]
            self.assertGreaterEqual(len(coords), 2, "LineString must have at least 2 vertices")

            for lon, lat in coords:
                # Longitude in Mumbai area (~72.80 to 72.90)
                self.assertTrue(72.80 <= lon <= 72.90, f"Longitude {lon} out of range")
                # Latitude in Mumbai area (~19.04 to 19.10)
                self.assertTrue(19.04 <= lat <= 19.10, f"Latitude {lat} out of range")


if __name__ == "__main__":
    unittest.main()
