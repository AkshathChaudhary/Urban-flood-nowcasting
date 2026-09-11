"""
Interactive Live Navigation CLI (Multi-City & Arbitrary Corridor Support)
========================================================================

Runs the flood-resilient routing engine in real-time across multiple urban environments:
1. Supports both Mumbai BKC (2x2 km pilot) and Kolkata EM Bypass (Kestopur -> Ruby, 12 km corridor).
2. Automatically retrieves user's live location or provides city-specific default origin anchors.
3. Takes destination as interactive input (landmark name or coordinates).
4. Evaluates flood conditions (dry vs real-time flood simulation) with adaptive-resolution physics.
5. Employs vehicle-specific wading clearance thresholds (Car, SUV, Ambulance, Truck, Pedestrian).
6. Outputs turn-by-turn safe navigation instructions, travel time, and submerged roads avoided.
7. Exports `live_navigation_route.geojson` for instant GIS/web visualization.
"""

import argparse
import json
import sys
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np

from backend.models.routing import RoutingEngine, VEHICLE_THRESHOLDS
from backend.models.location import (
    CITY_CONFIGS,
    get_live_location,
    resolve_destination,
    detect_city_from_text_or_coords,
    STUDY_AREA_LANDMARKS,
    KOLKATA_LANDMARKS,
)


