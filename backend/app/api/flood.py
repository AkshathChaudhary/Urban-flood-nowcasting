"""
API Router: /api/flood-forecast and /api/dem endpoints.
Coupled 2D hydrodynamic runoff & digital elevation terrain models.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import numpy as np

from backend.app.config import (
    CELL_SIZE_M,
    DATA_DIR,
    GRID_COLS,
    GRID_ROWS,
    ORIGIN_LAT,
    ORIGIN_LON,
)
from backend.app.engine_state import (
    compute_summary,
    get_current_scenario,
    get_engine,
    grid_to_lat_lon,
    lat_lon_to_grid,
)
from backend.app.engine.flood_engine import FloodEngine
from backend.app.models.drainage import DrainageGraph
from backend.data.rainfall.provider import KolkataMonsoonProvider
from backend.app.models.flood import (
    FloodForecastOverview,
    FloodGridResponse,
    PointDepthResponse,
)

router = APIRouter(prefix="/api", tags=["flood-forecast"])

# Kolkata In-Memory Cache for fast sub-millisecond responses
_kolkata_engine: Optional[FloodEngine] = None
_kolkata_grids: Optional[Dict[int, np.ndarray]] = None
_kolkata_scenario: str = "heavy"
_kolkata_scenario_title: Optional[str] = "Heavy Convective Storm (30 mm/hr)"


def set_kolkata_engine(engine: FloodEngine, grids: Dict[int, np.ndarray], scenario: str = "heavy", scenario_title: Optional[str] = None) -> None:
    global _kolkata_engine, _kolkata_grids, _kolkata_scenario, _kolkata_scenario_title
    _kolkata_engine = engine
    _kolkata_grids = grids
    _kolkata_scenario = scenario
    _kolkata_scenario_title = scenario_title or scenario.replace("_", " ").title()


def get_kolkata_scenario() -> str:
    global _kolkata_scenario
    return _kolkata_scenario


def get_kolkata_scenario_title() -> Optional[str]:
    global _kolkata_scenario_title
    return _kolkata_scenario_title


def reset_kolkata_forecast() -> None:
    """Resets cached Kolkata engine and grids, forcing reload from disk upon next request."""
    global _kolkata_engine, _kolkata_grids
    _kolkata_engine = None
    _kolkata_grids = None


def get_kolkata_forecast():
    global _kolkata_engine, _kolkata_grids, _kolkata_scenario
    if _kolkata_grids is not None and _kolkata_engine is not None:
        return _kolkata_engine, _kolkata_grids

    dem_path = DATA_DIR / "cities" / "kolkata" / "dem" / "elevation_grid.npy"
    nodes_path = DATA_DIR / "cities" / "kolkata" / "drainage" / "drainage_nodes.geojson"
    edges_path = DATA_DIR / "cities" / "kolkata" / "drainage" / "drainage_edges.geojson"

    dem = np.load(dem_path).astype(np.float32)
    drainage = DrainageGraph(
        nodes_path=nodes_path,
        edges_path=edges_path,
        cell_size_m=35.0,
    )
    rainfall_provider = KolkataMonsoonProvider(
        grid_shape=(int(dem.shape[0]), int(dem.shape[1])),
        cell_size_m=35.0,
    )
    engine = FloodEngine(
        dem=dem,
        drainage_graph=drainage,
        cell_size_m=35.0,
        boundary_condition="outflow",
        rainfall_provider=rainfall_provider,
        # Kolkata monsoon calibration:
        # KMC drainage is chronically silted/clogged — only ~15% of nominal capacity
        # functions during heavy convective storms (CPHEEO audit findings)
        drain_blockage_factor=0.15,
        # Pre-monsoon soil is already near saturation from June-July cumulative rainfall
        antecedent_saturation_fraction=0.6,
        # Hooghly tidal backwater locks outfall discharge during high tide
        tidal_lock=True,
    )
    _kolkata_engine = engine
    _kolkata_grids = engine.run_forecast(_kolkata_scenario, 180, 300.0)
    return _kolkata_engine, _kolkata_grids


# Universal Dynamic Corridor Engines Cache
_corridor_engines: Dict[str, Tuple[FloodEngine, Dict[int, np.ndarray]]] = {}
_corridor_scenarios: Dict[str, str] = {}


def get_corridor_forecast(city_slug: str):
    global _corridor_engines, _corridor_scenarios
    c = city_slug.lower().strip()
    if c in _corridor_engines:
        return _corridor_engines[c]

    city_dir = DATA_DIR / "cities" / c
    dem_path = city_dir / "dem" / "elevation_grid.npy"
    meta_path = city_dir / "dem" / "dem_metadata.json"
    nodes_path = city_dir / "drainage" / "drainage_nodes.geojson"
    edges_path = city_dir / "drainage" / "drainage_edges.geojson"

    if not dem_path.exists():
        raise HTTPException(status_code=404, detail=f"Corridor DEM not found for '{c}'.")

    dem = np.load(dem_path).astype(np.float32)
    rows, cols = dem.shape
    cell_size_m = 25.0
    bbox = [19.0, 19.1, 72.8, 72.9]
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                mdata = json.load(f)
                cell_size_m = float(mdata.get("cell_size_m", 25.0))
                bbox = mdata.get("bbox", bbox)
        except Exception:
            pass

    drainage = None
    if nodes_path.exists() and edges_path.exists():
        drainage = DrainageGraph(
            nodes_path=nodes_path,
            edges_path=edges_path,
            cell_size_m=cell_size_m,
        )

    from backend.data.rainfall.provider import CorridorRainfallProvider
    min_idx = np.unravel_index(np.argmin(dem), dem.shape)
    sink_r, sink_c = int(min_idx[0]), int(min_idx[1])
    center_lat = (bbox[0] + bbox[1]) / 2.0
    center_lon = (bbox[2] + bbox[3]) / 2.0

    scen = _corridor_scenarios.get(c, "heavy")
    rainfall_provider = CorridorRainfallProvider(
        lat=center_lat,
        lon=center_lon,
        grid_shape=(rows, cols),
        cell_size_m=cell_size_m,
        scenario=scen,
        hotspot_row=sink_r,
        hotspot_col=sink_c,
    )

    engine = FloodEngine(
        dem=dem,
        drainage_graph=drainage,
        cell_size_m=cell_size_m,
        boundary_condition="outflow",
        rainfall_provider=rainfall_provider,
    )
    grids = engine.run_forecast(scen, 180, 300.0)
    _corridor_engines[c] = (engine, grids)
    return engine, grids


class DemGridResponse(BaseModel):
    city: str
    rows: int
    cols: int
    cell_size_m: float
    min_elevation_m: float
    max_elevation_m: float
    mean_elevation_m: float
    bounds: List[List[float]]
    grid: List[List[float]]


@router.get("/dem/grid", response_model=DemGridResponse)
def get_dem_elevation_grid(city: Optional[str] = Query("mumbai")):
    """
    Returns Digital Elevation Model (DEM) elevation grid and metadata
    for 2D hypsometric terrain visualization and hydrodynamic slope analysis.
    Supports Mumbai, Kolkata, and any arbitrary dynamic corridor.
    """
    c = (city or "mumbai").lower().strip()
    if c == "kolkata":
        dem_path = DATA_DIR / "cities" / "kolkata" / "dem" / "elevation_grid.npy"
        dem = np.load(dem_path).astype(np.float32)
        return DemGridResponse(
            city="Kolkata",
            rows=int(dem.shape[0]),
            cols=int(dem.shape[1]),
            cell_size_m=35.0,
            min_elevation_m=round(float(np.min(dem)), 2),
            max_elevation_m=round(float(np.max(dem)), 2),
            mean_elevation_m=round(float(np.mean(dem)), 2),
            bounds=[[22.5050, 88.3850], [22.6020, 88.4380]],
            grid=np.round(dem, 2).tolist(),
        )
    elif (DATA_DIR / "cities" / c / "dem" / "elevation_grid.npy").exists():
        dem_path = DATA_DIR / "cities" / c / "dem" / "elevation_grid.npy"
        meta_path = DATA_DIR / "cities" / c / "dem" / "dem_metadata.json"
        dem = np.load(dem_path).astype(np.float32)
        cell_size_m = 25.0
        bounds = [[19.0600, 72.8500], [19.0800, 72.8700]]
        city_label = c
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                    cell_size_m = float(m.get("cell_size_m", 25.0))
                    city_label = m.get("city", c)
                    bbox = m.get("bbox")
                    if bbox and len(bbox) == 4:
                        bounds = [[float(bbox[0]), float(bbox[2])], [float(bbox[1]), float(bbox[3])]]
            except Exception:
                pass
        return DemGridResponse(
            city=city_label,
            rows=int(dem.shape[0]),
            cols=int(dem.shape[1]),
            cell_size_m=cell_size_m,
            min_elevation_m=round(float(np.min(dem)), 2),
            max_elevation_m=round(float(np.max(dem)), 2),
            mean_elevation_m=round(float(np.mean(dem)), 2),
            bounds=bounds,
            grid=np.round(dem, 2).tolist(),
        )
    else:
        dem_path = DATA_DIR / "dem" / "elevation_grid.npy"
        dem = np.load(dem_path).astype(np.float32)
        deg_lat = 2000.0 / 111320.0
        deg_lon = 2000.0 / (111320.0 * np.cos(np.radians(19.06)))
        return DemGridResponse(
            city="Mumbai",
            rows=int(dem.shape[0]),
            cols=int(dem.shape[1]),
            cell_size_m=10.0,
            min_elevation_m=round(float(np.min(dem)), 2),
            max_elevation_m=round(float(np.max(dem)), 2),
            mean_elevation_m=round(float(np.mean(dem)), 2),
            bounds=[[19.0600, 72.8500], [19.0600 + deg_lat, 72.8500 + deg_lon]],
            grid=np.round(dem, 2).tolist(),
        )


@router.get("/flood-forecast", response_model=FloodForecastOverview)
def get_flood_forecast_overview(city: Optional[str] = Query("mumbai")):
    """
    Returns an overview of the current flood forecast across all time horizons (0 to 180 min).
    Provides KPI summary stats (max depth, mean depth, flooded cell count) for each horizon.
    """
    c = (city or "mumbai").lower().strip()
    if c == "kolkata":
        k_engine, k_grids = get_kolkata_forecast()
        horizons = sorted(k_grids.keys())
        summaries = {h: compute_summary(k_grids[h], h, cell_size_m=35.0) for h in horizons}
        return FloodForecastOverview(
            scenario=get_kolkata_scenario(),
            scenario_title=get_kolkata_scenario_title(),
            horizons=horizons,
            summaries=summaries,
            total_rain_volume_m3=round(k_engine.total_rain_volume_m3, 1),
            total_infiltrated_volume_m3=round(k_engine.total_infiltrated_volume_m3, 1),
            total_absorbed_volume_m3=round(k_engine.total_absorbed_volume_m3, 1),
            total_overflow_volume_m3=round(k_engine.total_overflow_volume_m3, 1),
        )
    elif (DATA_DIR / "cities" / c / "dem" / "elevation_grid.npy").exists():
        c_engine, c_grids = get_corridor_forecast(c)
        horizons = sorted(c_grids.keys())
        summaries = {h: compute_summary(c_grids[h], h, cell_size_m=c_engine.cell_size) for h in horizons}
        scen_name = _corridor_scenarios.get(c, "heavy")
        sc_title = f"{scen_name.replace('_', ' ').title()} Nowcast"
        return FloodForecastOverview(
            scenario=scen_name,
            scenario_title=sc_title,
            horizons=horizons,
            summaries=summaries,
            total_rain_volume_m3=round(c_engine.total_rain_volume_m3, 1),
            total_infiltrated_volume_m3=round(c_engine.total_infiltrated_volume_m3, 1),
            total_absorbed_volume_m3=round(c_engine.total_absorbed_volume_m3, 1),
            total_overflow_volume_m3=round(c_engine.total_overflow_volume_m3, 1),
        )

    engine = get_engine()
    scenario = get_current_scenario()
    horizons = sorted(engine.forecast_grids.keys())

    summaries = {
        h: compute_summary(engine.forecast_grids[h], h) for h in horizons
    }

    from backend.app.api.simulate import SUPPORTED_SCENARIOS
    sc_title = SUPPORTED_SCENARIOS.get(scenario, {}).get("title", scenario.replace("_", " ").title())

    return FloodForecastOverview(
        scenario=scenario,
        scenario_title=sc_title,
        horizons=horizons,
        summaries=summaries,
        total_rain_volume_m3=round(engine.total_rain_volume_m3, 1),
        total_infiltrated_volume_m3=round(engine.total_infiltrated_volume_m3, 1),
        total_absorbed_volume_m3=round(engine.total_absorbed_volume_m3, 1),
        total_overflow_volume_m3=round(engine.total_overflow_volume_m3, 1),
    )


@router.get("/flood-forecast/point/query", response_model=PointDepthResponse)
def query_point_depth(
    row: Optional[int] = Query(None, ge=0),
    col: Optional[int] = Query(None, ge=0),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    city: Optional[str] = Query("mumbai"),
):
    """
    Query flood depth progression at a specific coordinate or grid cell.
    Supports Mumbai, Kolkata, and any arbitrary corridor.
    """
    c = (city or "mumbai").lower().strip()
    is_kolkata = c == "kolkata"

    if is_kolkata:
        k_engine, k_grids = get_kolkata_forecast()
        k_min_lat, k_max_lat = 22.5050, 22.6020
        k_min_lon, k_max_lon = 88.3850, 88.4380

        if lat is not None and lon is not None:
            norm_r = (k_max_lat - lat) / max(k_max_lat - k_min_lat, 1e-6)
            norm_c = (lon - k_min_lon) / max(k_max_lon - k_min_lon, 1e-6)
            r = int(np.clip(round(norm_r * 299), 0, 299))
            col_idx = int(np.clip(round(norm_c * 159), 0, 159))
        else:
            r = row if row is not None and row < 300 else 0
            col_idx = col if col is not None and col < 160 else 0
            lat = k_max_lat - (r / 299.0) * (k_max_lat - k_min_lat)
            lon = k_min_lon + (col_idx / 159.0) * (k_max_lon - k_min_lon)

        elevation = float(k_engine.dem[r, col_idx])
        depth_at_horizons = {h: round(float(k_grids[h][r, col_idx]), 3) for h in sorted(k_grids.keys())}
        street_depth_at_horizons = {h: round(float(k_grids[h][r, col_idx] / 0.8), 3) for h in sorted(k_grids.keys())}
        max_street_depth = max(street_depth_at_horizons.values()) if street_depth_at_horizons else 0.0

        hazard = "IMPASSABLE" if max_street_depth > 0.30 else "CAUTION" if max_street_depth > 0.10 else "CLEAR"

        return PointDepthResponse(
            lat=round(lat, 5),
            lon=round(lon, 5),
            row=r,
            col=col_idx,
            elevation_m=round(elevation, 2),
            depth_m_at_horizon=depth_at_horizons,
            street_depth_m_at_horizon=street_depth_at_horizons,
            porosity=0.8,
            hazard_level=hazard,
        )
    elif (DATA_DIR / "cities" / c / "dem" / "elevation_grid.npy").exists():
        c_engine, c_grids = get_corridor_forecast(c)
        meta_path = DATA_DIR / "cities" / c / "dem" / "dem_metadata.json"
        bbox = [19.0, 19.1, 72.8, 72.9]
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    bbox = json.load(f).get("bbox", bbox)
            except Exception:
                pass
        min_lat, max_lat, min_lon, max_lon = bbox[0], bbox[1], bbox[2], bbox[3]
        rows, cols = c_engine.rows, c_engine.cols

        if lat is not None and lon is not None:
            norm_r = (lat - min_lat) / max(max_lat - min_lat, 1e-6)
            norm_c = (lon - min_lon) / max(max_lon - min_lon, 1e-6)
            r = int(np.clip(round(norm_r * (rows - 1)), 0, rows - 1))
            col_idx = int(np.clip(round(norm_c * (cols - 1)), 0, cols - 1))
        else:
            r = row if row is not None and row < rows else 0
            col_idx = col if col is not None and col < cols else 0
            lat = min_lat + (r / max(rows - 1, 1)) * (max_lat - min_lat)
            lon = min_lon + (col_idx / max(cols - 1, 1)) * (max_lon - min_lon)

        elevation = float(c_engine.dem[r, col_idx])
        depth_at_horizons = {h: round(float(c_grids[h][r, col_idx]), 3) for h in sorted(c_grids.keys())}
        street_depth_at_horizons = {h: round(float(c_grids[h][r, col_idx] / 0.8), 3) for h in sorted(c_grids.keys())}
        max_street_depth = max(street_depth_at_horizons.values()) if street_depth_at_horizons else 0.0
        hazard = "IMPASSABLE" if max_street_depth > 0.30 else "CAUTION" if max_street_depth > 0.10 else "CLEAR"

        return PointDepthResponse(
            lat=round(lat, 5),
            lon=round(lon, 5),
            row=r,
            col=col_idx,
            elevation_m=round(elevation, 2),
            depth_m_at_horizon=depth_at_horizons,
            street_depth_m_at_horizon=street_depth_at_horizons,
            porosity=0.8,
            hazard_level=hazard,
        )

    # Mumbai Domain
    engine = get_engine()
    if row is None or col is None:
        if lat is not None and lon is not None:
            row, col = lat_lon_to_grid(lat, lon)
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either (row, col) or (lat, lon) coordinates.",
            )
    elif lat is None or lon is None:
        lat, lon = grid_to_lat_lon(row, col)

    elevation = float(engine.dem[row, col])
    porosity = float(engine.surface_porosity[row, col]) if hasattr(engine, "surface_porosity") else 1.0

    depth_at_horizons = {
        h: round(float(engine.forecast_grids[h][row, col]), 3)
        for h in sorted(engine.forecast_grids.keys())
    }

    street_depth_at_horizons = {
        h: round(float(engine.forecast_grids[h][row, col] / max(porosity, 0.1)), 3)
        for h in sorted(engine.forecast_grids.keys())
    }

    max_street_depth = max(street_depth_at_horizons.values()) if street_depth_at_horizons else 0.0
    hazard = "IMPASSABLE" if max_street_depth > 0.30 else "CAUTION" if max_street_depth > 0.10 else "CLEAR"

    return PointDepthResponse(
        lat=lat,
        lon=lon,
        row=row,
        col=col,
        elevation_m=round(elevation, 2),
        depth_m_at_horizon=depth_at_horizons,
        street_depth_m_at_horizon=street_depth_at_horizons,
        porosity=round(porosity, 3),
        hazard_level=hazard,
    )


@router.get("/flood-forecast/{minutes}", response_model=FloodGridResponse)
def get_flood_forecast_grid(minutes: int, city: Optional[str] = Query("mumbai")):
    """
    Returns the complete 2D water depth grid (in meters) for a specific time horizon and city.
    Ideal for GIS heatmap visualization in Leaflet.
    Supports Mumbai, Kolkata, and any arbitrary corridor.
    """
    c = (city or "mumbai").lower().strip()
    if c == "kolkata":
        k_engine, k_grids = get_kolkata_forecast()
        available = sorted(k_grids.keys())
        nearest_horizon = min(available, key=lambda h: abs(h - minutes))
        grid = k_grids[nearest_horizon]
        summary = compute_summary(grid, nearest_horizon)
        return FloodGridResponse(
            scenario=get_kolkata_scenario(),
            scenario_title=get_kolkata_scenario_title(),
            horizon_minutes=nearest_horizon,
            rows=int(grid.shape[0]),
            cols=int(grid.shape[1]),
            cell_size_m=35.0,
            origin_lat=22.5050,
            origin_lon=88.3850,
            bounds=[[22.5050, 88.3850], [22.6020, 88.4380]],
            summary=summary,
            depth_grid=np.round(grid, 3).tolist(),
        )
    elif (DATA_DIR / "cities" / c / "dem" / "elevation_grid.npy").exists():
        c_engine, c_grids = get_corridor_forecast(c)
        available = sorted(c_grids.keys())
        nearest_horizon = min(available, key=lambda h: abs(h - minutes))
        grid = c_grids[nearest_horizon]
        summary = compute_summary(grid, nearest_horizon, cell_size_m=c_engine.cell_size)

        meta_path = DATA_DIR / "cities" / c / "dem" / "dem_metadata.json"
        orig_lat, orig_lon = 19.06, 72.85
        bounds = None
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                    bbox = m.get("bbox")
                    if bbox and len(bbox) == 4:
                        orig_lat, orig_lon = float(bbox[0]), float(bbox[2])
                        bounds = [[float(bbox[0]), float(bbox[2])], [float(bbox[1]), float(bbox[3])]]
            except Exception:
                pass

        scen_name = _corridor_scenarios.get(c, "heavy")
        return FloodGridResponse(
            scenario=scen_name,
            scenario_title=f"{scen_name.replace('_', ' ').title()} Nowcast",
            horizon_minutes=nearest_horizon,
            rows=int(grid.shape[0]),
            cols=int(grid.shape[1]),
            cell_size_m=c_engine.cell_size,
            origin_lat=orig_lat,
            origin_lon=orig_lon,
            bounds=bounds,
            summary=summary,
            depth_grid=np.round(grid, 3).tolist(),
        )

    engine = get_engine()
    if minutes not in engine.forecast_grids:
        available = sorted(engine.forecast_grids.keys())
        if minutes < 0 or minutes > max(available):
            raise HTTPException(status_code=404, detail=f"Forecast horizon {minutes} min not found. Available: {available}")
        nearest_horizon = min(available, key=lambda h: abs(h - minutes))
        minutes = nearest_horizon

    grid = engine.forecast_grids[minutes]
    summary = compute_summary(grid, minutes)

    curr_sc = get_current_scenario()
    from backend.app.api.simulate import SUPPORTED_SCENARIOS
    sc_title = SUPPORTED_SCENARIOS.get(curr_sc, {}).get("title", curr_sc.replace("_", " ").title())

    deg_lat = 2000.0 / 111320.0
    deg_lon = 2000.0 / (111320.0 * np.cos(np.radians(19.06)))
    mumbai_bounds = [[19.0600, 72.8500], [19.0600 + deg_lat, 72.8500 + deg_lon]]

    return FloodGridResponse(
        scenario=curr_sc,
        scenario_title=sc_title,
        horizon_minutes=minutes,
        rows=GRID_ROWS,
        cols=GRID_COLS,
        cell_size_m=CELL_SIZE_M,
        origin_lat=ORIGIN_LAT,
        origin_lon=ORIGIN_LON,
        bounds=mumbai_bounds,
        summary=summary,
        depth_grid=np.round(grid, 3).tolist(),
    )
