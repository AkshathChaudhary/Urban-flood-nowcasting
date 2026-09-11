# Testing Patterns

**Analysis Date:** 2026-09-11

## Test Framework

**Runner:**
- Pytest (>=8.0) executed in Python virtual environment (`.venv`)
- Execution command: `python -m pytest backend/tests/ -v` or `python -m pytest tests/ -v`

**Assertion Style:**
- Native Python `assert` with descriptive failure context
- Numerical assertions: `pytest.approx()` and `numpy.testing.assert_allclose()` for floating point hydrodynamic depths and coordinate translations

## Test Organization

**Locations:**
- `backend/tests/`: Subsystem unit tests and coupled integration tests
  - `test_api.py`: FastAPI endpoint tests using `TestClient`
  - `test_coupled_integration.py`: Coupled simulation test between FloodEngine and DrainageGraph
  - `test_drainage.py`: Drainage pipe capacity, Manning's equation, and overflow tests
  - `test_flood_engine.py`: 2D surface runoff, flux equations, and water mass conservation
  - `test_rainfall_api.py` & `test_rainfall_provider.py`: Radar nowcasting and precipitation grid queries
  - `test_routing.py`: Dijkstra/A* routing with flood penalty weights
  - `test_surface_flow.py`: Numerical surface flow redistribution tests
- `tests/`: Root-level integration scenarios (e.g., `test_routing.py`, `test_kolkata_routing.py`, `test_drainage.py`)
- `cross_validation.py`: Algorithmic benchmark and ground-truth validation script

## Test Categories & Patterns

**1. Unit Testing (Mathematical Solvers & Graphs):**
- Verify mass conservation: total water in (rain) equals surface water + absorbed water + runoff out
- Verify pipe hydraulics: pipe flow capacity matches Manning's formula
- Verify graph routing: flooded segments are avoided in favor of slightly longer dry paths

**2. API Integration Testing:**
- Verify HTTP response status 200, GeoJSON schema adherence, and WebSocket stream connectivity

**3. Multi-City Generalization Tests:**
- Validates that the engine seamlessly switches between city configurations (Mumbai, Kolkata) without code modification

*Testing patterns analysis: 2026-09-11*
