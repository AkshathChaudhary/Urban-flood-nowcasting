"""
C1.7 — Road Data Engineer: Road Flood Susceptibility Scoring Pipeline
Urban Flood Nowcast Project

This script calculates a transparent, deterministic, multi-criteria flood susceptibility
score for every road segment using the derived DEM terrain and hydrological features.

Outputs:
1. backend/data/roads/road_flood_susceptibility.csv
    Tabular output containing road metadata, composite susceptibility scores,
    risk classifications (LOW, MODERATE, HIGH, VERY_HIGH), and component scores.
2. backend/data/roads/road_flood_susceptibility.geojson
    Map-ready vector layer preserving LineString geometries with risk properties.
3. backend/data/roads/road_graph_with_risk.json
    Canonical road graph enriched with a 'flood_risk' attribute block on each edge.
4. backend/data/roads/flood_susceptibility_methodology.md
    Technical documentation detailing the scoring formulation, normalizations,
    weights, assumptions, and scientific limitations.
"""

import sys
import csv
import json
import math
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Default file paths
DEFAULT_FEATURES_CSV = CURRENT_DIR / "road_flood_features.csv"
DEFAULT_GRAPH_WITH_FEATURES_JSON = CURRENT_DIR / "road_graph_with_features.json"
DEFAULT_GEOJSON_IN = CURRENT_DIR / "road_grid_mapping.geojson"

DEFAULT_OUTPUT_CSV = CURRENT_DIR / "road_flood_susceptibility.csv"
DEFAULT_OUTPUT_GEOJSON = CURRENT_DIR / "road_flood_susceptibility.geojson"
DEFAULT_OUTPUT_GRAPH_JSON = CURRENT_DIR / "road_graph_with_risk.json"
DEFAULT_OUTPUT_DOC = CURRENT_DIR / "flood_susceptibility_methodology.md"

# -------------------------------------------------------------------------
# SCORING CONFIGURATION & HEURISTIC WEIGHTS
# -------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "elevation": 0.20,
    "imperviousness": 0.20,
    "infiltration": 0.15,
    "flow_accumulation": 0.20,
    "twi": 0.15,
    "slope": 0.10,
}

# Empirical reference normalization thresholds based on Mumbai 2x2 km study area
ELEV_MIN: float = -3.0   # Lowest depression / tidal lowland (m ASL)
ELEV_MAX: float = 30.0   # Higher ridge / hilltop (m ASL)

IMP_MIN: float = 0.50    # Minimum urban imperviousness
IMP_MAX: float = 0.85    # High density built-up imperviousness

INF_MIN: float = 1.50    # Minimum infiltration rate (mm/hr)
INF_MAX: float = 5.00    # Maximum infiltration rate (mm/hr)

LOG_FA_MIN: float = math.log1p(1.0)     # Minimum log1p flow accumulation
LOG_FA_MAX: float = math.log1p(500.0)   # 99th percentile log1p flow accumulation

TWI_MIN: float = 5.0     # Minimum Topographic Wetness Index
TWI_MAX: float = 13.0    # Maximum Topographic Wetness Index

SLOPE_MIN: float = 0.0   # Flat terrain prone to pooling (degrees)
SLOPE_MAX: float = 12.0  # Moderate/high gradient facilitating runoff drainage (degrees)

# Risk classification thresholds
RISK_THRESHOLDS = {
    "LOW": (0.00, 0.25),
    "MODERATE": (0.25, 0.50),
    "HIGH": (0.50, 0.75),
    "VERY_HIGH": (0.75, 1.00),
}


