"""
C1 — Road Data Engineer: Road Attribute Normalization & Validation
Urban Flood Nowcast Project

This script processes the cleaned OpenStreetMap (OSM) road network graph
(backend/data/roads/raw/osm_roads_mumbai_cleaned.graphml) and produces a normalized,
fully-attributed intermediate GraphML representation:
backend/data/roads/raw/osm_roads_mumbai_attributes.graphml.

The cleaned GraphML file is preserved completely untouched.

Standardized Project Road Attributes:
- id            : Deterministic road identifier (R-001, R-002, ...)
- name          : Human-readable road name or None
- highway_type  : Normalized primary driveable highway class
- lanes         : Positive integer number of lanes (OSM or estimated)
- width_m       : Positive float road width in meters (OSM or estimated)
- length_m      : Positive float road length in meters
- maxspeed_kmh  : Positive integer speed limit in km/h (OSM or estimated)
- lanes_source  : "osm" or "estimated"
- width_source  : "osm" or "estimated"
- speed_source  : "osm" or "estimated"
"""

import re
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
import osmnx as ox

# -------------------------------------------------------------------------
# CONSTANTS & DEFAULTS
# -------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = SCRIPT_DIR / "raw"
DEFAULT_INPUT_PATH = RAW_DATA_DIR / "osm_roads_mumbai_cleaned.graphml"
DEFAULT_OUTPUT_PATH = RAW_DATA_DIR / "osm_roads_mumbai_attributes.graphml"

# Priority order for resolving multiple / ambiguous highway types
HIGHWAY_PRIORITY_ORDER: List[str] = [
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
]

# Explicit default lane counts when OSM data is missing or invalid
DEFAULT_LANES_BY_HIGHWAY: Dict[str, int] = {
    "motorway": 4,
    "motorway_link": 1,
    "trunk": 4,
    "trunk_link": 1,
    "primary": 4,
    "primary_link": 1,
    "secondary": 2,
    "secondary_link": 1,
    "tertiary": 2,
    "tertiary_link": 1,
    "residential": 2,
    "unclassified": 2,
}

# Explicit default road widths (in meters) when OSM data is missing or invalid
DEFAULT_WIDTH_BY_HIGHWAY: Dict[str, float] = {
    "motorway": 20.0,
    "motorway_link": 8.0,
    "trunk": 18.0,
    "trunk_link": 8.0,
    "primary": 14.0,
    "primary_link": 7.0,
    "secondary": 10.0,
    "secondary_link": 7.0,
    "tertiary": 8.0,
    "tertiary_link": 6.0,
    "residential": 6.0,
    "unclassified": 6.0,
}

# Explicit default speed limits (in km/h) when OSM data is missing or invalid
DEFAULT_SPEED_BY_HIGHWAY: Dict[str, int] = {
    "motorway": 80,
    "motorway_link": 50,
    "trunk": 60,
    "trunk_link": 40,
    "primary": 50,
    "primary_link": 40,
    "secondary": 40,
    "secondary_link": 30,
    "tertiary": 40,
    "tertiary_link": 30,
    "residential": 30,
    "unclassified": 30,
}

FALLBACK_DEFAULT_LANES = 2
FALLBACK_DEFAULT_WIDTH = 6.0
FALLBACK_DEFAULT_SPEED = 30


# -------------------------------------------------------------------------
# HELPER PARSING FUNCTIONS
# -------------------------------------------------------------------------

def parse_highway_type(raw_highway: Any) -> str:
    """
    Extracts and standardizes the highway classification string.
    If multiple highway values are present (list/tuple or semicolon-separated),
    selects the highest priority driveable class based on HIGHWAY_PRIORITY_ORDER.
    """
    if raw_highway is None:
        return "unclassified"

    candidates: List[str] = []

    if isinstance(raw_highway, (list, tuple, set)):
        for item in raw_highway:
            if isinstance(item, str):
                candidates.extend([h.strip() for h in item.split(";") if h.strip()])
    elif isinstance(raw_highway, str):
        candidates = [h.strip() for h in raw_highway.split(";") if h.strip()]
    else:
        candidates = [str(raw_highway).strip()]

    # Choose candidate matching the highest priority
    for prio_type in HIGHWAY_PRIORITY_ORDER:
        if prio_type in candidates:
            return prio_type

    # Fallback to first non-empty candidate or unclassified
    return candidates[0] if candidates else "unclassified"


