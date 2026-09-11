"""
Test routing between Kestopur and Ruby General Hospital in Kolkata.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.models.routing import RoutingEngine

def test_kolkata_kestopur_to_ruby():
    e = RoutingEngine(
        geojson_path="backend/data/cities/kolkata/roads/road_network.geojson",
        graph_path="backend/data/cities/kolkata/roads/road_graph.json",
    )
    assert e.graph.number_of_nodes() > 5000, "Should have loaded Kolkata road graph"

    # Coordinates: Kestopur -> Ruby Hospital
    src = (88.4230, 22.5930)
    dst = (88.4030, 22.5135)

    routes = e.find_alternative_routes(src, dst, vehicle_type="car", max_alternatives=2)
    assert len(routes) > 0, "Routes list should not be empty"
    primary = routes[0]
    assert primary["route_found"] is True, "Route from Kestopur to Ruby should be found"
    dist_km = primary["distance_m"] / 1000.0
    print(f"\n[KOLKATA ROUTING TEST]")
    print(f"  Origin: Kestopur (88.4230, 22.5930)")
    print(f"  Destination: Ruby Hospital (88.4030, 22.5135)")
    print(f"  Distance: {dist_km:.2f} km")
    print(f"  Travel Time: {primary['travel_time_min']:.1f} mins")
    print(f"  Traversed Segments: {primary['segment_count']}")
    assert 9.0 <= dist_km <= 16.0, f"Distance should be ~10-15 km, got {dist_km}"

if __name__ == "__main__":
    test_kolkata_kestopur_to_ruby()
