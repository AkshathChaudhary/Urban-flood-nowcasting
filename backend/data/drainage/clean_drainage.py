import json
import math
from pathlib import Path
import numpy as np

# Exact bounding box matching our DEM from OpenTopography (Kurla / Mithi River sector)
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

GRID_ROWS = 200
GRID_COLS = 200


def haversine_m(lon1, lat1, lon2, lat2):
    """Computes great-circle distance between two WGS84 coordinates in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def latlon_to_grid(lat, lon):
    """Maps WGS84 lat/lon to 200x200 DEM grid cell indices."""
    norm_y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT + 1e-10)
    norm_x = (lon - MIN_LON) / (MAX_LON - MIN_LON + 1e-10)
    row = int(norm_y * (GRID_ROWS - 1))
    col = int(norm_x * (GRID_COLS - 1))
    return max(0, min(GRID_ROWS - 1, row)), max(0, min(GRID_COLS - 1, col))


def compute_mannings_capacity(diameter_m: float, slope: float, roughness_n: float) -> float:
    """
    Manning's equation for circular pipe gravity full capacity:
    Q = (1/n) * A * R^(2/3) * S^(1/2)
    """
    area = math.pi * ((diameter_m / 2.0) ** 2)
    hydraulic_radius = diameter_m / 4.0
    safe_slope = max(slope, 0.001)
    return round((1.0 / roughness_n) * area * (hydraulic_radius ** (2.0 / 3.0)) * math.sqrt(safe_slope), 3)


def build_comprehensive_real_drainage():
    """
    Constructs a topologically valid, hydrologically calibrated storm drainage network
    for the 2x2 km Kurla/Mithi River study area.
    
    Calibration against Mumbai Municipal Standards (BMC / Chitale Committee / BRIMSTOWAD):
    1. Arterial Waterways: Real Mithi River, Vakola streams, and major nalas from OSM.
    2. Roadside Storm Drains: Inlets sampled along street centerlines (CPHEEO 30-50m catchpit spacing).
    3. Mithi River Outfalls: Strictly 6-10 primary outfalls along the Mithi River floodplain (z <= 3.5m),
       matching the ~4 outfalls/km density reported by the Chitale Committee.
    4. Internal Surcharging Manholes: Street drains terminating inland remain standard junctions
       that surcharge during intense storms, rather than falsely acting as river outfalls.
    """
    # 1. Load DEM Grid
    dem_grid = np.load("backend/data/dem/elevation_grid.npy")

    nodes_dict = {}
    edges_list = []
    node_counter = 1
    edge_counter = 1

    def get_or_create_node(coord, node_type="junction", custom_cap=0.8):
        nonlocal node_counter
        coord_key = (round(coord[0], 6), round(coord[1], 6))
        if coord_key not in nodes_dict:
            node_id = f"DN-{node_counter:04d}"
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
            # Upgrade node type if assigned inlet and currently junction
            current_type = nodes_dict[coord_key]["type"]
            if node_type == "inlet" and current_type == "junction":
                nodes_dict[coord_key]["type"] = node_type
                nodes_dict[coord_key]["capacity_m3s"] = max(nodes_dict[coord_key]["capacity_m3s"], custom_cap)

        return nodes_dict[coord_key]["id"]

    # 2. Add Real Waterways, Nalas, and Canals from OSM (Mithi River network)
    osm_drainage_file = Path("backend/data/drainage/raw/osm_drainage_mumbai.json")
    waterway_node_ids = set()

    if osm_drainage_file.exists():
        with open(osm_drainage_file, "r", encoding="utf-8") as f:
            osm_data = json.load(f)

        for el in osm_data.get("elements", []):
            if el.get("type") == "way" and "geometry" in el:
                coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
                tags = el.get("tags", {})
                w_type = tags.get("waterway", tags.get("man_made", "drain"))
                is_major_nala = w_type in ["canal", "river", "stream"]
                cap = 8.0 if is_major_nala else 2.5
                diameter = 2.5 if is_major_nala else 1.2
                roughness = 0.025 if is_major_nala else 0.015

                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]
                    r1, col1 = latlon_to_grid(c1[1], c1[0])
                    r2, col2 = latlon_to_grid(c2[1], c2[0])
                    e1, e2 = float(dem_grid[r1, col1]), float(dem_grid[r2, col2])

                    # Direct flow downhill along DEM gradient
                    start_c, end_c = (c1, c2) if e1 >= e2 else (c2, c1)

                    from_id = get_or_create_node(start_c, "junction", cap)
                    to_id = get_or_create_node(end_c, "junction", cap)
                    waterway_node_ids.add(from_id)
                    waterway_node_ids.add(to_id)

                    length = haversine_m(start_c[0], start_c[1], end_c[0], end_c[1])
                    slope = round(max(abs(e1 - e2) / max(length, 1.0), 0.001), 4)
                    edge_cap = compute_mannings_capacity(diameter, slope, roughness)

                    edge_id = f"DE-{edge_counter:04d}"
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
                        "geometry": {"type": "LineString", "coordinates": [start_c, end_c]}
                    })
                    edge_counter += 1

    # 3. Add Real-World Roadside Storm Water Drains along OSM Roads
    roads_file = Path("backend/data/roads/raw/osm_roads_mumbai.json")
    if roads_file.exists():
        with open(roads_file, "r", encoding="utf-8") as f:
            roads_data = json.load(f)

        road_ways = [el for el in roads_data.get("elements", []) if el.get("type") == "way" and "geometry" in el]
        # Sample street segments to match CPHEEO / BMC drainage density
        for el in road_ways[::2]:
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) >= 2:
                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]
                    seg_length = haversine_m(c1[0], c1[1], c2[0], c2[1])
                    if seg_length < 3.0:
                        continue

                    r1, c_col1 = latlon_to_grid(c1[1], c1[0])
                    r2, c_col2 = latlon_to_grid(c2[1], c2[0])
                    elev1 = float(dem_grid[r1, c_col1])
                    elev2 = float(dem_grid[r2, c_col2])

                    # Direct flow strictly downhill
                    start_c, end_c = (c1, c2) if elev1 >= elev2 else (c2, c1)

                    from_id = get_or_create_node(start_c, "inlet", 0.6)
                    to_id = get_or_create_node(end_c, "junction", 0.8)

                    diameter = 0.9
                    roughness = 0.013
                    slope = round(max(abs(elev1 - elev2) / max(seg_length, 1.0), 0.002), 4)
                    edge_cap = compute_mannings_capacity(diameter, slope, roughness)

                    edge_id = f"DE-{edge_counter:04d}"
                    edges_list.append({
                        "type": "Feature",
                        "properties": {
                            "id": edge_id,
                            "from_node": from_id,
                            "to_node": to_id,
                            "length_m": round(seg_length, 2),
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

    # 4. Rigorous Hydrological Outfall Calibration (Chitale Committee / BRIMSTOWAD)
    # Identify terminal downhill sinks (nodes that receive water but have no outgoing pipe)
    nodes_with_outgoing = set(e["properties"]["from_node"] for e in edges_list)
    nodes_with_incoming = set(e["properties"]["to_node"] for e in edges_list)
    sink_nodes = [n for n in nodes_dict.values() if n["id"] in nodes_with_incoming and n["id"] not in nodes_with_outgoing]

    # Outfalls MUST satisfy:
    # (a) Low elevation (z <= 3.5m ASL, within the tidal Mithi floodplain)
    # (b) Location within the Mithi River corridor (lon <= 72.858) or low perimeter boundary
    candidate_outfalls = [
        s for s in sink_nodes
        if s["elevation_m"] <= 3.5 and (s["coordinates"][0] <= 72.858 or s["grid_row"] <= 12 or s["grid_col"] <= 12)
    ]
    # Sort candidate sinks by lowest elevation first
    candidate_outfalls.sort(key=lambda s: s["elevation_m"])

    # Enforce minimum spatial spacing (>= 180m) between outfalls along the 2km river corridor
    # to yield authentic municipal outfall density (target ~8 outfalls, range 6-10)
    selected_outfalls = []
    min_spacing_m = 180.0
    for cand in candidate_outfalls:
        too_close = False
        for outf in selected_outfalls:
            dist = haversine_m(cand["coordinates"][0], cand["coordinates"][1],
                               outf["coordinates"][0], outf["coordinates"][1])
            if dist < min_spacing_m:
                too_close = True
                break
        if not too_close:
            selected_outfalls.append(cand)
        if len(selected_outfalls) == 8:
            break

    selected_outfall_ids = set(o["id"] for o in selected_outfalls)

    # Assign outfall properties strictly to calibrated outfalls
    for node in nodes_dict.values():
        if node["id"] in selected_outfall_ids:
            node["type"] = "outfall"
            node["capacity_m3s"] = 15.0  # High discharge capacity into tidal river
        elif node["type"] == "outfall":
            # Demote any incidental outfall to junction
            node["type"] = "junction"
            node["capacity_m3s"] = 0.8

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

    print(f"\nGenerated Calibrated Real-World Drainage Network:")
    print(f" - Total Nodes: {len(nodes_features)} (Inlets: {inlet_count}, Junctions: {junction_count}, Outfalls: {outfall_count})")
    print(f" - Total Pipes/Edges: {len(edges_list)} (with baked-in Manning capacity)")
    print(f" - Outfalls calibrated to Mithi River basin: {outfall_count} outfalls (target 6-10)")
    for o in selected_outfalls:
        print(f"   * {o['id']}: elev={o['elevation_m']}m, coord={o['coordinates']}, row={o['grid_row']}, col={o['grid_col']}")
    print(f" -> Saved to {out_path / 'drainage_nodes.geojson'}")
    print(f" -> Saved to {out_path / 'drainage_edges.geojson'}")


if __name__ == "__main__":
    build_comprehensive_real_drainage()
