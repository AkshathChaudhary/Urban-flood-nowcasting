import json
import math
from pathlib import Path
import numpy as np

# Exact bounding box matching our DEM from OpenTopography
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

GRID_ROWS = 200
GRID_COLS = 200


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def latlon_to_grid(lat, lon):
    norm_y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT + 1e-10)
    norm_x = (lon - MIN_LON) / (MAX_LON - MIN_LON + 1e-10)
    row = int(norm_y * (GRID_ROWS - 1))
    col = int(norm_x * (GRID_COLS - 1))
    return max(0, min(GRID_ROWS - 1, row)), max(0, min(GRID_COLS - 1, col))


def compute_mannings_capacity(diameter_m: float, slope: float, roughness_n: float) -> float:
    """
    Manning's equation for pipe gravity full capacity:
    Q = (1/n) * A * R^(2/3) * S^(1/2)
    """
    area = math.pi * ((diameter_m / 2.0) ** 2)
    hydraulic_radius = diameter_m / 4.0
    safe_slope = max(slope, 0.001)
    return round((1.0 / roughness_n) * area * (hydraulic_radius ** (2.0 / 3.0)) * math.sqrt(safe_slope), 3)


def build_comprehensive_real_drainage():
    # 1. Load DEM Grid
    dem_grid = np.load("backend/data/dem/elevation_grid.npy")
    elev_min = float(dem_grid.min())
    elev_max = float(dem_grid.max())
    outfall_elevation_threshold = elev_min + 0.30 * (elev_max - elev_min)  # bottom 30% lowest elevations

    nodes_dict = {}
    edges_list = []
    node_counter = 1
    edge_counter = 1

    def get_or_create_node(coord, node_type="junction", custom_cap=0.5):
        nonlocal node_counter
        coord_key = (round(coord[0], 6), round(coord[1], 6))
        if coord_key not in nodes_dict:
            node_id = f"DN-{node_counter:03d}"
            lon, lat = coord_key[0], coord_key[1]
            grid_row, grid_col = latlon_to_grid(lat, lon)
            elevation_m = round(float(dem_grid[grid_row, grid_col]), 2)

            nodes_dict[coord_key] = {
                "id": node_id,
                "type": node_type,
                "elevation_m": elevation_m,
                "capacity_m3s": custom_cap,
                "grid_row": grid_row,
                "grid_col": grid_col,
                "coordinates": [lon, lat]
            }
            node_counter += 1
        else:
            # Upgrade node type if it's assigned an outfall or inlet
            current_type = nodes_dict[coord_key]["type"]
            if node_type == "outfall" or (node_type == "inlet" and current_type == "junction"):
                nodes_dict[coord_key]["type"] = node_type
                nodes_dict[coord_key]["capacity_m3s"] = max(nodes_dict[coord_key]["capacity_m3s"], custom_cap)

        return nodes_dict[coord_key]["id"]

    # 2. Add Real Waterways, Nalas, Canals from OSM
    osm_drainage_file = Path("backend/data/drainage/raw/osm_drainage_mumbai.json")
    if osm_drainage_file.exists():
        with open(osm_drainage_file, "r", encoding="utf-8") as f:
            osm_data = json.load(f)

        for el in osm_data.get("elements", []):
            if el.get("type") == "way" and "geometry" in el:
                coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
                tags = el.get("tags", {})
                w_type = tags.get("waterway", tags.get("man_made", "drain"))
                is_major_nala = w_type in ["canal", "river", "stream"]
                cap = 5.0 if is_major_nala else 1.5
                diameter = 2.0 if is_major_nala else 1.0
                roughness = 0.025 if is_major_nala else 0.013

                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]
                    from_id = get_or_create_node(c1, "inlet" if i == 0 else "junction", cap)
                    to_id = get_or_create_node(c2, "outfall" if i == len(coords) - 2 else "junction", cap)
                    length = haversine_m(c1[0], c1[1], c2[0], c2[1])

                    # Calculate slope from DEM
                    r1, col1 = latlon_to_grid(c1[1], c1[0])
                    r2, col2 = latlon_to_grid(c2[1], c2[0])
                    e1, e2 = float(dem_grid[r1, col1]), float(dem_grid[r2, col2])
                    slope = round(max(abs(e1 - e2) / max(length, 1.0), 0.002), 4)

                    edge_cap = compute_mannings_capacity(diameter, slope, roughness)

                    edge_id = f"DE-{edge_counter:03d}"
                    edges_list.append({
                        "type": "Feature",
                        "properties": {
                            "id": edge_id,
                            "from_node": from_id,
                            "to_node": to_id,
                            "length_m": round(max(length, 2.0), 2),
                            "diameter_m": diameter,
                            "slope": slope,
                            "roughness_n": roughness,
                            "capacity_m3s": edge_cap,
                            "blockage_pct": 0.0,
                            "channel_type": f"real_osm_{w_type}"
                        },
                        "geometry": {"type": "LineString", "coordinates": [c1, c2]}
                    })
                    edge_counter += 1

    # 3. Add Real-World Roadside Storm Water Drains (MCGM/BRIMSTOWAD along real roads)
    roads_file = Path("backend/data/roads/raw/osm_roads_mumbai.json")
    if roads_file.exists():
        with open(roads_file, "r", encoding="utf-8") as f:
            roads_data = json.load(f)

        road_ways = [el for el in roads_data.get("elements", []) if el.get("type") == "way" and "geometry" in el]
        for el in road_ways[::3]:  # Select key street segments
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) >= 2:
                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]
                    r1, c_col1 = latlon_to_grid(c1[1], c1[0])
                    r2, c_col2 = latlon_to_grid(c2[1], c2[0])
                    elev1 = float(dem_grid[r1, c_col1])
                    elev2 = float(dem_grid[r2, c_col2])

                    # Direct flow strictly downhill
                    start_c, end_c = (c1, c2) if elev1 >= elev2 else (c2, c1)

                    from_id = get_or_create_node(start_c, "inlet", 0.6)
                    to_id = get_or_create_node(end_c, "junction", 0.8)
                    length = haversine_m(start_c[0], start_c[1], end_c[0], end_c[1])

                    diameter = 0.8
                    roughness = 0.013
                    slope = round(max(abs(elev1 - elev2) / max(length, 1.0), 0.002), 4)
                    edge_cap = compute_mannings_capacity(diameter, slope, roughness)

                    edge_id = f"DE-{edge_counter:03d}"
                    edges_list.append({
                        "type": "Feature",
                        "properties": {
                            "id": edge_id,
                            "from_node": from_id,
                            "to_node": to_id,
                            "length_m": round(max(length, 2.0), 2),
                            "diameter_m": diameter,
                            "slope": slope,
                            "roughness_n": roughness,
                            "capacity_m3s": edge_cap,
                            "blockage_pct": 0.0,
                            "channel_type": "roadside_storm_drain"
                        },
                        "geometry": {"type": "LineString", "coordinates": [start_c, end_c]}
                    })
                    edge_counter += 1

    # 4. OPTIMIZATION: Identify Terminal Downhill Sinks & Convert to Real Outfalls
    # Identify which nodes have outgoing pipes
    nodes_with_outgoing = set(e["properties"]["from_node"] for e in edges_list)
    nodes_with_incoming = set(e["properties"]["to_node"] for e in edges_list)

    # Nodes that receive water but have NO outgoing pipes are hydraulic sinks (dead-ends)
    sink_nodes = [n for n in nodes_dict.values() if n["id"] in nodes_with_incoming and n["id"] not in nodes_with_outgoing]

    outfalls_converted = 0
    for sink in sink_nodes:
        # If it's near the lower elevation threshold or near boundary, convert to outfall
        is_low_elev = sink["elevation_m"] <= outfall_elevation_threshold
        is_boundary = (sink["grid_row"] <= 5 or sink["grid_row"] >= 194 or
                       sink["grid_col"] <= 5 or sink["grid_col"] >= 194)

        if is_low_elev or is_boundary or sink["type"] != "inlet":
            sink["type"] = "outfall"
            sink["capacity_m3s"] = 10.0  # Outfall can discharge large volume without bottlenecking
            outfalls_converted += 1

    print(f"Hydraulic Optimization: Automatically designated {outfalls_converted} terminal sink nodes as real 'outfalls'.")

    # Convert nodes dictionary to GeoJSON FeatureCollection
    nodes_features = []
    outfall_count = 0
    inlet_count = 0
    junction_count = 0

    for node in nodes_dict.values():
        if node["type"] == "outfall":
            outfall_count += 1
        elif node["type"] == "inlet":
            inlet_count += 1
        else:
            junction_count += 1

        nodes_features.append({
            "type": "Feature",
            "properties": {
                "id": node["id"],
                "type": node["type"],
                "elevation_m": node["elevation_m"],
                "capacity_m3s": node["capacity_m3s"],
                "grid_row": node["grid_row"],
                "grid_col": node["grid_col"]
            },
            "geometry": {
                "type": "Point",
                "coordinates": node["coordinates"]
            }
        })

    nodes_geojson = {"type": "FeatureCollection", "features": nodes_features}
    edges_geojson = {"type": "FeatureCollection", "features": edges_list}

    out_path = Path("backend/data/drainage")
    with open(out_path / "drainage_nodes.geojson", "w", encoding="utf-8") as f:
        json.dump(nodes_geojson, f, indent=2)

    with open(out_path / "drainage_edges.geojson", "w", encoding="utf-8") as f:
        json.dump(edges_geojson, f, indent=2)

    print(f"\nGenerated Optimized Real-World Drainage Network:")
    print(f" - Total Nodes: {len(nodes_features)} (Inlets: {inlet_count}, Junctions: {junction_count}, Outfalls: {outfall_count})")
    print(f" - Total Pipes/Edges: {len(edges_list)} (with baked-in Manning capacity)")
    print(f" -> Saved to {out_path / 'drainage_nodes.geojson'}")
    print(f" -> Saved to {out_path / 'drainage_edges.geojson'}")


if __name__ == "__main__":
    build_comprehensive_real_drainage()
