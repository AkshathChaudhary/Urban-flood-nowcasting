# Road Dynamic Flood Risk Integration Methodology

## Overview
This document specifies the integration methodology connecting the **C1 static road flood susceptibility index** with the **B2 dynamic 2D hydraulic flood simulation grids** across multiple forecast time horizons (T+0 to T+180 min).

> [!IMPORTANT]
> **Scientific Guidance & Operational Scope:**
> - **C1.7** provides a static susceptibility baseline derived from elevation, imperviousness, infiltration, flow accumulation, TWI, and slope.
> - **B2** provides dynamic surface water depth predictions (meters) on the shared 200×200 grid ($10\,\text{m} \times 10\,\text{m}$ resolution).
> - **C1.8** combines these layers into a unified time-evolving road-level dynamic risk indicator.
> - This integration is a preliminary risk indicator designed for vehicular routing and hotspot prioritization; it is **NOT** a certified flood hazard map unless calibrated against field observations.

---

## 1. Mathematical Formulation

For each road segment $i$ and forecast timestamp $t$:

### 1.1 Road Cell Aggregation
Using the verified road-to-DEM mapping (`road_grid_mapping.csv`):
- All 10m grid cells traversed by road segment $i$ are sampled from the B2 200×200 flood depth grid $D_t(r, c)$.
- $\text{mean\_flood\_depth\_m} = \frac{1}{N_i} \sum_{(r,c) \in \text{Cells}_i} D_t(r, c)$
- $\text{max\_flood\_depth\_m} = \max_{(r,c) \in \text{Cells}_i} D_t(r, c)$

### 1.2 Dynamic Flood Factor ($F_{\text{dyn}}(t)$)
Dynamic inundation depth is scaled into $[0.0, 1.0]$ based on the critical impassability threshold $D_{\text{crit}} = 0.50\,\text{m}$:

$$F_{\text{dyn}}(t) = \text{clip}\left(\frac{\text{max\_flood\_depth\_m}}{D_{\text{crit}}}, 0.0, 1.0\right)$$

### 1.3 Combined Dynamic Risk Score ($R_{\text{dyn}}(t)$)

$$R_{\text{dyn}}(t) = w_{\text{static}} \cdot S_{\text{static}} + w_{\text{dynamic}} \cdot F_{\text{dyn}}(t)$$

- **Static Weight ($w_{\text{static}}$)**: **40%** ($0.40$)
- **Dynamic Weight ($w_{\text{dynamic}}$)**: **60%** ($0.60$)
- **Critical Inundation Threshold ($D_{\text{crit}}$)**: **0.50 m**

---

## 2. Vehicular Hazard & Risk Thresholds

| Water Depth ($D$) | Dynamic Risk Class | Vehicular Impact |
| :--- | :--- | :--- |
| **$D < 0.10\,\text{m}$** | `LOW` ($<0.25$) | Passable by all standard vehicles; minor splashing. |
| **$0.10\,\text{m} \le D < 0.25\,\text{m}$** | `MODERATE` ($0.25 - 0.50$) | Caution required; small passenger cars face exhaust intake risks. |
| **$0.25\,\text{m} \le D < 0.40\,\text{m}$** | `HIGH` ($0.50 - 0.75$) | Impassable for light vehicles; emergency and heavy high-clearance vehicles only. |
| **$D \ge 0.40\,\text{m}$** | `VERY_HIGH` ($0.75 - 1.00$) | Complete road closure required; structural floating and severe hazard risk. |
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
1. **Empirical Calibration**: Calibrate $w_{\text{static}}$ vs $w_{\text{dynamic}}$ against real-world BMC/MCGM flood-logging logbooks.
2. **Vehicle Class Specific Weights**: Provide configurable $D_{\text{crit}}$ for two-wheelers ($0.15\,\text{m}$), passenger sedans ($0.25\,\text{m}$), and buses/trucks ($0.50\,\text{m}$).
3. **C2 Dynamic Routing Penalties**: Route travel time multipliers proportional to $R_{\text{dyn}}(t)$ for A* pathfinding.
