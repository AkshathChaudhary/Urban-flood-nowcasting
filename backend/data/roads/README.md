# 🚗 Urban Flood Nowcasting — Road Network & Graph Engine (Pair C)

## 1. Executive Summary & Provenance
This directory contains the calibrated road transportation network and topological graph covering a **$2.0 \times 2.0\text{ km}$ ($400\text{ ha}$)** urban study area in **Kurla / Bandra-Kurla Complex (BKC), Mumbai, India** (`EPSG:4326`), coordinated with the subterranean drainage network (Pair A) and 2D flood depth grid (Pair B).

The dataset fuses **real OpenStreetMap (OSM) highway geometries** with **$10\text{m}$ hydro-conditioned Digital Elevation Model (DEM) grids** and highway design benchmarks from:
1. **Indian Roads Congress (IRC:73, IRC:86)** — Geometric design standards for urban roads.
2. **Ministry of Road Transport and Highways (MoRTH)** — Urban street cross-section specifications.
3. **OpenStreetMap Overpass API** — Real-world street topology, alignments, and classifications.
4. **CPHEEO & Chitale Committee Recommendations** — Road elevation low-points prone to water stagnation and culvert backwater ponding.

---

## 2. Network Topology & Road Classification

| Road Classification | Segments | Standard Lanes | Est. Width ($m$) | Base Speed ($km/h$) | Passing Elevation Range ($m$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Motorway / Trunk** | 24 | 4 – 6 | 14.0 – 21.0 | 60 – 80 | 4.5 – 12.0 |
| **Primary Arterials** (e.g. CST Rd, LBS Marg) | 88 | 4 | 14.0 | 50 | 3.2 – 8.5 |
| **Secondary Roads** | 62 | 2 | 7.5 | 40 | 3.0 – 7.8 |
| **Tertiary Streets** | 74 | 2 | 6.0 | 30 | 2.8 – 6.5 |
| **Residential / Unclassified** | 216 | 1 – 2 | 3.5 – 5.5 | 20 – 30 | 1.8 – 14.2 |
| **Total Road Segments** | **464** | — | — | — | **74.77 km Network** |
| **Graph Intersections (Nodes)** | **682** | — | — | — | **773 Directed Edges** |
| **Flood-Vulnerable Hotspots** | **63** | — | — | — | Elevation $\le 4.0\text{m}$ |

---

## 3. Physical & Routing Cost Formulation

### A. Base Traversal Time (Clear Road)
$$\tau_0(e) = \frac{L(e)}{v_{\text{max}}(e)}$$
Where:
* $L(e)$: Great-circle haversine segment length in meters.
* $v_{\text{max}}(e)$: Safe speed limit converted to $\text{m/s}$.

### B. Dynamic Flood Cost & Impassability Thresholds
Let $d(e, t)$ be the flood depth at the segment's geographic midpoint grid cell $(r, c)$ at time horizon $t$:
* **Vehicle Critical Depth Clearance ($d_{\text{crit}}$):**
  * Pedestrian: $0.15\text{ m}$ ($15\text{ cm}$)
  * Standard Car / Sedan: $0.30\text{ m}$ ($30\text{ cm}$)
  * SUV: $0.45\text{ m}$ ($45\text{ cm}$)
  * Emergency Ambulance: $0.45\text{ m}$ ($45\text{ cm}$)
  * Heavy Truck / Rescue Vehicle: $0.60\text{ m}$ ($60\text{ cm}$)

* **Effective Routing Weight:**
$$W(e) = \begin{cases} 
\infty & \text{if } d(e, t) \ge d_{\text{crit}} \quad (\text{Road Blocked / Submerged}) \\
\tau_0(e) \cdot 5.0 & \text{if } 0.15\text{ m} \le d(e, t) < d_{\text{crit}} \quad (\text{Severe Stagnation / Wake Hazard}) \\
\tau_0(e) \cdot 2.0 & \text{if } 0.05\text{ m} \le d(e, t) < 0.15\text{ m} \quad (\text{Moderate Ponding / Caution}) \\
\tau_0(e) & \text{if } d(e, t) < 0.05\text{ m} \quad (\text{Dry / Free Flow})
\end{cases}$$

### C. A* Heuristic
Haversine Euclidean distance lower bound to destination:
$$h(u, \text{dst}) = \frac{\text{haversine}(u, \text{dst})}{v_{\text{highway\_max}}}$$

---

## 4. File Inventory

```
backend/data/roads/
├── raw/
│   └── osm_roads_mumbai.json       # Raw Overpass API dump (464 ways, 2,604 nodes)
├── clean_roads.py                  # Processing pipeline converting OSM + DEM to GeoJSON & graph
├── fetch_real_roads.py             # Overpass API live fetcher (city-agnostic bounding box)
├── road_network.geojson            # FeatureCollection of LineStrings with physical attributes
├── road_graph.json                 # Serialized node coordinates & directed edge adjacency list
├── flood_hotspots.geojson          # 63 low-elevation intersections prone to severe inundation
└── README.md                       # This engineering reference document
```
