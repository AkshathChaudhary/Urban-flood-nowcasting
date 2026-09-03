import json
import math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import networkx as nx

# Exact bounding box matching our DEM from OpenTopography
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

GRID_ROWS = 200
GRID_COLS = 200

# Nodes within this distance of each other are treated as the same physical
# junction (e.g. a road-drain endpoint that lands near a waterway node but
# doesn't share exact digitized coordinates).
SNAP_TOLERANCE_M = 8.0

# Road classes that realistically carry roadside storm drains in an
# MCGM/BRIMSTOWAD-style network. Footpaths, tracks, etc. are excluded.
DRAINAGE_RELEVANT_HIGHWAYS = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "unclassified"
}


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def latlon_to_grid(lat, lon):
    norm_y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT + 1e-10)
    norm_x = (lon - MIN_LON) / (MAX_LON - MIN_LON + 1e-10)
    # round() instead of int() truncation avoids a systematic bias toward
    # the lower row/col on every lookup.
    row = int(round(norm_y * (GRID_ROWS - 1)))
    col = int(round(norm_x * (GRID_COLS - 1)))
    return max(0, min(GRID_ROWS - 1, row)), max(0, min(GRID_COLS - 1, col))


def manning_capacity_m3s(diameter_m, slope, roughness_n):
    """Full-flow capacity of a circular pipe/channel via Manning's equation.

    Replaces the old fixed capacity guesses (0.5 / 0.8 / 2.0) with a value
    derived from the geometry and roughness that's actually being stored.
    """
    if diameter_m <= 0 or slope <= 0 or roughness_n <= 0:
        return 0.0
    area = math.pi * (diameter_m / 2) ** 2
    hydraulic_radius = diameter_m / 4  # full circular pipe/culvert
    velocity = (1.0 / roughness_n) * (hydraulic_radius ** (2 / 3)) * (slope ** 0.5)
    return round(area * velocity, 3)


class NodeIndex:
    """Spatially-aware node store that snaps nearby coordinates together.

    Exact-coordinate dedup (round to 6 decimals) almost never merges nodes
    from two different OSM datasets (waterways vs. roads) even when they
    physically meet, which fragments the network into disconnected islands.
    This snaps any new point within SNAP_TOLERANCE_M of an existing node
    onto that node instead of creating a duplicate.
    """

    def __init__(self, dem_grid, tolerance_m=SNAP_TOLERANCE_M):
        self.dem_grid = dem_grid
        self.tolerance_m = tolerance_m
        self.coords = []       # [(lon, lat), ...] insertion order
        self.node_ids = []     # parallel list of node_id
        self.nodes_dict = {}   # node_id -> node record
        self.tree = None
        self._mx = None
        self._my = None
        self._since_rebuild = 0
        self._node_counter = 1

        # type priority so a more specific type (inlet/outfall) doesn't get
        # silently downgraded to "junction" if a second edge snaps to it
        self._type_priority = {"junction": 0, "inlet": 1, "outfall": 1}

    def _rebuild_tree(self):
        if not self.coords:
            return
        lat0 = np.mean([c[1] for c in self.coords])
        self._mx = 111320 * math.cos(math.radians(lat0))
        self._my = 110540
        pts = [(lon * self._mx, lat * self._my) for lon, lat in self.coords]
        self.tree = cKDTree(pts)
        self._since_rebuild = 0

    def find_or_create(self, coord, node_type="junction", custom_cap=0.5):
        lon, lat = coord

        if self.tree is not None:
            qx, qy = lon * self._mx, lat * self._my
            dist, idx = self.tree.query([qx, qy], k=1)
            if dist <= self.tolerance_m:
                node_id = self.node_ids[idx]
                # upgrade type if this occurrence is more specific
                existing = self.nodes_dict[node_id]
                if self._type_priority.get(node_type, 0) > self._type_priority.get(existing["type"], 0):
                    existing["type"] = node_type
                return node_id

        # no close-enough match -> create a new node
        node_id = f"DN-{self._node_counter:03d}"
        grid_row, grid_col = latlon_to_grid(lat, lon)
        elevation_m = round(float(self.dem_grid[grid_row, grid_col]), 2)

        self.nodes_dict[node_id] = {
            "id": node_id,
            "type": node_type,
            "elevation_m": elevation_m,
            "capacity_m3s": custom_cap,
            "grid_row": grid_row,
            "grid_col": grid_col,
            "coordinates": [lon, lat],
        }
        self.coords.append((lon, lat))
        self.node_ids.append(node_id)
        self._node_counter += 1
        self._since_rebuild += 1

        # Rebuild periodically rather than after every insert. A slightly
        # stale tree just means a handful of very recent points won't be
        # snap-candidates yet; they self-correct on the next rebuild.
        if self.tree is None or self._since_rebuild >= 15:
            self._rebuild_tree()

        return node_id


def check_connectivity(nodes_dict, edges_list):
    """Warn (rather than silently ship) if the network is fragmented."""
    G = nx.Graph()
    for node_id in nodes_dict:
        G.add_node(node_id)
    for edge in edges_list:
        p = edge["properties"]
        G.add_edge(p["from_node"], p["to_node"])

    components = list(nx.connected_components(G))
    components.sort(key=len, reverse=True)
    print(f" - Connectivity check: {len(components)} connected component(s)")
    if len(components) > 1:
        sizes = [len(c) for c in components]
        shown = sizes[:10]
        print(f"   WARNING: network is fragmented into {len(components)} pieces. "
              f"Component sizes: {shown}{'...' if len(sizes) > 10 else ''}")
    return components


