# Rainfall Data Sources & Ingestion Guide

This document details the meteorological data sources, ingestion pipelines, and synthetic scenario generation for the **Urban Flood Nowcasting** platform (Pair B).

---

## 1. Primary Data Sources

| Source | Provider | Resolution | Update Frequency | Access Protocol | Usage in Project |
|---|---|---|---|---|---|
| **One Weather API (OpenWeather One Call 3.0/2.5)** | OpenWeather | Minute-by-minute (60 min horizon) | Real-time (10 min updates) | REST JSON (`api.openweathermap.org/data/3.0/onecall`) | High-resolution nowcasting (`OneWeatherRadarNowcastProvider`) |
| **Open-Meteo High-Res Minutely API** | Open-Meteo | 15-minute sub-hourly (4 hr horizon) | Real-time | REST JSON (`api.open-meteo.com/v1/forecast?minutely_15=precipitation`) | Zero-key automated fallback for nowcasting |
| **RainViewer Doppler Radar API** | RainViewer | ~1 km radar tiles | 10 minutes | REST JSON & PNG tiles (`api.rainviewer.com/public/weather-maps.json`) | Live Doppler radar reflectivity frames & storm tracking |
| **Open-Meteo Historical Archive** | ERA5 / Copernicus | Hourly | Historical | REST JSON (`archive-api.open-meteo.com/v1/archive`) | Replaying historical flood events (e.g. Mumbai July 2023) (`HistoricalRainfallProvider`) — **Kept As Is** |
| **NASA GPM IMERG** | NASA GES DISC | 0.1° (~10 km) | 30 minutes | HDF5 / NetCDF4 via Earthdata HTTPS | Calibration & satellite baseline precipitation |
| **IMD Doppler Weather Radar** | India Meteorological Dept | ~1 km | 10 minutes | Radar reflectivity images / AWS rain gauge data | Ground-truth reference for cloudburst events |

---

## 2. Doppler Radar Reflectivity & Marshall-Palmer Equation

Doppler weather radar measures backscattered reflectivity factor $Z$ in $\text{mm}^6/\text{m}^3$ (expressed logarithmically in $\text{dBZ}$).
Rain rate $R$ (in $\text{mm/hr}$) is calculated using the standard empirical **Marshall-Palmer $Z-R$ relation**:

$$Z = 200 \cdot R^{1.6}$$

$$\text{dBZ} = 10 \log_{10}(Z) = 10 \log_{10}(200 \cdot R^{1.6})$$

$$R = \left(\frac{10^{(\text{dBZ}/10)}}{200}\right)^{0.625}$$

### Meteorological Benchmark Reference:
| Reflectivity (dBZ) | Rain Rate (mm/hr) | Weather Category |
|---|---|---|
| $< 15\text{ dBZ}$ | $< 0.3\text{ mm/hr}$ | Very light drizzle |
| $20\text{ dBZ}$ | $\approx 0.65\text{ mm/hr}$ | Light rain |
| $30\text{ dBZ}$ | $\approx 2.73\text{ mm/hr}$ | Moderate rain |
| $40\text{ dBZ}$ | $\approx 11.5\text{ mm/hr}$ | Heavy rain |
| $50\text{ dBZ}$ | $\approx 48.6\text{ mm/hr}$ | Intense tropical downpour |
| $55+\text{ dBZ}$ | $\approx 100+\text{ mm/hr}$ | Severe cloudburst core |

---

## 3. Ingestion Implementations

All providers implement the standard contract defined in [`provider.py`](file:///c:/Users/Aniket/OneDrive/Desktop/flood/Urban-flood-nowcasting/backend/data/rainfall/provider.py):

```python
class RainfallProvider(abc.ABC):
    @abc.abstractmethod
    def generate_nowcast(
        self, scenario: str = "live", horizon_minutes: int = 180
    ) -> Dict[int, np.ndarray]:
        """Returns {minutes: np.ndarray shape (200, 200) in mm/hr}"""
        pass

    def get_current_rainfall(self) -> float:
        """Returns instantaneous domain-average rain rate (mm/hr) at T=0."""
        pass

    def get_radar_frames(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns Doppler radar frames (timestamps, tile URLs, reflectivity dBZ, rain rate)."""
        pass

    def get_radar_reflectivity_grid(self, minute: float = 0.0) -> Optional[np.ndarray]:
        """Returns Doppler radar reflectivity field in dBZ across (rows, cols)."""
        pass
```

### Deterministic Synthetic Scenarios (Demo Mode)

For predictable, stress-testable demonstration and offline execution, 5 scenarios are pre-configured:
1. **Scenario 1: Moderate Rain (`moderate`)** — Uniform 10 mm/hr across the domain with linear ramp-up and ramp-down over 2 hours.
2. **Scenario 2: Heavy Rain (`heavy`)** — 30 mm/hr peak with a 2D Gaussian spatial bell centered over the low-lying southeastern valley.
3. **Scenario 3: Extreme Rainstorm (`extreme`)** — 60 mm/hr moving storm cell traveling northwest to southeast at 20 km/h.
4. **Scenario 4: Cloudburst (`cloudburst`)** — 120 mm/hr ultra-localized downpour (500m radius) active for 30 minutes.
5. **Scenario 5: Extreme Rainstorm + 40% Blockage (`extreme_blocked`)** — 60 mm/hr moving storm coupled with drainage network blockage flag for Pair A.

---

## 4. Python Usage

```python
from backend.data.rainfall.provider import get_rainfall_provider

# 1. One Weather API + Doppler Radar High-Resolution Nowcasting
# (Accepts optional api_key or reads OPENWEATHER_API_KEY environment variable;
#  automatically falls back to Open-Meteo Minutely-15 and RainViewer radar frames)
radar_provider = get_rainfall_provider(mode="one_weather", lat=19.07, lon=72.85)

# High-resolution nowcast grids across horizons [0, 30, 60, 90, 120, 180]
nowcast = radar_provider.generate_nowcast(horizon_minutes=180)

# Instantaneous domain-average rain rate (mm/hr)
current_rate = radar_provider.get_current_rainfall()

# Doppler radar frames with tile URLs and reflectivity estimates
frames = radar_provider.get_radar_frames(limit=5)

# Continuous 2D Doppler reflectivity field (dBZ)
dbz_grid = radar_provider.get_radar_reflectivity_grid(minute=15.0)

# 2. Historical Replay (Kept As Is)
hist_provider = get_rainfall_provider(
    mode="historical", lat=19.07, lon=72.85, date_str="2023-07-26", start_hour=11
)
hist_nowcast = hist_provider.generate_nowcast()

# 3. Spatial Historical Cloudburst Plume (Kept As Is)
spatial_hist = get_rainfall_provider(
    mode="spatial_historical", lat=19.07, lon=72.85, date_str="2023-07-26", start_hour=10
)
sp_nowcast = spatial_hist.generate_nowcast()

# 4. Demo Mode (Deterministic Scenarios)
demo_provider = get_rainfall_provider(mode="demo")
demo_nowcast = demo_provider.generate_nowcast(scenario="cloudburst", horizon_minutes=180)
```
