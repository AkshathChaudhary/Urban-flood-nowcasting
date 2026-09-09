"""
Pydantic schemas for rainfall and Doppler radar nowcasting API.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RadarFrameInfo(BaseModel):
    time: int = Field(..., description="Unix timestamp of radar frame")
    tile_url: str = Field(..., description="Web Mercator PNG tile URL for GIS mapping")
    relative_time: str = Field(..., description="Human-readable relative time (e.g., -10 min, +20 min)")
    rain_rate_mmh: float = Field(..., description="Estimated domain rain rate (mm/hr)")
    reflectivity_dbz: float = Field(..., description="Estimated radar reflectivity (dBZ)")


class RainfallSummary(BaseModel):
    horizon_minutes: int
    max_rate_mmh: float
    mean_rate_mmh: float
    max_reflectivity_dbz: float
    mean_reflectivity_dbz: float
    is_raining: bool


class RainfallOverviewResponse(BaseModel):
    scenario: str
    current_rain_rate_mmh: float
    api_source: str
    horizons: List[int]
    summaries: Dict[int, RainfallSummary]
    radar_frames: List[RadarFrameInfo] = []


class RainfallGridResponse(BaseModel):
    scenario: str
    horizon_minutes: int
    rows: int
    cols: int
    cell_size_m: float
    origin_lat: float
    origin_lon: float
    summary: RainfallSummary
    rain_rate_grid: List[List[float]]
    reflectivity_dbz_grid: List[List[float]]


class PointRainfallResponse(BaseModel):
    lat: Optional[float]
    lon: Optional[float]
    row: int
    col: int
    rain_rate_mmh_at_horizon: Dict[int, float]
    reflectivity_dbz_at_horizon: Dict[int, float]
    intensity_category: str  # NONE, LIGHT, MODERATE, HEAVY, CLOUDBURST
