"""
Test Kolkata Flood Raster Calibration & Ground-Truth Alignment
==============================================================

Verifies:
1. North-to-South coordinate system alignment (Row 0 = North, Row 299 = South).
2. DEM hypsometry (Western high ground, elevated Salt Lake, low Wetlands).
3. Historical waterlogging hotspots (Ultadanga, Science City, Chingrighata, Ruby)
   record realistic flood inundation depths.
4. Non-flood-prone areas (Salt Lake City reclaimed township, Western ridge)
   remain safe/dry with negligible ponding (< 5cm).
5. Cross-check point query API for accuracy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from backend.app.api.flood import get_kolkata_forecast, query_point_depth, reset_kolkata_forecast
from backend.data.cities.kolkata.build_kolkata_corridor import (
    GRID_ROWS,
    GRID_COLS,
    MIN_LAT,
    MAX_LAT,
    MIN_LON,
    MAX_LON,
    latlon_to_grid,
    grid_to_latlon,
)


def test_coordinate_orientation():
    """Verify that Row 0 is at North and Row 299 is at South."""
    # North coordinate (Kestopur / Ultadanga north)
    r_north, _ = latlon_to_grid(MAX_LAT, MIN_LON)
    assert r_north == 0, f"MAX_LAT should map to row 0, got {r_north}"

    # South coordinate (Ruby / Garia approach)
    r_south, _ = latlon_to_grid(MIN_LAT, MIN_LON)
    assert r_south == GRID_ROWS - 1, f"MIN_LAT should map to row {GRID_ROWS - 1}, got {r_south}"

    # Round trip check
    lat_0, _ = grid_to_latlon(0, 0)
    assert abs(lat_0 - MAX_LAT) < 1e-4, f"Row 0 should have lat {MAX_LAT}, got {lat_0}"

    lat_last, _ = grid_to_latlon(GRID_ROWS - 1, 0)
    assert abs(lat_last - MIN_LAT) < 1e-4, f"Row {GRID_ROWS - 1} should have lat {MIN_LAT}, got {lat_last}"
    print("[PASS] Coordinate orientation: Row 0 is North, Row 299 is South.")


def test_dem_elevation_profile():
    """Verify DEM elevation profiles match Kolkata topography."""
    dem_path = Path("backend/data/cities/kolkata/dem/elevation_grid.npy")
    assert dem_path.exists(), "DEM grid file must exist"
    dem = np.load(dem_path)

    # Western natural levee along Hooghly (Col ~ 0-20)
    west_elev = float(dem[150, 10])
    assert 6.0 <= west_elev <= 7.5, f"Western levee elevation should be 6.0-7.5m, got {west_elev:.2f}m"

    # Salt Lake City (Bidhannagar, North-East) - Reclaimed elevated silt fill
    r_sl, c_sl = latlon_to_grid(22.5860, 88.4200)
    salt_lake_elev = float(dem[r_sl, c_sl])
    assert 4.7 <= salt_lake_elev <= 5.8, f"Salt Lake should be elevated ~4.7-5.8m, got {salt_lake_elev:.2f}m"

    # East Kolkata Wetlands (EKW, South-East) - Natural saucer basin
    r_ekw, c_ekw = latlon_to_grid(22.5150, 88.4250)
    ekw_elev = float(dem[r_ekw, c_ekw])
    assert 2.5 <= ekw_elev <= 3.5, f"Wetlands should be low-lying ~2.5-3.5m, got {ekw_elev:.2f}m"

    # Salt Lake must be significantly higher than EKW
    assert salt_lake_elev > ekw_elev + 1.2, (
        f"Salt Lake ({salt_lake_elev:.2f}m) must be >1.2m higher than Wetlands ({ekw_elev:.2f}m)"
    )
    print(f"[PASS] DEM Profile: West={west_elev:.2f}m, Salt Lake={salt_lake_elev:.2f}m, EKW={ekw_elev:.2f}m.")


def test_hotspots_inundation_and_salt_lake_dryness():
    """
    Verify historical waterlogging hotspots register realistic depths
    while Salt Lake City and Western high ground remain safe/dry.
    """
    reset_kolkata_forecast()
    engine, grids = get_kolkata_forecast()
    assert 180 in grids, "180-minute forecast horizon must exist"

    hotspots = [
        ("Ultadanga Underpass", 22.5890, 88.3960, 0.20, 0.65),
        ("Science City / Parama", 22.5400, 88.3960, 0.15, 0.55),
        ("Chingrighata EM Bypass", 22.5650, 88.4050, 0.15, 0.55),
        ("Ruby Hospital Approach", 22.5135, 88.4010, 0.15, 0.55),
    ]

    print("\n--- HISTORICAL WATERLOGGING HOTSPOTS (180 min storm) ---")
    for name, lat, lon, min_expected_m, max_expected_m in hotspots:
        resp = query_point_depth(lat=lat, lon=lon, city="kolkata")
        depth_180_m = resp.depth_m_at_horizon.get(180, 0.0)
        print(f"  {name:<25}: Elev={resp.elevation_m:.2f}m, Depth={depth_180_m * 100:.1f}cm, Hazard={resp.hazard_level}")
        assert depth_180_m >= min_expected_m, (
            f"Hotspot {name} should have >= {min_expected_m*100:.1f}cm water, got {depth_180_m*100:.1f}cm"
        )
        assert depth_180_m <= max_expected_m, (
            f"Hotspot {name} should not exceed {max_expected_m*100:.1f}cm, got {depth_180_m*100:.1f}cm"
        )

    dry_zones = [
        ("Salt Lake Karunamoyee", 22.5860, 88.4200),
        ("Salt Lake Sector V", 22.5700, 88.4300),
        ("Western Levee Tangra", 22.5500, 88.3880),
    ]

    print("\n--- NON-FLOOD PRONE ELEVATED ZONES (180 min storm) ---")
    for name, lat, lon in dry_zones:
        resp = query_point_depth(lat=lat, lon=lon, city="kolkata")
        depth_180_m = resp.depth_m_at_horizon.get(180, 0.0)
        print(f"  {name:<25}: Elev={resp.elevation_m:.2f}m, Depth={depth_180_m * 100:.1f}cm, Hazard={resp.hazard_level}")
        assert depth_180_m < 0.05, (
            f"Dry zone {name} should not be submerged (<5cm), got {depth_180_m*100:.1f}cm"
        )
        assert resp.hazard_level == "CLEAR", (
            f"Dry zone {name} should have CLEAR hazard, got {resp.hazard_level}"
        )
    print("\n[PASS] All historical hotspots and non-flood zones calibrated correctly.")


if __name__ == "__main__":
    test_coordinate_orientation()
    test_dem_elevation_profile()
    test_hotspots_inundation_and_salt_lake_dryness()
