# Implementation Plan: Pair A Drainage Model (`DrainageGraph` + API)

This plan details the construction of the physics-based drainage simulation engine (`DrainageGraph`), test suites, and FastAPI endpoints for Pair A, written with deep educational walkthroughs of every Python module, hydraulic formula, and algorithm used.

## Proposed Changes

### 1. Drainage Simulation Engine
#### [NEW] [drainage.py](file:///c:/Users/aksha/urbanFlood/backend/models/drainage.py)
- **Module dependencies**:
  - `math`: Standard library for geometric calculations (pi, square root, power).
  - `json`: Standard library for parsing GeoJSON files.
  - `pathlib.Path`: Standard library for safe, cross-platform file path resolution.
  - `typing` (`Dict`, `List`, `Tuple`, `Optional`, `Any`): Static type hints for readability and IDE auto-completion.
  - `numpy`: Fast, vectorized matrix operations for 200×200 surface water grids.
  - `networkx`: Industry-standard graph library for modeling directed pipe networks, topological sorting, and node traversal.
- **Core components**:
  - `DrainageGraph.__init__(nodes_path, edges_path, cell_size_m=10.0)`
  - `_load_from_geojson()`: Parses Point and LineString features into NetworkX DiGraph attributes.
  - `compute_pipe_capacity(edge_id)`: Implements Manning's open/closed pipe flow equation.
  - `absorb_surface_water(depth_grid, dt)`: Transfers water from the 200×200 DEM surface into inlet nodes.
  - `propagate_flow(dt)`: Routes pipe water downstream via topological order and splits flow by pipe conveyance capacity.
  - `compute_overflow()`: Detects surcharges when nodes exceed retention/conveyance thresholds and returns excess volume in m³.
  - `set_blockage(edge_id, pct)`: Simulates sediment or trash blockage (0.0 to 1.0) on individual or all pipes.
  - `get_network_summary()` & diagnostic helpers (`get_node`, `get_edge`, `get_node_cell`).

---

### 2. Comprehensive Test Suite
#### [NEW] [test_drainage.py](file:///c:/Users/aksha/urbanFlood/tests/test_drainage.py)
- Unit tests:
  - Manning equation capacity verification against analytical solutions.
  - Blockage attenuation verification.
  - Surface absorption constraints (cannot absorb more than available water; cannot absorb more than inlet capacity).
  - Mass conservation verification: ensuring $\text{Water In} = \text{Water In System} + \text{Water Out} + \text{Overflow}$.
- Pair B Mock Integration Test:
  - Feeds a synthetic 200×200 flood depth grid over multiple timesteps and ensures stable absorption and overflow cycles.

---

### 3. FastAPI Drainage Router
#### [NEW] [drainage.py](file:///c:/Users/aksha/urbanFlood/backend/api/drainage.py)
- Endpoints:
  - `GET /api/drainage/summary`: Network stats (node count, pipe count, active water volume, overloaded nodes).
  - `GET /api/drainage/nodes`: Returns all nodes with status and hydraulic load.
  - `GET /api/drainage/node/{node_id}`: Detailed inspection of a specific node.
  - `GET /api/drainage/edges`: Returns all pipes with capacities and blockage levels.
  - `POST /api/drainage/blockage`: Dynamically updates pipe blockage percentage.

## Verification Plan
1. Run `tests/test_drainage.py` using `pytest` to verify all mathematical and physics assertions.
2. Run end-to-end integration simulation script against real `drainage_nodes.geojson` and `drainage_edges.geojson`.
