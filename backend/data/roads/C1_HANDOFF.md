# C1 Component Handoff Documentation: Road Network Flood Risk & Hotspot System

## 1. Executive Summary
The **C1 Road Data Engineering & Inundation Risk Pipeline** provides high-resolution road-network flood risk analytics, multi-criteria static terrain susceptibility, 2D hydraulic flood-depth integration with B2 simulation grids, multi-temporal hotspot rankings, a RESTful Flask API, and an interactive GIS frontend dashboard for the Mumbai 2×2 km study area.

---

## 2. Road Network Specifications
- **Source Dataset**: OpenStreetMap Mumbai road network (`backend/data/roads/raw/osm_roads_mumbai_attributes.graphml`)
- **Total Road Segments (Edges)**: `1,513` unique edges (`R-001` to `R-1513`)
- **Total Graph Nodes (Intersections)**: `691` nodes
- **Topology Integrity**: 100% connected, 0 isolated nodes, 100% valid directed/undirected edge mappings.
- **Coordinate Reference System (CRS)**: `WGS84 / EPSG:4326`

---

## 3. DEM & Shared Grid Convention (B2 Specification)
- **Study Area**: Mumbai, Maharashtra (~2 × 2 km)
- **Grid Dimensions**: `200 rows × 200 columns` (40,000 cells)
- **Nominal Cell Resolution**: `10 m × 10 m`
- **Geographic Cell Size**:
  - $\Delta\text{lat} = 0.0182^\circ / 200 = 0.0000910^\circ$ (~$10.07\,\text{m}$)
  - $\Delta\text{lon} = 0.0188^\circ / 200 = 0.0000940^\circ$ (~$9.89\,\text{m}$)
- **Bounding Box Coordinates**:
  - SW Origin (Minimum): `19.0600°N, 72.8500°E`
  - NE Bound (Maximum): `19.0782°N, 72.8688°E`
- **Array Orientation**:
  - Row 0: `19.0600°N` (SW baseline), Row 199: `19.0782°N` (Northern extent)
  - Col 0: `72.8500°E` (Western baseline), Col 199: `72.8688°E` (Eastern extent)

---

## 4. Road-to-DEM Grid Mapping
- **Roads Mapped Inside DEM**: `1,261` road segments (83.3%)
- **Roads Outside DEM (Boundary Buffer)**: `252` road segments (16.7%)
- **Unique DEM Grid Cells Covered**: `5,628` cells (14.07% network coverage)
- **Total Road-Cell Mapping Records**: `10,701` pairs in `road_grid_mapping.csv`
- **Boundary Handling**: Unmapped segments are explicitly assigned `null` flood depths and `UNKNOWN` risk classes to preserve integrity without data fabrication.

---

## 5. Static Susceptibility Scoring (C1.7)
- **Input Environmental Features**: Elevation, Imperviousness, Infiltration Deficit, Flow Accumulation, Topographic Wetness Index (TWI), Slope Flatness.
- **Formula**:
  $$S_{\text{static}} = 0.20 S_{\text{elev}} + 0.20 S_{\text{imp}} + 0.15 S_{\text{inf}} + 0.20 S_{\text{fa}} + 0.15 S_{\text{twi}} + 0.10 S_{\text{slope}}$$
- **Tiers**: `LOW` (<0.25), `MODERATE` (0.25–0.50), `HIGH` (0.50–0.75), `VERY_HIGH` (≥0.75), `UNKNOWN`.

---

## 6. Dynamic Flood Depth & Risk Integration (C1.8)
- **B2 Simulation Coupling**: Ingests $200 \times 200$ float32 surface water depth grids across 6 forecast horizons (`T+0min`, `T+30min`, `T+60min`, `T+90min`, `T+120min`, `T+180min`).
- **Dynamic Risk Formula**:
  $$F_{\text{dyn}}(t) = \text{clip}\left(\frac{\text{max\_flood\_depth\_m}(t)}{0.50\,\text{m}}, 0.0, 1.0\right)$$
  $$R_{\text{dyn}}(t) = 0.40 \cdot S_{\text{static}} + 0.60 \cdot F_{\text{dyn}}(t)$$

---

## 7. Hotspot Prioritization & Ranking (C1.9)
- **Hotspot Score Formulation**:
  $$\text{Score} = 0.40 S_{\text{peak\_depth}} + 0.25 S_{\text{persistence}} + 0.25 S_{\text{peak\_risk}} + 0.10 S_{\text{static}}$$
- **Deterministic Sort Order**: `hotspot_score` (desc) $\to$ `peak_flood_depth_m` (desc) $\to$ `peak_combined_risk` (desc) $\to$ `road_id` (asc).
- **Priority Tiers**: `LOW` (98), `MODERATE` (686), `HIGH` (452), `CRITICAL` (25), `UNKNOWN` (252).

---

## 8. Authoritative Output Files

| File Path | Description | Recommended Consumer |
| :--- | :--- | :--- |
| `backend/data/roads/road_graph.json` | Canonical topology with node/edge geometries and attributes | C2 Pathfinding / Routing Engine |
| `backend/data/roads/road_graph_with_risk.json` | Graph topology with embedded dynamic flood risk profiles | C2 Flood-Aware Route Planner |
| `backend/data/roads/road_flood_susceptibility.csv` | Static environmental features and multi-criteria scores | Risk Assessment / Offline Analysis |
| `backend/data/roads/road_dynamic_risk.csv` | Time-series inundation depth and combined risk per timestamp | Hydrodynamic Integration / Time Series |
| `backend/data/roads/road_hotspots.csv` | Comprehensive road hotspot rankings, scores, and durations | Emergency Dispatch / Prioritization |
| `backend/data/roads/road_hotspots.geojson` | Vector LineString layer with priority ranking properties | Frontend GIS Map Layer |
| `backend/data/roads/top_road_hotspots.json` | API-ready Top-10, Top-25, and Top-50 priority corridors | Backend REST API / Mobile Services |

---

## 9. Flask REST API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/roads/summary` | High-level network summary metrics and tier breakdowns. |
| `GET` | `/api/roads/hotspots?limit=N` | Ranked road flood hotspots list with optional limit filter. |
| `GET` | `/api/roads/<road_id>` | Detailed profile for an individual road segment. |
| `GET` | `/api/roads/<road_id>/timeseries` | Multi-timestamp dynamic inundation depth and risk series. |
| `GET` | `/api/roads/geojson` | Full vector road network GeoJSON with dynamic risk. |
| `GET` | `/api/roads/hotspots/geojson` | Road network GeoJSON with priority hotspot attributes. |
