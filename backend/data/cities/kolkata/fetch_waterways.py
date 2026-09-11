"""
Fetch real OSM waterways for Kolkata corridor (Canals, Rivers, Streams, Drains).
"""
import json
import urllib.request
import urllib.parse
from pathlib import Path

MIN_LAT = 22.5050
MAX_LAT = 22.6020
MIN_LON = 88.3850
MAX_LON = 88.4380

def fetch_waterways():
    out_dir = Path(__file__).resolve().parent / "dem" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "osm_waterways_kolkata.json"
    
    if out_file.exists() and out_file.stat().st_size > 1000:
        print(f"Waterways already exist at {out_file}")
        return out_file

    query = f"""[out:json][timeout:60];
(
  way["waterway"~"canal|drain|ditch|river|stream"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
  relation["waterway"~"canal|drain|river"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
);
out body geom;
>;
out skel qt;"""

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data, headers={"User-Agent": "UrbanFloodNowcasting/1.0"})
    
    print("Fetching real Kolkata waterways from OSM Overpass...")
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        ways = [e for e in res.get("elements", []) if e.get("type") == "way"]
        print(f"Fetched {len(ways)} waterways (canals/drains)!")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        return out_file

if __name__ == "__main__":
    fetch_waterways()
