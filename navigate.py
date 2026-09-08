"""
Interactive Live Navigation CLI (Pair C)
========================================

Runs the flood-resilient routing engine in real-time:
1. Automatically retrieves the user's current live location (with intelligent bounding box handling).
2. Takes destination as interactive input (landmark name or coordinates).
3. Takes vehicle type (Car, SUV, Ambulance, Truck, Pedestrian).
4. Evaluates flood conditions (dry vs real-time flood simulation).
5. Outputs turn-by-turn safe navigation instructions, travel time, and roads avoided.
6. Saves `live_navigation_route.geojson`.
"""

import sys
import json
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np

from backend.models.routing import RoutingEngine, VEHICLE_THRESHOLDS
from backend.models.location import get_live_location, resolve_destination, STUDY_AREA_LANDMARKS


def run_navigation():
    print("=" * 70)
    print(" 🚗 URBAN FLOOD NOWCASTING — REAL-TIME RESILIENT NAVIGATION")
    print("=" * 70)

    # 1. Acquire Live Location
    print("\n[1/4] Acquiring live user location...")
    live_loc = get_live_location()
    src_lon, src_lat = live_loc["lon"], live_loc["lat"]
    print(f"  📍 Current Location: {live_loc['location_name']}")
    print(f"  Coordinates: [{src_lat:.5f}° N, {src_lon:.5f}° E]")
    if live_loc.get("is_clamped"):
        print(f"  ℹ️  {live_loc['message']}")

    # 2. Get Destination from User
    print("\n[2/4] Available Destination Landmarks in Study Area:")
    sample_landmarks = list(STUDY_AREA_LANDMARKS.keys())[:8]
    print("  Options: " + ", ".join([l.title() for l in sample_landmarks]) + ", or enter 'lat, lon'")
    
    dest_input = input("\n👉 Enter Destination [Default: 'Kurla Station']: ").strip()
    if not dest_input:
        dest_input = "Kurla Station"

    dst_lon, dst_lat, dest_name = resolve_destination(dest_input)
    print(f"  🎯 Destination Resolved: {dest_name}")
    print(f"  Coordinates: [{dst_lat:.5f}° N, {dst_lon:.5f}° E]")

    # 3. Select Vehicle Type
    print("\n[3/4] Select Vehicle Class:")
    print("  1. Standard Car / Sedan (30 cm water wading limit)")
    print("  2. SUV (45 cm water wading limit)")
    print("  3. Emergency Ambulance (45 cm limit + 15% arterial priority)")
    print("  4. Heavy Rescue Truck (60 cm water wading limit)")
    print("  5. Pedestrian (15 cm safe wading limit)")
    
    v_choice = input("👉 Select Vehicle [1-5, Default: 1 (Car)]: ").strip()
    v_map = {"1": "car", "2": "suv", "3": "ambulance", "4": "truck", "5": "pedestrian"}
    vehicle_type = v_map.get(v_choice, "car")
    clearance_cm = int(VEHICLE_THRESHOLDS[vehicle_type] * 100)
    print(f"  🚙 Selected: {vehicle_type.capitalize()} (Safe Wading Limit: {clearance_cm} cm)")

    # 4. Flood Conditions Simulation
    print("\n[4/4] Road Weather / Flood Conditions:")
    print("  1. Dry Road Network (Baseline shortest path)")
    print("  2. Moderate Monsoon Ponding (15 cm low-point water accumulation)")
    print("  3. Severe Flash Flood Inundation (40 cm water over low-elevation roads)")
    
    f_choice = input("👉 Select Flood Scenario [1-3, Default: 3 (Severe Flood)]: ").strip()
    
    mock_depth_grid = None
    if f_choice == "2":
        mock_depth_grid = np.zeros((200, 200), dtype=np.float32)
        print("  ⚠️ Applying 15 cm moderate ponding across lowlands...")
    elif f_choice != "1":
        # Default severe flood (40cm on low-lying crossings)
        mock_depth_grid = np.zeros((200, 200), dtype=np.float32)
        print("  🌊 Simulating 40 cm severe flash flood across low-elevation corridors...")

    # Initialize Engine & Calculate Route
    print("\nCalculating flood-resilient route using A* with vehicle clearance physics...")
    engine = RoutingEngine()

    if mock_depth_grid is not None:
        sim_depth = 0.15 if f_choice == "2" else 0.40
        for edge in engine.edge_attributes.values():
            if edge.get("elevation_m", 10.0) <= 3.8:
                r = edge.get("midpoint_grid_row", 0)
                c = edge.get("midpoint_grid_col", 0)
                mock_depth_grid[r, c] = sim_depth

    routes = engine.find_alternative_routes(
        src=(src_lon, src_lat),
        dst=(dst_lon, dst_lat),
        vehicle_type=vehicle_type,
        depth_grid=mock_depth_grid,
        max_alternatives=2,
    )

    if not routes or not routes[0].get("route_found"):
        print("\n❌ NO SAFE ROUTE FOUND:")
        print("  All viable street corridors to destination exceed your vehicle's wading clearance.")
        print("  Recommendation: Dispatch heavy rescue truck or wait for drainage recession.")
        return

    primary = routes[0]
    print("\n" + "=" * 70)
    print(f" ✅ SAFE ROUTE FOUND ({dest_name.upper()})")
    print("=" * 70)
    print(f"  📏 Total Travel Distance : {primary['distance_m']:.1f} meters ({(primary['distance_m']/1000):.2f} km)")
    print(f"  ⏱️ Estimated Travel Time : {primary['travel_time_min']:.1f} minutes")
    print(f"  🌊 Maximum Water Depth   : {primary['max_flood_depth_m']*100:.1f} cm")
    print(f"  🛡️ Safety / Flood Risk   : {primary['flood_risk']}")
    print(f"  🛣️ Road Segments Traversed: {primary['segment_count']} segments")

    roads_traversed = primary.get("roads_traversed", [])
    if roads_traversed:
        print("\n  📍 Turn-by-Turn Key Corridors:")
        seen_names = []
        for r in roads_traversed:
            name = r.get("name", "Unnamed Road")
            if not seen_names or seen_names[-1] != name:
                seen_names.append(name)
        for i, nm in enumerate(seen_names[:8], 1):
            print(f"     {i}. {nm}")
        if len(seen_names) > 8:
            print(f"     ... and {len(seen_names) - 8} more streets")

    roads_avoided = primary.get("roads_avoided", [])
    if roads_avoided:
        print(f"\n  🚫 Submerged Roads Safely Avoided ({len(roads_avoided)} segments):")
        avoided_names = list(set(r.get("name", "Road") for r in roads_avoided[:5]))
        for an in avoided_names:
            print(f"     • {an}")

    if len(routes) > 1:
        print("\n  🔀 Alternative Safe Detours Available:")
        for idx, alt in enumerate(routes[1:], 1):
            print(f"     Detour {idx}: {alt['distance_m']:.0f}m | {alt['travel_time_min']:.1f} min | Risk: {alt['flood_risk']}")

    # Save to GeoJSON for visualization
    out_file = Path("live_navigation_route.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(primary["geojson"], f, indent=2)
    print(f"\n  💾 Exported route vector layer to: {out_file}")
    print("=" * 70)


if __name__ == "__main__":
    run_navigation()
