"""
C1 — Road Data Engineer: Road Network Cleaning & Topology Simplification
Urban Flood Nowcast Project

This script processes the raw OpenStreetMap (OSM) road network graph
(backend/data/roads/raw/osm_roads_mumbai.graphml) and produces a cleaned,
topologically simplified road graph for C1/C2 routing pipelines.

The raw GraphML file is preserved completely untouched.

Cleaning Pipeline Stages:
1. Load raw GraphML file and verify integrity.
2. Filter and retain driveable road classes (including driveable link roads).
3. Extract the largest weakly connected component (preserving one-way directionality).
4. Perform topological simplification (removing interstitial nodes while preserving LineString geometries).
5. Inspect graph health (self-loops, missing attributes, geometric validity).
6. Save the cleaned graph to backend/data/roads/raw/osm_roads_mumbai_cleaned.graphml.
"""

import sys
import argparse
from pathlib import Path
from typing import Set, Tuple, List, Any
import networkx as nx
import osmnx as ox

# -------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = SCRIPT_DIR / "raw"
DEFAULT_INPUT_PATH = RAW_DATA_DIR / "osm_roads_mumbai.graphml"
DEFAULT_OUTPUT_PATH = RAW_DATA_DIR / "osm_roads_mumbai_cleaned.graphml"

# Permitted driveable highway classifications and corresponding link roads
DRIVEABLE_HIGHWAY_CLASSES: Set[str] = {
    # Main vehicle-routing road classes
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    # Driveable link roads
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}


def is_driveable_highway(highway_attr: Any) -> bool:
    """
    Determines whether a road's highway attribute qualifies as a driveable class.
    Handles string, list, tuple, or set representations from OSM data.

    Parameters:
    -----------
    highway_attr : Any
        The 'highway' edge attribute (str, list, tuple, or None).

    Returns:
    --------
    bool
        True if the highway matches at least one driveable class, False otherwise.
    """
    if highway_attr is None:
        return False

    if isinstance(highway_attr, str):
        return highway_attr in DRIVEABLE_HIGHWAY_CLASSES

    if isinstance(highway_attr, (list, tuple, set)):
        return any(h in DRIVEABLE_HIGHWAY_CLASSES for h in highway_attr if isinstance(h, str))

    return str(highway_attr) in DRIVEABLE_HIGHWAY_CLASSES


def get_highway_types_in_graph(G: nx.MultiDiGraph) -> List[str]:
    """
    Collects and returns sorted unique highway type strings present across all edges.
    """
    highway_types: Set[str] = set()
    for _, _, data in G.edges(data=True):
        hw = data.get("highway")
        if isinstance(hw, str):
            highway_types.add(hw)
        elif isinstance(hw, (list, tuple, set)):
            for item in hw:
                if isinstance(item, str):
                    highway_types.add(item)
        elif hw is not None:
            highway_types.add(str(hw))
    return sorted(list(highway_types))


