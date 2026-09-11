"""
Kolkata EM Bypass Corridor Road Fetcher & Builder
=================================================
Fetches real OSM roads for Kestopur -> Ruby Hospital corridor (12 km).
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path

# Bounding box covering Ruby Hospital -> Science City -> Salt Lake -> Kestopur
MIN_LAT = 22.5050
MAX_LAT = 22.6020
MIN_LON = 88.3850
MAX_LON = 88.4380

def fetch_roads():
    out_dir = Path(__file__).resolve().parent / "roads" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "osm_roads_kolkata.json"
    
    if out_file.exists() and out_file.stat().st_size > 10000:
        print(f"Road data already exists at {out_file} ({out_file.stat().st_size} bytes)")
        return out_file

    query = f"""[out:json][timeout:90];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
);
out body geom;
>;
out skel qt;"""

    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    
    for url in endpoints:
        print(f"Querying Overpass at {url} for Kolkata corridor...")
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "UrbanFloodNowcasting/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                ways = [e for e in res.get("elements", []) if e.get("type") == "way"]
                print(f"Successfully fetched {len(ways)} road ways from {url}!")
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(res, f, indent=2)
                return out_file
        except Exception as e:
            print(f"Endpoint {url} failed: {e}")

    raise RuntimeError("Could not fetch OSM road data from any Overpass endpoint.")

if __name__ == "__main__":
    fetch_roads()
