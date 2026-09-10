"""
Centralized Configuration Loader for City-Agnostic Urban Flood Nowcasting
========================================================================

Provides shared access to city metadata, spatial bounding boxes, raster grid
dimensions, simulation parameters, and dynamic filesystem paths.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import yaml

_CONFIG: Optional[Dict[str, Any]] = None
_LOADED_PATH: Optional[Path] = None


def get_default_config_path() -> Path:
    """Returns the default path to city_config.yaml located in the backend folder."""
    backend_dir = Path(__file__).resolve().parent
    return backend_dir / "city_config.yaml"


def sanitize_slug(name: str) -> str:
    """Converts a descriptive city name to a filesystem-safe slug (e.g. 'mumbai_bandra_west')."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
    return slug or "default_city"


def load_config(config_path: Optional[str | Path] = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Loads and parses the city YAML configuration file.
    Caches the loaded configuration in memory unless force_reload is True.
    """
    global _CONFIG, _LOADED_PATH

    target_path = Path(config_path) if config_path else Path(os.environ.get("CITY_CONFIG_PATH", get_default_config_path()))

    if _CONFIG is not None and not force_reload and _LOADED_PATH == target_path:
        return _CONFIG

    if not target_path.exists():
        # Fallback default configuration for Mumbai (Bandra West / Kurla)
        _CONFIG = {
            "city_name": "Mumbai - Bandra West",
            "city_slug": "mumbai_bandra_west",
            "bbox": {
                "min_lat": 19.06013888888332,
                "max_lat": 19.07819444443888,
                "min_lon": 72.84986111114458,
                "max_lon": 72.86875000003347,
            },
            "grid": {
                "rows": 200,
                "cols": 200,
                "cell_size_m": 10.0,
            },
            "crs": "EPSG:4326",
            "simulation": {
                "dt_seconds": 300,
                "forecast_horizons": [0, 30, 60, 90, 120, 180],
            },
        }
        _LOADED_PATH = target_path
        return _CONFIG

    with open(target_path, "r", encoding="utf-8") as f:
        _CONFIG = yaml.safe_load(f) or {}

    _LOADED_PATH = target_path
    return _CONFIG


def get_city_name(config_path: Optional[str | Path] = None) -> str:
    """Returns the human-readable city name."""
    cfg = load_config(config_path)
    return cfg.get("city_name", "Unknown City")


def get_city_slug(config_path: Optional[str | Path] = None) -> str:
    """Returns a directory-safe slug identifier for the active city."""
    cfg = load_config(config_path)
    if "city_slug" in cfg and cfg["city_slug"]:
        return cfg["city_slug"]
    return sanitize_slug(get_city_name(config_path))


def get_bbox(config_path: Optional[str | Path] = None) -> Tuple[float, float, float, float]:
    """
    Returns the bounding box coordinates as (min_lat, max_lat, min_lon, max_lon).
    """
    cfg = load_config(config_path)
    b = cfg.get("bbox", {})
    return (
        float(b.get("min_lat", 19.06013888888332)),
        float(b.get("max_lat", 19.07819444443888)),
        float(b.get("min_lon", 72.84986111114458)),
        float(b.get("max_lon", 72.86875000003347)),
    )


def get_grid(config_path: Optional[str | Path] = None) -> Tuple[int, int, float]:
    """
    Returns grid dimensions as (rows, cols, cell_size_m).
    """
    cfg = load_config(config_path)
    g = cfg.get("grid", {})
    return (
        int(g.get("rows", 200)),
        int(g.get("cols", 200)),
        float(g.get("cell_size_m", 10.0)),
    )


def get_crs(config_path: Optional[str | Path] = None) -> str:
    """Returns Coordinate Reference System string (e.g. 'EPSG:4326')."""
    cfg = load_config(config_path)
    return cfg.get("crs", "EPSG:4326")


def get_simulation_params(config_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Returns simulation time steps and forecast horizons."""
    cfg = load_config(config_path)
    return cfg.get("simulation", {"dt_seconds": 300, "forecast_horizons": [0, 30, 60, 90, 120, 180]})


def get_data_paths(config_path: Optional[str | Path] = None) -> Dict[str, Path]:
    """
    Returns resolved filesystem paths for DEM, drainage, and road datasets.
    Supports city-isolated directories under backend/data/cities/<slug>/
    with seamless fallback to backend/data/ for the baseline Mumbai dataset.
    """
    slug = get_city_slug(config_path)
    backend_dir = Path(__file__).resolve().parent
    legacy_data_dir = backend_dir / "data"

    city_data_dir = legacy_data_dir / "cities" / slug
    
    # Check if a city-specific folder with data already exists
    if city_data_dir.exists() and (city_data_dir / "dem" / "elevation_grid.npy").exists():
        dem_dir = city_data_dir / "dem"
        drainage_dir = city_data_dir / "drainage"
        roads_dir = city_data_dir / "roads"
        base_dir = city_data_dir
    else:
        # Default/legacy layout in backend/data/
        dem_dir = legacy_data_dir / "dem"
        drainage_dir = legacy_data_dir / "drainage"
        roads_dir = legacy_data_dir / "roads"
        base_dir = legacy_data_dir

    # Ensure output and raw directories exist
    dem_dir.mkdir(parents=True, exist_ok=True)
    (dem_dir / "raw").mkdir(parents=True, exist_ok=True)
    drainage_dir.mkdir(parents=True, exist_ok=True)
    (drainage_dir / "raw").mkdir(parents=True, exist_ok=True)
    roads_dir.mkdir(parents=True, exist_ok=True)
    (roads_dir / "raw").mkdir(parents=True, exist_ok=True)

    return {
        "base_dir": base_dir,
        "dem_dir": dem_dir,
        "drainage_dir": drainage_dir,
        "roads_dir": roads_dir,
    }
