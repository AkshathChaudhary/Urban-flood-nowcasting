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

### Gap 6: Unified Multi-Model WebSocket Telemetry
- **Problem**: The live WebSocket feed (`/ws/flood-updates`) streamed only hydrodynamic raster metrics without road network or drainage status.
- **Solution**: Enriched [websocket.py](file:///c:/Users/aksha/urbanFlood/backend/app/api/websocket.py#L29) to stream a unified multi-model status package containing:
  - Hydrodynamic: surface water volume, max depth, flooded cell counts (10cm, 30cm thresholds).
  - Drainage: total water in system, cumulative outfall discharge, surcharge node count.
  - Road Network: count of clear, caution, and impassable road corridors.

---

## 2. Verification & Test Results

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
