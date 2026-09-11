"""
Shim module for backend.config backwards compatibility.
Re-exports configuration loader functions and app configuration constants.
"""

import sys
from pathlib import Path

# Add project root to sys.path to access root config if not present
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Import symbols from root config.py
from config import (
    get_default_config_path,
    sanitize_slug,
    load_config,
    get_city_name,
    get_city_slug,
    get_bbox,
    get_grid,
    get_crs,
    get_simulation_params,
    get_data_paths,
)

# Also import from backend.app.config
from backend.app.config import *
