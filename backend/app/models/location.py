"""
Live Location & Destination Geocoding Provider
==============================================

Provides:
1. Live user GPS / IP-based location detection.
2. Intelligent bounding box clamping for the 2x2 km Mumbai study area.
3. Natural-language destination resolver for popular landmarks in the study area.
4. Extensible interface ready for device GPS / browser Geolocation API.
"""

from __future__ import annotations

import json
import math
import urllib.request
from typing import Any, Dict, Optional, Tuple, Union

# Bounding box of the 2x2 km Kurla / Mithi River, Mumbai study sector
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

# Pre-indexed landmarks within the 2x2 km study sector (Mumbai BKC/Kurla)
STUDY_AREA_LANDMARKS: Dict[str, Tuple[float, float]] = {
    "bkc": (72.8545, 19.0665),
    "bkc connector": (72.8545, 19.0665),
    "cst road": (72.8580, 19.0700),
    "kurla": (72.8660, 19.0740),
    "kurla west": (72.8660, 19.0740),
    "kurla station": (72.8670, 19.0690),
    "lbs marg": (72.8625, 19.0770),
    "lbs road": (72.8625, 19.0770),
    "mithi river": (72.8605, 19.0725),
    "mithi bridge": (72.8590, 19.0710),
    "taximens colony": (72.8610, 19.0735),
    "kalina campus": (72.8515, 19.0715),
    "kalina university": (72.8515, 19.0715),
    "sg barve marg": (72.8650, 19.0750),
    "chunabhatti link": (72.8640, 19.0620),
}

# Pre-indexed landmarks for Kolkata EM Bypass Corridor (~12 km)
KOLKATA_LANDMARKS: Dict[str, Tuple[float, float]] = {
    "kestopur": (88.4230, 22.5930),
    "kestopur canal": (88.4230, 22.5930),
    "vip road": (88.4200, 22.5950),
    "ultadanga": (88.3960, 22.5890),
    "ultadanga underpass": (88.3960, 22.5890),
    "hudco": (88.3970, 22.5870),
    "salt lake": (88.4150, 22.5750),
    "salt lake sector v": (88.4320, 22.5800),
    "karunamoyee": (88.4190, 22.5860),
    "chingrighata": (88.4050, 22.5650),
    "beliaghata bypass": (88.4030, 22.5670),
    "science city": (88.3960, 22.5400),
    "parama island": (88.3960, 22.5400),
    "em bypass": (88.4010, 22.5500),
    "kasba": (88.3920, 22.5180),
    "acropolis mall": (88.3920, 22.5180),
    "ruby": (88.4030, 22.5135),
    "ruby hospital": (88.4030, 22.5135),
    "ruby general hospital": (88.4030, 22.5135),
    "kalikapur": (88.3990, 22.5020),
    "anandapur": (88.4100, 22.5150),
}

# Master Multi-City Configurations
CITY_CONFIGS: Dict[str, Dict[str, Any]] = {
    "mumbai": {
        "name": "Mumbai — BKC / Kurla Pilot Basin",
        "bbox": (19.06013888888332, 19.07819444443888, 72.84986111114458, 72.86875000003347),
        "grid": (200, 200, 10.0),
        "default_anchor": (72.8550, 19.0660),
        "default_anchor_name": "BKC / CST Road West Entrance",
        "landmarks": STUDY_AREA_LANDMARKS,
        "roads_geojson": "backend/data/roads/road_network.geojson",
        "roads_graph": "backend/data/roads/road_graph.json",
        "dem_npy": "backend/data/dem/elevation_grid.npy",
    },
    "kolkata": {
        "name": "Kolkata — EM Bypass Corridor (Kestopur to Ruby)",
        "bbox": (22.5050, 22.6020, 88.3850, 88.4380),
        "grid": (300, 160, 35.0),
        "default_anchor": (88.4230, 22.5930),
        "default_anchor_name": "Kestopur VIP Road Junction",
        "landmarks": KOLKATA_LANDMARKS,
        "roads_geojson": "backend/data/cities/kolkata/roads/road_network.geojson",
        "roads_graph": "backend/data/cities/kolkata/roads/road_graph.json",
        "dem_npy": "backend/data/cities/kolkata/dem/elevation_grid.npy",
    },
}

