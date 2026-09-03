"""
C1.9 — Road Data Engineer: Road Flood Hotspot Detection & Prioritization
Urban Flood Nowcast Project

This script calculates multi-temporal road flood hotspot scores and rankings
from the dynamic road risk time-series (C1.8).

Outputs:
1. backend/data/roads/road_hotspots.csv
    Full tabular dataset containing per-road hotspot scores, risk duration,
    temporal peak timestamps, and deterministic rankings.
2. backend/data/roads/road_hotspots.geojson
    Map-ready vector layer for visualization of priority hotspot corridors.
3. backend/data/roads/top_road_hotspots.json
    Structured API-ready payload containing Top-10, Top-25, and Top-50 hotspots.
4. backend/data/roads/hotspot_methodology.md
    Technical documentation on the prioritization formulation, weights, and limitations.
"""

import sys
import csv
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Default paths
DEFAULT_DYNAMIC_CSV = CURRENT_DIR / "road_dynamic_risk.csv"
DEFAULT_GEOJSON_IN = CURRENT_DIR / "road_grid_mapping.geojson"

DEFAULT_OUTPUT_CSV = CURRENT_DIR / "road_hotspots.csv"
DEFAULT_OUTPUT_GEOJSON = CURRENT_DIR / "road_hotspots.geojson"
DEFAULT_OUTPUT_TOP_JSON = CURRENT_DIR / "top_road_hotspots.json"
DEFAULT_OUTPUT_DOC = CURRENT_DIR / "hotspot_methodology.md"

# -------------------------------------------------------------------------
# HOTSPOT PRIORITIZATION WEIGHTS & CONFIGURATION
# -------------------------------------------------------------------------

DEFAULT_HOTSPOT_WEIGHTS: Dict[str, float] = {
    "peak_depth": 0.40,      # 40% Peak inundation severity
    "persistence": 0.25,     # 25% High-risk duration persistence
    "peak_risk": 0.25,       # 25% Peak combined dynamic risk
    "static_susceptibility": 0.10,  # 10% Static topographic susceptibility
}

# Critical inundation depth scale in meters (0.50m represents critical vehicle impassability)
CRITICAL_FLOOD_DEPTH_M: float = 0.50

# Hotspot classification thresholds
HOTSPOT_THRESHOLDS = {
    "LOW": (0.00, 0.25),
    "MODERATE": (0.25, 0.50),
    "HIGH": (0.50, 0.75),
    "CRITICAL": (0.75, 1.00),
}


def classify_hotspot(score: Optional[float]) -> str:
    """Classifies a continuous hotspot prioritization score into qualitative bins."""
    if score is None:
        return "UNKNOWN"
    if score < 0.25:
        return "LOW"
    elif score < 0.50:
        return "MODERATE"
    elif score < 0.75:
        return "HIGH"
    else:
        return "CRITICAL"


