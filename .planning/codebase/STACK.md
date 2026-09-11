# Technology Stack

**Analysis Date:** 2026-09-11

## Languages

**Primary:**
- Python 3.12 (`.venv`, `backend/`, root scripts) - Core simulation, hydrodynamic algorithms, graph routing, API layer

**Secondary:**
- JavaScript/HTML5/CSS3 (Planned frontend UI dashboard)
- Shell / PowerShell / YAML - Tooling, docker compose, city configs

## Runtime

**Environment:**
- Python 3.12 (Windows / Linux containerized via Docker)
- Docker & Docker Compose (`docker-compose.yml`, `backend/Dockerfile`)

**Package Manager:**
- pip (`requirements.txt`, `backend/requirements.txt`)
- Virtualenv: `.venv`

## Frameworks

**Core:**
- FastAPI (>=0.110.0) - High-performance asynchronous API server, WebSocket server
- Uvicorn (>=0.28.0) - ASGI server implementation
- Pydantic (>=2.6.0) - Schema validation and data modeling (Pydantic v2)

**Geospatial & Scientific Computing:**
- NumPy (>=1.24.0) - 2D grid matrix operations for elevation, rainfall, and flood depth
- SciPy (>=1.10.0) - Spatial distance transforms and scientific numerical solvers
- Rasterio (>=1.3.0) & Affine - GeoTIFF DEM raster reading, coordinate bounds transform
- Shapely & GeoPandas - Vector geometric spatial operations
- PyProj (>=3.6.0) - Coordinate Reference System projections (EPSG:4326 to UTM/metric)
- NetworkX (>=3.0) - Graph algorithms for drainage pipe network and road network routing

**Testing:**
- Pytest (>=8.0.0) - Unit and integration testing suites (`backend/tests/`, `tests/`)

## Key Dependencies

**Critical:**
- `numpy`: Fast 2D array math for 200x200 grid calculations (depth, elevation, rainfall)
- `scipy.ndimage`: Convolution kernels for 2D flow redistribution and Gaussian smoothing
- `networkx`: MultiDiGraph modeling for drainage pipe capacity and road network A*/Dijkstra routing
- `fastapi` & `websockets`: Real-time bidirectional streaming of simulation states and alerts
- `pydantic`: Type-safe request/response contracts across all 3 pair modules
- `pyyaml`: Configuration parsing (`city_config.yaml`)

**Infrastructure:**
- `uvicorn`: ASGI server host
- `httpx`: Async HTTP client for external integrations and testing
- `docker`: Multi-container deployment runtime

## Configuration

**Environment Variables:**
- Loaded via python standard library and `backend/app/config.py`
- Grid settings: `GRID_ROWS=200`, `GRID_COLS=200`, `CELL_SIZE_M=10.0` (2km x 2km area)
- Geo origin: `ORIGIN_LAT=19.0600`, `ORIGIN_LON=72.8500` (Mumbai reference)
- Time horizon: `FORECAST_HORIZONS=[0, 30, 60, 90, 120, 180]` (minutes)
- Simulation step: `DT_SECONDS=300` (5 minutes)

*Technology stack analysis: 2026-09-11*
