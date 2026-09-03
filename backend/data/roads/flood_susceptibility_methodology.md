# Road Flood Susceptibility Scoring Methodology

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
| **Elevation** | S_elev | **20%** (0.20) | Low-lying depressions and coastal lowlands collect surface runoff. |
| **Imperviousness** | S_imp | **20%** (0.20) | High paved surface fraction inhibits soil percolation and accelerates surface runoff volume. |
| **Infiltration Capacity** | S_inf | **15%** (0.15) | Soil permeability directly governs rainfall absorption; low infiltration increases ponding. |
| **Flow Accumulation** | S_fa | **20%** (0.20) | Upstream contributing catchment size determines hydrological convergence and concentrated flow. |
| **Topographic Wetness Index** | S_twi | **15%** (0.15) | ln(a / tan(beta)) measures steady-state wetness and potential water stagnation tendencies. |
| **Terrain Slope** | S_slope | **10%** (0.10) | Flatter slopes reduce gravitational drainage velocity, promoting localized waterlogging. |

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
