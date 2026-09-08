"""
Clean Roads Pipeline (Pair C - Task C1.1 to C1.7)
=================================================

Transforms raw OpenStreetMap road data (Overpass API JSON) and hydro-conditioned DEM
into:
1. `road_network.geojson` (FeatureCollection of LineStrings with physical & topological attributes)
2. `road_graph.json` (Serialized graph structure with node coordinates and edge attributes for NetworkX)
3. `flood_hotspots.geojson` (Critical low-elevation intersections vulnerable to flood ponding)

City-agnostic with configurable bounding box and DEM extent.
Splits OSM ways at shared intersection nodes and filters to the largest connected driveable component.
"""

import json
import math
from pathlib import Path
from collections import deque
from typing import Dict, Any, List, Tuple, Optional, Set
import numpy as np

# Default Bounding Box for Kurla / Mithi River, Mumbai
DEFAULT_MIN_LAT = 19.06013888888332
DEFAULT_MAX_LAT = 19.07819444443888
DEFAULT_MIN_LON = 72.84986111114458
DEFAULT_MAX_LON = 72.86875000003347

GRID_ROWS = 200
GRID_COLS = 200

# Speed limits and width defaults per highway classification (CPHEEO / IRC standards)
HIGHWAY_DEFAULTS = {
    "motorway": {"lanes": 6, "width_m": 21.0, "maxspeed": 80},
    "motorway_link": {"lanes": 2, "width_m": 7.0, "maxspeed": 50},
    "trunk": {"lanes": 4, "width_m": 14.0, "maxspeed": 60},
    "trunk_link": {"lanes": 2, "width_m": 7.0, "maxspeed": 40},
    "primary": {"lanes": 4, "width_m": 14.0, "maxspeed": 50},
    "primary_link": {"lanes": 2, "width_m": 7.0, "maxspeed": 35},
    "secondary": {"lanes": 2, "width_m": 7.5, "maxspeed": 40},
    "secondary_link": {"lanes": 1, "width_m": 4.0, "maxspeed": 30},
    "tertiary": {"lanes": 2, "width_m": 6.0, "maxspeed": 30},
    "tertiary_link": {"lanes": 1, "width_m": 3.5, "maxspeed": 25},
    "residential": {"lanes": 2, "width_m": 5.5, "maxspeed": 30},
    "living_street": {"lanes": 1, "width_m": 4.0, "maxspeed": 20},
    "service": {"lanes": 1, "width_m": 3.5, "maxspeed": 20},
    "unclassified": {"lanes": 2, "width_m": 5.0, "maxspeed": 30},
}

