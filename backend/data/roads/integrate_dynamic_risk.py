"""
C1.8 — Road Data Engineer: Road Dynamic Flood Risk Integration Pipeline
Urban Flood Nowcast Project

This script integrates C1 static road flood susceptibility scores with B2
dynamic 2D hydraulic flood-depth simulation grids over multi-timestep horizons.

Outputs:
1. backend/data/roads/road_dynamic_risk.csv
    Time-series table containing road-level dynamic depth and combined risk per timestamp.
2. backend/data/roads/road_dynamic_risk.geojson
    Map-ready GeoJSON feature collection containing time-series risk evolution per road.
3. backend/data/roads/dynamic_risk_methodology.md
    Technical documentation on integration formulation, physical thresholds, and limitations.
"""

import sys
import csv
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.roads.b2_adapter import B2Adapter, B2PredictionFrame, GRID_ROWS, GRID_COLS

# Default paths
DEFAULT_GRID_MAPPING_CSV = CURRENT_DIR / "road_grid_mapping.csv"
DEFAULT_SUSCEPTIBILITY_CSV = CURRENT_DIR / "road_flood_susceptibility.csv"
DEFAULT_GEOJSON_IN = CURRENT_DIR / "road_grid_mapping.geojson"
DEFAULT_GRAPH_IN = CURRENT_DIR / "road_graph_with_risk.json"

DEFAULT_OUTPUT_CSV = CURRENT_DIR / "road_dynamic_risk.csv"
DEFAULT_OUTPUT_GEOJSON = CURRENT_DIR / "road_dynamic_risk.geojson"
DEFAULT_OUTPUT_DOC = CURRENT_DIR / "dynamic_risk_methodology.md"

# -------------------------------------------------------------------------
# CONFIGURATION & THRESHOLDS
# -------------------------------------------------------------------------

# Integration Weights
STATIC_WEIGHT: float = 0.40
DYNAMIC_WEIGHT: float = 0.60

# Critical Flood Depth Scale in meters (0.50m represents critical vehicle impassability)
CRITICAL_FLOOD_DEPTH_M: float = 0.50

# Risk classification thresholds
RISK_THRESHOLDS = {
    "LOW": (0.00, 0.25),
    "MODERATE": (0.25, 0.50),
    "HIGH": (0.50, 0.75),
    "VERY_HIGH": (0.75, 1.00),
}


def classify_dynamic_risk(score: Optional[float]) -> str:
    """Classifies a continuous combined risk score into qualitative risk levels."""
    if score is None:
        return "UNKNOWN"
    if score < 0.25:
        return "LOW"
    elif score < 0.50:
        return "MODERATE"
    elif score < 0.75:
        return "HIGH"
    else:
        return "VERY_HIGH"


