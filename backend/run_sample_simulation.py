"""
B2 Flood Engine Sample Demonstration Run.

Demonstrates:
1. Terrain loading & D8 flow direction computation
2. Cloudburst rainfall deposition (120 mm/hr burst)
3. 2D downhill overland runoff & depression ponding
4. Pair A interaction (drainage inlet absorption & pipe overflow)
5. Pair C interface (road flood depth checks & hazard classification)
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from backend.app.engine.flood_engine import FloodEngine
from backend.data.rainfall.provider import get_rainfall_provider


# 1. Mock Drainage Graph representing Pair A's network interface
class MockDrainageGraph:
    def __init__(self):
        # 3 drainage inlets in Mumbai study area
        self.inlets = [(60, 60), (120, 140), (160, 160)]
        self.blocked_node = "inlet_3"

    def absorb_surface_water(self, depth_grid: np.ndarray, dt: float) -> np.ndarray:
        absorbed = np.zeros_like(depth_grid)
        for r, c in self.inlets:
            # Drain can absorb up to 0.05m per timestep if water is present
            avail = depth_grid[r, c]
            take = min(avail, 0.05)
            absorbed[r, c] = take
        return absorbed

    def compute_overflow(self) -> dict:
        # The blocked inlet backs up and overflows 25 m^3 onto the road
        return {self.blocked_node: 25.0}

    def get_node_cell(self, node_id: str) -> tuple:
        return (160, 160)


def main():
    print("==================================================================")
    print("      B2 FLOOD ENGINE SAMPLE TEST RUN -- CLOUDBURST SCENARIO")
    print("==================================================================")

    # 2. Instantiate FloodEngine with real terrain & mock drainage
    mock_drainage = MockDrainageGraph()
    engine = FloodEngine.from_default_data(drainage_graph=mock_drainage)

    print(f"Domain: 200x200 grid (40,000 cells) | Cell Size: 10m x 10m (2km x 2km)")
    print(f"Topography: Min Elevation = {engine.dem.min():.2f}m, Max Elevation = {engine.dem.max():.2f}m")
    print(f"Depression Sinks Identified: {int(np.sum(engine.sinks_mask))} sink cells")
    print("------------------------------------------------------------------")

    # 3. Run full 3-hour forecast simulation (36 timesteps of 5 min)
    print("Simulating 180-minute Cloudburst Scenario (120 mm/hr localized burst)...")
    forecast = engine.run_forecast(scenario="cloudburst", horizon_minutes=180, dt=300.0)
    print("Simulation completed successfully!\n")

    # 4. Multi-Horizon Output Grids
    print("[1] Multi-Horizon Output Grids (Used by Frontend Heatmap & Pair C):")
    for t in [0, 30, 60, 90, 120, 180]:
        grid = forecast[t]
        max_d = float(np.max(grid))
        mean_d = float(np.mean(grid))
        flooded_15cm = int(np.sum(grid > 0.15))
        flooded_30cm = int(np.sum(grid > 0.30))
        print(f"   T+{t:3d} min -> Max Depth: {max_d:5.2f}m | Mean: {mean_d*100:4.2f}cm | Cells >15cm: {flooded_15cm:4d} | Cells >30cm: {flooded_30cm:4d}")

    # 5. Drainage Interaction with Pair A
    print("\n[2] Interaction with Pair A (Drainage Network):")
    print(f"   -> Surface water absorbed by storm drains: {engine.total_absorbed_volume_m3:10.1f} m^3")
    print(f"   -> Pipe back-pressure overflow erupted:   {engine.total_overflow_volume_m3:10.1f} m^3")

    # 6. Road Inundation Query with Pair C
    print("\n[3] Interface with Pair C (Emergency Vehicle Road Routing):")
    sample_roads = [
        ("SV Road (Lowlands)", 150, 150),
        ("Hill Road (Ridge)", 40, 50),
        ("Linking Road (Depression)", 160, 160),
    ]
    for road_name, r, c in sample_roads:
        depth_t30 = engine.forecast_grids[30][r, c]
        depth_t180 = engine.forecast_grids[180][r, c]
        if depth_t180 > 0.30:
            status = "BLOCKED / IMPASSABLE (>30cm)"
        elif depth_t180 > 0.10:
            status = "CAUTION (10-30cm)"
        else:
            status = "CLEAR (<10cm)"

        print(f"   Road: {road_name:<26} | Elev: {engine.dem[r,c]:4.1f}m | T+30: {depth_t30*100:4.1f}cm | T+180: {depth_t180*100:4.1f}cm -> {status}")

    # 7. Mass Balance
    print("\n[4] Water Conservation Balance:")
    print(f"   Gross Rain Deposited:   {engine.total_rain_volume_m3:10.1f} m^3")
    print(f"   Soil Infiltration:     -{engine.total_infiltrated_volume_m3:10.1f} m^3")
    print(f"   Drainage Absorbed:     -{engine.total_absorbed_volume_m3:10.1f} m^3")
    print(f"   Drainage Overflow:     +{engine.total_overflow_volume_m3:10.1f} m^3")
    actual_surface = float(np.sum(engine.water_depth) * engine.cell_area)
    print(f"   Final Surface Ponding:  {actual_surface:10.1f} m^3")
    print("==================================================================")


if __name__ == "__main__":
    main()
