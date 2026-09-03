import json
import math
import urllib.request
import urllib.parse
from pathlib import Path
import numpy as np

# Exact bounding box matching our DEM from OpenTopography
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

GRID_ROWS = 200
GRID_COLS = 200

def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def latlon_to_grid(lat, lon):
    # Normalized position [0.0, 1.0] across exact DEM bounding box
    norm_y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT)
    norm_x = (lon - MIN_LON) / (MAX_LON - MIN_LON)
    
    row = int(norm_y * (GRID_ROWS - 1))
    col = int(norm_x * (GRID_COLS - 1))
    return max(0, min(GRID_ROWS - 1, row)), max(0, min(GRID_COLS - 1, col))

def fetch_overpass_drainage():
    # Overpass QL Query for real drainage, canals, culverts, waterways, and infrastructure
    query = f"""[out:json][timeout:120];
(
  way["waterway"~"drain|canal|stream|ditch|river"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  way["man_made"~"drain|culvert"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  way["tunnel"="culvert"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  relation["waterway"~"drain|canal|stream|ditch|river"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  node["man_made"~"manhole|drainage|pumping_station"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  node["waterway"~"pumping_station|drain"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
);
out body geom;
>;
out skel qt;
"""
    print(f"Fetching real-world drainage from Overpass API for bounds: [{MIN_LAT:.4f}, {MIN_LON:.4f}] to [{MAX_LAT:.4f}, {MAX_LON:.4f}]...")
    
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "UrbanFloodNowcasting/1.0 (Research)"})
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            print(f"Received {len(res_json.get('elements', []))} raw OSM elements from Overpass.")
            
            raw_out = Path("backend/data/drainage/raw/osm_drainage_mumbai.json")
            with open(raw_out, "w", encoding="utf-8") as f:
                json.dump(res_json, f, indent=2)
            print(f"Saved raw JSON to {raw_out}")
            return res_json
    except Exception as e:
        print(f"Overpass API error: {e}")
        return None

if __name__ == "__main__":
    fetch_overpass_drainage()