# Structured Destination Catalog for Frontend Dropdowns and Interactive Map Markers
DESTINATIONS_CATALOG = [
    {
        "id": "kurla-station",
        "name": "Kurla Railway Station (Central & Harbour)",
        "category": "Transit Hub",
        "lat": 19.0690,
        "lon": 72.8670,
        "elevation_m": 4.1,
        "description": "Major suburban rail junction with flood-prone pedestrian subway and low-lying approaches.",
        "recommended_as_destination": True,
    },
    {
        "id": "bkc-hub",
        "name": "Bandra-Kurla Complex (BKC) Financial Center",
        "category": "Commercial Hub",
        "lat": 19.0665,
        "lon": 72.8545,
        "elevation_m": 6.8,
        "description": "High-density financial district on elevated western ground; prime evacuation safe zone.",
        "recommended_as_destination": True,
    },
    {
        "id": "cst-road",
        "name": "CST Road (Santacruz-Chembur Link Corridor)",
        "category": "Arterial Highway",
        "lat": 19.0700,
        "lon": 72.8580,
        "elevation_m": 5.2,
        "description": "Key east-west arterial connector bridging BKC and eastern suburbs.",
        "recommended_as_destination": True,
    },
    {
        "id": "kalina-campus",
        "name": "Mumbai University Kalina Campus",
        "category": "Civic & Institutional",
        "lat": 19.0715,
        "lon": 72.8515,
        "elevation_m": 7.5,
        "description": "Extensive university campus on western ridge with high ground and open assembly zones.",
        "recommended_as_destination": True,
    },
    {
        "id": "lbs-marg",
        "name": "LBS Marg (Kurla West Crossing)",
        "category": "Flood Hazard Hotspot",
        "lat": 19.0770,
        "lon": 72.8625,
        "elevation_m": 3.6,
        "description": "Historically severe monsoon waterlogging corridor parallel to Mithi River basin.",
        "recommended_as_destination": True,
    },
    {
        "id": "mithi-bridge",
        "name": "Mithi River Bridge & CST Road Junction",
        "category": "Hydraulic Chokepoint",
        "lat": 19.0710,
        "lon": 72.8590,
        "elevation_m": 3.2,
        "description": "Central drainage channel crossing subject to riverbank overtopping and tidal locking.",
        "recommended_as_destination": True,
    },
    {
        "id": "taximens-colony",
        "name": "Taximens Colony (Kurla Low-Lying Settlement)",
        "category": "Residential Settlement",
        "lat": 19.0735,
        "lon": 72.8610,
        "elevation_m": 3.4,
        "description": "High-density residential neighborhood prone to prolonged street ponding >40 cm.",
        "recommended_as_destination": True,
    },
    {
        "id": "chunabhatti-link",
        "name": "Chunabhatti-BKC Connector Gateway",
        "category": "Entry Gateway",
        "lat": 19.0620,
        "lon": 72.8640,
        "elevation_m": 5.9,
        "description": "Elevated southern gateway connecting Eastern Express Highway and Sion.",
        "recommended_as_destination": True,
    },
]

# Gateway entry points into the 2x2 km pilot basin for travelers originating outside Mumbai study area
ENTRY_GATEWAYS = [
    {
        "id": "gate-west-bkc",
        "name": "Western Gateway (BKC Connector / Western Express)",
        "lat": 19.0665,
        "lon": 72.8545,
        "direction": "West",
        "connects_to": "Airport, Bandra, Western Suburbs",
    },
    {
        "id": "gate-north-lbs",
        "name": "Northern Gateway (LBS Marg / Ghatkopar)",
        "lat": 19.0780,
        "lon": 72.8625,
        "direction": "North",
        "connects_to": "Ghatkopar, Thane, Central Suburbs",
    },
    {
        "id": "gate-south-chunabhatti",
        "name": "Southern Gateway (Chunabhatti / Sion / Freeway)",
        "lat": 19.0620,
        "lon": 72.8640,
        "direction": "South",
        "connects_to": "Sion, Dadar, South Mumbai",
    },
    {
        "id": "gate-east-kurla",
        "name": "Eastern Gateway (Kurla East / Chembur / SCLR)",
        "lat": 19.0700,
        "lon": 72.8680,
        "direction": "East",
        "connects_to": "Chembur, Navi Mumbai, Eastern Express",
    },
]