def run_navigation():
    parser = argparse.ArgumentParser(description="Urban Flood Resilient Navigation")
    parser.add_argument("--city", choices=["mumbai", "kolkata"], help="Target operational city (mumbai or kolkata)")
    parser.add_argument("--src", help="Source landmark name or 'lat, lon'")
    parser.add_argument("--dst", help="Destination landmark name or 'lat, lon'")
    parser.add_argument("--vehicle", choices=["car", "suv", "ambulance", "truck", "pedestrian"], help="Vehicle class")
    parser.add_argument("--flood", choices=["dry", "moderate", "severe"], help="Flood scenario")
    args = parser.parse_args()

    print("=" * 75)
    print(" 🚗 URBAN FLOOD NOWCASTING — MULTI-CITY RESILIENT NAVIGATION ENGINE")
    print("=" * 75)

    # 0. City Selection
    selected_city = args.city
    if not selected_city:
        print("\n[0/4] Select Operational Study Corridor:")
        print("  1. Mumbai — Bandra-Kurla Complex (BKC) / Mithi River Basin (2x2 km Pilot)")
        print("  2. Kolkata — EM Bypass Corridor: Kestopur to Ruby General Hospital (12 km)")
        c_choice = input("👉 Select City [1-2, Default: 2 (Kolkata)]: ").strip()
        selected_city = "mumbai" if c_choice == "1" else "kolkata"

    city_cfg = CITY_CONFIGS.get(selected_city, CITY_CONFIGS["kolkata"])
    print(f"\n  🏙️ Operational City Active: {city_cfg['name']}")

    # 1. Acquire Live Location / Origin
    print(f"\n[1/4] Acquiring User Origin in {selected_city.capitalize()}...")
    if args.src:
        src_lon, src_lat, src_name = resolve_destination(args.src, city=selected_city)
        print(f"  📍 Origin Specified: {src_name} [{src_lat:.5f}° N, {src_lon:.5f}° E]")
    else:
        live_loc = get_live_location(city=selected_city)
        src_lon, src_lat = live_loc["lon"], live_loc["lat"]
        print(f"  📍 Origin Anchor: {live_loc['location_name']}")
        print(f"  Coordinates: [{src_lat:.5f}° N, {src_lon:.5f}° E]")
        if live_loc.get("is_clamped"):
            print(f"  ℹ️  {live_loc['message']}")

        # Allow user to customize origin if desired
        custom_src = input(f"👉 Press ENTER to use [{live_loc['location_name']}] or type origin landmark: ").strip()
        if custom_src:
            src_lon, src_lat, src_name = resolve_destination(custom_src, city=selected_city)
            print(f"  📍 Origin Updated: {src_name} [{src_lat:.5f}° N, {src_lon:.5f}° E]")

    # 2. Get Destination
    print(f"\n[2/4] Available Destination Landmarks in {selected_city.capitalize()} Corridor:")
    landmarks_dict = city_cfg["landmarks"]
    sample_landmarks = list(landmarks_dict.keys())[:10]
    print("  Options: " + ", ".join([l.title() for l in sample_landmarks]) + ", or enter 'lat, lon'")

    default_dest = "Ruby Hospital" if selected_city == "kolkata" else "Kurla Station"
    if args.dst:
        dest_input = args.dst
    else:
        dest_input = input(f"\n👉 Enter Destination [Default: '{default_dest}']: ").strip()
        if not dest_input:
            dest_input = default_dest

    dst_lon, dst_lat, dest_name = resolve_destination(dest_input, city=selected_city)
    print(f"  🎯 Destination Resolved: {dest_name}")
    print(f"  Coordinates: [{dst_lat:.5f}° N, {dst_lon:.5f}° E]")

    # 3. Select Vehicle Type
    print("\n[3/4] Select Vehicle Class:")
    print("  1. Standard Car / Sedan (30 cm water wading limit)")
    print("  2. SUV (45 cm water wading limit)")
    print("  3. Emergency Ambulance (45 cm limit + 15% arterial priority)")
    print("  4. Heavy Rescue Truck (60 cm water wading limit)")
    print("  5. Pedestrian (15 cm safe wading limit)")

    if args.vehicle:
        vehicle_type = args.vehicle
    else:
        v_choice = input("👉 Select Vehicle [1-5, Default: 1 (Car)]: ").strip()
        v_map = {"1": "car", "2": "suv", "3": "ambulance", "4": "truck", "5": "pedestrian"}
        vehicle_type = v_map.get(v_choice, "car")

    clearance_cm = int(VEHICLE_THRESHOLDS[vehicle_type] * 100)
    print(f"  🚙 Selected: {vehicle_type.capitalize()} (Safe Wading Limit: {clearance_cm} cm)")

    # 4. Flood Conditions Simulation
    print("\n[4/4] Road Weather / Flood Conditions:")
    print("  1. Dry Road Network (Baseline shortest path)")
    print("  2. Moderate Monsoon Ponding (15 cm low-point water accumulation)")
    print("  3. Severe Flash Flood Inundation (40 cm water over low-elevation corridors)")

    if args.flood:
        f_choice_map = {"dry": "1", "moderate": "2", "severe": "3"}
        f_choice = f_choice_map.get(args.flood, "3")
    else:
        f_choice = input("👉 Select Flood Scenario [1-3, Default: 3 (Severe Flood)]: ").strip()

    grid_rows, grid_cols, cell_size_m = city_cfg["grid"]
    mock_depth_grid = None

    if f_choice == "2":
        mock_depth_grid = np.zeros((grid_rows, grid_cols), dtype=np.float32)
        print(f"  ⚠️ Applying 15 cm moderate ponding across {selected_city.capitalize()} lowlands...")
    elif f_choice != "1":
        mock_depth_grid = np.zeros((grid_rows, grid_cols), dtype=np.float32)
        print(f"  🌊 Simulating 40 cm severe flash flood across low-elevation {selected_city.capitalize()} corridors...")

    # Initialize Engine & Calculate Route
    print(f"\nInitializing RoutingEngine for {city_cfg['name']}...")
    engine = RoutingEngine(
        geojson_path=city_cfg["roads_geojson"],
        graph_path=city_cfg["roads_graph"],
    )

    # Apply flood depth to low-lying elevation segments
    if mock_depth_grid is not None:
        sim_depth = 0.15 if f_choice == "2" else 0.40
        # Elevation threshold for low-lying water accumulation
        elev_threshold = 3.3 if selected_city == "kolkata" else 3.8

        for edge in engine.edge_attributes.values():
            if edge.get("elevation_m", 10.0) <= elev_threshold:
                r = edge.get("midpoint_grid_row", 0)
                c = edge.get("midpoint_grid_col", 0)
                if 0 <= r < grid_rows and 0 <= c < grid_cols:
                    mock_depth_grid[r, c] = sim_depth

    print("Calculating flood-resilient route using A* with vehicle clearance physics...")
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
        print(f"  Vehicle Limit: {clearance_cm} cm. Recommendation: Dispatch heavy rescue truck.")
        return

    primary = routes[0]
    print("\n" + "=" * 75)
    print(f" ✅ SAFE ROUTE FOUND ({dest_name.upper()} IN {selected_city.upper()})")
    print("=" * 75)
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
        for i, nm in enumerate(seen_names[:10], 1):
            print(f"     {i}. {nm}")
        if len(seen_names) > 10:
            print(f"     ... and {len(seen_names) - 10} more street segments")

    roads_avoided = primary.get("roads_avoided", [])
    if roads_avoided:
        print(f"\n  🚫 Submerged Roads Safely Avoided ({len(roads_avoided)} segments):")
        avoided_names = list(set(r.get("name", "Road") for r in roads_avoided[:8]))
        for an in avoided_names:
            print(f"     • {an}")

    if len(routes) > 1:
        print("\n  🔀 Alternative Safe Detours Available:")
        for idx, alt in enumerate(routes[1:], 1):
            print(f"     Detour {idx}: {alt['distance_m']/1000:.2f} km | {alt['travel_time_min']:.1f} min | Risk: {alt['flood_risk']}")

    # Save to GeoJSON for visualization
    out_file = Path("live_navigation_route.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(primary["geojson"], f, indent=2)
    print(f"\n  💾 Exported route vector layer to: {out_file}")
    print("=" * 75)


if __name__ == "__main__":
    run_navigation()
