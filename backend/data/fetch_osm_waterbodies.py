"""
Fetch all OpenStreetMap water bodies and waterways for the 2x2 km Mumbai BKC domain.
Queries Overpass API for:
- waterway (river, stream, canal, drain, ditch, riverbank, tidal_channel)
- natural=water (water polygons, lakes, ponds, reservoirs, basins)
- water=*
- landuse=basin / landuse=reservoir
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path

MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

def fetch_osm_waterbodies():
    query = f"""[out:json][timeout:90];
(
  way["waterway"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  relation["waterway"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  way["natural"="water"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  relation["natural"="water"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  way["water"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  relation["water"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  way["landuse"="basin"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  way["landuse"="reservoir"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
);
out body geom;
>;
out skel qt;
"""
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "UrbanFloodNowcasting/1.0 (Research; WaterbodyExtraction)"}
    )

    print(f"Fetching OpenStreetMap water bodies for [{MIN_LAT:.4f}, {MIN_LON:.4f}] to [{MAX_LAT:.4f}, {MAX_LON:.4f}]...")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        
        elements = result.get("elements", [])
        ways = [e for e in elements if e.get("type") == "way"]
        relations = [e for e in elements if e.get("type") == "relation"]
        print(f"Successfully fetched {len(ways)} water ways and {len(relations)} water relations from OpenStreetMap!")

        out_path = Path("backend/data/osm_waterbodies.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Saved to {out_path}")
        return result
    except Exception as e:
        print(f"Error fetching from Overpass: {e}")
        return None

if __name__ == "__main__":
    fetch_osm_waterbodies()
