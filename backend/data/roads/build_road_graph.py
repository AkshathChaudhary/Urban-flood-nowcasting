"""
C1.5 — Road Data Engineer: Road Graph JSON Generator & Validator
Urban Flood Nowcast Project

This script constructs the canonical machine-readable road network graph:
backend/data/roads/road_graph.json.

It integrates the topologically verified road graph (from GraphML) with the
200x200 B2 DEM grid mapping for direct consumption by flood routing, hotspot
detection, and traffic vulnerability modules.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np
import networkx as nx
from shapely import wkt
from shapely.geometry import LineString

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.roads.grid_mapping import (
    ORIGIN_LAT,
    ORIGIN_LON,
    MAX_LAT,
    MAX_LON,
    GRID_ROWS,
    GRID_COLS,
    CELL_SIZE_M,
    latlon_to_grid,
    is_in_bounds,
    sample_linestring_to_cells,
)

DEFAULT_INPUT_GRAPHML = CURRENT_DIR / "raw" / "osm_roads_mumbai_attributes.graphml"
DEFAULT_DEM_DIR = PROJECT_ROOT / "backend" / "data" / "dem"
DEFAULT_OUTPUT_JSON = CURRENT_DIR / "road_graph.json"


def build_road_graph(
    graphml_path: Path = DEFAULT_INPUT_GRAPHML,
    dem_dir: Path = DEFAULT_DEM_DIR,
    output_json_path: Path = DEFAULT_OUTPUT_JSON,
    indent: Optional[int] = 2,
) -> Dict[str, Any]:
    """
    Builds and validates the canonical road graph JSON from the input GraphML
    and DEM grid elevation data.
    """
    print("=================================================================")
    print("C1.5: Road Network Graph JSON Generation")
    print("=================================================================")
    print(f"Input Road GraphML  : {graphml_path}")
    print(f"DEM Directory       : {dem_dir}")
    print(f"Output Graph JSON   : {output_json_path}")
    print("-----------------------------------------------------------------")

    # 1. VERIFY INPUT FILES
    if not graphml_path.exists():
        raise FileNotFoundError(f"Input GraphML file not found: {graphml_path}")

    elev_path = dem_dir / "elevation_grid.npy"
    if not elev_path.exists():
        raise FileNotFoundError(f"Elevation grid file not found: {elev_path}")

    # 2. LOAD DEM & GRAPH
    elev_grid = np.load(elev_path).astype(np.float32)
    assert elev_grid.shape == (GRID_ROWS, GRID_COLS), f"DEM shape mismatch: {elev_grid.shape}"

    G = nx.read_graphml(graphml_path)
    total_raw_nodes = len(G.nodes)
    total_raw_edges = len(G.edges)
    print(f"Loaded GraphML: {total_raw_nodes:,} nodes, {total_raw_edges:,} edges.")

    # 3. BUILD NODES
    nodes_list: List[Dict[str, Any]] = []
    node_id_set: Set[str] = set()
    nodes_with_grid = 0
    nodes_outside_grid = 0

    # Deterministically sort nodes by node_id
    sorted_nodes = sorted(G.nodes(data=True), key=lambda x: str(x[0]))

    for n_id, data in sorted_nodes:
        n_id_str = str(n_id)
        if n_id_str in node_id_set:
            raise ValueError(f"Duplicate node ID detected: {n_id_str}")
        node_id_set.add(n_id_str)

        lat = float(data.get("y", 0.0))
        lon = float(data.get("x", 0.0))
        street_count = int(data.get("street_count", 1))

        if is_in_bounds(lat, lon):
            r, c = latlon_to_grid(lat, lon, clamp=False)
            # Boundary safety clamp
            r = max(0, min(GRID_ROWS - 1, r))
            c = max(0, min(GRID_COLS - 1, c))
            inside_grid = True
            grid_row: Optional[int] = r
            grid_col: Optional[int] = c
            elev_m: Optional[float] = round(float(elev_grid[r, c]), 2)
            nodes_with_grid += 1
        else:
            inside_grid = False
            grid_row = None
            grid_col = None
            elev_m = None
            nodes_outside_grid += 1

        node_obj = {
            "node_id": n_id_str,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "grid_row": grid_row,
            "grid_col": grid_col,
            "inside_grid": inside_grid,
            "elevation_m": elev_m,
            "street_count": street_count,
        }
        nodes_list.append(node_obj)

    # 4. BUILD EDGES
    edges_list: List[Dict[str, Any]] = []
    edge_id_set: Set[str] = set()
    road_id_set: Set[str] = set()
    invalid_edges = 0
    edges_with_valid_topology = 0
    edges_inside_grid = 0

    # Deterministically sort edges by (u, v, key)
    sorted_edges = sorted(G.edges(keys=True, data=True), key=lambda x: (str(x[0]), str(x[1]), x[2]))

    for idx, (u, v, k, data) in enumerate(sorted_edges, start=1):
        u_str, v_str = str(u), str(v)

        # Topology validation
        if u_str not in node_id_set or v_str not in node_id_set:
            invalid_edges += 1
            print(f"[ERROR] Edge ({u_str} -> {v_str}) references non-existent node!", file=sys.stderr)
            continue

        edges_with_valid_topology += 1

        edge_id = f"E-{idx:04d}" if idx < 10000 else f"E-{idx}"
        if edge_id in edge_id_set:
            raise ValueError(f"Duplicate edge ID generated: {edge_id}")
        edge_id_set.add(edge_id)

        road_id = str(data.get("id") or f"R-{idx:03d}")
        road_id_set.add(road_id)

        road_name = data.get("name", "")
        if road_name is None or str(road_name).lower() in ["none", "nan", "null"]:
            road_name = ""

        road_class = data.get("highway_type") or data.get("highway") or "unclassified"
        lanes = int(data.get("lanes", 2))
        width_m = float(data.get("width_m", 6.0))
        length_m = float(data.get("length_m") or data.get("length") or 0.0)
        maxspeed_kmh = int(data.get("maxspeed_kmh", 30))
        oneway_val = data.get("oneway", "False")
        oneway = True if str(oneway_val).lower() in ["true", "1"] else False
        lanes_src = data.get("lanes_source", "estimated")
        width_src = data.get("width_source", "estimated")
        speed_src = data.get("speed_source", "estimated")

        # Parse geometry
        geom = None
        if "geometry" in data and data["geometry"]:
            try:
                geom = wkt.loads(data["geometry"]) if isinstance(data["geometry"], str) else data["geometry"]
            except Exception:
                geom = None

        if geom is None:
            u_node = G.nodes[u]
            v_node = G.nodes[v]
            x1, y1 = float(u_node["x"]), float(u_node["y"])
            x2, y2 = float(v_node["x"]), float(v_node["y"])
            geom = LineString([(x1, y1), (x2, y2)])

        # Sample grid cells along geometry
        cells = sample_linestring_to_cells(geom, sample_step_m=5.0, keep_only_in_bounds=True)
        is_inside = len(cells) > 0
        if is_inside:
            edges_inside_grid += 1

        edge_obj = {
            "edge_id": edge_id,
            "source": u_str,
            "target": v_str,
            "road_id": road_id,
            "road_class": road_class,
            "name": road_name,
            "length_m": round(length_m, 2),
            "lanes": lanes,
            "width_m": round(width_m, 2),
            "maxspeed_kmh": maxspeed_kmh,
            "oneway": oneway,
            "lanes_source": lanes_src,
            "width_source": width_src,
            "speed_source": speed_src,
            "inside_grid": is_inside,
            "grid_cells": [[r, c] for r, c in cells],
        }
        edges_list.append(edge_obj)

    # 5. CHECK ISOLATED / DISCONNECTED NODES
    degrees = dict(G.degree())
    isolated_nodes = [str(n) for n, deg in degrees.items() if deg == 0]

    # 6. ASSEMBLE ROAD GRAPH JSON
    road_graph = {
        "metadata": {
            "name": "Mumbai Urban Flood Road Graph",
            "crs": "EPSG:4326",
            "grid_rows": GRID_ROWS,
            "grid_cols": GRID_COLS,
            "cell_size_m": CELL_SIZE_M,
            "bbox": {
                "south": ORIGIN_LAT,
                "west": ORIGIN_LON,
                "north": MAX_LAT,
                "east": MAX_LON,
            },
            "total_nodes": len(nodes_list),
            "nodes_inside_grid": nodes_with_grid,
            "nodes_outside_grid": nodes_outside_grid,
            "total_edges": len(edges_list),
            "edges_inside_grid": edges_inside_grid,
            "total_road_segments": len(road_id_set),
            "disconnected_nodes": len(isolated_nodes),
            "invalid_edges": invalid_edges,
        },
        "nodes": nodes_list,
        "edges": edges_list,
    }

    # 7. SAVE OUTPUT FILE
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(road_graph, f, indent=indent)

    print(f"Saved road graph JSON to: {output_json_path} ({output_json_path.stat().st_size / 1024:.1f} KB)")

    # 8. PRINT SUMMARY REPORT
    print("=================================================================")
    print("ROAD GRAPH JSON VALIDATION SUMMARY")
    print("=================================================================")
    print(f"Total nodes              : {len(nodes_list)}")
    print(f"Total edges              : {len(edges_list)}")
    print(f"Total road segments      : {len(road_id_set)}")
    print(f"Nodes with grid mapping  : {nodes_with_grid}")
    print(f"Nodes outside grid       : {nodes_outside_grid}")
    print(f"Edges with valid topology: {edges_with_valid_topology}")
    print(f"Disconnected nodes       : {len(isolated_nodes)}")
    print(f"Invalid edges            : {invalid_edges}")
    print("=================================================================")

    return road_graph


def main():
    parser = argparse.ArgumentParser(description="Generate canonical road graph JSON.")
    parser.add_argument("--input-graphml", type=Path, default=DEFAULT_INPUT_GRAPHML, help="Path to input GraphML file")
    parser.add_argument("--dem-dir", type=Path, default=DEFAULT_DEM_DIR, help="Path to DEM directory")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON, help="Path to output JSON")
    args = parser.parse_args()

    build_road_graph(
        graphml_path=args.input_graphml,
        dem_dir=args.dem_dir,
        output_json_path=args.output_json,
    )


if __name__ == "__main__":
    main()