def detect_and_rank_hotspots(
    dynamic_csv_path: Path = DEFAULT_DYNAMIC_CSV,
    geojson_in_path: Path = DEFAULT_GEOJSON_IN,
    output_csv_path: Path = DEFAULT_OUTPUT_CSV,
    output_geojson_path: Path = DEFAULT_OUTPUT_GEOJSON,
    output_top_json_path: Path = DEFAULT_OUTPUT_TOP_JSON,
    output_doc_path: Path = DEFAULT_OUTPUT_DOC,
    weights: Dict[str, float] = DEFAULT_HOTSPOT_WEIGHTS,
    critical_depth_m: float = CRITICAL_FLOOD_DEPTH_M,
) -> Dict[str, Any]:
    """
    Aggregates time-series risk data, computes hotspot scores, and generates outputs.
    """
    print("=================================================================")
    print("C1.9: Road Flood Hotspot Detection and Ranking")
    print("=================================================================")
    print(f"Dynamic Risk CSV Input : {dynamic_csv_path}")
    print(f"Output Hotspots CSV    : {output_csv_path}")
    print(f"Output Hotspots GeoJSON: {output_geojson_path}")
    print(f"Output Top-N JSON      : {output_top_json_path}")
    print(f"Output Methodology Doc : {output_doc_path}")
    print("-----------------------------------------------------------------")

    if not dynamic_csv_path.exists():
        raise FileNotFoundError(f"Dynamic risk CSV not found: {dynamic_csv_path}")

    # 1. LOAD TIME-SERIES DATA & GROUP BY ROAD ID
    print("[STAGE 1/5] Loading and grouping dynamic risk time-series...")
    road_timeseries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    total_records = 0

    with open(dynamic_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_records += 1
            road_timeseries[row["road_id"]].append(row)

    total_roads = len(road_timeseries)
    print(f"  -> Ingested {total_records:,} time-series records for {total_roads:,} road segments.")

    # 2. CALCULATE ROAD-LEVEL HOTSPOT METRICS & SCORES
    print("[STAGE 2/5] Calculating temporal metrics & multi-criteria hotspot scores...")
    hotspot_entries: List[Dict[str, Any]] = []

    for r_id, t_rows in road_timeseries.items():
        # Sort chronologically by timestamp
        t_rows.sort(key=lambda x: x["timestamp"])
        first_row = t_rows[0]
        num_ts = len(t_rows)

        source = first_row["source"]
        target = first_row["target"]
        length_m = float(first_row["length_m"])
        road_class = first_row["road_class"]

        is_mapped = first_row["static_susceptibility"] != ""

        if is_mapped:
            # Numeric series
            max_depths = [float(r["max_flood_depth_m"]) for r in t_rows]
            mean_depths = [float(r["mean_flood_depth_m"]) for r in t_rows]
            comb_risks = [float(r["combined_risk"]) for r in t_rows]
            static_s = float(first_row["static_susceptibility"])

            peak_depth = float(np.max(max_depths))
            mean_depth = float(np.mean(mean_depths))
            peak_risk = float(np.max(comb_risks))
            mean_risk = float(np.mean(comb_risks))

            # Duration metrics
            risk_duration = sum(1 for rk in comb_risks if rk >= 0.25)
            high_risk_duration = sum(1 for rk in comb_risks if rk >= 0.50)
            very_high_risk_duration = sum(1 for rk in comb_risks if rk >= 0.75)
            frac_high_risk = high_risk_duration / float(num_ts)

            # Temporal milestones
            first_high_ts = None
            first_crit_ts = None
            for r in t_rows:
                rk = float(r["combined_risk"])
                if rk >= 0.50 and first_high_ts is None:
                    first_high_ts = r["timestamp"]
                if rk >= 0.75 and first_crit_ts is None:
                    first_crit_ts = r["timestamp"]

            peak_risk_idx = int(np.argmax(comb_risks))
            peak_risk_ts = t_rows[peak_risk_idx]["timestamp"]
            peak_depth_idx = int(np.argmax(max_depths))
            peak_depth_ts = t_rows[peak_depth_idx]["timestamp"]

            # Hotspot Score Formulation
            s_depth = float(np.clip(peak_depth / critical_depth_m, 0.0, 1.0))
            s_persist = float(np.clip(frac_high_risk, 0.0, 1.0))
            s_peak_risk = float(np.clip(peak_risk, 0.0, 1.0))
            s_static = float(np.clip(static_s, 0.0, 1.0))

            composite_score = (
                weights["peak_depth"] * s_depth +
                weights["persistence"] * s_persist +
                weights["peak_risk"] * s_peak_risk +
                weights["static_susceptibility"] * s_static
            )
            composite_score = round(float(np.clip(composite_score, 0.0, 1.0)), 4)
            h_class = classify_hotspot(composite_score)

            hotspot_entries.append({
                "road_id": r_id,
                "source": source,
                "target": target,
                "length_m": round(length_m, 2),
                "road_class": road_class,
                "is_mapped": True,
                "hotspot_score": composite_score,
                "hotspot_class": h_class,
                "peak_flood_depth_m": round(peak_depth, 3),
                "mean_flood_depth_m": round(mean_depth, 3),
                "peak_combined_risk": round(peak_risk, 4),
                "mean_combined_risk": round(mean_risk, 4),
                "risk_duration": risk_duration,
                "high_risk_duration": high_risk_duration,
                "very_high_risk_duration": very_high_risk_duration,
                "fraction_of_time_high_risk": round(frac_high_risk, 3),
                "first_high_risk_timestamp": first_high_ts,
                "first_critical_timestamp": first_crit_ts,
                "peak_risk_timestamp": peak_risk_ts,
                "peak_flood_depth_timestamp": peak_depth_ts,
                "number_of_timestamps": num_ts,
            })
        else:
            hotspot_entries.append({
                "road_id": r_id,
                "source": source,
                "target": target,
                "length_m": round(length_m, 2),
                "road_class": road_class,
                "is_mapped": False,
                "hotspot_score": None,
                "hotspot_class": "UNKNOWN",
                "peak_flood_depth_m": None,
                "mean_flood_depth_m": None,
                "peak_combined_risk": None,
                "mean_combined_risk": None,
                "risk_duration": 0,
                "high_risk_duration": 0,
                "very_high_risk_duration": 0,
                "fraction_of_time_high_risk": 0.0,
                "first_high_risk_timestamp": None,
                "first_critical_timestamp": None,
                "peak_risk_timestamp": None,
                "peak_flood_depth_timestamp": None,
                "number_of_timestamps": num_ts,
            })

    # 3. DETERMINISTIC RANKING
    print("[STAGE 3/5] Sorting and assigning deterministic priority ranks...")
    mapped_entries = [e for e in hotspot_entries if e["is_mapped"]]
    unmapped_entries = [e for e in hotspot_entries if not e["is_mapped"]]

    # Sort descending by: (1) hotspot_score, (2) peak_flood_depth_m, (3) peak_combined_risk, (4) road_id ascending
    mapped_entries.sort(key=lambda x: (
        -x["hotspot_score"],
        -x["peak_flood_depth_m"],
        -x["peak_combined_risk"],
        x["road_id"]
    ))
    unmapped_entries.sort(key=lambda x: x["road_id"])

    ranked_all_entries: List[Dict[str, Any]] = []
    for idx, e in enumerate(mapped_entries, start=1):
        e["rank"] = idx
        ranked_all_entries.append(e)

    for idx, e in enumerate(unmapped_entries, start=len(mapped_entries) + 1):
        e["rank"] = idx
        ranked_all_entries.append(e)

    # 4. WRITE CSV OUTPUT
    print("[STAGE 4/5] Writing outputs...")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_headers = [
        "rank", "road_id", "source", "target", "length_m", "road_class",
        "hotspot_score", "hotspot_class", "peak_flood_depth_m", "mean_flood_depth_m",
        "peak_combined_risk", "mean_combined_risk", "risk_duration",
        "high_risk_duration", "very_high_risk_duration", "fraction_of_time_high_risk",
        "first_high_risk_timestamp", "first_critical_timestamp",
        "peak_risk_timestamp", "peak_flood_depth_timestamp", "number_of_timestamps"
    ]

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for e in ranked_all_entries:
            row_dict = {
                "rank": e["rank"],
                "road_id": e["road_id"],
                "source": e["source"],
                "target": e["target"],
                "length_m": e["length_m"],
                "road_class": e["road_class"],
                "hotspot_score": e["hotspot_score"] if e["hotspot_score"] is not None else "",
                "hotspot_class": e["hotspot_class"],
                "peak_flood_depth_m": e["peak_flood_depth_m"] if e["peak_flood_depth_m"] is not None else "",
                "mean_flood_depth_m": e["mean_flood_depth_m"] if e["mean_flood_depth_m"] is not None else "",
                "peak_combined_risk": e["peak_combined_risk"] if e["peak_combined_risk"] is not None else "",
                "mean_combined_risk": e["mean_combined_risk"] if e["mean_combined_risk"] is not None else "",
                "risk_duration": e["risk_duration"],
                "high_risk_duration": e["high_risk_duration"],
                "very_high_risk_duration": e["very_high_risk_duration"],
                "fraction_of_time_high_risk": e["fraction_of_time_high_risk"] if e["is_mapped"] else "",
                "first_high_risk_timestamp": e["first_high_risk_timestamp"] if e["first_high_risk_timestamp"] is not None else "",
                "first_critical_timestamp": e["first_critical_timestamp"] if e["first_critical_timestamp"] is not None else "",
                "peak_risk_timestamp": e["peak_risk_timestamp"] if e["peak_risk_timestamp"] is not None else "",
                "peak_flood_depth_timestamp": e["peak_flood_depth_timestamp"] if e["peak_flood_depth_timestamp"] is not None else "",
                "number_of_timestamps": e["number_of_timestamps"],
            }
            writer.writerow(row_dict)
    print(f"  -> Saved CSV: {output_csv_path} ({len(ranked_all_entries):,} rows)")

    # 5. WRITE GEOJSON
    hotspots_by_id = {e["road_id"]: e for e in ranked_all_entries}
    if geojson_in_path.exists():
        with open(geojson_in_path, "r", encoding="utf-8") as f:
            base_geojson = json.load(f)

        for feat in base_geojson.get("features", []):
            r_id = feat["properties"]["road_id"]
            if r_id in hotspots_by_id:
                h_info = hotspots_by_id[r_id]
                feat["properties"]["rank"] = h_info["rank"]
                feat["properties"]["hotspot_score"] = h_info["hotspot_score"]
                feat["properties"]["hotspot_class"] = h_info["hotspot_class"]
                feat["properties"]["peak_flood_depth_m"] = h_info["peak_flood_depth_m"]
                feat["properties"]["mean_flood_depth_m"] = h_info["mean_flood_depth_m"]
                feat["properties"]["peak_combined_risk"] = h_info["peak_combined_risk"]
                feat["properties"]["risk_duration"] = h_info["risk_duration"]
                feat["properties"]["high_risk_duration"] = h_info["high_risk_duration"]
                feat["properties"]["peak_risk_timestamp"] = h_info["peak_risk_timestamp"]
                feat["properties"]["first_high_risk_timestamp"] = h_info["first_high_risk_timestamp"]
                feat["properties"]["first_critical_timestamp"] = h_info["first_critical_timestamp"]

        with open(output_geojson_path, "w", encoding="utf-8") as f:
            json.dump(base_geojson, f, indent=2)
        print(f"  -> Saved GeoJSON: {output_geojson_path} ({len(base_geojson.get('features', [])):,} features)")

    # 6. WRITE TOP-N JSON
    def format_top_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "rank": entry["rank"],
            "road_id": entry["road_id"],
            "road_class": entry["road_class"],
            "hotspot_score": entry["hotspot_score"],
            "hotspot_class": entry["hotspot_class"],
            "peak_flood_depth_m": entry["peak_flood_depth_m"],
            "mean_flood_depth_m": entry["mean_flood_depth_m"],
            "peak_combined_risk": entry["peak_combined_risk"],
            "high_risk_duration_timesteps": entry["high_risk_duration"],
            "peak_risk_timestamp": entry["peak_risk_timestamp"],
            "first_high_risk_timestamp": entry["first_high_risk_timestamp"],
            "first_critical_timestamp": entry["first_critical_timestamp"],
        }

    top_json_payload = {
        "generated_from": "road_dynamic_risk.csv",
        "study_area": "Mumbai 2x2km",
        "total_evaluated_roads": total_roads,
        "total_ranked_hotspots": len(mapped_entries),
        "scoring_weights": weights,
        "critical_depth_threshold_m": critical_depth_m,
        "top_10": [format_top_entry(e) for e in mapped_entries[:10]],
        "top_25": [format_top_entry(e) for e in mapped_entries[:25]],
        "top_50": [format_top_entry(e) for e in mapped_entries[:50]],
    }

    with open(output_top_json_path, "w", encoding="utf-8") as f:
        json.dump(top_json_payload, f, indent=2)
    print(f"  -> Saved Top-N Hotspots JSON: {output_top_json_path}")

    # 7. WRITE METHODOLOGY DOC
    write_hotspot_methodology_doc(output_doc_path, weights, critical_depth_m)

    # 8. SUMMARY REPORT
    scores_mapped = [e["hotspot_score"] for e in mapped_entries]
    class_counts = {
        "LOW": sum(1 for e in mapped_entries if e["hotspot_class"] == "LOW"),
        "MODERATE": sum(1 for e in mapped_entries if e["hotspot_class"] == "MODERATE"),
        "HIGH": sum(1 for e in mapped_entries if e["hotspot_class"] == "HIGH"),
        "CRITICAL": sum(1 for e in mapped_entries if e["hotspot_class"] == "CRITICAL"),
        "UNKNOWN": len(unmapped_entries),
    }

    summary = {
        "total_roads": total_roads,
        "roads_usable": len(mapped_entries),
        "roads_missing": len(unmapped_entries),
        "num_timestamps": mapped_entries[0]["number_of_timestamps"] if mapped_entries else 0,
        "min_score": round(float(np.min(scores_mapped)), 4) if scores_mapped else None,
        "max_score": round(float(np.max(scores_mapped)), 4) if scores_mapped else None,
        "mean_score": round(float(np.mean(scores_mapped)), 4) if scores_mapped else None,
        "class_counts": class_counts,
        "top_10_roads": [e["road_id"] for e in mapped_entries[:10]],
    }

    print("=================================================================")
    print("C1.9 ROAD FLOOD HOTSPOT PRIORITIZATION SUMMARY")
    print("=================================================================")
    print(f"Total roads evaluated             : {summary['total_roads']:,}")
    print(f"Roads with usable time series     : {summary['roads_usable']:,} ({summary['roads_usable']/total_roads*100:.1f}%)")
    print(f"Roads with missing DEM/B2 data    : {summary['roads_missing']:,} ({summary['roads_missing']/total_roads*100:.1f}%)")
    print(f"Total timestamps evaluated        : {summary['num_timestamps']}")
    print(f"Highest hotspot score             : {summary['max_score']}")
    print(f"Lowest hotspot score              : {summary['min_score']}")
    print(f"Mean hotspot score                : {summary['mean_score']}")
    print(f"LOW                               : {class_counts['LOW']}")
    print(f"MODERATE                          : {class_counts['MODERATE']}")
    print(f"HIGH                              : {class_counts['HIGH']}")
    print(f"CRITICAL                          : {class_counts['CRITICAL']}")
    print(f"Top 10 Hotspot Road IDs           : {', '.join(summary['top_10_roads'])}")
    print("=================================================================")

    return summary


