from pathlib import Path

# Project Base Paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

DEM_DIR = DATA_DIR / "dem"
RAINFALL_DIR = DATA_DIR / "rainfall"
DRAINAGE_DIR = DATA_DIR / "drainage"
ROADS_DIR = DATA_DIR / "roads"

# Grid Parameters
GRID_ROWS = 200
GRID_COLS = 200
CELL_SIZE_M = 10.0        # 10m x 10m cells -> 2km x 2km domain
CELL_AREA_M2 = CELL_SIZE_M * CELL_SIZE_M  # 100 m^2

# Georeferencing (Mumbai Bandra Study Area)
ORIGIN_LAT = 19.0600      # SW corner latitude
ORIGIN_LON = 72.8500      # SW corner longitude
CRS = "EPSG:4326"

# Simulation Temporal Parameters
FORECAST_HORIZONS = [0, 30, 60, 90, 120, 180]  # in minutes
DT_SECONDS = 300                                # 5-minute timestep (300 seconds)
FLOW_SUB_PASSES = 4                            # Stability passes per timestep

# Standard File Locations
DEM_ELEVATION_FILE = DEM_DIR / "elevation_grid.npy"
DEM_IMPERVIOUSNESS_FILE = DEM_DIR / "imperviousness.npy"
DEM_INFILTRATION_FILE = DEM_DIR / "infiltration.npy"
DEM_WATER_BODY_MASK_FILE = DEM_DIR / "water_body_mask.npy"
DRAINAGE_NODES_FILE = DRAINAGE_DIR / "drainage_nodes.geojson"
DRAINAGE_EDGES_FILE = DRAINAGE_DIR / "drainage_edges.geojson"