import time

# Default anchor within study area (BKC-Kurla Gateway, safe high ground)
DEFAULT_LIVE_ANCHOR = (72.8550, 19.0660)

# In-memory cache for live geolocation to eliminate repeated network latency
_LOCATION_CACHE: Dict[str, Any] = {}
LOCATION_CACHE_TTL_SEC = 3600.0  # 1 hour TTL


def detect_city_from_text_or_coords(val: Union[str, Tuple[float, float]]) -> str:
    """Intelligently detects whether an input points to Mumbai or Kolkata."""
    if isinstance(val, (tuple, list)):
        lon, lat = float(val[0]), float(val[1])
        if 22.4 <= lat <= 22.7 and 88.2 <= lon <= 88.6:
            return "kolkata"
        if 18.9 <= lat <= 19.3 and 72.7 <= lon <= 73.0:
            return "mumbai"
        return "mumbai"

    val_str = str(val).lower().strip()
    # Check Kolkata keywords
    kolkata_keys = list(KOLKATA_LANDMARKS.keys()) + ["kolkata", "calcutta", "west bengal", "em bypass", "vip road"]
    if any(k in val_str for k in kolkata_keys):
        return "kolkata"
    return "mumbai"


def is_inside_study_area(lon: float, lat: float, city: str = "mumbai") -> bool:
    """Checks whether coordinates lie inside the active city bounding box."""
    cfg = CITY_CONFIGS.get(city, CITY_CONFIGS["mumbai"])
    min_lat, max_lat, min_lon, max_lon = cfg["bbox"]
    return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)


