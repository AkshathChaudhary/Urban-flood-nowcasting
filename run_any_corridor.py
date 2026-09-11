"""
Run Any Corridor: Unified Tri-Model Execution CLI
=================================================

Allows input of ANY two locations (names, landmarks, addresses, or coordinates)
and executes all 3 core research models sequentially:
  1. Subterranean Storm Drainage Hydraulics (Pair A)
  2. 2D Hydrodynamic Surface Flood Simulation (Pair B)
  3. Dynamic Flood-Resilient Vehicle Routing (Pair C)
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.app.engine.corridor_pipeline import run_unified_corridor_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Unified Tri-Model Execution Across Any Two Geographic Locations"
    )
    parser.add_argument(
        "--src",
        type=str,
        default=None,
        help="Origin location name, landmark, or 'lat, lon'",
    )
    parser.add_argument(
        "--dst",
        type=str,
        default=None,
        help="Destination location name, landmark, or 'lat, lon'",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["moderate", "heavy", "extreme", "cloudburst"],
        default="heavy",
        help="Monsoon rainfall intensity scenario (default: heavy)",
    )
    parser.add_argument(
        "--vehicle",
        type=str,
        choices=["car", "suv", "ambulance", "truck", "pedestrian"],
        default="car",
        help="Vehicle class clearance constraint (default: car)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=60,
        help="Simulation forecast horizon in minutes (default: 60)",
    )

    args = parser.parse_args()

    # Interactive input if not provided via CLI flags
    src_input = args.src
    dst_input = args.dst

    if not src_input:
        print("=" * 75)
        print(" 🚀 RUN ANY CORRIDOR — UNIFIED TRI-MODEL SIMULATION & ROUTING")
        print("=" * 75)
        print("\nQuick presets you can try:")
        print("  • Kolkata Corridor : 'Kestopur'  -> 'Ruby Hospital'")
        print("  • Mumbai Basin     : 'BKC'        -> 'Kurla Station'")
        print("  • Custom Addr / GPS: Any landmark or 'lat, lon'")
        src_input = input("\n👉 Enter Origin Location [Default: 'Kestopur']: ").strip()
        if not src_input:
            src_input = "Kestopur"

    if not dst_input:
        dst_input = input("👉 Enter Destination Location [Default: 'Ruby Hospital']: ").strip()
        if not dst_input:
            dst_input = "Ruby Hospital"

    run_unified_corridor_pipeline(
        src_input=src_input,
        dst_input=dst_input,
        scenario=args.scenario,
        vehicle_type=args.vehicle,
        horizon_minutes=args.horizon,
    )


if __name__ == "__main__":
    main()