def parse_name(raw_name: Any) -> Optional[str]:
    """
    Extracts a clean, single string road name from OSM attributes.
    If name is missing or empty, returns None.
    If multiple names exist (list or semicolon-delimited), selects the primary (first).
    """
    if raw_name is None:
        return None

    if isinstance(raw_name, (list, tuple, set)):
        for item in raw_name:
            if item and str(item).strip():
                return str(item).strip()
        return None

    name_str = str(raw_name).strip()
    if not name_str or name_str.lower() in {"none", "null", "nan"}:
        return None

    # Handle semicolon-delimited multilingual or alternate names
    parts = [p.strip() for p in name_str.split(";") if p.strip()]
    return parts[0] if parts else None


def parse_lanes(raw_lanes: Any, highway_type: str) -> Tuple[int, str]:
    """
    Safely parses the number of lanes into a positive integer.
    Handles strings ("2", "2;3", "4"), lists, and compound values.
    For compound values (e.g. "2;3"), takes the maximum numeric value.
    If missing or unparseable, falls back to the highway-type default.

    Returns:
    --------
    Tuple[int, str]: (lanes, "osm" | "estimated")
    """
    if raw_lanes is not None:
        lane_candidates: List[int] = []

        if isinstance(raw_lanes, (list, tuple, set)):
            items = list(raw_lanes)
        else:
            items = str(raw_lanes).split(";")

        for item in items:
            # Extract first numeric sequence
            match = re.search(r"\d+", str(item))
            if match:
                try:
                    val = int(match.group())
                    if val > 0:
                        lane_candidates.append(val)
                except ValueError:
                    pass

        if lane_candidates:
            # Semicolon compound values like "2;3" -> take max representing total lane capacity
            return max(lane_candidates), "osm"

    # Default fallback
    estimated_lanes = DEFAULT_LANES_BY_HIGHWAY.get(highway_type, FALLBACK_DEFAULT_LANES)
    return estimated_lanes, "estimated"


def parse_width(raw_width: Any, highway_type: str) -> Tuple[float, str]:
    """
    Safely parses road width in meters into a positive float.
    Strips textual units ("m", "meters", etc.) and handles lists/compounds.
    If missing or unparseable, falls back to the highway-type default.

    Returns:
    --------
    Tuple[float, str]: (width_m, "osm" | "estimated")
    """
    if raw_width is not None:
        width_candidates: List[float] = []

        if isinstance(raw_width, (list, tuple, set)):
            items = list(raw_width)
        else:
            items = str(raw_width).split(";")

        for item in items:
            cleaned = str(item).lower().replace("m", "").replace("meters", "").strip()
            cleaned = cleaned.replace(",", ".")
            match = re.search(r"\d+(\.\d+)?", cleaned)
            if match:
                try:
                    val = float(match.group())
                    if val > 0:
                        width_candidates.append(val)
                except ValueError:
                    pass

        if width_candidates:
            return round(max(width_candidates), 2), "osm"

    # Default fallback
    estimated_width = DEFAULT_WIDTH_BY_HIGHWAY.get(highway_type, FALLBACK_DEFAULT_WIDTH)
    return round(float(estimated_width), 2), "estimated"


def parse_maxspeed(raw_maxspeed: Any, highway_type: str) -> Tuple[int, str]:
    """
    Safely parses speed limit in km/h into a positive integer.
    Handles units ("km/h", "mph"), lists, and compound values ("30;40").
    Converts mph to km/h if present.
    If missing or unparseable, falls back to the highway-type default.

    Returns:
    --------
    Tuple[int, str]: (maxspeed_kmh, "osm" | "estimated")
    """
    if raw_maxspeed is not None:
        speed_candidates: List[int] = []

        if isinstance(raw_maxspeed, (list, tuple, set)):
            items = list(raw_maxspeed)
        else:
            items = str(raw_maxspeed).split(";")

        for item in items:
            s_str = str(item).strip().lower()
            is_mph = "mph" in s_str
            match = re.search(r"\d+(\.\d+)?", s_str)
            if match:
                try:
                    val = float(match.group())
                    if is_mph:
                        val = val * 1.60934
                    int_val = int(round(val))
                    if int_val > 0:
                        speed_candidates.append(int_val)
                except ValueError:
                    pass

        if speed_candidates:
            return max(speed_candidates), "osm"

    # Default fallback
    estimated_speed = DEFAULT_SPEED_BY_HIGHWAY.get(highway_type, FALLBACK_DEFAULT_SPEED)
    return estimated_speed, "estimated"


def parse_length(
    raw_length: Any,
    geom: Any,
    G: nx.MultiDiGraph,
    u: Any,
    v: Any
) -> Tuple[float, bool]:
    """
    Validates and extracts edge length in meters.
    If length attribute is missing, attempts calculation from Shapely geometry length
    or reports validity.

    Returns:
    --------
    Tuple[float, bool]: (length_m, is_valid)
    """
    if raw_length is not None:
        try:
            val = float(raw_length)
            if val > 0:
                return round(val, 3), True
        except (ValueError, TypeError):
            pass

    # Attempt geometry measurement fallback if available
    if geom is not None and hasattr(geom, "length"):
        try:
            val = float(geom.length)
            if val > 0:
                return round(val, 3), True
        except Exception:
            pass

    return 0.0, False


