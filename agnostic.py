"""
City-Agnostic Subterranean Drainage Graph Builder
=================================================

Constructs an interconnected hydraulic drainage network (nodes and edges) from:
  1. Hydro-conditioned Digital Elevation Model (DEM)
  2. OpenStreetMap waterways (canals, rivers, streams, ditches, culverts)
  3. Real-world roadside stormwater drains along major urban corridors

City-Agnostic Enhancements:
  - Dynamically loads bounding box and grid dimensions from `backend.config`
    instead of relying on hardcoded constants.
  - Automatically resolves data directories per active city configuration
    with intelligent fallback to baseline assets.
  - Flexible CLI allowing execution across different city configuration files.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles to prevent charmap codec errors
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

try:
    from backend import config as cfg_module
except ImportError:
    try:
        import config as cfg_module
    except ImportError:
        cfg_module = None

# Spatial snapping tolerance in meters: joins disjoint street drains and waterways
SNAP_TOLERANCE_M = 8.0

# Road categories carrying formal stormwater conduits
DRAINAGE_RELEVANT_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
}


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculates great-circle distance between two geographic points in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def make_latlon_to_grid(bbox: Tuple[float, float, float, float], grid_rows: int, grid_cols: int):
    """
    Creates a coordinate projection closure bound to the target city's bounding box and grid.
    Avoids global state pollution when processing multiple cities.
    """
    min_lat, max_lat, min_lon, max_lon = bbox
    lat_span = max_lat - min_lat + 1e-10
    lon_span = max_lon - min_lon + 1e-10

    def latlon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
        norm_y = (lat - min_lat) / lat_span
        norm_x = (lon - min_lon) / lon_span
        row = int(round(norm_y * (grid_rows - 1)))
        col = int(round(norm_x * (grid_cols - 1)))
        return max(0, min(grid_rows - 1, row)), max(0, min(grid_cols - 1, col))

    return latlon_to_grid


def manning_capacity_m3s(diameter_m: float, slope: float, roughness_n: float) -> float:
    """
    Computes maximum gravity conveyance capacity for a circular conduit via Manning's Equation:
        Q = (1 / n) * A * R^(2/3) * S^(1/2)
    """
    if diameter_m <= 0.0 or slope <= 0.0 or roughness_n <= 0.0:
        return 0.0
    area = math.pi * (diameter_m / 2.0) ** 2
    hydraulic_radius = diameter_m / 4.0
    velocity = (1.0 / roughness_n) * (hydraulic_radius ** (2.0 / 3.0)) * (slope ** 0.5)
    return round(float(area * velocity), 3)


class NodeIndex:
    """
    Spatially-indexed node registry with metric cKDTree nearest-neighbor snapping.
    Snaps nearby pipe ends together to form a physically connected hydraulic network.
    """

    def __init__(self, dem_grid: np.ndarray, latlon_to_grid_fn, tolerance_m: float = SNAP_TOLERANCE_M):
        self.dem_grid = dem_grid
        self.latlon_to_grid = latlon_to_grid_fn
        self.tolerance_m = tolerance_m
        self.coords: List[Tuple[float, float]] = []
        self.node_ids: List[str] = []
        self.nodes_dict: Dict[str, Dict[str, Any]] = {}
        self.tree: Optional[cKDTree] = None
        self._mx: float = 111320.0
        self._my: float = 110540.0
        self._since_rebuild: int = 0
        self._node_counter: int = 1
        self._type_priority = {"junction": 0, "inlet": 1, "outfall": 2}

    def _rebuild_tree(self) -> None:
        if not self.coords:
            return
        lat0 = float(np.mean([c[1] for c in self.coords]))
        self._mx = 111320.0 * math.cos(math.radians(lat0))
        self._my = 110540.0
        pts = [(lon * self._mx, lat * self._my) for lon, lat in self.coords]
        self.tree = cKDTree(pts)
        self._since_rebuild = 0

    def find_or_create(
        self,
        coord: List[float] | Tuple[float, float],
        node_type: str = "junction",
        custom_cap: float = 0.5,
    ) -> str:
        lon, lat = float(coord[0]), float(coord[1])

        if self.tree is not None and len(self.coords) > 0:
            qx, qy = lon * self._mx, lat * self._my
            dist, idx = self.tree.query([qx, qy], k=1)
            if dist <= self.tolerance_m:
                node_id = self.node_ids[idx]
                existing = self.nodes_dict[node_id]
                # Elevate node priority if inlet or outfall
                if self._type_priority.get(node_type, 0) > self._type_priority.get(existing["type"], 0):
                    existing["type"] = node_type
                return node_id

        node_id = f"DN-{self._node_counter:03d}"
        grid_row, grid_col = self.latlon_to_grid(lat, lon)
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

        if self.tree is None or self._since_rebuild >= 25:
            self._rebuild_tree()

        return node_id


def check_connectivity(nodes_dict: Dict[str, Dict[str, Any]], edges_list: List[Dict[str, Any]]) -> List[set]:
    """Analyzes the graph topological connectivity and reports connected components."""
    G = nx.Graph()
    for node_id in nodes_dict:
        G.add_node(node_id)
    for edge in edges_list:
        p = edge["properties"]
        G.add_edge(p["from_node"], p["to_node"])

    components = list(nx.connected_components(G))
    components.sort(key=len, reverse=True)
    print(f"📊 Topological Connectivity: {len(components)} connected component(s)")
    if len(components) > 1:
        sizes = [len(c) for c in components]
        print(f"   ℹ️ Component size distribution: {sizes[:8]}{'...' if len(sizes) > 8 else ''}")
    return components


def resolve_osm_file(directory: Path, base_name: str, pattern: str) -> Optional[Path]:
    """Locates an OSM JSON file either by exact name or glob pattern in raw/."""
    primary = directory / "raw" / base_name
    if primary.exists():
        return primary
    # Search fallback pattern in directory / raw
    raw_dir = directory / "raw"
    if raw_dir.exists():
        matches = list(raw_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def build_grid_drainage(
    bbox: Tuple[float, float, float, float],
    grid_rows: int,
    grid_cols: int,
    dem_grid: np.ndarray,
    osm_drainage_file: Optional[Path] = None,
    osm_roads_file: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    city_name: str = "Dynamic Domain",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Constructs a connected subterranean hydraulic drainage network for an arbitrary
    raster grid (rows x cols) and elevation model. Can output to GeoJSON if output_dir given.
    """
    latlon_to_grid = make_latlon_to_grid(bbox, grid_rows, grid_cols)
    index = NodeIndex(dem_grid, latlon_to_grid, tolerance_m=SNAP_TOLERANCE_M)
    edges_list: List[Dict[str, Any]] = []
    edge_counter = 1

    # 1. Process Natural & Canal Waterways from OSM
    if osm_drainage_file and osm_drainage_file.exists():
        print(f"🌊 [{city_name}] Processing OSM waterways from: {osm_drainage_file.name}")
        with open(osm_drainage_file, "r", encoding="utf-8") as f:
            osm_data = json.load(f)

        waterway_count = 0
        for el in osm_data.get("elements", []):
            if el.get("type") == "way" and "geometry" in el:
                coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
                if len(coords) < 2:
                    continue
                waterway_count += 1
                tags = el.get("tags", {})
                w_type = tags.get("waterway", tags.get("man_made", "drain"))
                is_major_nala = w_type in ["canal", "river", "stream"]
                diameter = 1.8 if is_major_nala else 0.8
                roughness_n = 0.025 if is_major_nala else 0.013

                for i in range(len(coords) - 1):
                    c1, c2 = coords[i], coords[i + 1]

                    r1, col1 = latlon_to_grid(c1[1], c1[0])
                    r2, col2 = latlon_to_grid(c2[1], c2[0])
                    elev1 = float(dem_grid[r1, col1])
                    elev2 = float(dem_grid[r2, col2])

                    # Orient flow gravitationally downhill
                    start_c, end_c = (c1, c2) if elev1 >= elev2 else (c2, c1)

                    length = round(max(haversine_m(start_c[0], start_c[1], end_c[0], end_c[1]), 2.0), 2)
                    slope_value = round(max(abs(elev1 - elev2) / length, 0.001), 4)
                    cap_flow = manning_capacity_m3s(diameter, slope_value, roughness_n)

                    from_id = index.find_or_create(start_c, "inlet" if i == 0 else "junction", cap_flow)
                    to_id = index.find_or_create(end_c, "outfall" if i == len(coords) - 2 else "junction", cap_flow)

                    edges_list.append({
                        "type": "Feature",
                        "properties": {
                            "id": f"DE-{edge_counter:03d}",
                            "from_node": from_id,
                            "to_node": to_id,
                            "length_m": length,
                            "diameter_m": diameter,
                            "slope": slope_value,
                            "roughness_n": roughness_n,
                            "capacity_m3s": cap_flow,
                            "blockage_pct": 0.0,
                            "channel_type": f"real_osm_{w_type}",
                        },
                        "geometry": {"type": "LineString", "coordinates": [start_c, end_c]},
                    })
                    edge_counter += 1
        print(f"   -> Extracted {waterway_count} waterway features.")
    else:
        print(f"⚠️ [{city_name}] No OSM drainage file provided or found. Skipping waterways.")

    # 2. Process Roadside Stormwater Drains
    if osm_roads_file and osm_roads_file.exists():
        print(f"🛣️ [{city_name}] Processing roadside storm conduits from: {osm_roads_file.name}")
        with open(osm_roads_file, "r", encoding="utf-8") as f:
            roads_data = json.load(f)

        road_ways = [
            el
            for el in roads_data.get("elements", [])
            if el.get("type") == "way"
            and "geometry" in el
            and el.get("tags", {}).get("highway") in DRAINAGE_RELEVANT_HIGHWAYS
        ]

        diameter, roughness_n = 0.6, 0.013
        for el in road_ways:
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) < 2:
                continue
            for i in range(len(coords) - 1):
                c1, c2 = coords[i], coords[i + 1]
                r1, col1 = latlon_to_grid(c1[1], c1[0])
                r2, col2 = latlon_to_grid(c2[1], c2[0])
                elev1 = float(dem_grid[r1, col1])
                elev2 = float(dem_grid[r2, col2])

                start_c, end_c = (c1, c2) if elev1 >= elev2 else (c2, c1)
                length = round(max(haversine_m(start_c[0], start_c[1], end_c[0], end_c[1]), 2.0), 2)
                slope_value = round(max(abs(elev1 - elev2) / length, 0.002), 4)
                cap_flow = manning_capacity_m3s(diameter, slope_value, roughness_n)

                from_id = index.find_or_create(start_c, "inlet", cap_flow)
                to_id = index.find_or_create(end_c, "junction", cap_flow)

                edges_list.append({
                    "type": "Feature",
                    "properties": {
                        "id": f"DE-{edge_counter:03d}",
                        "from_node": from_id,
                        "to_node": to_id,
                        "length_m": length,
                        "diameter_m": diameter,
                        "slope": slope_value,
                        "roughness_n": roughness_n,
                        "capacity_m3s": cap_flow,
                        "blockage_pct": 0.0,
                        "channel_type": "roadside_storm_drain",
                    },
                    "geometry": {"type": "LineString", "coordinates": [start_c, end_c]},
                })
                edge_counter += 1
        print(f"   -> Extracted {len(road_ways)} roadside drain corridors.")
    else:
        print(f"⚠️ [{city_name}] No OSM roads file provided or found. Skipping roadside drains.")

    nodes_features = [
        {
            "type": "Feature",
            "properties": {k: v for k, v in node.items() if k != "coordinates"},
            "geometry": {"type": "Point", "coordinates": node["coordinates"]},
        }
        for node in index.nodes_dict.values()
    ]

    check_connectivity(index.nodes_dict, edges_list)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        nodes_path = output_dir / "drainage_nodes.geojson"
        edges_path = output_dir / "drainage_edges.geojson"

        with open(nodes_path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": nodes_features}, f, indent=2)

        with open(edges_path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": edges_list}, f, indent=2)

        print(f"\n🎉 Successfully saved drainage network for '{city_name}':")
        print(f"   • Nodes: {len(nodes_features)} -> {nodes_path}")
        print(f"   • Edges: {len(edges_list)} -> {edges_path}\n")

    return nodes_features, edges_list


def build_comprehensive_real_drainage(config_path: Optional[str | Path] = None) -> Tuple[int, int]:
    """
    Main pipeline entrypoint to build city drainage GeoJSON assets.
    """
    city_name = cfg_module.get_city_name(config_path)
    bbox = cfg_module.get_bbox(config_path)
    grid_rows, grid_cols, cell_size_m = cfg_module.get_grid(config_path)
    paths = cfg_module.get_data_paths(config_path)

    print(f"\n========================================================")
    print(f"🏗️  Building Drainage Graph for '{city_name}'")
    print(f"📍 BBox: Lat [{bbox[0]:.5f}, {bbox[1]:.5f}], Lon [{bbox[2]:.5f}, {bbox[3]:.5f}]")
    print(f"📐 Grid: {grid_rows}x{grid_cols} (Cell resolution: {cell_size_m}m)")
    print(f"📁 Target Directory: {paths['drainage_dir']}")
    print(f"========================================================\n")

    dem_path = paths["dem_dir"] / "elevation_grid.npy"
    if not dem_path.exists():
        raise FileNotFoundError(
            f"❌ Elevation grid missing at {dem_path}. "
            f"Please run DEM raster extraction first (e.g. backend/data/dem/process_dem.py)."
        )
    dem_grid = np.load(dem_path)
    print(f"✅ Loaded DEM grid: shape={dem_grid.shape}, min={dem_grid.min():.2f}m, max={dem_grid.max():.2f}m")

    osm_drainage_file = resolve_osm_file(paths["drainage_dir"], "osm_drainage.json", "*drainage*.json")
    roads_file = resolve_osm_file(paths["roads_dir"], "osm_roads.json", "*roads*.json")

    nodes_features, edges_list = build_grid_drainage(
        bbox=bbox,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        dem_grid=dem_grid,
        osm_drainage_file=osm_drainage_file,
        osm_roads_file=roads_file,
        output_dir=paths["drainage_dir"],
        city_name=city_name,
    )

    return len(nodes_features), len(edges_list)


def main():
    parser = argparse.ArgumentParser(
        description="Build city-agnostic urban drainage network from DEM and OSM data."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to city YAML configuration file (defaults to backend/city_config.yaml)",
    )
    args = parser.parse_args()

    try:
        build_comprehensive_real_drainage(config_path=args.config)
    except Exception as exc:
        print(f"❌ Error building drainage network: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()