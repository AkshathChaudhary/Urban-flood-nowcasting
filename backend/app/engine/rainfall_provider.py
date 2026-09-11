"""
Rainfall Provider Engine Module (Pair B)
========================================

Provides abstract and concrete rainfall nowcasting providers.
"""

from backend.data.rainfall.provider import (
    RainfallProvider,
    DemoRainfallProvider,
    OneWeatherRadarNowcastProvider,
    HistoricalRainfallProvider,
    SpatialHistoricalProvider,
    SpatialDemoProvider,
    get_rainfall_provider,
)

# Canonical alias for live provider
LiveRainfallProvider = OneWeatherRadarNowcastProvider

__all__ = [
    "RainfallProvider",
    "DemoRainfallProvider",
    "LiveRainfallProvider",
    "OneWeatherRadarNowcastProvider",
    "HistoricalRainfallProvider",
    "SpatialHistoricalProvider",
    "SpatialDemoProvider",
    "get_rainfall_provider",
]
