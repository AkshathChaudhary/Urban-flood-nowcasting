import json
import urllib.request
import urllib.parse
from pathlib import Path

MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

def fetch_real_roads():
    query = f"""[out:json][timeout:120];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified"]({MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON});
);
out body geom;
>;
out skel qt;"""

    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "UrbanFloodNowcasting/1.0"})
    
    print(f"Fetching real roads for [{MIN_LAT:.4f}, {MIN_LON:.4f}] to [{MAX_LAT:.4f}, {MAX_LON:.4f}]...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        d = json.loads(resp.read().decode("utf-8"))
        ways = [e for e in d.get("elements", []) if e.get("type") == "way"]
        print(f"Successfully fetched {len(ways)} real road segments!")
        
        out_file = Path("backend/data/roads/raw/osm_roads_mumbai.json")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print(f"Saved to {out_file}")

if __name__ == "__main__":
    fetch_real_roads()
