# Codebase Structure

**Analysis Date:** 2026-09-11

## Directory Layout

```
urbanFlood/
├── .planning/                  # GSD planning, codebase maps, roadmaps, and requirements
│   ├── codebase/               # Architectural and codebase discovery docs
│   └── onboarding/             # Onboarding summaries
├── .agents/                    # Agent customizations and skills (e.g. ui-ux-pro-max)
│   └── skills/                 # Design, UI/UX, brand, banner skills
├── backend/                    # Backend Python simulation and FastAPI application
│   ├── api/                    # Legacy/standalone API scripts
│   ├── app/                    # Production FastAPI package
│   │   ├── api/                # Subsystem route handlers
│   │   │   ├── drainage.py     # Pair A: Drainage routes
│   │   │   ├── flood.py        # Pair B: Flood forecast routes
│   │   │   ├── rainfall.py     # Pair B: Rainfall nowcast routes
│   │   │   ├── roads.py        # Pair C: Road network routes
│   │   │   ├── route.py        # Pair C: Resilient routing routes
│   │   │   ├── simulate.py     # Coupled simulation trigger routes
│   │   │   └── websocket.py    # Live telemetry broadcast WebSocket
│   │   ├── engine/             # Multi-city corridor execution pipelines
│   │   ├── models/             # Subsystem domain models and core physics
│   │   │   ├── drainage.py     # Graph pipe network, inlet absorption, overflow
│   │   │   ├── flood.py        # 2D hydrodynamic overland flow engine
│   │   │   ├── location.py     # Geolocation and coordinate transform primitives
│   │   │   ├── rainfall.py     # Radar precipitation extrapolation
│   │   │   └── road.py         # OSM road graph and A* dynamic router
│   │   ├── utils/              # Grid utilities, coordinate converters, math
│   │   ├── config.py           # Domain geometry, origin coords, timestep configs
│   │   ├── engine_state.py     # Singleton orchestrator managing coupled engines
│   │   └── main.py             # FastAPI entrypoint, middleware, router mount
│   ├── data/                   # Geographic datasets, raw elevation, radar, OSM roads
│   ├── tests/                  # Backend test suite
│   ├── Dockerfile              # Container definition for backend
│   └── requirements.txt        # Backend dependencies
├── tests/                      # Top-level system and integration tests
├── city_config.yaml            # Multi-city configuration file (Mumbai, Kolkata, etc.)
├── docker-compose.yml          # Container orchestration
├── navigate.py                 # CLI demonstration tool for flood-aware routing
├── run_any_corridor.py         # Multi-city corridor runner
├── config.py                   # Root configuration settings
└── README.md                   # Team specification, API contracts, architecture guide
```

## Directory Purposes

**`backend/app/api/`:**
- **Purpose:** FastAPI REST & WebSocket endpoints
- **Contains:** Router modules for drainage, flood, rainfall, roads, routing, and simulation
- **Key files:** `main.py`, `route.py`, `flood.py`, `websocket.py`

**`backend/app/models/`:**
- **Purpose:** Core numerical simulation physics and graph mathematics
- **Contains:** 2D surface flow solvers, drainage graph capacity modeling, OSM road network parsing and dynamic cost routing

**`backend/data/`:**
- **Purpose:** Spatial data caches (OSM vector networks, DEM rasters, rainfall radar grids)
- **Subdirectories:** `elevation/`, `rainfall/`, `roads/`, `drainage/`, `cities/`

**`tests/` and `backend/tests/`:**
- **Purpose:** Pytest suites covering unit calculations, Manning's pipe equation, Dijkstra edge penalization, and full coupled integration

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI server and WebSocket hub
- `navigate.py`: CLI corridor navigation demo
- `run_any_corridor.py`: Multi-city scenario runner

**Configuration:**
- `backend/app/config.py`: Core simulation constants (200x200 grid, 10m cells, Mumbai coordinates)
- `city_config.yaml`: Multi-city configuration specs

*Structure analysis: 2026-09-11*
