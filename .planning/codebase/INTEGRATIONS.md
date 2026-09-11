# External Integrations

**Analysis Date:** 2026-09-11

## APIs & External Services

**Geospatial & Road Networks:**
- OpenStreetMap (OSM) / Overpass API
  - Usage: Extracting road networks, road classification (primary, secondary, residential), max speed, bridge/tunnel attributes, elevation profiles
  - Raw storage: `backend/data/roads/raw/osm_roads_mumbai.json`
  - Integration method: JSON ingestion and GeoJSON translation to NetworkX `MultiDiGraph`

**Meteorological Radar & Weather Observations:**
- IMD (India Meteorological Department) / Doppler Weather Radar (DWR)
  - Usage: Real-time radar reflectivity (dBZ) and rainfall rate (mm/hr) estimates
  - Forecast method: Extrapolation / Optical flow radar nowcasting over 0–180 minutes horizon
  - Raw storage: `backend/data/rainfall/raw/`

**Elevation & Topography:**
- SRTM / TanDEM-X / CartoDEM Digital Elevation Models (DEM)
  - Usage: Terrain slope, overland water runoff flow direction, depression storage
  - Raw storage: `backend/data/elevation/raw/` GeoTIFF raster grids
  - Integration method: `rasterio` raster grid sampling reprojected to EPSG:4326

## Data Storage

**Static GeoJSON & Vector Layers:**
- `live_navigation_route.geojson`: Exported emergency route geometry
- `live_corridor_navigation.geojson`: Corridor navigation segments
- `backend/data/drainage/`: Drainage network pipes, inlets, outfalls, pump stations
- `backend/data/cities/`: Multi-city configuration YAMLs (`city_config.yaml`)

**Databases & Caching:**
- In-memory coupled simulation state managed via singleton engine in `backend/app/engine_state.py`
- GeoTIFF and JSON flat file storage for static assets
- Real-time WebSocket pub/sub channel for frontend subscribers (`/ws/flood-updates`)

## Authentication & Security

- API tier is designed for municipal command centers and emergency dispatchers
- CORS middleware configured in `backend/app/main.py` allowing cross-origin requests from frontend development servers
- Health probes: `GET /health`, `GET /`

*External integrations analysis: 2026-09-11*
