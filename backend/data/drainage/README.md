# 🌊 Urban Flood Nowcasting — Subterranean Drainage Network (Pair A)

## 1. Executive Summary & Provenance
This directory contains the calibrated storm water drainage (SWD) network dataset covering a **$2.0 \times 2.0\text{ km}$ ($400\text{ ha}$)** urban study area in **Kurla / Bandra-Kurla Complex (BKC), Mumbai, India** (`EPSG:4326`).

The dataset fuses **real OpenStreetMap (OSM) subterranean infrastructure** with **SRTM 30m / ALOS World 3D DEM elevation grids (interpolated to 10m)** and municipal civil engineering benchmarks from:
1. **Brihanmumbai Municipal Corporation (BMC) Storm Water Drainage Department** (Master Plan & SWD Design Manual).
2. **Fact-Finding Committee on Mumbai Floods (Chitale Committee, 2006)**.
3. **BRIMSTOWAD** (Brihanmumbai Storm Water Drainage Project) Feasibility Reports.
4. **CPHEEO Manual on Urban Storm Water Drainage Systems** (Ministry of Housing and Urban Affairs, Govt. of India).
5. **Indian Roads Congress Guidelines for Urban Drainage (IRC:SP:50)**.

---

## 2. Network Topology & Municipal Calibration

| Component | Raw Unfiltered OSM | Calibrated Final Dataset | Municipal Benchmark / Source |
| :--- | :--- | :--- | :--- |
| **Total Drainage Nodes** | 1,479 | **1,479** | Mapped to $10\text{m}$ DEM elevation grid |
| **Surface Curb Inlets** | 17 (sparse tags) | **1,005** (820 in $2\times 2\text{km}$ core) | CPHEEO / IRC standard: $25\text{--}35\text{m}$ curb spacing along arterial roads |
| **Internal Pipe Junctions / Manholes** | 1,389 | **466** | Intermediate inspection chambers every $30\text{--}50\text{m}$ |
| **Primary River Outfalls** | 73 (unfiltered artifacts) | **8 Calibrated Outfalls** | Chitale Report 2006: 107 outfalls along entire $17.8\text{km}$ Mithi course ($\approx 5\text{--}8$ per $2\text{km}$ reach) |
| **Total Pipe Segments (Edges)** | 1,316 | **1,316** | Directed graph with downhill slope $S \ge 0.0001$ |
| **Conduit Diameters** | Missing / Default | **$0.6\text{m}$ to $2.5\text{m}$** | $0.6\text{--}0.9\text{m}$ lateral street drains, $1.2\text{--}2.5\text{m}$ trunk nalas & culverts |
| **Roughness Coefficient ($n$)** | N/A | **$0.014\text{--}0.024$** | $0.015$ aged concrete pipe, $0.022$ brick masonry, $0.025$ natural nala bed |

---

## 3. Physical & Hydraulic Governing Equations

### A. Pipe Conveyance Capacity (Manning's Open-Channel / Pipe Equation)
For each conduit $e = (u, v)$:
$$Q_{\text{full}} = \frac{1}{n} \cdot A \cdot R_h^{2/3} \cdot S_0^{1/2} \cdot (1 - \beta)$$
Where:
* $Q_{\text{full}}$: Maximum discharge capacity ($\text{m}^3/\text{s}$).
* $n$: Manning's roughness coefficient ($0.014\text{--}0.024$).
* $A = \pi \cdot (D / 2)^2$: Full-pipe cross-sectional area ($\text{m}^2$).
* $R_h = D / 4$: Hydraulic radius for circular section ($\text{m}$).
* $S_0 = \max\left(\frac{z_u - z_v}{L}, 0.0001\right)$: Longitudinal hydraulic bed slope ($\text{m/m}$).
* $\beta \in [0.0, 1.0]$: Silt / solid waste blockage ratio (Scenario 5 testing: $\beta = 0.40$).

### B. Surface Runoff Ingestion (Orifice / Weir Inlet Flow)
For surface curb inlets during flood timesteps $\Delta t = 300\text{s}$:
$$V_{\text{absorbed}} = \min\left(h_{\text{surface}} \cdot A_{\text{cell}}, \; Q_{\text{inlet}} \cdot \Delta t\right)$$
Where $A_{\text{cell}} = 10\text{m} \times 10\text{m} = 100\text{m}^2$.

### C. Manhole Surcharge & Surface Backflow
When subterranean storage at node $i$ exceeds its storage capacity $V_{\max} = Q_{\text{cap}} \cdot \Delta t$:
$$V_{\text{overflow}} = \max\left(0, \; V_{\text{current}} - V_{\max}\right)$$
This excess surcharge water is returned to the surface flood grid $h_{\text{surface}}$ to feed Pair B's 2D flood model and penalize flooded road corridors in Pair C's routing.

---

## 4. File Inventory

```
backend/data/drainage/
├── drainage_nodes.geojson         # 1,479 points (inlet, junction, outfall) with DEM elevation
├── drainage_edges.geojson         # 1,316 lines with diameter, slope, roughness, capacity
├── clean_drainage.py              # Calibration and pipeline cleaning script
├── fetch_real_osm_drainage.py     # Overpass Turbo API extractor
├── visualize_drainage_simulation.py # 4-panel hydraulic validation visualizer
├── drainage_simulation_results.png # High-resolution 160 DPI output graphic
└── README.md                      # This technical data provenance document
```

---

## 5. System Integration Contracts

### Pair B (Flood Engine) $\leftrightarrow$ Pair A
* `DrainageGraph.absorb_surface_water(depth_grid: np.ndarray, dt: float) -> np.ndarray`
* `DrainageGraph.propagate_flow(dt: float) -> float`
* `DrainageGraph.compute_overflow(dt: float) -> dict[str, float]`

### Pair C (Road Routing) $\leftrightarrow$ Pair A
* Real-time node surcharge risk: `GET /api/drainage/nodes`
* Pipe capacity vs load ratio: `GET /api/drainage/edges`
