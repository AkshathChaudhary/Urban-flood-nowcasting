# Walkthrough: Architecture Alignment & Cross-Model Integration

We have completed the backend directory reorganization and closed all 6 cross-model integration gaps between Pair A (Drainage), Pair B (Hydrodynamics & Radar), and Pair C (Roads & Routing), achieving 100% test pass rate across all 104 unit and integration tests.

---

## 1. Summary of Completed Cross-Model Integrations

### Gap 1: Hydrodynamic $\leftrightarrow$ Subterranean Flow Propagation (Pair A $\leftrightarrow$ Pair B)
- **Problem**: Previously, `FloodEngine.simulate_timestep` called `inlet_intake()`, but water sat statically at inlet nodes without being routed through underground pipes (`propagate_flow()`).
- **Solution**: Wired `self.drainage_graph.propagate_flow(dt)` into [flood_engine.py](file:///c:/Users/aksha/urbanFlood/backend/app/engine/flood_engine.py#L274). Inflow discharges propagate from upstream catchments toward outfalls, preventing subterranean water loss.

### Gap 2: Road Building Displacement / Porosity (Pair B $\leftrightarrow$ Pair C)
- **Problem**: Flood depths from 2D hydrodynamics were evaluated assuming flat, unobstructed cells. In urban street corridors, buildings displace water into street channels, significantly deepening local flood depth.
- **Solution**: Implemented `FloodEngine.get_street_depth(row, col, horizon_minutes)` and `get_street_depth_grid(horizon_minutes)` in [flood_engine.py](file:///c:/Users/aksha/urbanFlood/backend/app/engine/flood_engine.py#L320), applying building porosity displacement:
  $$d_{\text{street}} = \frac{d_{\text{grid}}}{\phi}, \quad \text{where } \phi = 1 - \text{building\_coverage}$$
  Supports both point queries `(row, col)` for routing and full-grid evaluations.

### Gap 3: Corridor-Level Passability & Horizon Depths (Pair C $\leftrightarrow$ Pair B)
- **Problem**: The routing engine assessed road segments individually without a corridor-wide safety classification endpoint or dynamic horizon parameter for road queries.
- **Solution**:
  - Implemented `RoutingEngine.classify_corridors()` classifying major corridors into `CLEAR` ($<10\text{ cm}$), `CAUTION` ($10-30\text{ cm}$), and `IMPASSABLE` ($>30\text{ cm}$).
  - Added endpoint `GET /api/roads/corridors/passability` in [roads.py](file:///c:/Users/aksha/urbanFlood/backend/app/api/roads.py#L112).
  - Updated `GET /api/roads/{road_id}` to accept query parameter `time_horizon_min: int = 0`.

### Gap 4 & 5: Simulation Scenario State Coupling (Scenario Engine $\leftrightarrow$ Drainage)
- **Problem**: Simulation runs did not reset subterranean pipe surcharge states between runs, and Scenario 5 (`blocked_drainage` / `extreme_blocked`) did not programmatically trigger drainage blockage.
- **Solution**:
  - In [simulate.py](file:///c:/Users/aksha/urbanFlood/backend/app/api/simulate.py#L141), added `engine.drainage_graph.reset_state()` at the start of each simulation run.
  - Linked Scenario 5 to automatically call `engine.drainage_graph.set_global_blockage(0.40)`.

# Resilient Evacuation Routing & Multi-City GIS Verification

This update addresses all user feedback regarding:
1. **Waypoint Markers (Pin A & Pin B):** Origin and Destination are immediately placed, badged, and animated with pulsing beacons on the GIS map as soon as they are selected in the dropdowns.
2. **Multi-Route Alternatives & Safest Route Recommendation:** Upon running route calculation, the engine now computes both the **★ Recommended Safest Route** (glowing emerald solid corridor with lowest flood depth exposure) and **Alternative Detours** (amber & sky-blue dashed corridors). A comparison selector allows dispatchers to toggle and inspect detour metrics.
3. **Subterranean Drainage Markings Clarification:** The green dashed lines (1,316 subterranean stormwater pipes & 1,479 manholes) now default to **OFF** to eliminate visual clutter. An interactive **Map Legend & Guide** in the bottom-left explicitly documents all map symbols.
4. **Kolkata EM Bypass Multi-City Support:** Switching the city context to **Kolkata** now transitions the map to Kolkata's actual bounding box (`[22.5050, 88.3850]` to `[22.6020, 88.4380]`), loads 3,435 OSM road vectors, loads Kolkata emergency landmarks (Ruby Hospital, Science City, Kestopur Canal), and solves multi-route evacuation along the EM Bypass.

---

## 1. Visual Verification & Proof

### Kolkata Evacuation Corridor (Ruby Hospital to Kestopur VIP Road)
![Kolkata Evacuation Corridor](file:///C:/Users/aksha/.gemini/antigravity-ide/brain/d4a6a96d-3194-475b-acf4-c666f4e0bab3/kolkata_routing_1789133601028.png)

* **Bounding Box:** Correctly positioned over Kolkata EM Bypass corridor (`22.5050°N - 22.6020°N`).
* **Road Network:** Ingested 3,435 major road segments.
* **Waypoints:** Origin `Ruby General Hospital (4.8m)` marked as **Point A**, Destination `Kestopur VIP Road (3.6m)` marked as **Point B**.
* **Routes Solved:**
  * **★ Recommended Safest Route (Emerald Solid):** 10.83 km, 14.5 min, Peak depth 8 cm (Safest passage).
  * **Alternative Detour 1 (Amber Dashed):** 11.70 km, 17.5 min.
  * **Alternative Detour 2 (Cyan Dashed):** 11.72 km, 17.7 min.

---

### Mumbai Evacuation Corridor (BKC Hub to Kurla Station)
![Mumbai Evacuation Corridor](file:///C:/Users/aksha/.gemini/antigravity-ide/brain/d4a6a96d-3194-475b-acf4-c666f4e0bab3/mumbai_routing_1789133530147.png)

* **Waypoints:** Origin Pin A (BKC Financial Center) & Destination Pin B (Kurla Railway Station).
* **Routes Solved:**
  * **★ Recommended Safest Route:** 1.52 km, 3.0 min (Emerald solid line).
  * **Alternative Detour 1:** 1.74 km, 3.5 min (Amber dashed line).
* **Interactive Map Legend & Guide:** Bottom-left card clearly documents all symbols.
* **Point Depth Inspection:** Interactive inspection popup showing terrain elevation, water depth, and 0–180m temporal progression.

---

## 2. Key Code Changes

| Component | Changes Made |
| :--- | :--- |
| [`backend/app/api/route.py`](file:///c:/Users/aksha/urbanFlood/backend/app/api/route.py) | Added `KOLKATA_DESTINATIONS_CATALOG` (Ruby Hospital, Science City, Salt Lake Sec V, Ultadanga, Kestopur, Chingrighata, Acropolis), updated `/api/route/destinations?city=...` and `/api/route` to route over Kolkata's graph. |
| [`backend/app/api/roads.py`](file:///c:/Users/aksha/urbanFlood/backend/app/api/roads.py) | Added multi-city caching for `get_routing_engine(city)`, mapped OSM highway attributes, filtered major corridors for fast GeoJSON delivery. |
| [`frontend/src/services/api.ts`](file:///c:/Users/aksha/urbanFlood/frontend/src/services/api.ts) | Added `city` query param to `fetchRoadsSummary`, `fetchRoadNetwork`, `fetchFloodHotspots`, and `fetchDestinationsCatalog`. |
| [`frontend/src/components/GisMap.tsx`](file:///c:/Users/aksha/urbanFlood/frontend/src/components/GisMap.tsx) | Decoupled waypoint pins (rendered immediately upon selection), rendered Primary vs Alternative detours with glowing emerald and dashed amber/cyan styles, added city bounds fly-to, and added the persistent **Map Legend & Guide**. |
| [`frontend/src/components/RoutePanel.tsx`](file:///c:/Users/aksha/urbanFlood/frontend/src/components/RoutePanel.tsx) | Added multi-route comparison selector card, highlighted safest route recommendation, and enabled switching between detours. |
| [`frontend/src/components/CommandCenterView.tsx`](file:///c:/Users/aksha/urbanFlood/frontend/src/components/CommandCenterView.tsx) | Defaulted `showDrainagePipes` to `false`, wired `routeAlternatives` and `activeRouteIndex`, and updated city landmarks initialization. |

---

## 3. Browser Session Video
The complete test session recording is archived at:
- `verify_routing_fix_1789133327042.webp`

---

## 4. Verification & Test Results

### Comprehensive Test Suite
- **Backend Test Suite (`backend/tests`)**: **74/74 Passed (100%)** in 13.3s.
  - 5 Coupled integration tests in [test_coupled_integration.py](file:///c:/Users/aksha/urbanFlood/backend/tests/test_coupled_integration.py) covering subterranean flow propagation, porosity street displacement, corridor passability, scenario blockage, and WebSocket telemetry generation.
  - 69 Unit tests across `test_flood_engine.py`, `test_surface_flow.py`, `test_rainfall_provider.py`, `test_rainfall_api.py`, `test_api.py`, `test_drainage.py`, and `test_routing.py`.
  - [BENCHMARK] Average timestep duration on $200 \times 200$ grid: **25.66 ms** (well within real-time requirement < 200 ms).
- **Root Test Suite (`tests`)**: **30/30 Passed (100%)** in 1.8s.
- **Total Tests Passed**: **104 / 104 Passed (0 failures, 0 errors)**.

### Backward Compatibility Verification
- [navigate.py](file:///c:/Users/aksha/urbanFlood/navigate.py): verified import and execution (`navigate.py import OK`).
- [agnostic.py](file:///c:/Users/aksha/urbanFlood/agnostic.py): verified import and config binding (`agnostic and config OK`).
- [config.py](file:///c:/Users/aksha/urbanFlood/config.py) and [backend/config.py](file:///c:/Users/aksha/urbanFlood/backend/config.py): verified shim bridge.
