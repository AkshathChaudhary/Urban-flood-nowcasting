# 🏙️ Making the System City-Agnostic — Architecture Proposal

## The Problem Right Now

The same bounding box and grid parameters are **hardcoded in 4 different files**:

| File | Hardcoded Values |
|---|---|
| [`process_dem.py`](file:///c:/Users/aksha/urbanFlood/backend/data/dem/process_dem.py#L6-L10) | `GRID_ROWS`, `GRID_COLS`, `CELL_SIZE_M`, `ORIGIN_LAT`, `ORIGIN_LON` |
| [`clean_drainage.py`](file:///c:/Users/aksha/urbanFlood/backend/data/drainage/clean_drainage.py#L7-L13) | `MIN_LAT`, `MAX_LAT`, `MIN_LON`, `MAX_LON`, `GRID_ROWS`, `GRID_COLS` |
| [`fetch_real_osm_drainage.py`](file:///c:/Users/aksha/urbanFlood/backend/data/drainage/fetch_real_osm_drainage.py#L9-L15) | Same bbox + grid |
| [`fetch_real_roads.py`](file:///c:/Users/aksha/urbanFlood/backend/data/roads/fetch_real_roads.py#L6-L9) | Same bbox |

To switch cities, you'd have to edit all 4 files manually → error-prone and slow.

---

## The Solution — 3 Changes

### Change 1: Single Config File

Create one `city_config.yaml` that every script reads from:

```yaml
# backend/city_config.yaml

city_name: "Mumbai - Bandra West"

# Bounding box (SW corner to NE corner)
bbox:
  min_lat: 19.06013888888332
  max_lat: 19.07819444443888
  min_lon: 72.84986111114458
  max_lon: 72.86875000003347

# Grid parameters
grid:
  rows: 200
  cols: 200
  cell_size_m: 10.0

# Coordinate reference system
crs: "EPSG:4326"

# Simulation parameters
simulation:
  dt_seconds: 300
  forecast_horizons: [0, 30, 60, 90, 120, 180]
```

### Change 2: Shared Config Loader

One Python module that all scripts import:

```python
# backend/config.py

import yaml
from pathlib import Path

_CONFIG = None

def load_config(config_path: str = None) -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    
    if config_path is None:
        # Auto-find config relative to this file
        config_path = Path(__file__).parent / "city_config.yaml"
    
    with open(config_path, "r") as f:
        _CONFIG = yaml.safe_load(f)
    return _CONFIG

def get_bbox():
    cfg = load_config()
    b = cfg["bbox"]
    return b["min_lat"], b["max_lat"], b["min_lon"], b["max_lon"]

def get_grid():
    cfg = load_config()
    g = cfg["grid"]
    return g["rows"], g["cols"], g["cell_size_m"]

def get_city_name():
    return load_config()["city_name"]
```

Then every script replaces its hardcoded values with:

```python
# Before (in clean_drainage.py):
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
# ... etc

# After:
from backend.config import get_bbox, get_grid
MIN_LAT, MAX_LAT, MIN_LON, MAX_LON = get_bbox()
GRID_ROWS, GRID_COLS, _ = get_grid()
```

> [!TIP]
> This is a ~5 line change per file. The logic stays identical — only the source of the values changes.

### Change 3: One-Command Pipeline

A single script that runs the entire data pipeline for any city:

```python
# backend/setup_city.py

"""
Usage:
  python -m backend.setup_city --bbox 28.55,77.15,28.57,77.17 --name "Delhi - Connaught Place"
  python -m backend.setup_city --city "Chennai, India"     ← auto-computes bbox!
  python -m backend.setup_city --config backend/city_config.yaml  ← use existing config
"""

import argparse, yaml, time
from pathlib import Path

def auto_bbox_from_city(city_name: str, radius_km: float = 1.0) -> dict:
    """Use OSM Nominatim to get center coords, then build a bbox around it."""
    import urllib.request, json
    url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "UrbanFloodNowcast/1.0"})
    with urllib.request.urlopen(req) as resp:
        results = json.loads(resp.read())
    
    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    # ~0.009 degrees ≈ 1 km at equator
    offset = radius_km * 0.009
    return {
        "min_lat": lat - offset,
        "max_lat": lat + offset,
        "min_lon": lon - offset,
        "max_lon": lon + offset
    }

def write_config(city_name, bbox, config_path):
    config = {
        "city_name": city_name,
        "bbox": bbox,
        "grid": {"rows": 200, "cols": 200, "cell_size_m": 10.0},
        "crs": "EPSG:4326",
        "simulation": {"dt_seconds": 300, "forecast_horizons": [0, 30, 60, 90, 120, 180]}
    }
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    print(f"✅ Config written to {config_path}")

def run_pipeline():
    """Run all data collection + processing in sequence."""
    print("\n🔧 Step 1/4: Fetching DEM from OpenTopography...")
    # fetch_dem()  ← your DEM download + process_dem.py
    
    print("\n🔧 Step 2/4: Fetching drainage from Overpass API...")
    # fetch_real_osm_drainage.fetch_overpass_drainage()
    
    print("\n🔧 Step 3/4: Cleaning drainage network...")
    # clean_drainage.build_comprehensive_real_drainage()
    
    print("\n🔧 Step 4/4: Fetching and processing roads...")
    # fetch_real_roads.fetch_real_roads()
    
    print("\n✅ City setup complete!")
```

---

## What the Demo Experience Looks Like After This

### Switching to a new city in the demo:

```bash
# Option A: Give a city name (auto-detects bbox via Nominatim)
python -m backend.setup_city --city "Delhi, India"

# Option B: Give exact coordinates
python -m backend.setup_city --bbox 28.55,77.15,28.57,77.17 --name "Delhi - CP"
```

**That's it. One command. Everything runs automatically.**

Estimated time: **~2-5 minutes** (mostly waiting for Overpass API + DEM download), not 2-3 hours of manual work.

---

## Bonus: DEM Auto-Download from OpenTopography

The DEM is the one file you currently download manually. You can automate it too:

```python
def fetch_dem_from_opentopography(bbox, output_dir):
    """Download DEM via OpenTopography REST API (free, no API key needed for SRTM)."""
    import urllib.request
    
    url = (
        f"https://portal.opentopography.org/API/globaldem"
        f"?demtype=SRTMGL1"  # 30m SRTM — free, global coverage
        f"&south={bbox['min_lat']}&north={bbox['max_lat']}"
        f"&west={bbox['min_lon']}&east={bbox['max_lon']}"
        f"&outputFormat=GTiff"
        f"&API_Key=demoapikeyot2022"  # public demo key
    )
    
    out_path = Path(output_dir) / "raw" / "Hydro_Conditioned_DEM.tif"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, out_path)
    print(f"✅ DEM downloaded to {out_path}")
```

> [!IMPORTANT]
> OpenTopography has a free API for SRTM 30m data globally. For the 2×2 km patches you're working with, this is more than sufficient. For higher resolution (1m LiDAR), you'd need specific datasets per city.

---

## Optional: Cache Previously Set Up Cities

Store processed data per city so you never re-process the same city twice:

```
backend/data/
├── cities/
│   ├── mumbai_bandra_west/
│   │   ├── city_config.yaml
│   │   ├── dem/
│   │   ├── drainage/
│   │   └── roads/
│   ├── delhi_cp/
│   │   ├── city_config.yaml
│   │   ├── dem/
│   │   ├── drainage/
│   │   └── roads/
│   └── ...
├── active -> cities/mumbai_bandra_west/   ← symlink to current city
```

Then switching cities becomes instant if already cached:
```bash
python -m backend.setup_city --city "Mumbai"   # instant — already cached
python -m backend.setup_city --city "Delhi"     # 2-5 min first time, instant after
```

---

## Summary of Changes Needed

| Change | Files to Modify | Effort |
|---|---|---|
| Create `city_config.yaml` | New file | 5 min |
| Create `config.py` loader | New file | 15 min |
| Update `process_dem.py` to import from config | ~5 lines changed | 5 min |
| Update `clean_drainage.py` to import from config | ~5 lines changed | 5 min |
| Update `fetch_real_osm_drainage.py` to import from config | ~5 lines changed | 5 min |
| Update `fetch_real_roads.py` to import from config | ~5 lines changed | 5 min |
| Create `setup_city.py` pipeline | New file | 30 min |
| *Optional:* DEM auto-download | Add to pipeline | 20 min |
| *Optional:* City caching | Directory restructure | 30 min |

**Core changes: ~40 minutes. Full pipeline with caching: ~2 hours.**

> [!NOTE]
> **Do this AFTER your drainage model is working.** The model code (`DrainageGraph`) already reads from GeoJSON files — it doesn't care where they came from. The config centralization is an infrastructure improvement you can do during integration phase (Sep 10-11) or even during hackathon polish time.