DRIVEABLE_TYPES = set(HIGHWAY_DEFAULTS.keys())


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Computes great-circle distance between two coordinates in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def compute_linestring_length(coords: List[List[float]]) -> float:
    """Computes cumulative length of a coordinate sequence in meters."""
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine_m(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
    return round(total, 2)


def get_linestring_midpoint(coords: List[List[float]]) -> Tuple[float, float]:
    """Finds the geographic midpoint (lon, lat) along a coordinate sequence."""
    if len(coords) == 1:
        return coords[0][0], coords[0][1]
    
    mid_idx = len(coords) // 2
    return coords[mid_idx][0], coords[mid_idx][1]


def latlon_to_grid(
    lat: float,
    lon: float,
    min_lat: float = DEFAULT_MIN_LAT,
    max_lat: float = DEFAULT_MAX_LAT,
    min_lon: float = DEFAULT_MIN_LON,
    max_lon: float = DEFAULT_MAX_LON,
    rows: int = GRID_ROWS,
    cols: int = GRID_COLS,
) -> Tuple[int, int]:
    """Maps WGS84 lat/lon to raster grid indices [row, col]."""
    norm_y = (lat - min_lat) / (max_lat - min_lat + 1e-10)
    norm_x = (lon - min_lon) / (max_lon - min_lon + 1e-10)
    row = int(norm_y * (rows - 1))
    col = int(norm_x * (cols - 1))
    return max(0, min(rows - 1, row)), max(0, min(cols - 1, col))


def clean_and_build_roads(
    raw_osm_path: str = "backend/data/roads/raw/osm_roads_mumbai.json",
    dem_path: str = "backend/data/dem/elevation_grid.npy",
    output_dir: str = "backend/data/roads",
    min_lat: float = DEFAULT_MIN_LAT,
    max_lat: float = DEFAULT_MAX_LAT,
    min_lon: float = DEFAULT_MIN_LON,
    max_lon: float = DEFAULT_MAX_LON,
    min_component_nodes: int = 5,
) -> Dict[str, Any]:
    """
    Main pipeline:
    1. Parse OSM driveable ways and nodes.
    2. Segment ways at shared intersection nodes into individual edges.
    3. Remove tiny disconnected components to ensure route continuity.
    4. Map midpoint elevations from DEM.
    5. Export GeoJSON, Graph JSON, and Hotspots.
    """
    raw_file = Path(raw_osm_path)
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw OSM road file not found at: {raw_file}")
    
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Load DEM elevation grid
    dem_file = Path(dem_path)
    if dem_file.exists():
        dem_grid = np.load(dem_file)
    else:
        dem_grid = np.full((GRID_ROWS, GRID_COLS), 5.0, dtype=np.float32)

    with open(raw_file, "r", encoding="utf-8") as f:
        osm_data = json.load(f)

    elements = osm_data.get("elements", [])

    # Index OSM nodes
    osm_node_coords: Dict[int, Tuple[float, float]] = {}
    for el in elements:
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            osm_node_coords[el["id"]] = (round(el["lon"], 6), round(el["lat"], 6))

    # Identify driveable ways
    driveable_ways = []
    node_usage_count: Dict[int, int] = {}

    for el in elements:
        if el.get("type") != "way":
            continue

        tags = el.get("tags", {})
        highway = tags.get("highway")
        if not highway or highway not in DRIVEABLE_TYPES:
            continue

        nodes = el.get("nodes", [])
        if len(nodes) < 2:
            continue

        # Count node occurrences
        for nid in nodes:
            node_usage_count[nid] = node_usage_count.get(nid, 0) + 1

        driveable_ways.append(el)

    # 2. Segment ways at intersections (start, end, or shared nodes)
    raw_segments = []
    for el in driveable_ways:
        tags = el.get("tags", {})
        highway = tags.get("highway")
        nodes = el.get("nodes", [])

        # Subdivide way into segments between intersection nodes
        seg_nodes = [nodes[0]]
        for nid in nodes[1:]:
            seg_nodes.append(nid)
            # Intersection if shared by multiple ways or end of way
            if node_usage_count.get(nid, 0) > 1 or nid == nodes[-1]:
                # Extract coordinates
                coords = [
                    [osm_node_coords[n][0], osm_node_coords[n][1]]
                    for n in seg_nodes
                    if n in osm_node_coords
                ]
                if len(coords) >= 2:
                    raw_segments.append({
                        "osm_way_id": el["id"],
                        "tags": tags,
                        "highway": highway,
                        "u_osm": seg_nodes[0],
                        "v_osm": seg_nodes[-1],
                        "coords": coords,
                    })
                seg_nodes = [nid]

    # 3. Build Adjacency to Filter Disconnected Islands
    adj: Dict[int, Set[int]] = {}
    for seg in raw_segments:
        u, v = seg["u_osm"], seg["v_osm"]
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)

    # Breadth-first search for connected components
    visited = set()
    components: List[Set[int]] = []
    for node in adj:
        if node not in visited:
            comp = set()
            queue = deque([node])
            visited.add(node)
            while queue:
                curr = queue.popleft()
                comp.add(curr)
                for neighbor in adj.get(curr, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(comp)

    # Keep components that meet minimum node threshold (focus on main urban network)
    components.sort(key=len, reverse=True)
    valid_nodes = set()
    for comp in components:
        if len(comp) >= min_component_nodes:
            valid_nodes.update(comp)

    # 4. Map Validated Segments & Format Schema
    parsed_roads = []
    way_counter = 1
    node_id_map: Dict[int, str] = {}
    node_details: Dict[str, Dict[str, Any]] = {}
    node_counter = 1

    def get_or_create_node(osm_nid: int, lon: float, lat: float) -> str:
        nonlocal node_counter
        if osm_nid not in node_id_map:
            nid = f"RN-{node_counter:04d}"
            node_counter += 1
            node_id_map[osm_nid] = nid
            r, c = latlon_to_grid(lat, lon, min_lat, max_lat, min_lon, max_lon)
            elev = round(float(dem_grid[r, c]), 2)
            node_details[nid] = {
                "id": nid,
                "osm_id": osm_nid,
                "coordinates": [round(lon, 6), round(lat, 6)],
                "grid_row": r,
                "grid_col": c,
                "elevation_m": elev,
                "degree": 0,
            }
        return node_id_map[osm_nid]

    for seg in raw_segments:
        if seg["u_osm"] not in valid_nodes or seg["v_osm"] not in valid_nodes:
            continue

        u_coord = osm_node_coords[seg["u_osm"]]
        v_coord = osm_node_coords[seg["v_osm"]]
        u_id = get_or_create_node(seg["u_osm"], u_coord[0], u_coord[1])
        v_id = get_or_create_node(seg["v_osm"], v_coord[0], v_coord[1])

        tags = seg["tags"]
        highway = seg["highway"]
        defaults = HIGHWAY_DEFAULTS.get(highway, HIGHWAY_DEFAULTS["residential"])

        # Parse lanes
        lanes_val = tags.get("lanes")
        try:
            lanes = int(lanes_val) if lanes_val else defaults["lanes"]
        except ValueError:
            lanes = defaults["lanes"]

        # Parse speed
        speed_val = tags.get("maxspeed")
        try:
            if speed_val:
                speed_str = speed_val.split()[0]
                maxspeed = int(speed_str)
            else:
                maxspeed = defaults["maxspeed"]
        except (ValueError, IndexError):
            maxspeed = defaults["maxspeed"]

        # Width estimation
        width_val = tags.get("width")
        try:
            width_m = float(width_val) if width_val else round(lanes * 3.5, 1)
        except ValueError:
            width_m = defaults["width_m"]

        length_m = compute_linestring_length(seg["coords"])
        if length_m < 1.0:
            continue

        mid_lon, mid_lat = get_linestring_midpoint(seg["coords"])
        grid_r, grid_c = latlon_to_grid(mid_lat, mid_lon, min_lat, max_lat, min_lon, max_lon)
        elev_m = round(float(dem_grid[grid_r, grid_c]), 2)

        oneway_tag = tags.get("oneway", "no").lower()
        is_oneway = oneway_tag in ["yes", "1", "true"]

        name = tags.get("name")
        if not name:
            name = f"Unnamed {highway.capitalize()} Road"

        road_id = f"R-{way_counter:04d}"
        way_counter += 1

        node_details[u_id]["degree"] += 1
        node_details[v_id]["degree"] += 1

        parsed_roads.append({
            "id": road_id,
            "osm_id": seg["osm_way_id"],
            "name": name,
            "highway_type": highway,
            "lanes": lanes,
            "width_m": width_m,
            "length_m": length_m,
            "maxspeed_kmh": maxspeed,
            "oneway": is_oneway,
            "bridge": tags.get("bridge") == "yes",
            "tunnel": tags.get("tunnel") == "yes",
            "midpoint_grid_row": grid_r,
            "midpoint_grid_col": grid_c,
            "elevation_m": elev_m,
            "coordinates": seg["coords"],
            "start_node": u_id,
            "end_node": v_id,
        })

    # 5. Export Road Network GeoJSON
    features = []
    for road in parsed_roads:
        features.append({
            "type": "Feature",
            "properties": {
                "id": road["id"],
                "osm_id": road["osm_id"],
                "name": road["name"],
                "highway_type": road["highway_type"],
                "lanes": road["lanes"],
                "width_m": road["width_m"],
                "length_m": road["length_m"],
                "maxspeed_kmh": road["maxspeed_kmh"],
                "oneway": road["oneway"],
                "bridge": road["bridge"],
                "tunnel": road["tunnel"],
                "midpoint_grid_row": road["midpoint_grid_row"],
                "midpoint_grid_col": road["midpoint_grid_col"],
                "elevation_m": road["elevation_m"],
                "start_node": road["start_node"],
                "end_node": road["end_node"],
            },
            "geometry": {
                "type": "LineString",
                "coordinates": road["coordinates"],
            },
        })

    road_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "name": "Mumbai Kurla Study Area Road Network",
            "total_segments": len(features),
            "total_length_km": round(sum(r["length_m"] for r in parsed_roads) / 1000.0, 2),
            "bbox": [min_lon, min_lat, max_lon, max_lat],
        },
        "features": features,
    }

    geojson_file = out_path / "road_network.geojson"
    with open(geojson_file, "w", encoding="utf-8") as f:
        json.dump(road_geojson, f, indent=2)

    # 6. Export Road Graph JSON (Task C1.6)
    graph_nodes = {nid: details for nid, details in node_details.items()}
    graph_edges = []

    for road in parsed_roads:
        edge_data = {
            "id": road["id"],
            "u": road["start_node"],
            "v": road["end_node"],
            "name": road["name"],
            "highway_type": road["highway_type"],
            "length_m": road["length_m"],
            "maxspeed_kmh": road["maxspeed_kmh"],
            "lanes": road["lanes"],
            "width_m": road["width_m"],
            "midpoint_grid_row": road["midpoint_grid_row"],
            "midpoint_grid_col": road["midpoint_grid_col"],
            "elevation_m": road["elevation_m"],
            "coordinates": road["coordinates"],
            "oneway": road["oneway"],
        }
        graph_edges.append(edge_data)
        # Reverse edge if bidirectional
        if not road["oneway"]:
            rev_edge = dict(edge_data)
            rev_edge["u"] = road["end_node"]
            rev_edge["v"] = road["start_node"]
            rev_edge["coordinates"] = list(reversed(road["coordinates"]))
            graph_edges.append(rev_edge)

    road_graph_data = {
        "metadata": {
            "total_nodes": len(graph_nodes),
            "total_directed_edges": len(graph_edges),
            "bbox": [min_lon, min_lat, max_lon, max_lat],
        },
        "nodes": graph_nodes,
        "edges": graph_edges,
    }

    graph_file = out_path / "road_graph.json"
    with open(graph_file, "w", encoding="utf-8") as f:
        json.dump(road_graph_data, f, indent=2)

    # 7. Generate Flood Hotspots GeoJSON (Task C1.7)
    hotspot_features = []
    sorted_nodes = sorted(node_details.values(), key=lambda n: n["elevation_m"])
    low_elev_threshold = 4.0

    hotspot_idx = 1
    for node in sorted_nodes:
        if node["degree"] >= 2 and node["elevation_m"] <= low_elev_threshold:
            hotspot_features.append({
                "type": "Feature",
                "properties": {
                    "id": f"HS-{hotspot_idx:03d}",
                    "node_id": node["id"],
                    "elevation_m": node["elevation_m"],
                    "intersection_degree": node["degree"],
                    "grid_row": node["grid_row"],
                    "grid_col": node["grid_col"],
                    "severity": "CRITICAL" if node["elevation_m"] < 3.0 else "HIGH",
                    "description": f"Low-elevation road crossing at {node['elevation_m']}m elev",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": node["coordinates"],
                },
            })
            hotspot_idx += 1

    hotspots_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "total_hotspots": len(hotspot_features),
            "elevation_cutoff_m": low_elev_threshold,
        },
        "features": hotspot_features,
    }

    hotspots_file = out_path / "flood_hotspots.geojson"
    with open(hotspots_file, "w", encoding="utf-8") as f:
        json.dump(hotspots_geojson, f, indent=2)

    print(f"Road cleaning and topological graph generation complete:")
    print(f" - Cleaned Road Segments: {len(parsed_roads)}")
    print(f" - Total Road Length: {road_geojson['metadata']['total_length_km']} km")
    print(f" - Topologically Valid Nodes: {len(graph_nodes)}, Directed Edges: {len(graph_edges)}")
    print(f" - Flood Hotspots Identified: {len(hotspot_features)}")
    print(f" - Saved: {geojson_file}")
    print(f" - Saved: {graph_file}")
    print(f" - Saved: {hotspots_file}")

    return {
        "total_roads": len(parsed_roads),
        "total_nodes": len(graph_nodes),
        "total_edges": len(graph_edges),
        "total_hotspots": len(hotspot_features),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean raw OSM roads and generate network graph + hotspots")
    parser.add_argument("--osm", default="backend/data/roads/raw/osm_roads_mumbai.json", help="Path to raw OSM JSON")
    parser.add_argument("--dem", default="backend/data/dem/elevation_grid.npy", help="Path to DEM grid")
    parser.add_argument("--out", default="backend/data/roads", help="Output directory")
    args = parser.parse_args()

    clean_and_build_roads(raw_osm_path=args.osm, dem_path=args.dem, output_dir=args.out)
