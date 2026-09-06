"""
Unit tests for D8 surface flow routing and hydrological routines.
"""

import math
import unittest
import numpy as np

from backend.app.engine.surface_flow import (
    compute_d8_flow_directions,
    identify_sinks,
    route_surface_water,
)


class TestSurfaceFlow(unittest.TestCase):
    def test_d8_tilted_plane(self):
        """A plane sloping uniformly East should direct all flow East (direction 0)."""
        rows, cols = 20, 20
        # Elevation decreases from left to right (Eastward slope)
        dem = np.tile(np.linspace(100, 50, cols, dtype=np.float32), (rows, 1))

        flow_dirs = compute_d8_flow_directions(dem, cell_size_m=10.0)

        # Interior cells should all point East (0)
        interior = flow_dirs[:, :-1]
        self.assertTrue(np.all(interior == 0))

    def test_sink_detection(self):
        """A local depression surrounded by higher ground must be identified as a sink."""
        dem = np.full((7, 7), 20.0, dtype=np.float32)
        # Center cell is 5 meters lower
        dem[3, 3] = 15.0

        flow_dirs = compute_d8_flow_directions(dem, cell_size_m=10.0)
        sinks = identify_sinks(dem, flow_dirs)

        self.assertEqual(flow_dirs[3, 3], -1)
        self.assertTrue(sinks[3, 3])
        # Neighbors of the sink should drain towards center (3, 3)
        self.assertEqual(flow_dirs[2, 3], 2)  # South
        self.assertEqual(flow_dirs[4, 3], 6)  # North
        self.assertEqual(flow_dirs[3, 2], 0)  # East
        self.assertEqual(flow_dirs[3, 4], 4)  # West

    def test_water_conservation_closed_boundary(self):
        """In a closed boundary domain, surface water volume must be strictly conserved."""
        rows, cols = 30, 30
        cell_size = 10.0
        # Bowl terrain: lowest in middle
        y, x = np.ogrid[:rows, :cols]
        dem = 10.0 + ((y - rows // 2) ** 2 + (x - cols // 2) ** 2) * 0.1

        # Add initial pool of water
        water_depth = np.zeros((rows, cols), dtype=np.float32)
        water_depth[10:20, 10:20] = 0.5  # 50 cm of water

        initial_volume = float(np.sum(water_depth) * (cell_size ** 2))

        # Run multiple timesteps of overland flow
        current_depth = water_depth.copy()
        for _ in range(5):
            current_depth, outflow = route_surface_water(
                elevation=dem,
                water_depth=current_depth,
                dt=300.0,
                cell_size_m=cell_size,
                sub_passes=4,
                boundary_condition="closed",
            )
            self.assertEqual(outflow, 0.0)

        final_volume = float(np.sum(current_depth) * (cell_size ** 2))

        # Volume must match within floating-point precision
        self.assertAlmostEqual(initial_volume, final_volume, places=3)
        self.assertTrue(np.all(current_depth >= 0.0))

    def test_water_flows_downhill(self):
        """Water placed at the high side of a slope should move downhill."""
        rows, cols = 15, 15
        dem = np.tile(np.linspace(50, 10, cols, dtype=np.float32), (rows, 1))

        # Place water only on upper/western edge
        water_depth = np.zeros((rows, cols), dtype=np.float32)
        water_depth[:, 0] = 1.0  # 1 meter

        routed_depth, _ = route_surface_water(
            elevation=dem,
            water_depth=water_depth,
            dt=300.0,
            cell_size_m=10.0,
            sub_passes=4,
            boundary_condition="closed",
        )

        # Downhill cells (e.g. col 1, 2) should have received water
        self.assertGreater(float(np.sum(routed_depth[:, 1:4])), 0.0)
        # Source cell depth should have decreased
        self.assertLess(float(np.mean(routed_depth[:, 0])), 1.0)


if __name__ == "__main__":
    unittest.main()
