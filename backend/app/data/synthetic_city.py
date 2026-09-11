"""
Synthetic City Dataset Generator (Phase 2 / Benchmark Generator)
===============================================================

Generates a complete, self-contained synthetic urban environment (2 km × 2 km):
- 200×200 DEM raster (Gaussian hills, ridge, low-lying drainage basin)
- Imperviousness & infiltration grids
- 50 Drainage nodes & 60 drainage pipes
- 120 Road corridors with vehicle attributes
- Scenario rainfall distributions
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, Tuple
import numpy as np


def generate_synthetic_dem(rows: int = 200, cols: int = 200, base_elevation: float = 5.0) -> np.ndarray:
    """Generates a realistic 200x200 micro-topography DEM raster."""
    x = np.linspace(-3, 3, cols)
    y = np.linspace(-3, 3, rows)
    xx, yy = np.meshgrid(x, y)

    # Hill in North-West
    hill_nw = 12.0 * np.exp(-((xx + 1.5) ** 2 + (yy + 1.5) ** 2) / 1.5)
    # Low-lying retention basin in South-East
    basin_se = -3.5 * np.exp(-((xx - 1.2) ** 2 + (yy - 1.2) ** 2) / 2.0)
    # Gentle East-to-West regional slope
    regional_slope = -0.003 * np.arange(cols)

    dem = base_elevation + hill_nw + basin_se + regional_slope
    dem = np.clip(dem, 0.5, 30.0).astype(np.float32)
    return dem


def generate_synthetic_drainage(
    origin_lat: float = 19.0600,
    origin_lon: float = 72.8500,
    cell_size_deg: float = 0.00009,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generates synthetic 50 nodes and 60 edges for drainage network."""
    nodes = []
    edges = []

    # Create a 7x7 grid of drainage nodes (49 nodes) + 1 outfall = 50 nodes
    for r in range(7):
        for c in range(7):
            idx = r * 7 + c + 1
            node_id = f"SYN-DN-{idx:03d}"
            lon = origin_lon + (c * 25 + 20) * cell_size_deg
            lat = origin_lat + (r * 25 + 20) * cell_size_deg

            # Classify node type
            if r == 0 and c == 0:
                ntype = "outfall"
                cap = 3.0
            elif (r + c) % 2 == 0:
                ntype = "inlet"
                cap = 0.6
            else:
                ntype = "junction"
                cap = 1.2

            nodes.append({
                "type": "Feature",
                "properties": {
                    "id": node_id,
                    "type": ntype,
                    "elevation_m": round(5.0 + 0.5 * (r + c), 2),
                    "capacity_m3s": cap,
                    "grid_row": int(r * 25 + 20),
                    "grid_col": int(c * 25 + 20),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(lon, 5), round(lat, 5)],
                },
            })

    # Outfall node
    outfall_id = "SYN-DN-050"
    outfall_lon = origin_lon + 10 * cell_size_deg
    outfall_lat = origin_lat + 10 * cell_size_deg
    nodes.append({
        "type": "Feature",
        "properties": {
            "id": outfall_id,
            "type": "outfall",
            "elevation_m": 1.5,
            "capacity_m3s": 5.0,
            "grid_row": 10,
            "grid_col": 10,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [round(outfall_lon, 5), round(outfall_lat, 5)],
        },
    })

    # Create 60 directed edges connecting grid nodes towards outfall
    edge_idx = 1
    for r in range(7):
        for c in range(7):
            u_id = f"SYN-DN-{r * 7 + c + 1:03d}"
            # Connect west (c -> c-1)
            if c > 0 and edge_idx <= 60:
                v_id = f"SYN-DN-{r * 7 + (c - 1) + 1:03d}"
                edges.append({
                    "type": "Feature",
                    "properties": {
                        "id": f"SYN-DE-{edge_idx:03d}",
                        "from_node": u_id,
                        "to_node": v_id,
                        "length_m": 250.0,
                        "diameter_m": 0.8,
                        "slope": 0.005,
                        "roughness_n": 0.013,
                        "blockage_pct": 0.0,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            nodes[r * 7 + c]["geometry"]["coordinates"],
                            nodes[r * 7 + c - 1]["geometry"]["coordinates"],
                        ],
                    },
                })
                edge_idx += 1
            # Connect south (r -> r-1)
            if r > 0 and edge_idx <= 60:
                v_id = f"SYN-DN-{(r - 1) * 7 + c + 1:03d}"
                edges.append({
                    "type": "Feature",
                    "properties": {
                        "id": f"SYN-DE-{edge_idx:03d}",
                        "from_node": u_id,
                        "to_node": v_id,
                        "length_m": 250.0,
                        "diameter_m": 0.8,
                        "slope": 0.005,
                        "roughness_n": 0.013,
                        "blockage_pct": 0.0,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            nodes[r * 7 + c]["geometry"]["coordinates"],
                            nodes[(r - 1) * 7 + c]["geometry"]["coordinates"],
                        ],
                    },
                })
                edge_idx += 1

    nodes_fc = {"type": "FeatureCollection", "features": nodes}
    edges_fc = {"type": "FeatureCollection", "features": edges}
    return nodes_fc, edges_fc


def generate_synthetic_roads(
    origin_lat: float = 19.0600,
    origin_lon: float = 72.8500,
    cell_size_deg: float = 0.00009,
) -> Dict[str, Any]:
    """Generates 120 synthetic road segments forming an urban arterial grid."""
    features = []
    seg_idx = 1

    # North-South Streets (columns 10, 30, 50, ..., 190)
    for c in range(10, 190, 20):
        lon = origin_lon + c * cell_size_deg
        for r_start in range(0, 180, 30):
            r_end = r_start + 30
            lat1 = origin_lat + r_start * cell_size_deg
            lat2 = origin_lat + r_end * cell_size_deg
            features.append({
                "type": "Feature",
                "properties": {
                    "id": f"SYN-R-{seg_idx:04d}",
                    "name": f"Avenue {c}",
                    "highway_type": "primary" if c in [50, 130] else "residential",
                    "lanes": 4 if c in [50, 130] else 2,
                    "width_m": 14.0 if c in [50, 130] else 8.0,
                    "length_m": 300.0,
                    "maxspeed_kmh": 50 if c in [50, 130] else 30,
                    "midpoint_grid_row": int(r_start + 15),
                    "midpoint_grid_col": int(c),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[round(lon, 5), round(lat1, 5)], [round(lon, 5), round(lat2, 5)]],
                },
            })
            seg_idx += 1

    # East-West Streets
    for r in range(15, 185, 30):
        lat = origin_lat + r * cell_size_deg
        for c_start in range(0, 180, 30):
            if seg_idx > 120:
                break
            c_end = c_start + 30
            lon1 = origin_lon + c_start * cell_size_deg
            lon2 = origin_lon + c_end * cell_size_deg
            features.append({
                "type": "Feature",
                "properties": {
                    "id": f"SYN-R-{seg_idx:04d}",
                    "name": f"Street {r}",
                    "highway_type": "secondary" if r == 75 else "residential",
                    "lanes": 3 if r == 75 else 2,
                    "width_m": 10.0 if r == 75 else 7.0,
                    "length_m": 300.0,
                    "maxspeed_kmh": 40 if r == 75 else 30,
                    "midpoint_grid_row": int(r),
                    "midpoint_grid_col": int(c_start + 15),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[round(lon1, 5), round(lat), 5], [round(lon2, 5), round(lat, 5)]],
                },
            })
            seg_idx += 1

    return {"type": "FeatureCollection", "features": features[:120]}