def compute_component_scores(feature_row: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Computes individual [0, 1] normalized component scores for a single road record.
    Returns None if the road has no DEM mapping (grid_cell_count == 0).
    """
    cell_count = int(feature_row.get("grid_cell_count", 0))
    if cell_count == 0 or feature_row.get("mean_elevation_m") in ["", None]:
        return None

    # 1. Elevation Score (Lower elevation -> Higher flood susceptibility)
    elev = float(feature_row["mean_elevation_m"])
    s_elev = float(1.0 - np.clip((elev - ELEV_MIN) / (ELEV_MAX - ELEV_MIN), 0.0, 1.0))

    # 2. Imperviousness Score (Higher imperviousness -> Higher runoff)
    imp = float(feature_row["mean_imperviousness"])
    s_imp = float(np.clip((imp - IMP_MIN) / (IMP_MAX - IMP_MIN), 0.0, 1.0))

    # 3. Infiltration Score (Lower infiltration -> Higher surface ponding)
    inf = float(feature_row["mean_infiltration_mm_hr"])
    s_inf = float(1.0 - np.clip((inf - INF_MIN) / (INF_MAX - INF_MIN), 0.0, 1.0))

    # 4. Flow Accumulation Score (Log-scaled: Higher upstream area -> Higher flow volume)
    fa_str = feature_row.get("mean_flow_accumulation", "")
    fa = float(fa_str) if fa_str != "" else 1.0
    s_fa = float(np.clip((math.log1p(fa) - LOG_FA_MIN) / (LOG_FA_MAX - LOG_FA_MIN), 0.0, 1.0))

    # 5. Topographic Wetness Index Score (Higher TWI -> Higher moisture / saturation)
    twi_str = feature_row.get("mean_twi", "")
    twi = float(twi_str) if twi_str != "" else 7.0
    s_twi = float(np.clip((twi - TWI_MIN) / (TWI_MAX - TWI_MIN), 0.0, 1.0))

    # 6. Slope Score (Lower slope -> Poor drainage / water logging prone)
    slope_str = feature_row.get("mean_slope_deg", "")
    if slope_str != "":
        slope = float(slope_str)
        s_slope = float(1.0 - np.clip((slope - SLOPE_MIN) / (SLOPE_MAX - SLOPE_MIN), 0.0, 1.0))
    else:
        s_slope = 0.5  # Neutral default when slope raster has boundary nodata

    return {
        "elevation_score": round(s_elev, 4),
        "imperviousness_score": round(s_imp, 4),
        "infiltration_score": round(s_inf, 4),
        "flow_accumulation_score": round(s_fa, 4),
        "twi_score": round(s_twi, 4),
        "slope_score": round(s_slope, 4),
    }


def classify_risk(score: Optional[float]) -> str:
    """Classifies a continuous [0, 1] flood susceptibility score into qualitative bins."""
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


def calculate_flood_susceptibility(
    features_csv_path: Path = DEFAULT_FEATURES_CSV,
    graph_json_path: Path = DEFAULT_GRAPH_WITH_FEATURES_JSON,
    geojson_in_path: Path = DEFAULT_GEOJSON_IN,
    output_csv_path: Path = DEFAULT_OUTPUT_CSV,
    output_geojson_path: Path = DEFAULT_OUTPUT_GEOJSON,
    output_graph_json_path: Path = DEFAULT_OUTPUT_GRAPH_JSON,
    output_doc_path: Path = DEFAULT_OUTPUT_DOC,
    weights: Dict[str, float] = DEFAULT_WEIGHTS,
) -> Dict[str, Any]:
    """
    Executes the complete Road Flood Susceptibility scoring and exporter pipeline.
    """
    print("=================================================================")
    print("C1.7: Road Flood Susceptibility Scoring Pipeline")
    print("=================================================================")
    print(f"Features CSV Input  : {features_csv_path}")
    print(f"Graph JSON Input    : {graph_json_path}")
    print(f"Output CSV          : {output_csv_path}")
    print(f"Output GeoJSON      : {output_geojson_path}")
    print(f"Output Graph JSON   : {output_graph_json_path}")
    print(f"Output Methodology  : {output_doc_path}")
    print("-----------------------------------------------------------------")

    # 1. LOAD FEATURES CSV
    if not features_csv_path.exists():
        raise FileNotFoundError(f"Features CSV missing: {features_csv_path}")
    if not graph_json_path.exists():
        raise FileNotFoundError(f"Graph JSON missing: {graph_json_path}")

    print("[STAGE 1/5] Loading road features...")
    features_data: List[Dict[str, Any]] = []
    with open(features_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            features_data.append(r)

    total_roads = len(features_data)
    print(f"  -> Loaded {total_roads:,} road records.")

    # 2. CALCULATE SCORES
    print("[STAGE 2/5] Calculating multi-criteria composite susceptibility scores...")
    road_scores: Dict[str, Dict[str, Any]] = {}
    csv_rows: List[Dict[str, Any]] = []

    risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "VERY_HIGH": 0, "UNKNOWN": 0}
    scores_list: List[float] = []

    for r in features_data:
        r_id = r["road_id"]
        source = r["source"]
        target = r["target"]
        length_m = float(r["length_m"])
        road_class = r["road_class"]

        comp_scores = compute_component_scores(r)

        if comp_scores is not None:
            # Weighted sum
            composite_score = (
                weights["elevation"] * comp_scores["elevation_score"] +
                weights["imperviousness"] * comp_scores["imperviousness_score"] +
                weights["infiltration"] * comp_scores["infiltration_score"] +
                weights["flow_accumulation"] * comp_scores["flow_accumulation_score"] +
                weights["twi"] * comp_scores["twi_score"] +
                weights["slope"] * comp_scores["slope_score"]
            )
            composite_score = round(float(np.clip(composite_score, 0.0, 1.0)), 4)
            risk_class = classify_risk(composite_score)
            scores_list.append(composite_score)
        else:
            composite_score = None
            risk_class = "UNKNOWN"

        risk_counts[risk_class] += 1

        road_score_entry = {
            "road_id": r_id,
            "source": source,
            "target": target,
            "length_m": length_m,
            "road_class": road_class,
            "flood_susceptibility_score": composite_score,
            "risk_class": risk_class,
            "elevation_score": comp_scores["elevation_score"] if comp_scores else None,
            "imperviousness_score": comp_scores["imperviousness_score"] if comp_scores else None,
            "infiltration_score": comp_scores["infiltration_score"] if comp_scores else None,
            "flow_accumulation_score": comp_scores["flow_accumulation_score"] if comp_scores else None,
            "twi_score": comp_scores["twi_score"] if comp_scores else None,
            "slope_score": comp_scores["slope_score"] if comp_scores else None,
        }
        road_scores[r_id] = road_score_entry

        csv_rows.append({
            "road_id": r_id,
            "source": source,
            "target": target,
            "length_m": round(length_m, 2),
            "road_class": road_class,
            "flood_susceptibility_score": composite_score if composite_score is not None else "",
            "risk_class": risk_class,
            "elevation_score": comp_scores["elevation_score"] if comp_scores else "",
            "imperviousness_score": comp_scores["imperviousness_score"] if comp_scores else "",
            "infiltration_score": comp_scores["infiltration_score"] if comp_scores else "",
            "flow_accumulation_score": comp_scores["flow_accumulation_score"] if comp_scores else "",
            "twi_score": comp_scores["twi_score"] if comp_scores else "",
            "slope_score": comp_scores["slope_score"] if comp_scores else "",
        })

    # 3. WRITE CSV
    print("[STAGE 3/5] Writing road_flood_susceptibility.csv...")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "road_id", "source", "target", "length_m", "road_class",
        "flood_susceptibility_score", "risk_class",
        "elevation_score", "imperviousness_score", "infiltration_score",
        "flow_accumulation_score", "twi_score", "slope_score"
    ]
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"  -> Saved CSV: {output_csv_path} ({len(csv_rows):,} rows)")

    # 4. WRITE GEOJSON
    print("[STAGE 4/5] Generating map-ready GeoJSON with susceptibility scores...")
    if geojson_in_path.exists():
        with open(geojson_in_path, "r", encoding="utf-8") as f:
            base_geojson = json.load(f)

        for feat in base_geojson.get("features", []):
            r_id = feat["properties"]["road_id"]
            if r_id in road_scores:
                score_info = road_scores[r_id]
                feat["properties"]["flood_susceptibility_score"] = score_info["flood_susceptibility_score"]
                feat["properties"]["risk_class"] = score_info["risk_class"]
                feat["properties"]["elevation_score"] = score_info["elevation_score"]
                feat["properties"]["imperviousness_score"] = score_info["imperviousness_score"]
                feat["properties"]["infiltration_score"] = score_info["infiltration_score"]
                feat["properties"]["flow_accumulation_score"] = score_info["flow_accumulation_score"]
                feat["properties"]["twi_score"] = score_info["twi_score"]
                feat["properties"]["slope_score"] = score_info["slope_score"]

        with open(output_geojson_path, "w", encoding="utf-8") as f:
            json.dump(base_geojson, f, indent=2)
        print(f"  -> Saved GeoJSON: {output_geojson_path} ({len(base_geojson.get('features', [])):,} features)")

    # 5. WRITE ENRICHED ROAD GRAPH WITH RISK
    print("[STAGE 5/5] Writing road_graph_with_risk.json...")
    with open(graph_json_path, "r", encoding="utf-8") as f:
        graph_obj = json.load(f)

    for edge in graph_obj.get("edges", []):
        r_id = edge["road_id"]
        if r_id in road_scores:
            s_info = road_scores[r_id]
            edge["flood_risk"] = {
                "score": s_info["flood_susceptibility_score"],
                "class": s_info["risk_class"],
                "component_scores": {
                    "elevation": s_info["elevation_score"],
                    "imperviousness": s_info["imperviousness_score"],
                    "infiltration": s_info["infiltration_score"],
                    "flow_accumulation": s_info["flow_accumulation_score"],
                    "twi": s_info["twi_score"],
                    "slope": s_info["slope_score"],
                }
            }

    with open(output_graph_json_path, "w", encoding="utf-8") as f:
        json.dump(graph_obj, f, indent=2)
    print(f"  -> Saved road graph with risk JSON: {output_graph_json_path} ({output_graph_json_path.stat().st_size / 1024:.1f} KB)")

    # 6. WRITE METHODOLOGY DOCUMENT
    write_methodology_doc(output_doc_path, weights)

    # 7. SUMMARY REPORT
    summary = {
        "total_roads": total_roads,
        "roads_scored": len(scores_list),
        "roads_unmapped": risk_counts["UNKNOWN"],
        "min_score": round(float(np.min(scores_list)), 4) if scores_list else None,
        "mean_score": round(float(np.mean(scores_list)), 4) if scores_list else None,
        "max_score": round(float(np.max(scores_list)), 4) if scores_list else None,
        "risk_distribution": risk_counts,
    }

    print("=================================================================")
    print("C1.7 FLOOD SUSCEPTIBILITY VALIDATION SUMMARY")
    print("=================================================================")
    print(f"Total roads evaluated             : {summary['total_roads']:,}")
    print(f"Roads scored                      : {summary['roads_scored']:,} ({summary['roads_scored']/total_roads*100:.1f}%)")
    print(f"Roads without sufficient DEM data : {summary['roads_unmapped']:,}")
    print(f"Minimum score                     : {summary['min_score']}")
    print(f"Maximum score                     : {summary['max_score']}")
    print(f"Mean score                        : {summary['mean_score']}")
    print(f"LOW                               : {risk_counts['LOW']}")
    print(f"MODERATE                          : {risk_counts['MODERATE']}")
    print(f"HIGH                              : {risk_counts['HIGH']}")
    print(f"VERY_HIGH                         : {risk_counts['VERY_HIGH']}")
    print("=================================================================")

    return summary


def write_methodology_doc(doc_path: Path, weights: Dict[str, float]):
    """Writes the scientific documentation and limitations markdown file."""
    w_elev = int(weights['elevation'] * 100)
    w_imp = int(weights['imperviousness'] * 100)
    w_inf = int(weights['infiltration'] * 100)
    w_fa = int(weights['flow_accumulation'] * 100)
    w_twi = int(weights['twi'] * 100)
    w_slope = int(weights['slope'] * 100)

    content = f"""# Road Flood Susceptibility Scoring Methodology

## Overview
This document outlines the formulation, normalization methodology, heuristic weighting, and scientific limitations of the **first-pass road flood susceptibility score** for the Mumbai 2x2 km study area (C1.7).

> [!IMPORTANT]
> **Scientific Limitations & Operational Guidance:**
> - This score is a **static, terrain-based susceptibility index** representing relative topographic and physical vulnerability to surface water accumulation.
> - It is **NOT** a dynamic flood forecast, hydrodynamic simulation, or calibrated flood prediction.
> - Current calculations do **not** yet incorporate real-time rainfall depth/intensity, storm duration, tidal surge levels, or underground storm sewer capacity.
> - Feature weights are **heuristic baseline coefficients** that must be calibrated and validated against B2 2D hydraulic flood-depth outputs and empirical flood observations.
> - **A road segment with a HIGH or VERY_HIGH susceptibility score should NOT be assumed to be actively inundated** without dynamic hydrologic forcing.

---

## 1. Multi-Criteria Scoring Formulation

The composite Flood Susceptibility Score is computed as a linear weighted combination of six normalized component scores:

Score = w_elev * S_elev + w_imp * S_imp + w_inf * S_inf + w_fa * S_fa + w_twi * S_twi + w_slope * S_slope

### Feature Weights

| Factor | Component | Weight | Rationale |
| :--- | :--- | :---: | :--- |
| **Elevation** | S_elev | **{w_elev}%** (0.20) | Low-lying depressions and coastal lowlands collect surface runoff. |
| **Imperviousness** | S_imp | **{w_imp}%** (0.20) | High paved surface fraction inhibits soil percolation and accelerates surface runoff volume. |
| **Infiltration Capacity** | S_inf | **{w_inf}%** (0.15) | Soil permeability directly governs rainfall absorption; low infiltration increases ponding. |
| **Flow Accumulation** | S_fa | **{w_fa}%** (0.20) | Upstream contributing catchment size determines hydrological convergence and concentrated flow. |
| **Topographic Wetness Index** | S_twi | **{w_twi}%** (0.15) | ln(a / tan(beta)) measures steady-state wetness and potential water stagnation tendencies. |
| **Terrain Slope** | S_slope | **{w_slope}%** (0.10) | Flatter slopes reduce gravitational drainage velocity, promoting localized waterlogging. |

Total Weights Sum = 100% (1.00)

---

## 2. Normalization Methodology

Each raw environmental metric is transformed into a continuous component score in [0.0, 1.0] such that **1.0 represents maximum susceptibility** and **0.0 represents minimum susceptibility**.

### 2.1 Elevation (S_elev)
- **Concept**: Lower elevation corresponds to higher flood risk.
- **Reference Range**: ELEV_min = -3.0 m, ELEV_max = 30.0 m ASL.
- **Formula**:
  S_elev = 1.0 - clip((elevation - (-3.0)) / (30.0 - (-3.0)), 0.0, 1.0)

### 2.2 Imperviousness (S_imp)
- **Concept**: High urban paving increases surface runoff coefficient.
- **Reference Range**: IMP_min = 0.50, IMP_max = 0.85.
- **Formula**:
  S_imp = clip((imperviousness - 0.50) / (0.85 - 0.50), 0.0, 1.0)

### 2.3 Infiltration (S_inf)
- **Concept**: Low soil infiltration capacity increases water accumulation.
- **Reference Range**: INF_min = 1.50 mm/hr, INF_max = 5.00 mm/hr.
- **Formula**:
  S_inf = 1.0 - clip((infiltration - 1.50) / (5.00 - 1.50), 0.0, 1.0)

### 2.4 Flow Accumulation (S_fa)
- **Concept**: Upstream contributing drainage cells exhibit exponential distribution. A logarithmic transformation is applied to prevent extreme outliers from distorting the score.
- **Reference Range**: ln(1 + 1.0) to ln(1 + 500.0).
- **Formula**:
  S_fa = clip((ln(1 + FlowAccum) - ln(2)) / (ln(501) - ln(2)), 0.0, 1.0)

### 2.5 Topographic Wetness Index (S_twi)
- **Concept**: Higher TWI values represent saturated depressions and natural drainage pathways.
- **Reference Range**: TWI_min = 5.0, TWI_max = 13.0.
- **Formula**:
  S_twi = clip((TWI - 5.0) / (13.0 - 5.0), 0.0, 1.0)

### 2.6 Slope Gradient (S_slope)
- **Concept**: Flat roads (0 to 2 deg) retain ponding water, whereas sloped roads allow runoff to shed downhill.
- **Reference Range**: SLOPE_min = 0.0 deg, SLOPE_max = 12.0 deg.
- **Formula**:
  S_slope = 1.0 - clip((slope - 0.0) / (12.0 - 0.0), 0.0, 1.0)

---

## 3. Qualitative Risk Classification

| Score Range | Risk Class | Interpretation |
| :--- | :--- | :--- |
| **0.00 <= S < 0.25** | `LOW` | High ground, low flow convergence, good natural drainage. |
| **0.25 <= S < 0.50** | `MODERATE` | Intermediate elevation or moderate imperviousness; minor ponding risk. |
| **0.50 <= S < 0.75** | `HIGH` | Low-lying, heavily paved, or elevated upstream contributing catchment. |
| **0.75 <= S <= 1.00** | `VERY_HIGH` | Critical topographic depression, concentrated flow accumulation path, high imperviousness. |
| **null** | `UNKNOWN` | Road segment outside DEM grid extent (no terrain data available). |

---

## 4. Calibration & Next Steps
1. **Coupling with B2 Hydraulic Model**: Cross-validate susceptibility scores against 2D Saint-Venant hydraulic flood depth grids generated during simulation runs.
2. **Rainfall Forcing Integration**: Multiply static susceptibility scores by dynamic hyetograph precipitation intensities.
3. **Drainage Network Capacity**: Integrate with storm sewer inlet capacities from C2/drainage models.
"""
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Saved methodology document: {doc_path}")



def main():
    parser = argparse.ArgumentParser(description="Calculate road flood susceptibility scores.")
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument("--graph-json", type=Path, default=DEFAULT_GRAPH_WITH_FEATURES_JSON)
    parser.add_argument("--geojson-in", type=Path, default=DEFAULT_GEOJSON_IN)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-geojson", type=Path, default=DEFAULT_OUTPUT_GEOJSON)
    parser.add_argument("--output-graph-json", type=Path, default=DEFAULT_OUTPUT_GRAPH_JSON)
    parser.add_argument("--output-doc", type=Path, default=DEFAULT_OUTPUT_DOC)
    args = parser.parse_args()

    calculate_flood_susceptibility(
        features_csv_path=args.features_csv,
        graph_json_path=args.graph_json,
        geojson_in_path=args.geojson_in,
        output_csv_path=args.output_csv,
        output_geojson_path=args.output_geojson,
        output_graph_json_path=args.output_graph_json,
        output_doc_path=args.output_doc,
    )


if __name__ == "__main__":
    main()
