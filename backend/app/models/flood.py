"""Pydantic schemas for flood nowcasting API."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SimulateRequest(BaseModel):
    city: Optional[str] = Field(default="mumbai", description="City to simulate: 'mumbai' or 'kolkata'")
    scenario: str = Field(
        default="moderate",
        description="Scenario: moderate, heavy, extreme, cloudburst, extreme_blocked, live, historical"
    )
    horizon_minutes: int = Field(default=180, ge=30, le=360)
    dt_seconds: float = Field(default=300.0, ge=60.0, le=600.0)
    lat: Optional[float] = Field(default=None, description="Latitude for live/historical query")
    lon: Optional[float] = Field(default=None, description="Longitude for live/historical query")
    date_str: Optional[str] = Field(
        default=None,
        description="YYYY-MM-DD for historical query",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    start_hour: Optional[int] = Field(default=None, ge=0, le=23)


class FloodSummary(BaseModel):
    horizon_minutes: int
    max_depth_m: float
    mean_depth_m: float
    flooded_cells_15cm: int
    flooded_cells_30cm: int
    surface_water_volume_m3: float


class FloodGridResponse(BaseModel):
    scenario: str
    horizon_minutes: int
    rows: int
    cols: int
    cell_size_m: float
    origin_lat: float
    origin_lon: float
    summary: FloodSummary
    depth_grid: List[List[float]]


class FloodForecastOverview(BaseModel):
    scenario: str
    horizons: List[int]
    summaries: Dict[int, FloodSummary]
    total_rain_volume_m3: float
    total_infiltrated_volume_m3: float
    total_absorbed_volume_m3: float
    total_overflow_volume_m3: float


class PointDepthResponse(BaseModel):
    lat: Optional[float]
    lon: Optional[float]
    row: int
    col: int
    elevation_m: float
    depth_m_at_horizon: Dict[int, float]
    street_depth_m_at_horizon: Optional[Dict[int, float]] = None
    porosity: Optional[float] = None
    hazard_level: str  # CLEAR, CAUTION, IMPASSABLE