def build_comprehensive_real_drainage():
    # 1. Load DEM Grid
    dem_grid = np.load("backend/data/dem/elevation_grid.npy")

    index = NodeIndex(dem_grid)
    edges_list = []
    edge_counter = 1

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
                diameter = 1.8 if is_major_nala else 0.8
                roughness_n = 0.025 if is_major_nala else 0.013

                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]

                    # Orient every segment downhill using the DEM (previously
                    # only the road-drain loop did this; a waterway digitized
                    # "uphill" in OSM would otherwise create a backwards edge).
                    r1, col1 = latlon_to_grid(c1[1], c1[0])
                    r2, col2 = latlon_to_grid(c2[1], c2[0])
                    elev1 = float(dem_grid[r1, col1])
                    elev2 = float(dem_grid[r2, col2])
                    start_c, end_c = (c1, c2) if elev1 >= elev2 else (c2, c1)

                    length = haversine_m(start_c[0], start_c[1], end_c[0], end_c[1])
                    length = round(max(length, 2.0), 2)

                    # Derive slope from real elevation difference instead of
                    # a flat hardcoded 0.005.
                    slope_value = round(max(abs(elev1 - elev2) / length, 0.001), 4)
                    cap_flow = manning_capacity_m3s(diameter, slope_value, roughness_n)

                    from_id = index.find_or_create(
                        start_c, "inlet" if i == 0 else "junction", cap_flow)
                    to_id = index.find_or_create(
                        end_c, "outfall" if i == len(coords) - 2 else "junction", cap_flow)

                    edge_id = f"DE-{edge_counter:03d}"
                    edges_list.append({
                        "type": "Feature",
                        "properties": {
                            "id": edge_id,
                            "from_node": from_id,
                            "to_node": to_id,
                            "length_m": length,
                            "diameter_m": diameter,
                            "slope": slope_value,
                            "roughness_n": roughness_n,
                            "capacity_m3s": cap_flow,
                            "blockage_pct": 0.0,
                            "channel_type": f"real_osm_{w_type}"
                        },
                        "geometry": {"type": "LineString", "coordinates": [start_c, end_c]}
                    })
                    edge_counter += 1

    # 3. Add Real-World Roadside Storm Water Drains (MCGM/BRIMSTOWAD standard along real roads)
    roads_file = Path("backend/data/roads/raw/osm_roads_mumbai.json")
    if roads_file.exists():
        with open(roads_file, "r", encoding="utf-8") as f:
            roads_data = json.load(f)

        # Filter by drainage-relevant road classification instead of an
        # arbitrary every-third-way stride, so selection reflects where
        # storm drains actually exist rather than OSM's element ordering.
        road_ways = [
            el for el in roads_data.get("elements", [])
            if el.get("type") == "way" and "geometry" in el
            and el.get("tags", {}).get("highway") in DRAINAGE_RELEVANT_HIGHWAYS
        ]

        diameter = 0.6
        roughness_n = 0.013

        for el in road_ways:
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) >= 2:
                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]
                    r1, col1 = latlon_to_grid(c1[1], c1[0])
                    r2, col2 = latlon_to_grid(c2[1], c2[0])
                    elev1 = float(dem_grid[r1, col1])
                    elev2 = float(dem_grid[r2, col2])

                    start_c, end_c = (c1, c2) if elev1 >= elev2 else (c2, c1)
                    length = haversine_m(start_c[0], start_c[1], end_c[0], end_c[1])
                    length = round(max(length, 2.0), 2)
                    slope_value = round(max(abs(elev1 - elev2) / length, 0.002), 4)
                    cap_flow = manning_capacity_m3s(diameter, slope_value, roughness_n)

                    from_id = index.find_or_create(start_c, "inlet", cap_flow)
                    to_id = index.find_or_create(end_c, "junction", cap_flow)

                    edge_id = f"DE-{edge_counter:03d}"
                    edges_list.append({
                        "type": "Feature",
                        "properties": {
                            "id": edge_id,
                            "from_node": from_id,
                            "to_node": to_id,
                            "length_m": length,
                            "diameter_m": diameter,
                            "slope": slope_value,
                            "roughness_n": roughness_n,
                            "capacity_m3s": cap_flow,
                            "blockage_pct": 0.0,
                            "channel_type": "roadside_storm_drain"
                        },
                        "geometry": {"type": "LineString", "coordinates": [start_c, end_c]}
                    })
                    edge_counter += 1

    # Convert nodes dictionary to GeoJSON FeatureCollection
    nodes_features = []
    for node in index.nodes_dict.values():
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

    # Connectivity check runs before writing output so a fragmented network
    # is flagged immediately instead of surfacing later in a simulation.
    check_connectivity(index.nodes_dict, edges_list)

    out_path = Path("backend/data/drainage")
    with open(out_path / "drainage_nodes.geojson", "w", encoding="utf-8") as f:
        json.dump(nodes_geojson, f, indent=2)

    with open(out_path / "drainage_edges.geojson", "w", encoding="utf-8") as f:
        json.dump(edges_geojson, f, indent=2)

    print(f"Generated Comprehensive Real-World Drainage Network:")
    print(f" - {len(nodes_features)} Real Drainage Nodes -> {out_path / 'drainage_nodes.geojson'}")
    print(f" - {len(edges_list)} Real Drain/Pipe Edges -> {out_path / 'drainage_edges.geojson'}")


if __name__ == "__main__":
    build_comprehensive_real_drainage()