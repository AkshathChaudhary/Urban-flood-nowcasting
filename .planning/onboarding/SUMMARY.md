# Onboarding Summary

## Project State
- PROJECT.md: missing (ready for /gsd-new-project)
- REQUIREMENTS.md: missing
- ROADMAP.md: missing
- STATE.md: missing

## Codebase Context
- Brownfield repo: yes
- Map readiness: complete
- Codebase map: .planning/codebase/ (complete codebase map)
  - STACK.md: Python 3.12, FastAPI, NumPy, SciPy, Rasterio, NetworkX, PyProj, Shapely
  - INTEGRATIONS.md: OpenStreetMap (OSM roads), IMD Doppler Radar, DEM GeoTIFFs, WebSockets
  - ARCHITECTURE.md: 3-layer hydrodynamic simulation (Drainage, Overland Flood, Resilient Routing)
  - STRUCTURE.md: Full backend and test directories mapped
  - CONVENTIONS.md: Pydantic v2 schemas, EPSG:4326/metric planar coords, coupled interfaces
  - TESTING.md: Pytest test suite, numerical mass conservation, routing impedance checks
  - CONCERNS.md: Missing production frontend dashboard, spatial grid memory scaling, route isolation
- Fast map available: yes

## Design System & UI/UX Context
- UI/UX Pro Max Design System: `design-system/urban-flood-command-center/MASTER.md`
- Visual Theme: Cinematic Dark Mode Command Center (Glassmorphism, High Density 9/10, Inter typography)
- Components: Interactive GIS Leaflet/MapLibre map, temporal nowcast timeline scrubber, emergency routing corridor selector, real-time WebSocket telemetry

## Recommended Next Step
- `/gsd-new-project` to initialize project goals, requirements, and frontend roadmap