def clean_road_network(
    input_path: Path = DEFAULT_INPUT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    force: bool = False,
) -> bool:
    """
    Loads the raw OSM road network, cleans non-driveable edges, keeps the largest
    weakly connected component, simplifies topology, and saves the cleaned graph.

    Parameters:
    -----------
    input_path : Path
        Path to the raw GraphML file.
    output_path : Path
        Path to save the cleaned GraphML file.
    force : bool
        If True, overwrites existing output file.

    Returns:
    --------
    bool
        True if cleaning and saving succeeded, False otherwise.
    """
    # 0. Safety and overwrite checks
    if not input_path.exists():
        print(f"[ERROR] Input raw graph does not exist: {input_path}", file=sys.stderr)
        return False

    if output_path.exists() and not force:
        print(f"[INFO] Cleaned dataset already exists at: {output_path}")
        print("[INFO] Cleaning skipped. Use '--force' or '--overwrite' to re-run and overwrite.")
        return True

    print("==================================================")
    print("C1: Road Network Cleaning & Topology Simplification")
    print("==================================================")
    print(f"Input Raw Graph   : {input_path}")
    print(f"Output Target     : {output_path}")
    print(f"OSMnx Version     : {ox.__version__}")
    print(f"NetworkX Version  : {nx.__version__}")
    print("--------------------------------------------------")

    try:
        # 1. LOAD RAW GRAPH
        print("[STAGE 1/6] Loading raw GraphML road network...")
        G_raw = ox.load_graphml(input_path)
        raw_node_count = G_raw.number_of_nodes()
        raw_edge_count = G_raw.number_of_edges()
        print(f"  -> Raw graph loaded: {raw_node_count} nodes, {raw_edge_count} edges.")

        if raw_node_count == 0 or raw_edge_count == 0:
            print("[ERROR] Loaded graph is empty!", file=sys.stderr)
            return False

        # Work on an isolated copy to guarantee the raw graph is never mutated
        G = G_raw.copy()

        # 2. FILTER DRIVEABLE ROADS
        print("[STAGE 2/6] Filtering driveable road classifications...")
        edges_to_remove = [
            (u, v, k)
            for u, v, k, data in G.edges(keys=True, data=True)
            if not is_driveable_highway(data.get("highway"))
        ]

        if edges_to_remove:
            print(f"  -> Removing {len(edges_to_remove)} non-driveable edges...")
            G.remove_edges_from(edges_to_remove)
            # Remove any orphan isolated nodes left after edge removal
            isolates = list(nx.isolates(G))
            if isolates:
                G.remove_nodes_from(isolates)
                print(f"  -> Removed {len(isolates)} isolated nodes after edge filtering.")
        else:
            print("  -> All edges matched permitted driveable road classes (0 removed).")

        filtered_node_count = G.number_of_nodes()
        filtered_edge_count = G.number_of_edges()
        print(f"  -> After driveable filtering: {filtered_node_count} nodes, {filtered_edge_count} edges.")

        # 3. SELECT LARGEST WEAKLY CONNECTED COMPONENT
        print("[STAGE 3/6] Analyzing connectivity and isolating largest component...")
        wccs = list(nx.weakly_connected_components(G))
        wcc_count_before = len(wccs)
        print(f"  -> Total Weakly Connected Components (WCCs) found: {wcc_count_before}")

        # Extract largest weakly connected component (ox.truncate.largest_component creates a new copy)
        G_wcc = ox.truncate.largest_component(G, strongly=False)
        wcc_node_count = G_wcc.number_of_nodes()
        wcc_edge_count = G_wcc.number_of_edges()
        print(f"  -> Largest WCC selected: {wcc_node_count} nodes, {wcc_edge_count} edges.")

        # 4. SIMPLIFY TOPOLOGY
        print("[STAGE 4/6] Simplifying topology (contracting interstitial nodes)...")
        # ox.simplify_graph merges chains of intermediate nodes into single edges with LineString geometries
        G_simplified = ox.simplify_graph(G_wcc)
        simp_node_count = G_simplified.number_of_nodes()
        simp_edge_count = G_simplified.number_of_edges()
        print(f"  -> After simplification: {simp_node_count} nodes, {simp_edge_count} edges.")

        # 5. INSPECT GRAPH HEALTH & PROBLEMATIC EDGES
        print("[STAGE 5/6] Inspecting graph health, geometry validity, and edge attributes...")
        self_loop_edges = list(nx.selfloop_edges(G_simplified))
        self_loop_count = len(self_loop_edges)

        zero_or_neg_length_count = 0
        missing_highway_count = 0
        missing_explicit_geom_count = 0
        invalid_geom_count = 0

        for u, v, k, data in G_simplified.edges(keys=True, data=True):
            # Check length
            length = data.get("length")
            try:
                if length is None or float(length) <= 0:
                    zero_or_neg_length_count += 1
            except (ValueError, TypeError):
                zero_or_neg_length_count += 1

            # Check highway
            if not data.get("highway"):
                missing_highway_count += 1

            # Check geometry
            geom = data.get("geometry")
            if geom is None:
                # Normal in OSMnx when an edge is a direct single segment between intersections
                missing_explicit_geom_count += 1
            else:
                if hasattr(geom, "is_valid") and not geom.is_valid:
                    invalid_geom_count += 1

        remaining_highway_types = get_highway_types_in_graph(G_simplified)

        # 6. SAVE CLEANED GRAPH
        print(f"[STAGE 6/6] Saving cleaned graph to: {output_path} ...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(G_simplified, filepath=output_path)
        final_file_size = output_path.stat().st_size
        print(f"[SUCCESS] Cleaned road graph saved ({final_file_size:,} bytes).")

        # 7. VALIDATION SUMMARY
        print("\n==================================================")
        print("C1 Road Network Cleaning Validation Summary")
        print("==================================================")
        print(f"1.  Raw Graph Nodes                  : {raw_node_count}")
        print(f"2.  Raw Graph Edges                  : {raw_edge_count}")
        print(f"3.  Nodes After Driveable Filtering  : {filtered_node_count}")
        print(f"4.  Edges After Driveable Filtering  : {filtered_edge_count}")
        print(f"5.  WCCs Count Before Selection      : {wcc_count_before}")
        print(f"6.  Nodes in Largest WCC             : {wcc_node_count}")
        print(f"7.  Edges in Largest WCC             : {wcc_edge_count}")
        print(f"8.  Nodes After Simplification       : {simp_node_count}")
        print(f"9.  Edges After Simplification       : {simp_edge_count}")
        print(f"10. Highway Types Remaining          : {remaining_highway_types}")
        print(f"11. Self-Loop Edge Count             : {self_loop_count}")
        print(f"12. Direct Straight-Line Edges       : {missing_explicit_geom_count} (endpoint-derived geometry)")
        print(f"13. Invalid Geometry Count           : {invalid_geom_count}")
        print(f"14. Zero / Negative Length Count     : {zero_or_neg_length_count}")
        print(f"15. Missing Highway Attribute Count  : {missing_highway_count}")
        print(f"16. Final Output Path                : {output_path.resolve()}")
        print(f"17. Final Output File Size           : {final_file_size:,} bytes")
        print("==================================================")

        return True

    except Exception as e:
        print(f"\n[ERROR] Road network cleaning failed: {str(e)}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Clean and simplify raw OpenStreetMap road network graph for C1/C2 routing."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Input raw GraphML file path (default: {DEFAULT_INPUT_PATH})"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Target cleaned GraphML output path (default: {DEFAULT_OUTPUT_PATH})"
    )
    parser.add_argument(
        "--force",
        "--overwrite",
        action="store_true",
        help="Overwrite target cleaned GraphML file if it already exists."
    )
    args = parser.parse_args()

    success = clean_road_network(
        input_path=args.input,
        output_path=args.output,
        force=args.force
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
