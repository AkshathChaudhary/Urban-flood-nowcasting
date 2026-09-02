import json
import math
from pathlib import Path
import numpy as np

# Project Grid Parameters (From developer_assignments.md)
GRID_ROWS = 200
GRID_COLS = 200
CELL_SIZE_M = 10.0
ORIGIN_LAT = 19.0600   # SW corner
ORIGIN_LON = 72.8500   # SW corner

def haversine_m(lon1, lat1, lon2, lat2):
    """Calculate distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def latlon_to_grid(lat, lon):
    """Convert Lat/Lon to 200x200 DEM Grid Cell (row, col)."""
    # Approximate meters per degree at Mumbai latitude (~19 deg N)
    m_per_deg_lat = 110700.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(19.07))
    
    dy = (lat - ORIGIN_LAT) * m_per_deg_lat
    dx = (lon - ORIGIN_LON) * m_per_deg_lon
    
    row = int(dy / CELL_SIZE_M)
    col = int(dx / CELL_SIZE_M)
    
    # Clamp to grid bounds [0, 199]
    row = max(0, min(GRID_ROWS - 1, row))
    col = max(0, min(GRID_COLS - 1, col))
    return row, col

def clean_and_build_drainage_network(raw_path: str, output_dir: str):
    raw_file = Path(raw_path)
    if not raw_file.exists():
        print(f"Error: {raw_path} not found.")
        return

    with open(raw_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    nodes_dict = {}
    edges_list = []
    node_counter = 1
    edge_counter = 1

    # Load DEM elevation grid if available
    dem_grid = None
    dem_file = Path("backend/data/dem/elevation_grid.npy")
    if dem_file.exists():
        try:
            dem_grid = np.load(dem_file)
            print("Loaded elevation_grid.npy for precise drainage node elevations.")
        except Exception:
            pass

    def get_or_create_node(coord, node_type="junction"):
        nonlocal node_counter
        coord_key = (round(coord[0], 6), round(coord[1], 6))
        if coord_key not in nodes_dict:
            node_id = f"DN-{node_counter:03d}"
            lon, lat = coord_key[0], coord_key[1]
            grid_row, grid_col = latlon_to_grid(lat, lon)
            
            # Lookup exact elevation from DEM grid or fallback
            if dem_grid is not None:
                elevation_m = round(float(dem_grid[grid_row, grid_col]), 2)
            else:
                elevation_m = round(8.0 - (node_counter * 0.05) % 4.0, 2)

            nodes_dict[coord_key] = {
                "id": node_id,
                "type": node_type,
                "elevation_m": elevation_m,
                "capacity_m3s": 0.5,                                         # Standard 0.5 m³/s inlet capacity
                "grid_row": grid_row,
                "grid_col": grid_col,
                "coordinates": [lon, lat]
            }
            node_counter += 1
        return nodes_dict[coord_key]["id"]

    for feature in raw_data.get("features", []):
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])
        
        if geom.get("type") == "LineString" and len(coords) >= 2:
            for i in range(len(coords) - 1):
                c1, c2 = coords[i], coords[i+1]
                
                from_id = get_or_create_node(c1, "inlet" if i == 0 else "junction")
                to_id = get_or_create_node(c2, "outfall" if i == len(coords)-2 else "junction")
                
                length = haversine_m(c1[0], c1[1], c2[0], c2[1])
                
                edge_id = f"DE-{edge_counter:03d}"
                edges_list.append({
                    "type": "Feature",
                    "properties": {
                        "id": edge_id,
                        "from_node": from_id,
                        "to_node": to_id,
                        "length_m": round(max(length, 1.0), 2),
                        "diameter_m": 0.6,        # Standard storm drain pipe diameter
                        "slope": 0.005,           # 0.5% slope
                        "roughness_n": 0.013,     # Manning's n for concrete pipe
                        "blockage_pct": 0.0       # Initial blockage 0%
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [c1, c2]
                    }
                })
                edge_counter += 1

    # Convert nodes dictionary to GeoJSON FeatureCollection
    nodes_features = []
    for node in nodes_dict.values():
        nodes_features.append({
            "type": "Feature",
            "properties": {
                "id": node["id"],
                "type": node["type"],
                "elevation_m": node["elevation_m"],
                "capacity_m3s": node["capacity_m3s"],
                "grid_row": node["grid_row"],
                "grid_col": node["grid_col"]
            },
            "geometry": {
                "type": "Point",
                "coordinates": node["coordinates"]
            }
        })

    nodes_geojson = {"type": "FeatureCollection", "features": nodes_features}
    edges_geojson = {"type": "FeatureCollection", "features": edges_list}

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    nodes_out_file = out_path / "drainage_nodes.geojson"
    edges_out_file = out_path / "drainage_edges.geojson"

    with open(nodes_out_file, "w", encoding="utf-8") as f:
        json.dump(nodes_geojson, f, indent=2)

    with open(edges_out_file, "w", encoding="utf-8") as f:
        json.dump(edges_geojson, f, indent=2)

    print(f"Successfully processed drainage network:")
    print(f" - Extracted {len(nodes_features)} Nodes -> {nodes_out_file}")
    print(f" - Extracted {len(edges_list)} Edges -> {edges_out_file}")

if __name__ == "__main__":
    raw_path = "backend/data/drainage/raw/osm_drainage_mumbai.geojson"
    out_dir = "backend/data/drainage"
    clean_and_build_drainage_network(raw_path, out_dir)