# -------------------------------------------------------------------------
# MAIN ATTRIBUTE PROCESSING PIPELINE
# -------------------------------------------------------------------------

def process_road_attributes(
    input_path: Path = DEFAULT_INPUT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    force: bool = False,
) -> bool:
    """
    Loads the cleaned GraphML road network, normalizes edge attributes,
    assigns deterministic project IDs (R-001, R-002, ...), and saves the graph.
    """
    if not input_path.exists():
        print(f"[ERROR] Input cleaned graph not found: {input_path}", file=sys.stderr)
        return False

    if output_path.exists() and not force:
        print(f"[INFO] Attributed dataset already exists at: {output_path}")
        print("[INFO] Processing skipped. Use '--force' or '--overwrite' to re-process and overwrite.")
        return True

    print("==================================================")
    print("C1: Road Network Attribute Normalization")
    print("==================================================")
    print(f"Input Cleaned Graph : {input_path}")
    print(f"Output Target Graph : {output_path}")
    print(f"OSMnx Version       : {ox.__version__}")
    print(f"NetworkX Version    : {nx.__version__}")
    print("--------------------------------------------------")

    try:
        # 1. LOAD CLEANED GRAPH
        print("[STAGE 1/4] Loading cleaned GraphML road network...")
        G_cleaned = ox.load_graphml(input_path)
        input_node_count = G_cleaned.number_of_nodes()
        input_edge_count = G_cleaned.number_of_edges()
        print(f"  -> Loaded graph: {input_node_count} nodes, {input_edge_count} edges.")

        if input_node_count == 0 or input_edge_count == 0:
            print("[ERROR] Input graph is empty!", file=sys.stderr)
            return False

        # Work on an isolated copy
        G = G_cleaned.copy()

        # 2. DETERMINISTIC ORDERING & ID ASSIGNMENT
        print("[STAGE 2/4] Normalizing edge attributes and generating project IDs...")

        # Sort edges deterministically by (u, v, key)
        sorted_edges = sorted(G.edges(keys=True, data=True), key=lambda x: (str(x[0]), str(x[1]), x[2]))

        # Metric tracking counters
        missing_ids = 0
        missing_highway_type = 0
        missing_name = 0
        missing_or_invalid_lanes = 0
        estimated_lanes_count = 0
        missing_or_invalid_width = 0
        estimated_width_count = 0
        missing_or_invalid_length = 0
        missing_or_invalid_speed = 0
        estimated_speed_count = 0
        geometry_none_count = 0
        unique_highway_types: Set[str] = set()

        for idx, (u, v, k, data) in enumerate(sorted_edges, start=1):
            # 2a. Deterministic Project Road ID (R-001, R-002, ...)
            project_id = f"R-{idx:03d}" if idx < 1000 else f"R-{idx}"
            if not project_id:
                missing_ids += 1

            # 2b. Highway Type
            raw_hw = data.get("highway")
            hw_type = parse_highway_type(raw_hw)
            if not hw_type:
                missing_highway_type += 1
            unique_highway_types.add(hw_type)

            # 2c. Road Name
            raw_nm = data.get("name")
            road_name = parse_name(raw_nm)
            if road_name is None:
                missing_name += 1

            # 2d. Lanes & Provenance
            raw_lanes = data.get("lanes")
            lanes, lanes_src = parse_lanes(raw_lanes, hw_type)
            if lanes_src == "estimated":
                estimated_lanes_count += 1
            if lanes <= 0:
                missing_or_invalid_lanes += 1

            # 2e. Width & Provenance
            raw_width = data.get("width")
            width_m, width_src = parse_width(raw_width, hw_type)
            if width_src == "estimated":
                estimated_width_count += 1
            if width_m <= 0:
                missing_or_invalid_width += 1

            # 2f. Length
            raw_length = data.get("length")
            geom = data.get("geometry")
            length_m, is_len_valid = parse_length(raw_length, geom, G, u, v)
            if not is_len_valid or length_m <= 0:
                missing_or_invalid_length += 1

            # 2g. Speed & Provenance
            raw_speed = data.get("maxspeed")
            maxspeed_kmh, speed_src = parse_maxspeed(raw_speed, hw_type)
            if speed_src == "estimated":
                estimated_speed_count += 1
            if maxspeed_kmh <= 0:
                missing_or_invalid_speed += 1

            # 2h. Geometry check
            if geom is None:
                geometry_none_count += 1

            # Update edge data with normalized attributes
            G[u][v][k]["id"] = project_id
            G[u][v][k]["name"] = road_name if road_name is not None else ""
            G[u][v][k]["highway_type"] = hw_type
            G[u][v][k]["lanes"] = lanes
            G[u][v][k]["width_m"] = width_m
            G[u][v][k]["length_m"] = length_m
            G[u][v][k]["maxspeed_kmh"] = maxspeed_kmh
            G[u][v][k]["lanes_source"] = lanes_src
            G[u][v][k]["width_source"] = width_src
            G[u][v][k]["speed_source"] = speed_src

        # 3. SAVE ATTRIBUTED GRAPH
        print(f"[STAGE 3/4] Saving attributed graph to: {output_path} ...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(G, filepath=output_path)
        output_file_size = output_path.stat().st_size
        print(f"[SUCCESS] Attributed road graph saved ({output_file_size:,} bytes).")

        # 4. COMPREHENSIVE VALIDATION CHECKS
        print("[STAGE 4/4] Performing integrity and schema verifications...")
        output_node_count = G.number_of_nodes()
        output_edge_count = G.number_of_edges()
        self_loop_count = len(list(nx.selfloop_edges(G)))

        # Verification Assertions
        assert input_edge_count == output_edge_count, "Edge count mismatch!"
        assert input_node_count == output_node_count, "Node count mismatch!"
        assert missing_ids == 0, f"Found {missing_ids} missing road IDs!"
        assert missing_highway_type == 0, f"Found {missing_highway_type} missing highway types!"
        assert missing_or_invalid_length == 0, f"Found {missing_or_invalid_length} invalid lengths!"
        assert missing_or_invalid_lanes == 0, f"Found {missing_or_invalid_lanes} invalid lanes!"
        assert missing_or_invalid_width == 0, f"Found {missing_or_invalid_width} invalid widths!"
        assert missing_or_invalid_speed == 0, f"Found {missing_or_invalid_speed} invalid speeds!"

        # Print validation summary
        print("\n==================================================")
        print("C1 Road Attribute Normalization Summary")
        print("==================================================")
        print(f"1.  Input Node Count                 : {input_node_count}")
        print(f"2.  Input Edge Count                 : {input_edge_count}")
        print(f"3.  Output Node Count                : {output_node_count}")
        print(f"4.  Output Edge Count                : {output_edge_count}")
        print(f"5.  Unique Highway Types Count       : {len(unique_highway_types)}")
        print(f"6.  Highway Types Found              : {sorted(list(unique_highway_types))}")
        print(f"7.  Missing Road IDs                 : {missing_ids}")
        print(f"8.  Missing Highway Types            : {missing_highway_type}")
        print(f"9.  Unnamed Roads (name=None)        : {missing_name}")
        print(f"10. Missing/Invalid Lanes            : {missing_or_invalid_lanes}")
        print(f"11. Estimated Lane Count             : {estimated_lanes_count} ({estimated_lanes_count/output_edge_count*100:.1f}%)")
        print(f"12. Missing/Invalid Widths           : {missing_or_invalid_width}")
        print(f"13. Estimated Width Count            : {estimated_width_count} ({estimated_width_count/output_edge_count*100:.1f}%)")
        print(f"14. Missing/Invalid Lengths          : {missing_or_invalid_length}")
        print(f"15. Missing/Invalid MaxSpeeds        : {missing_or_invalid_speed}")
        print(f"16. Estimated MaxSpeed Count         : {estimated_speed_count} ({estimated_speed_count/output_edge_count*100:.1f}%)")
        print(f"17. Straight-Line Edges (geom=None)  : {geometry_none_count} (endpoint-derived)")
        print(f"18. Self-Loop Edge Count             : {self_loop_count}")
        print(f"19. Output File Path                 : {output_path.resolve()}")
        print(f"20. Output File Size                 : {output_file_size:,} bytes")
        print("==================================================")

        return True

    except Exception as e:
        print(f"\n[ERROR] Attribute processing failed: {str(e)}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Normalize and validate road attributes for C1/C2 routing graph."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Input cleaned GraphML file path (default: {DEFAULT_INPUT_PATH})"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Target attributed GraphML output path (default: {DEFAULT_OUTPUT_PATH})"
    )
    parser.add_argument(
        "--force",
        "--overwrite",
        action="store_true",
        help="Overwrite target attributed GraphML file if it already exists."
    )
    args = parser.parse_args()

    success = process_road_attributes(
        input_path=args.input,
        output_path=args.output,
        force=args.force
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
