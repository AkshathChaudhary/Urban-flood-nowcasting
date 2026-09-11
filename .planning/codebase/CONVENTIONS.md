# Coding Conventions

**Analysis Date:** 2026-09-11

## Naming Patterns

**Files & Modules:**
- Python modules: snake_case (e.g. `engine_state.py`, `corridor_pipeline.py`, `test_flood_engine.py`)
- Test files: `test_*.py` prefixed, located in `tests/` or `backend/tests/`
- Configuration files: `config.py`, `city_config.yaml`

**Functions & Methods:**
- Functions: `snake_case()` (e.g., `get_depth_at_cell()`, `absorb_surface_water()`, `find_safe_route()`)
- Factory / Singleton accessors: `get_engine()`, `get_current_scenario()`
- FastAPI routes: `snake_case()` handlers decorated with `@router.get(...)` / `@router.post(...)`

**Variables & Constants:**
- Constants: `UPPER_SNAKE_CASE` (e.g., `GRID_ROWS`, `GRID_COLS`, `CELL_SIZE_M`, `ORIGIN_LAT`, `ORIGIN_LON`, `CRS`, `DT_SECONDS`)
- Local & instance variables: `snake_case` (e.g., `water_depth`, `node_id`, `rainfall_rate`)
- Coordinates: `(lat, lon)` or `(row, col)` tuples; explicit units noted in variable names (e.g., `_m`, `_mm_hr`, `_sec`)

**Types & Classes:**
- Classes: `PascalCase` (e.g., `FloodEngine`, `DrainageGraph`, `RoadNetwork`, `SimulationState`)
- Pydantic Models: `PascalCase` inheriting from `pydantic.BaseModel` (e.g., `RouteRequest`, `FloodForecastResponse`, `DrainageNodeStatus`)

## Code Style & Architecture Conventions

**Coordinate Reference System (CRS):**
- Standard geographic coordinate representation: WGS84 (`EPSG:4326`)
- Metric projection calculations: Local UTM or planar 10m x 10m Cartesian grid (`row`, `col`) mapped via origin reference `(ORIGIN_LAT, ORIGIN_LON)`

**Pydantic v2 Contracts:**
- All API payloads and responses use Pydantic models with explicit field descriptions and validation constraints
- Strict separation between numerical NumPy arrays in internal engines and JSON-serializable models for API transfer

**Coupling & Separation of Concerns:**
- Subsystem pairs interact only via well-defined interface methods:
  1. `FloodEngine.get_depth_at_cell(row, col) -> float`
  2. `DrainageGraph.absorb_surface_water(depth_grid) -> overflow_grid`
  3. `RoadNetwork.update_edge_weights(depth_grid) -> None`
- Engine lifecycle is managed by `backend/app/engine_state.py` singleton to avoid repeated disk reads or graph rebuilds on every HTTP request

**Error Handling:**
- FastAPI `HTTPException` with status codes (400 Bad Request, 404 Not Found, 500 Simulation Failure)
- Boundary checks for geospatial coordinates outside the defined grid bounds `(GRID_ROWS, GRID_COLS)`
- Fallback routing: If all paths exceed critical flood depth thresholds, return the least-inundated path with explicit warning flags

*Coding conventions analysis: 2026-09-11*
