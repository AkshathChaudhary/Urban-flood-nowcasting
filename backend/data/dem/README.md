# DEM & Hydrological Terrain Data

## Overview
This directory contains elevation grids, hydrological derivatives, and terrain analysis data for the 2×2 km study area in Mumbai (EPSG:4326).

## Directory Structure
- `elevation_grid.npy`: 200×200 NumPy float32 elevation array (meters) resampled from Copernicus/NASADEM.
- `imperviousness.npy`: 200×200 surface imperviousness / runoff coefficient grid (0.0 to 1.0).
- `infiltration.npy`: 200×200 soil infiltration rate grid (mm/hr).
- `process_dem.py`: Script to process raw GeoTIFF rasters into standard simulation grids.
- `raw/`:
  - `Hydro_Conditioned_DEM.tif`: Pit-removed, depression-filled digital elevation model.
  - `output_be.tif`: Raw NASADEM Bare-Earth elevation raster.
  - `D8_Flow_Direction.tif`: Pre-calculated D8 flow direction raster.
  - `D8_Flow_Accumulation.tif`: Upstream contributing cell count raster.
  - `TWI.tif`: Topographic Wetness Index raster ($\ln(a / \tan\beta)$).
  - `streams/`: Vector shapefile (`streams.shp`) of natural drainage streams/nalas.
  - `viz/`:
    - `viz.be_color-relief.tif`: Colorized elevation relief image.
    - `viz.be_slope.tif`: Slope steepness gradient image.

## Provenance
- **Source**: OpenTopography (NASA NASADEM / Copernicus GLO-30 Global DEM)
- **Bounding Box**: Lat 19.0600° to 19.0782° N, Lon 72.8500° to 72.8688° E
- **Resolution**: Resampled to 10 m × 10 m (200 × 200 grid)
- **CRS**: WGS 84 (`EPSG:4326`)
