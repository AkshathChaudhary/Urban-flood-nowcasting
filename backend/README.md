# Urban Flood Nowcasting — Backend Service

High-resolution physics-based urban hydrodynamic flood nowcasting, subterranean stormwater drainage modeling, and flood-resilient emergency routing engine.

---

## Architecture Overview

The backend integrates three core subsystems into a unified FastAPI service:

1. **Pair A (Drainage Network)**: `backend/app/models/drainage.py` & `backend/app/api/drainage.py`
   - NetworkX directed graph of 1,479 drainage inlets, manholes, junctions, and outfalls.
   - Manning's equation pipe conveyance and sewer surcharge overflow.
2. **Pair B (2D Hydrodynamics & Nowcasting)**: `backend/app/engine/flood_engine.py` & `backend/app/api/flood.py`
   - 200×200 grid (10m cells, 2 km × 2 km domain) micro-topography routing (D8 + MDD).
   - Infiltration saturation feedback, retention detention ponds, municipal pump stations, and coastal tidal backpressure.
   - Doppler radar Marshall-Palmer Z-R conversion and multi-horizon nowcasts (T+0 to T+180 min).
3. **Pair C (Road Graph & Resilient Routing)**: `backend/app/models/routing.py` & `backend/app/api/route.py`
   - 913 OSM road corridors (72.65 km).
   - Dynamic A* routing with vehicle-specific water wading clearance limits (Pedestrian, Car, SUV, Ambulance, Truck).

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py                  # Unified FastAPI application entrypoint
│   ├── config.py                # Grid, path, and temporal configurations
│   ├── engine_state.py          # Pre-warmed singleton FloodEngine state
│   ├── models/                  # Pydantic schemas and domain graph models
│   │   ├── flood.py             # FloodForecast schemas
│   │   ├── drainage.py          # DrainageGraph model
│   │   ├── routing.py           # RoutingEngine model
│   │   ├── location.py          # Live location & landmark resolvers
│   │   └── rainfall.py          # Radar & scenario schemas
│   ├── api/                     # REST and WebSocket endpoints
│   │   ├── flood.py             # /api/flood-forecast endpoints
│   │   ├── drainage.py          # /api/drainage endpoints
│   │   ├── roads.py             # /api/roads endpoints
│   │   ├── route.py             # /api/route endpoints
│   │   ├── rainfall.py          # /api/rainfall endpoints
│   │   ├── simulate.py          # /api/simulate endpoint
│   │   └── websocket.py         # /ws/flood-updates streaming
│   ├── engine/                  # Hydrodynamic, drainage, and routing algorithms
│   │   ├── flood_engine.py      # Coupled FloodEngine orchestrator
│   │   ├── surface_flow.py      # Vectorized 2D overland flow router
│   │   ├── drainage_network.py  # DrainageGraph alias
│   │   ├── routing_engine.py    # RoutingEngine alias
│   │   └── rainfall_provider.py # RainfallProvider base and implementations
│   ├── data/                    # Standardized asset loaders
│   │   ├── dem_loader.py        # DEM raster loader
│   │   ├── geojson_loader.py    # GeoJSON asset loader
│   │   └── synthetic_city.py    # Synthetic benchmark generator
│   └── utils/
│       ├── geo.py               # Haversine & coordinate transformations
│       └── logger.py            # Structured logging
├── data/                        # Processed GIS and raster assets
│   ├── dem/                     # Copernicus 10m DEM rasters (.npy)
│   ├── drainage/                # drainage_nodes.geojson, drainage_edges.geojson
│   ├── roads/                   # road_network.geojson, flood_hotspots.geojson
│   ├── rainfall/                # Provider and scenario definitions
│   └── config/                  # scenarios.yaml
├── tests/                       # Unit and integration test suite
├── Dockerfile                   # Production container definition
└── requirements.txt             # Pinned Python dependencies
```

---

## Running the Server

### Local Development
```bash
# From workspace root
uvicorn backend.app.main:app --reload --port 8000
```

Interactive OpenAPI docs will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Docker
```bash
docker-compose up --build
```

---

## Running Tests
```bash
python -m unittest discover -s backend/tests
```