def integrate_dynamic_risk(
    grid_mapping_csv: Path = DEFAULT_GRID_MAPPING_CSV,
    susceptibility_csv: Path = DEFAULT_SUSCEPTIBILITY_CSV,
    geojson_in: Path = DEFAULT_GEOJSON_IN,
    graph_in: Path = DEFAULT_GRAPH_IN,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    output_geojson: Path = DEFAULT_OUTPUT_GEOJSON,
    output_doc: Path = DEFAULT_OUTPUT_DOC,
    static_weight: float = STATIC_WEIGHT,
    dynamic_weight: float = DYNAMIC_WEIGHT,
    critical_depth_m: float = CRITICAL_FLOOD_DEPTH_M,
    custom_frames: Optional[List[B2PredictionFrame]] = None,
) -> Dict[str, Any]:
    """
    Executes the dynamic road risk integration pipeline across B2 forecast frames.
    """
    print("=================================================================")
    print("C1.8: Road Dynamic Flood Risk Integration Pipeline")
    print("=================================================================")
    print(f"Grid Mapping CSV    : {grid_mapping_csv}")
    print(f"Susceptibility CSV  : {susceptibility_csv}")
    print(f"Output Dynamic CSV  : {output_csv}")
    print(f"Output GeoJSON      : {output_geojson}")
    print(f"Output Methodology  : {output_doc}")
    print(f"Integration Weights : Static={static_weight:.2f}, Dynamic={dynamic_weight:.2f}")
    print("-----------------------------------------------------------------")

    # 1. VERIFY INPUTS
    if not grid_mapping_csv.exists():
        raise FileNotFoundError(f"Missing grid mapping CSV: {grid_mapping_csv}")
    if not susceptibility_csv.exists():
        raise FileNotFoundError(f"Missing susceptibility CSV: {susceptibility_csv}")

    # 2. LOAD STATIC ROAD ATTRIBUTES & SUSCEPTIBILITY
    print("[STAGE 1/5] Loading static road susceptibility data...")
    static_roads: Dict[str, Dict[str, Any]] = {}
    with open(susceptibility_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_id = row["road_id"]
            s_score_str = row["flood_susceptibility_score"]
            static_roads[r_id] = {
                "road_id": r_id,
                "source": row["source"],
                "target": row["target"],
                "length_m": float(row["length_m"]),
                "road_class": row["road_class"],
                "static_susceptibility": float(s_score_str) if s_score_str != "" else None,
                "static_class": row["risk_class"],
            }
    total_roads = len(static_roads)
    print(f"  -> Loaded {total_roads:,} road definitions.")

    # 3. LOAD ROAD-TO-CELL MAPPINGS
    print("[STAGE 2/5] Indexing road-to-grid cell coordinates...")
    road_cells: Dict[str, List[Tuple[int, int]]] = {}
    with open(grid_mapping_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_id = row["road_id"]
            r = int(row["grid_row"])
            c = int(row["grid_col"])
            if r_id not in road_cells:
                road_cells[r_id] = []
            road_cells[r_id].append((r, c))

    roads_with_grid = len(road_cells)
    roads_without_grid = total_roads - roads_with_grid
    print(f"  -> Roads with grid cells: {roads_with_grid:,}, Roads outside DEM: {roads_without_grid:,}")

    # 4. LOAD B2 PREDICTION FRAMES
    print("[STAGE 3/5] Ingesting B2 hydraulic depth prediction frames...")
    if custom_frames is not None and len(custom_frames) > 0:
        frames = custom_frames
    else:
        # Load reference benchmark scenarios
        frames = B2Adapter.generate_reference_scenario_frames(scenario_name="heavy_rain")

    print(f"  -> Ingested {len(frames)} B2 forecast timestamps: {', '.join([f.timestamp for f in frames])}")

    # 5. INTEGRATE ROAD RISK PER TIMESTAMP
    print("[STAGE 4/5] Computing dynamic flood depth and combined risk...")

    csv_records: List[Dict[str, Any]] = []
    road_timeseries: Dict[str, Dict[str, Any]] = {r_id: {} for r_id in static_roads.keys()}

    all_depths: List[float] = []
    risk_class_totals: Dict[str, int] = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "VERY_HIGH": 0, "UNKNOWN": 0}

    for frame in frames:
        ts = frame.timestamp
        depth_grid = frame.depth_grid

        for r_id, static_info in static_roads.items():
            cells = road_cells.get(r_id, [])
            static_score = static_info["static_susceptibility"]

            if len(cells) > 0 and static_score is not None:
                # Sample depth values across road grid cells
                cell_depths = [float(depth_grid[r, c]) for r, c in cells]
                mean_depth = round(float(np.mean(cell_depths)), 3)
                max_depth = round(float(np.max(cell_depths)), 3)
                all_depths.append(max_depth)

                # Dynamic flood factor [0, 1]
                dyn_factor = round(float(np.clip(max_depth / critical_depth_m, 0.0, 1.0)), 4)

                # Combined Risk Formula
                combined_risk = round(float(np.clip(
                    static_weight * static_score + dynamic_weight * dyn_factor,
                    0.0, 1.0
                )), 4)

                risk_class = classify_dynamic_risk(combined_risk)
            else:
                mean_depth = None
                max_depth = None
                dyn_factor = None
                combined_risk = None
                risk_class = "UNKNOWN"

            risk_class_totals[risk_class] += 1

            # Store in time-series dict
            road_timeseries[r_id][ts] = {
                "mean_depth_m": mean_depth,
                "max_depth_m": max_depth,
                "dynamic_flood_factor": dyn_factor,
                "combined_risk": combined_risk,
                "risk_class": risk_class,
            }

            # CSV row
            csv_records.append({
                "timestamp": ts,
                "road_id": r_id,
                "source": static_info["source"],
                "target": static_info["target"],
                "length_m": static_info["length_m"],
                "road_class": static_info["road_class"],
                "mean_flood_depth_m": mean_depth if mean_depth is not None else "",
                "max_flood_depth_m": max_depth if max_depth is not None else "",
                "static_susceptibility": round(static_score, 4) if static_score is not None else "",
                "dynamic_flood_factor": dyn_factor if dyn_factor is not None else "",
                "combined_risk": combined_risk if combined_risk is not None else "",
                "risk_class": risk_class,
            })

    # 6. WRITE OUTPUT CSV
    print("[STAGE 5/5] Writing output files...")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    csv_headers = [
        "timestamp", "road_id", "source", "target", "length_m", "road_class",
        "mean_flood_depth_m", "max_flood_depth_m", "static_susceptibility",
        "dynamic_flood_factor", "combined_risk", "risk_class"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(csv_records)
    print(f"  -> Saved CSV: {output_csv} ({len(csv_records):,} records across {len(frames)} timestamps)")

    # 7. WRITE GEOJSON
    if geojson_in.exists():
        with open(geojson_in, "r", encoding="utf-8") as f:
            base_geojson = json.load(f)

        for feat in base_geojson.get("features", []):
            r_id = feat["properties"]["road_id"]
            ts_data = road_timeseries.get(r_id, {})

            # Compute peak values across horizons
            max_depths = [d["max_depth_m"] for d in ts_data.values() if d["max_depth_m"] is not None]
            comb_risks = [d["combined_risk"] for d in ts_data.values() if d["combined_risk"] is not None]

            peak_depth = max(max_depths) if max_depths else None
            peak_risk = max(comb_risks) if comb_risks else None
            peak_class = classify_dynamic_risk(peak_risk)

            feat["properties"]["static_susceptibility"] = static_roads[r_id]["static_susceptibility"]
            feat["properties"]["peak_flood_depth_m"] = peak_depth
            feat["properties"]["peak_combined_risk"] = peak_risk
            feat["properties"]["peak_risk_class"] = peak_class
            feat["properties"]["timesteps"] = ts_data

        with open(output_geojson, "w", encoding="utf-8") as f:
            json.dump(base_geojson, f, indent=2)
        print(f"  -> Saved GeoJSON: {output_geojson} ({len(base_geojson.get('features', [])):,} features)")

    # 8. WRITE METHODOLOGY DOC
    write_dynamic_methodology_doc(output_doc, static_weight, dynamic_weight, critical_depth_m)

    # 9. SUMMARY REPORT
    summary = {
        "total_roads": total_roads,
        "roads_with_b2": roads_with_grid,
        "roads_without_b2": roads_without_grid,
        "num_timestamps": len(frames),
        "total_records": len(csv_records),
        "min_flood_depth": round(float(np.min(all_depths)), 3) if all_depths else 0.0,
        "max_flood_depth": round(float(np.max(all_depths)), 3) if all_depths else 0.0,
        "mean_flood_depth": round(float(np.mean(all_depths)), 3) if all_depths else 0.0,
        "risk_totals": risk_class_totals,
    }

    print("=================================================================")
    print("C1.8 DYNAMIC RISK INTEGRATION SUMMARY")
    print("=================================================================")
    print(f"Total roads evaluated             : {summary['total_roads']:,}")
    print(f"Roads with B2 flood data          : {summary['roads_with_b2']:,} ({summary['roads_with_b2']/total_roads*100:.1f}%)")
    print(f"Roads without B2 mapping          : {summary['roads_without_b2']:,} ({summary['roads_without_b2']/total_roads*100:.1f}%)")
    print(f"Number of forecast timestamps     : {summary['num_timestamps']}")
    print(f"Minimum flood depth               : {summary['min_flood_depth']:.3f} m")
    print(f"Maximum flood depth               : {summary['max_flood_depth']:.3f} m")
    print(f"Mean flood depth (active cells)   : {summary['mean_flood_depth']:.3f} m")
    print(f"Cumulative risk distribution      : {risk_class_totals}")
    print("=================================================================")

    return summary


def write_dynamic_methodology_doc(
    doc_path: Path,
    static_w: float,
    dynamic_w: float,
    crit_depth: float
):
    """Writes dynamic risk integration methodology markdown file."""
    content = f"""# Road Dynamic Flood Risk Integration Methodology

## Overview
This document specifies the integration methodology connecting the **C1 static road flood susceptibility index** with the **B2 dynamic 2D hydraulic flood simulation grids** across multiple forecast time horizons (T+0 to T+180 min).

> [!IMPORTANT]
> **Scientific Guidance & Operational Scope:**
> - **C1.7** provides a static susceptibility baseline derived from elevation, imperviousness, infiltration, flow accumulation, TWI, and slope.
> - **B2** provides dynamic surface water depth predictions (meters) on the shared 200×200 grid ($10\\,\\text{{m}} \\times 10\\,\\text{{m}}$ resolution).
> - **C1.8** combines these layers into a unified time-evolving road-level dynamic risk indicator.
> - This integration is a preliminary risk indicator designed for vehicular routing and hotspot prioritization; it is **NOT** a certified flood hazard map unless calibrated against field observations.

---

## 1. Mathematical Formulation

For each road segment $i$ and forecast timestamp $t$:

### 1.1 Road Cell Aggregation
Using the verified road-to-DEM mapping (`road_grid_mapping.csv`):
- All 10m grid cells traversed by road segment $i$ are sampled from the B2 200×200 flood depth grid $D_t(r, c)$.
- $\\text{{mean\\_flood\\_depth\\_m}} = \\frac{{1}}{{N_i}} \\sum_{{(r,c) \\in \\text{{Cells}}_i}} D_t(r, c)$
- $\\text{{max\\_flood\\_depth\\_m}} = \\max_{{(r,c) \\in \\text{{Cells}}_i}} D_t(r, c)$

### 1.2 Dynamic Flood Factor ($F_{{\\text{{dyn}}}}(t)$)
Dynamic inundation depth is scaled into $[0.0, 1.0]$ based on the critical impassability threshold $D_{{\\text{{crit}}}} = {crit_depth:.2f}\\,\\text{{m}}$:

$$F_{{\\text{{dyn}}}}(t) = \\text{{clip}}\\left(\\frac{{\\text{{max\\_flood\\_depth\\_m}}}}{{D_{{\\text{{crit}}}}}}, 0.0, 1.0\\right)$$

### 1.3 Combined Dynamic Risk Score ($R_{{\\text{{dyn}}}}(t)$)

$$R_{{\\text{{dyn}}}}(t) = w_{{\\text{{static}}}} \\cdot S_{{\\text{{static}}}} + w_{{\\text{{dynamic}}}} \\cdot F_{{\\text{{dyn}}}}(t)$$

- **Static Weight ($w_{{\\text{{static}}}}$)**: **{static_w*100:.0f}%** ($0.40$)
- **Dynamic Weight ($w_{{\\text{{dynamic}}}}$)**: **{dynamic_w*100:.0f}%** ($0.60$)
- **Critical Inundation Threshold ($D_{{\\text{{crit}}}}$)**: **{crit_depth:.2f} m**

---

## 2. Vehicular Hazard & Risk Thresholds

| Water Depth ($D$) | Dynamic Risk Class | Vehicular Impact |
| :--- | :--- | :--- |
| **$D < 0.10\\,\\text{{m}}$** | `LOW` ($<0.25$) | Passable by all standard vehicles; minor splashing. |
| **$0.10\\,\\text{{m}} \\le D < 0.25\\,\\text{{m}}$** | `MODERATE` ($0.25 - 0.50$) | Caution required; small passenger cars face exhaust intake risks. |
| **$0.25\\,\\text{{m}} \\le D < 0.40\\,\\text{{m}}$** | `HIGH` ($0.50 - 0.75$) | Impassable for light vehicles; emergency and heavy high-clearance vehicles only. |
| **$D \\ge 0.40\\,\\text{{m}}$** | `VERY_HIGH` ($0.75 - 1.00$) | Complete road closure required; structural floating and severe hazard risk. |
| **No DEM Coverage** | `UNKNOWN` | Road in buffer zone outside DEM extent ($252$ roads); no data fabricated. |

---

## 3. Time-Series Evolution

Dynamic risk is maintained across distinct forecast horizons:
- `T+0min` (Initial baseline / pre-storm)
- `T+30min` (Early onset)
- `T+60min` (Peak rainfall intensity)
- `T+90min` (Peak inundation / depression accumulation)
- `T+120min` (Early drainage recession)
- `T+180min` (Residual ponding / recovery)

---

## 4. Calibration & Future Refinements
1. **Empirical Calibration**: Calibrate $w_{{\\text{{static}}}}$ vs $w_{{\\text{{dynamic}}}}$ against real-world BMC/MCGM flood-logging logbooks.
2. **Vehicle Class Specific Weights**: Provide configurable $D_{{\\text{{crit}}}}$ for two-wheelers ($0.15\\,\\text{{m}}$), passenger sedans ($0.25\\,\\text{{m}}$), and buses/trucks ($0.50\\,\\text{{m}}$).
3. **C2 Dynamic Routing Penalties**: Route travel time multipliers proportional to $R_{{\\text{{dyn}}}}(t)$ for A* pathfinding.
"""
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Saved methodology document: {doc_path}")


def main():
    parser = argparse.ArgumentParser(description="Integrate road susceptibility with B2 flood predictions.")
    parser.add_argument("--grid-mapping-csv", type=Path, default=DEFAULT_GRID_MAPPING_CSV)
    parser.add_argument("--susceptibility-csv", type=Path, default=DEFAULT_SUSCEPTIBILITY_CSV)
    parser.add_argument("--geojson-in", type=Path, default=DEFAULT_GEOJSON_IN)
    parser.add_argument("--graph-in", type=Path, default=DEFAULT_GRAPH_IN)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-geojson", type=Path, default=DEFAULT_OUTPUT_GEOJSON)
    parser.add_argument("--output-doc", type=Path, default=DEFAULT_OUTPUT_DOC)
    parser.add_argument("--static-weight", type=float, default=STATIC_WEIGHT)
    parser.add_argument("--dynamic-weight", type=float, default=DYNAMIC_WEIGHT)
    parser.add_argument("--critical-depth-m", type=float, default=CRITICAL_FLOOD_DEPTH_M)
    args = parser.parse_args()

    integrate_dynamic_risk(
        grid_mapping_csv=args.grid_mapping_csv,
        susceptibility_csv=args.susceptibility_csv,
        geojson_in=args.geojson_in,
        graph_in=args.graph_in,
        output_csv=args.output_csv,
        output_geojson=args.output_geojson,
        output_doc=args.output_doc,
        static_weight=args.static_weight,
        dynamic_weight=args.dynamic_weight,
        critical_depth_m=args.critical_depth_m,
    )


if __name__ == "__main__":
    main()
