# Drainage Network Data

## Overview
This directory contains storm water drainage network data for the 2×2 km study area in Mumbai (EPSG:4326).

## Directory Structure
- `raw/osm_drainage_mumbai.geojson`: Raw Overpass Turbo export of storm drains, waterways, culverts, and manholes.
- `drainage_nodes.geojson`: Processed point features (inlets, manholes, junctions, pump stations, outfalls).
- `drainage_edges.geojson`: Processed line features (pipes, culverts, drains, nala channels) with diameter, slope, roughness, and blockage.

## Provenance
- **Source**: OpenStreetMap via Overpass Turbo
- **Tags Queried**:
  - `way["man_made"="drain"]`
  - `way["waterway"="drain"]`
  - `way["waterway"="canal"]`
  - `way["tunnel"="culvert"]`
  - `node["man_made"="manhole"]`
  - `node["man_made"="drainage"]`
- **CRS**: WGS 84 (`EPSG:4326`)
