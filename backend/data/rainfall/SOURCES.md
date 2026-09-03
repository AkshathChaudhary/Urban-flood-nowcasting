# Rainfall Data Sources & Ingestion Guide

This document details the meteorological data sources, ingestion pipelines, and synthetic scenario generation for the **Urban Flood Nowcasting** platform (Pair B).

---

## 1. Primary Data Sources

| Source | Provider | Resolution | Update Frequency | Access Protocol | Usage in Project |
|---|---|---|---|---|---|
| **Open-Meteo Weather API** | Open-Meteo | Hourly / Minutely | Real-time | REST JSON (`api.open-meteo.com/v1/forecast`) | Real-time live precipitation fetching (`LiveRainfallProvider`) |
| **Open-Meteo Historical Archive** | ERA5 / Copernicus | Hourly | Historical | REST JSON (`archive-api.open-meteo.com/v1/archive`) | Replaying historical flood events (e.g. Mumbai July 2023) (`HistoricalRainfallProvider`) |
| **NASA GPM IMERG** | NASA GES DISC | 0.1° (~10 km) | 30 minutes | HDF5 / NetCDF4 via Earthdata HTTPS | Calibration & satellite baseline precipitation |
| **IMD Doppler Weather Radar** | India Meteorological Dept | ~1 km | 10 minutes | Radar reflectivity images / AWS rain gauge data | Ground-truth reference for cloudburst events |

---

## 2. Ingestion Implementations

All providers implement the standard interface contract defined in [`provider.py`](file:///c:/Users/Aniket/OneDrive/Desktop/flood/Urban-flood-nowcasting/backend/data/rainfall/provider.py):

```python
class RainfallProvider(abc.ABC):
    @abc.abstractmethod
    def generate_nowcast(
        self, scenario: str = "moderate", horizon_minutes: int = 180
    ) -> Dict[int, np.ndarray]:
        """Returns {minutes: np.ndarray shape (200, 200) in mm/hr}"""
        pass
```

### Deterministic Synthetic Scenarios (Demo Mode)

For predictable, stress-testable demonstration and offline execution, 5 scenarios are pre-configured:

1. **Scenario 1: Moderate Rain (`moderate`)**
   * Uniform 10 mm/hr across the domain with linear ramp-up and ramp-down over 2 hours.
2. **Scenario 2: Heavy Rain (`heavy`)**
   * 30 mm/hr peak with a 2D Gaussian spatial bell centered over the low-lying southeastern valley.
3. **Scenario 3: Extreme Rainstorm (`extreme`)**
   * 60 mm/hr moving storm cell traveling northwest to southeast at 20 km/h.
4. **Scenario 4: Cloudburst (`cloudburst`)**
   * 120 mm/hr ultra-localized downpour (500m radius) active for 30 minutes.
5. **Scenario 5: Extreme Rainstorm + 40% Blockage (`extreme_blocked`)**
   * 60 mm/hr moving storm coupled with drainage network blockage flag for Pair A.

---

## 3. Python Usage

```python
from backend.data.rainfall.provider import get_rainfall_provider

# 1. Demo Mode
provider = get_rainfall_provider(mode="demo")
nowcast = provider.generate_nowcast(scenario="cloudburst", horizon_minutes=180)

# 2. Live API Mode (Mumbai coordinates)
live_provider = get_rainfall_provider(mode="live", lat=19.07, lon=72.85)
live_nowcast = live_provider.generate_nowcast()

# 3. Historical Replay
hist_provider = get_rainfall_provider(
    mode="historical", lat=19.07, lon=72.85, date_str="2023-07-26", start_hour=11
)
hist_nowcast = hist_provider.generate_nowcast()
```