def write_hotspot_methodology_doc(
    doc_path: Path,
    weights: Dict[str, float],
    crit_depth: float
):
    """Writes the technical documentation for hotspot ranking."""
    content = f"""# Road Flood Hotspot Detection and Ranking Methodology

## Overview
This document specifies the methodology for detecting, scoring, and ranking **road flood hotspots** across the Mumbai 2x2 km study area based on the dynamic C1+B2 time-series outputs (C1.9).

> [!IMPORTANT]
> **Operational Guidance & Scientific Scope:**
> - C1.9 provides a **multi-temporal prioritization and ranking layer** to identify critical road segments most severely affected by inundation and risk persistence.
> - It is **NOT** a new hydrodynamic model; it synthesizes the time-series outputs generated by the C1.8 integration pipeline.
> - Hotspot rankings are designed for emergency response dispatching, traffic rerouting priority, and mitigation planning.

---

## 1. Hotspot Prioritization Formulation

The composite Hotspot Score S_hotspot in [0.0, 1.0] combines four key risk dimensions:

Score = w_depth * S_depth + w_persist * S_persist + w_peak_risk * S_peak_risk + w_static * S_static

### Feature Weights

| Factor | Component | Weight | Rationale |
| :--- | :--- | :---: | :--- |
| **Peak Flood Severity** | S_depth | **{weights['peak_depth']*100:.0f}%** (0.40) | Maximum predicted water depth scaled against critical depth threshold D_crit = {crit_depth:.2f} m. |
| **Risk Persistence** | S_persist | **{weights['persistence']*100:.0f}%** (0.25) | Proportion of time horizons during which the road remains in HIGH or VERY_HIGH risk states. |
| **Peak Combined Risk** | S_peak_risk | **{weights['peak_risk']*100:.0f}%** (0.25) | Maximum combined dynamic risk score reached during the storm simulation. |
| **Static Susceptibility** | S_static | **{weights['static_susceptibility']*100:.0f}%** (0.10) | Baseline terrain and soil vulnerability index (C1.7). |

Total Weights Sum = 100% (1.00)

---

## 2. Component Normalization

1. **Peak Flood Depth Factor (S_depth)**:
   S_depth = clip(peak_flood_depth_m / {crit_depth:.2f}, 0.0, 1.0)
2. **Risk Persistence Factor (S_persist)**:
   S_persist = high_risk_duration_timesteps / total_timesteps
3. **Peak Combined Risk Factor (S_peak_risk)**:
   S_peak_risk = peak_combined_risk
4. **Static Susceptibility Factor (S_static)**:
   S_static = static_susceptibility

---

## 3. Qualitative Hotspot Severity Tiers

| Score Range | Hotspot Class | Operational Interpretation |
| :--- | :--- | :--- |
| **0.00 <= S < 0.25** | `LOW` | Minimal water accumulation; normal traffic operations continue. |
| **0.25 <= S < 0.50** | `MODERATE` | Transient shallow ponding; caution advised for low-clearance vehicles. |
| **0.50 <= S < 0.75** | `HIGH` | Substantial inundation or extended risk duration; targeted for active traffic diversion. |
| **0.75 <= S <= 1.00** | `CRITICAL` | Severe inundation (>= 0.40m) or persistent impassability; immediate emergency response priority. |
| **null** | `UNKNOWN` | Road segments in outer buffer zone without DEM/B2 coverage (252 roads). |

---

## 4. Deterministic Ranking & Tie-Breaking

Road segments are sorted descending using strict hierarchical ordering:
1. `hotspot_score` (descending)
2. `peak_flood_depth_m` (descending)
3. `peak_combined_risk` (descending)
4. `road_id` (ascending deterministic tie-breaker)

---

## 5. Limitations & Next Steps
- Weights should be calibrated against emergency department road closure records during monsoon events.
- Traffic volume / critical arterial classifications from C2 should be factored into operational dispatch weights.
"""
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Saved methodology document: {doc_path}")


def main():
    parser = argparse.ArgumentParser(description="Detect and rank road flood hotspots.")
    parser.add_argument("--dynamic-csv", type=Path, default=DEFAULT_DYNAMIC_CSV)
    parser.add_argument("--geojson-in", type=Path, default=DEFAULT_GEOJSON_IN)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-geojson", type=Path, default=DEFAULT_OUTPUT_GEOJSON)
    parser.add_argument("--output-top-json", type=Path, default=DEFAULT_OUTPUT_TOP_JSON)
    parser.add_argument("--output-doc", type=Path, default=DEFAULT_OUTPUT_DOC)
    args = parser.parse_args()

    detect_and_rank_hotspots(
        dynamic_csv_path=args.dynamic_csv,
        geojson_in_path=args.geojson_in,
        output_csv_path=args.output_csv,
        output_geojson_path=args.output_geojson,
        output_top_json_path=args.output_top_json,
        output_doc_path=args.output_doc,
    )


if __name__ == "__main__":
    main()
