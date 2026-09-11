"""Data loading and generation package."""
from backend.app.data.dem_loader import load_dem, load_surface_rasters
from backend.app.data.geojson_loader import load_geojson, extract_features
from backend.app.data.synthetic_city import (
    generate_synthetic_dem,
    generate_synthetic_drainage,
    generate_synthetic_roads,
)

__all__ = [
    "load_dem",
    "load_surface_rasters",
    "load_geojson",
    "extract_features",
    "generate_synthetic_dem",
    "generate_synthetic_drainage",
    "generate_synthetic_roads",
]
