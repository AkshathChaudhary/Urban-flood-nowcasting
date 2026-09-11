"""
GeoJSON Infrastructure Network Loader
=====================================

Loads and validates GeoJSON vector layers for drainage nodes/edges and road networks.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def load_geojson(path: Union[str, Path]) -> Dict[str, Any]:
    """Loads and parses a GeoJSON file into a Python dictionary."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"GeoJSON asset not found at: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise ValueError(f"File at {file_path} is not a valid GeoJSON FeatureCollection.")

    return data


def extract_features(geojson_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts features list from a GeoJSON FeatureCollection."""
    return geojson_data.get("features", [])