def get_live_location(force_refresh: bool = False, city: Optional[str] = None) -> Dict[str, Any]:
    """
    Detects user location with in-memory TTL caching.
    Uses real GPS coordinates if inside the study plot, or anchors realistically based on active city.
    """
    active_city = city or "mumbai"
    cfg = CITY_CONFIGS.get(active_city, CITY_CONFIGS["mumbai"])
    default_anchor = cfg["default_anchor"]
    default_anchor_name = cfg["default_anchor_name"]
    min_lat, max_lat, min_lon, max_lon = cfg["bbox"]

    cache_key = f"location_{active_city}"
    now = time.time()
    if not force_refresh and _LOCATION_CACHE.get(cache_key) is not None:
        if now - _LOCATION_CACHE[cache_key]["timestamp"] < LOCATION_CACHE_TTL_SEC:
            return _LOCATION_CACHE[cache_key]["data"]

    real_detected = None
    city_name = "Unknown"
    country_name = "Unknown"

    try:
        req = urllib.request.Request(
            "https://ipapi.co/json/",
            headers={"User-Agent": "UrbanFloodNavigation/1.0"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode())
            if "latitude" in data and "longitude" in data:
                lat = float(data["latitude"])
                lon = float(data["longitude"])
                city_name = data.get("city", "Unknown")
                country_name = data.get("country_name", "Unknown")
                real_detected = (lon, lat)
    except Exception:
        try:
            req2 = urllib.request.Request(
                "http://ip-api.com/json/",
                headers={"User-Agent": "UrbanFloodNavigation/1.0"}
            )
            with urllib.request.urlopen(req2, timeout=2.0) as resp2:
                data2 = json.loads(resp2.read().decode())
                if data2.get("status") == "success":
                    lat = float(data2["lat"])
                    lon = float(data2["lon"])
                    city_name = data2.get("city", "Unknown")
                    country_name = data2.get("country_name", "Unknown")
                    real_detected = (lon, lat)
        except Exception:
            pass

    if real_detected and is_inside_study_area(real_detected[0], real_detected[1], city=active_city):
        result = {
            "source": "live_real_gps",
            "lon": real_detected[0],
            "lat": real_detected[1],
            "location_name": f"Live GPS ({city_name})",
            "is_clamped": False,
            "city": active_city,
            "message": f"Using real live user coordinates from {city_name}.",
        }
    else:
        result = {
            "source": "live_study_area_simulated",
            "lon": default_anchor[0],
            "lat": default_anchor[1],
            "location_name": f"{default_anchor_name} (Simulated Live Position)",
            "is_clamped": True,
            "city": active_city,
            "real_detected": real_detected,
            "real_location_summary": f"{city_name}, {country_name}" if real_detected else "Offline",
            "message": (
                f"Detected physical location: {city_name}, {country_name} "
                f"({real_detected[1]:.4f} N, {real_detected[0]:.4f} E). "
                f"Anchoring simulated position to {cfg['name']} gateway ({default_anchor[1]:.4f} N, {default_anchor[0]:.4f} E)."
                if real_detected else
                f"Offline mode: live user position anchored to {default_anchor_name}."
            ),
        }

    _LOCATION_CACHE[cache_key] = {"data": result, "timestamp": now}
    return result


def resolve_destination(dest_input: str, city: Optional[str] = None) -> Tuple[float, float, str]:
    """
    Resolves destination string with multi-city landmark catalog and coordinate parsing.
    Returns (lon, lat, resolved_name).
    """
    clean = dest_input.strip()[:100].lower()

    # Determine which city landmark dictionary to search
    active_city = city or detect_city_from_text_or_coords(clean)

    # 1. Search Active City Landmarks
    target_landmarks = CITY_CONFIGS.get(active_city, {}).get("landmarks", {})
    for landmark_key, coords in target_landmarks.items():
        if landmark_key in clean or clean in landmark_key:
            return coords[0], coords[1], landmark_key.title()

    # 2. Search Other City Landmarks
    for cname, ccfg in CITY_CONFIGS.items():
        if cname == active_city:
            continue
        for landmark_key, coords in ccfg.get("landmarks", {}).items():
            if landmark_key in clean or clean in landmark_key:
                return coords[0], coords[1], landmark_key.title()

    # 3. Parse Coordinate String: "lat, lon" or "lon, lat"
    if "," in clean:
        parts = [p.strip() for p in clean.split(",")]
        if len(parts) == 2:
            try:
                v1, v2 = float(parts[0]), float(parts[1])
                if (8.0 <= v1 <= 38.0) and (65.0 <= v2 <= 100.0):
                    lat, lon = v1, v2
                elif (65.0 <= v2 <= 100.0) and (8.0 <= v1 <= 38.0):
                    lon, lat = v1, v2
                else:
                    lat, lon = v1, v2

                # Clamp to bounding box of active city
                cfg = CITY_CONFIGS.get(active_city, CITY_CONFIGS["mumbai"])
                min_lat, max_lat, min_lon, max_lon = cfg["bbox"]
                clamped_lat = max(min_lat, min(max_lat, lat))
                clamped_lon = max(min_lon, min(max_lon, lon))
                return clamped_lon, clamped_lat, f"Coordinates ({clamped_lat:.4f}, {clamped_lon:.4f})"
            except ValueError:
                pass

    # 4. Fallback per active city
    if active_city == "kolkata":
        fallback_coords = KOLKATA_LANDMARKS.get("ruby", (88.4030, 22.5135))
        return fallback_coords[0], fallback_coords[1], f"Ruby Hospital (Default for '{dest_input}')"
    else:
        fallback_coords = STUDY_AREA_LANDMARKS.get("kurla station", (72.8670, 19.0690))
        return fallback_coords[0], fallback_coords[1], f"Kurla Station (Default for '{dest_input}')"
