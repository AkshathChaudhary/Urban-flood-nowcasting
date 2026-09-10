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
from typing import Dict, Optional, Tuple, Union

# Bounding box of the 2x2 km Kurla / Mithi River, Mumbai study sector
MIN_LAT = 19.06013888888332
MAX_LAT = 19.07819444443888
MIN_LON = 72.84986111114458
MAX_LON = 72.86875000003347

# Pre-indexed landmarks within the 2x2 km study sector
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

import time

# Default anchor within study area (BKC-Kurla Gateway, safe high ground)
DEFAULT_LIVE_ANCHOR = (72.8550, 19.0660)

# In-memory cache for live geolocation to eliminate repeated network latency
_LOCATION_CACHE: Dict[str, Any] = {"data": None, "timestamp": 0.0}
LOCATION_CACHE_TTL_SEC = 3600.0  # 1 hour TTL


def is_inside_study_area(lon: float, lat: float) -> bool:
    """Checks whether coordinates lie inside the 2x2 km study plot."""
    return (MIN_LAT <= lat <= MAX_LAT) and (MIN_LON <= lon <= MAX_LON)


def get_live_location(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Detects user location with in-memory TTL caching.
    Uses real GPS coordinates if inside the study plot, or anchors realistically to BKC gateway if outside.
    """
    now = time.time()
    if not force_refresh and _LOCATION_CACHE["data"] is not None:
        if now - _LOCATION_CACHE["timestamp"] < LOCATION_CACHE_TTL_SEC:
            return _LOCATION_CACHE["data"]

    real_detected = None
    city_name = "Unknown"
    country_name = "Unknown"

    try:
        # Query IP-based geolocation with HTTPS and strict timeout
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
        # Fallback to secondary endpoint if primary fails
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
                    country_name = data2.get("country", "Unknown")
                    real_detected = (lon, lat)
        except Exception:
            pass

    if real_detected and is_inside_study_area(real_detected[0], real_detected[1]):
        result = {
            "source": "live_real_gps",
            "lon": real_detected[0],
            "lat": real_detected[1],
            "location_name": f"Live GPS ({city_name})",
            "is_clamped": False,
            "message": f"Using real live user coordinates from {city_name}.",
        }
    else:
        result = {
            "source": "live_study_area_simulated",
            "lon": DEFAULT_LIVE_ANCHOR[0],
            "lat": DEFAULT_LIVE_ANCHOR[1],
            "location_name": "BKC / CST Road West Entrance (Simulated Live Position)",
            "is_clamped": True,
            "real_detected": real_detected,
            "real_location_summary": f"{city_name}, {country_name}" if real_detected else "Offline",
            "message": (
                f"Detected physical location: {city_name}, {country_name} "
                f"({real_detected[1]:.4f} N, {real_detected[0]:.4f} E). "
                f"Since current model tests the 2x2 km Mumbai plot, live user position is "
                f"anchored to BKC / CST Road ({DEFAULT_LIVE_ANCHOR[1]:.4f}, {DEFAULT_LIVE_ANCHOR[0]:.4f})."
                if real_detected else
                "Offline mode: live user position anchored inside study area."
            ),
        }

    _LOCATION_CACHE["data"] = result
    _LOCATION_CACHE["timestamp"] = now
    return result


def resolve_destination(dest_input: str) -> Tuple[float, float, str]:
    """
    Resolves destination string with strict input length sanitization.
    """
    # Sanitize and truncate to prevent regex / substring DoS
    clean = dest_input.strip()[:100].lower()

    # 1. Check Landmark Dictionary
    for landmark_key, coords in STUDY_AREA_LANDMARKS.items():
        if landmark_key in clean or clean in landmark_key:
            return coords[0], coords[1], landmark_key.title()

    # 2. Parse Coordinate String: "lat, lon" or "lon, lat"
    if "," in clean:
        parts = [p.strip() for p in clean.split(",")]
        if len(parts) == 2:
            try:
                v1, v2 = float(parts[0]), float(parts[1])
                # Check if first is Lat (~19) and second is Lon (~72)
                if (15.0 <= v1 <= 25.0) and (70.0 <= v2 <= 80.0):
                    lat, lon = v1, v2
                elif (70.0 <= v1 <= 80.0) and (15.0 <= v2 <= 25.0):
                    lon, lat = v1, v2
                else:
                    lon, lat = v1, v2

                # Check if inside study area or clamp
                clamped_lat = max(MIN_LAT, min(MAX_LAT, lat))
                clamped_lon = max(MIN_LON, min(MAX_LON, lon))
                return clamped_lon, clamped_lat, f"Coordinates ({clamped_lat:.4f}, {clamped_lon:.4f})"
            except ValueError:
                pass

    # Fallback to Kurla Station if unrecognized
    fallback_coords = STUDY_AREA_LANDMARKS["kurla station"]
    return fallback_coords[0], fallback_coords[1], f"Kurla Station (Default for '{dest_input}')"
