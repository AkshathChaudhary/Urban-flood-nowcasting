"""
C1 — Road Data Engineer: Raw Road Network Downloader
Urban Flood Nowcast Project

This script downloads the untouched raw OpenStreetMap (OSM) road network
for the Mumbai study area using OSMnx (v2.1.1) and stores it as a GraphML
file under backend/data/roads/raw/.

No attribute filtering, simplification, or normalization is performed here;
raw data preservation is maintained for subsequent pipeline stages.
"""

import sys
import argparse
from pathlib import Path
import osmnx as ox

# -------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -------------------------------------------------------------------------

# Study Area Bounding Box (approx. 2 km x 2 km region in Mumbai)
SOUTH = 19.0600
WEST = 72.8500
NORTH = 19.0800
EAST = 72.8700

# Directory paths
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = SCRIPT_DIR / "raw"
DEFAULT_OUTPUT_FILENAME = "osm_roads_mumbai.graphml"
DEFAULT_OUTPUT_PATH = RAW_DATA_DIR / DEFAULT_OUTPUT_FILENAME

# Relevant driveable road classes for vehicle routing
# Overpass QL custom filter applied during download
ROAD_FILTER = (
    '["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified"]'
)


def download_raw_roads(output_path: Path = DEFAULT_OUTPUT_PATH, force: bool = False) -> bool:
    """
    Downloads raw OSM road network data for the study area bounding box
    and saves it to GraphML format.

    Parameters:
    -----------
    output_path : Path
        Target destination path for the .graphml file.
    force : bool
        If True, overwrites existing file. Otherwise, stops with a message.

    Returns:
    --------
    bool
        True if download and save succeeded, False otherwise.
    """
    # 1. Check for existing dataset to avoid silent overwrites
    if output_path.exists() and not force:
        print(f"[INFO] Raw dataset already exists at: {output_path}")
        print("[INFO] Download skipped. Use '--force' or '--overwrite' to re-download and overwrite.")
        return True

    # 2. Ensure raw data directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print("C1: Starting Raw OpenStreetMap Road Network Download")
    print("==================================================")
    print(f"OSMnx Version : {ox.__version__}")
    print(f"Bounding Box  : South={SOUTH}, West={WEST}, North={NORTH}, East={EAST}")
    print(f"Road Filter   : {ROAD_FILTER}")
    print(f"Output Target : {output_path}")
    print("--------------------------------------------------")

    try:
        # 3. Query and construct graph using OSMnx 2.1.1 API
        # OSMnx 2.x bbox format is (left, bottom, right, top) -> (west, south, east, north)
        bbox = (WEST, SOUTH, EAST, NORTH)
        
        print("[PROGRESS] Querying Overpass API for road network graph...")
        # simplify=False and retain_all=True ensure raw topology and all components are preserved
        G = ox.graph_from_bbox(
            bbox=bbox,
            custom_filter=ROAD_FILTER,
            simplify=False,
            retain_all=True
        )

        print("[PROGRESS] Graph successfully retrieved from OpenStreetMap.")
        
        # 4. Save raw graph to GraphML format
        print(f"[PROGRESS] Saving raw graph to: {output_path} ...")
        ox.save_graphml(G, filepath=output_path)
        print("[SUCCESS] Raw road network saved successfully.")

        # 5. Print summary metrics
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()

        print("\n==================================================")
        print("C1 Raw Download Summary")
        print("==================================================")
        print(f"Total Nodes In Graph   : {num_nodes}")
        print(f"Total Edges In Graph   : {num_edges}")
        print(f"Bounding Box (S,W,N,E) : ({SOUTH}, {WEST}, {NORTH}, {EAST})")
        print(f"Saved Output File      : {output_path.resolve()}")
        print("==================================================")
        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to download or save raw road network: {str(e)}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download raw OpenStreetMap road network graph for C1 study area."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Target output file path (default: {DEFAULT_OUTPUT_PATH})"
    )
    parser.add_argument(
        "--force",
        "--overwrite",
        action="store_true",
        help="Overwrite target file if it already exists."
    )
    args = parser.parse_args()

    success = download_raw_roads(output_path=args.output, force=args.force)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
