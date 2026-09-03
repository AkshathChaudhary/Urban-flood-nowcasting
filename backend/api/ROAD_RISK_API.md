# Road Flood Risk REST API Documentation

## Overview
This document specifies the RESTful API endpoints exposed by the backend for accessing the C1 road network flood risk, dynamic time series, hotspot rankings, summary statistics, and GeoJSON visualization layers.

- **Base URL**: `http://localhost:5000`
- **Prefix**: `/api/roads`
- **Data Format**: `JSON` / `GeoJSON`
- **CORS**: Enabled (`*`)

---

## Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/roads/summary` | High-level summary metrics for the road network. |
| `GET` | `/api/roads/hotspots` | Ranked road flood hotspots (supports `?limit=N`). |
| `GET` | `/api/roads/<road_id>` | Detailed static, dynamic, and hotspot properties for an individual road. |
| `GET` | `/api/roads/<road_id>/timeseries` | Multi-timestamp dynamic flood depth and combined risk evolution. |
| `GET` | `/api/roads/geojson` | Map-ready GeoJSON of the road network with dynamic risk properties. |
| `GET` | `/api/roads/hotspots/geojson` | Map-ready GeoJSON of the road network with hotspot priority ranks. |

---

## 1. GET `/api/roads/summary`

Returns aggregated statistics and breakdown metrics across the 1,513 road segments in the study area.

### Response `200 OK`
```json
{
  "study_area": "Mumbai 2x2km",
  "crs": "EPSG:4326",
  "total_roads": 1513,
  "mapped_roads": 1261,
  "unmapped_roads": 252,
  "critical_hotspots": 25,
  "high_hotspots": 452,
  "moderate_hotspots": 686,
  "low_hotspots": 98,
  "timestamps": [
    "T+0min",
    "T+30min",
    "T+60min",
    "T+90min",
    "T+120min",
    "T+180min"
  ],
  "number_of_timestamps": 6,
  "max_flood_depth_m": 0.475,
  "mean_hotspot_score": 0.4479,
  "hotspot_class_breakdown": {
    "CRITICAL": 25,
    "HIGH": 452,
    "MODERATE": 686,
    "LOW": 98,
    "UNKNOWN": 252
  }
}
```

---

## 2. GET `/api/roads/hotspots`

Returns the deterministically ranked list of road flood hotspots.

### Query Parameters
- `limit` *(optional, integer)*: Maximum number of ranked hotspots to return (e.g., `?limit=10`).

### Example Request
```http
GET /api/roads/hotspots?limit=2
```

### Response `200 OK`
```json
{
  "total_ranked_hotspots": 1261,
  "limit": 2,
  "hotspots": [
    {
      "rank": 1,
      "road_id": "R-301",
      "source": "13617067006",
      "target": "13617067002",
      "road_class": "residential",
      "length_m": 8.02,
      "hotspot_score": 0.7959,
      "hotspot_class": "CRITICAL",
      "peak_flood_depth_m": 0.405,
      "mean_flood_depth_m": 0.177,
      "peak_combined_risk": 0.8534,
      "mean_combined_risk": 0.58,
      "risk_duration": 6,
      "high_risk_duration": 5,
      "very_high_risk_duration": 2,
      "fraction_of_time_high_risk": 0.833,
      "first_high_risk_timestamp": "T+30min",
      "first_critical_timestamp": "T+60min",
      "peak_risk_timestamp": "T+90min",
      "peak_flood_depth_timestamp": "T+90min",
      "number_of_timestamps": 6
    },
    {
      "rank": 2,
      "road_id": "R-303",
      "source": "13617067008",
      "target": "13617067006",
      "road_class": "residential",
      "length_m": 8.02,
      "hotspot_score": 0.7959,
      "hotspot_class": "CRITICAL",
      "peak_flood_depth_m": 0.405,
      "mean_flood_depth_m": 0.177,
      "peak_combined_risk": 0.8534,
      "mean_combined_risk": 0.58,
      "risk_duration": 6,
      "high_risk_duration": 5,
      "very_high_risk_duration": 2,
      "fraction_of_time_high_risk": 0.833,
      "first_high_risk_timestamp": "T+30min",
      "first_critical_timestamp": "T+60min",
      "peak_risk_timestamp": "T+90min",
      "peak_flood_depth_timestamp": "T+90min",
      "number_of_timestamps": 6
    }
  ]
}
```

---

## 3. GET `/api/roads/<road_id>`

Returns complete information for an individual road segment.

### Example Request
```http
GET /api/roads/R-1184
```

### Response `200 OK`
```json
{
  "road_id": "R-1184",
  "source": "3193827827",
  "target": "3193827830",
  "road_class": "residential",
  "length_m": 22.84,
  "static_susceptibility": 0.7327,
  "static_risk_class": "HIGH",
  "component_scores": {
    "elevation": 0.9633,
    "imperviousness": 0.7514,
    "infiltration": 0.2486,
    "flow_accumulation": 0.3542,
    "twi": 0.2789,
    "slope": 0.8692
  },
  "hotspot_rank": 3,
  "hotspot_score": 0.7941,
  "hotspot_class": "CRITICAL",
  "peak_flood_depth_m": 0.475,
  "mean_flood_depth_m": 0.187,
  "peak_combined_risk": 0.8631,
  "peak_risk_timestamp": "T+90min",
  "first_high_risk_timestamp": "T+30min",
  "first_critical_timestamp": "T+60min",
  "risk_duration_timesteps": 6,
  "high_risk_duration_timesteps": 5
}
```

### Error Response `404 Not Found`
```json
{
  "error": "Road not found",
  "road_id": "INVALID-ID",
  "message": "Road segment 'INVALID-ID' does not exist in the C1 road dataset."
}
```

---

## 4. GET `/api/roads/<road_id>/timeseries`

Returns time-series evolution across all 6 forecast time horizons for a road.

### Example Request
```http
GET /api/roads/R-1184/timeseries
```

### Response `200 OK`
```json
{
  "road_id": "R-1184",
  "road_class": "residential",
  "static_susceptibility": 0.7327,
  "hotspot_rank": 3,
  "hotspot_class": "CRITICAL",
  "number_of_timestamps": 6,
  "timeseries": [
    {
      "timestamp": "T+0min",
      "mean_flood_depth_m": 0.0,
      "max_flood_depth_m": 0.0,
      "static_susceptibility": 0.7327,
      "dynamic_flood_factor": 0.0,
      "combined_risk": 0.2931,
      "risk_class": "MODERATE"
    },
    {
      "timestamp": "T+30min",
      "mean_flood_depth_m": 0.147,
      "max_flood_depth_m": 0.147,
      "static_susceptibility": 0.7327,
      "dynamic_flood_factor": 0.294,
      "combined_risk": 0.4695,
      "risk_class": "MODERATE"
    },
    {
      "timestamp": "T+60min",
      "mean_flood_depth_m": 0.369,
      "max_flood_depth_m": 0.369,
      "static_susceptibility": 0.7327,
      "dynamic_flood_factor": 0.738,
      "combined_risk": 0.7359,
      "risk_class": "HIGH"
    },
    {
      "timestamp": "T+90min",
      "mean_flood_depth_m": 0.475,
      "max_flood_depth_m": 0.475,
      "static_susceptibility": 0.7327,
      "dynamic_flood_factor": 0.95,
      "combined_risk": 0.8631,
      "risk_class": "VERY_HIGH"
    },
    {
      "timestamp": "T+120min",
      "mean_flood_depth_m": 0.311,
      "max_flood_depth_m": 0.311,
      "static_susceptibility": 0.7327,
      "dynamic_flood_factor": 0.622,
      "combined_risk": 0.6663,
      "risk_class": "HIGH"
    },
    {
      "timestamp": "T+180min",
      "mean_flood_depth_m": 0.123,
      "max_flood_depth_m": 0.123,
      "static_susceptibility": 0.7327,
      "dynamic_flood_factor": 0.246,
      "combined_risk": 0.4407,
      "risk_class": "MODERATE"
    }
  ]
}
```

---

## 5. GET `/api/roads/geojson`

Returns a standard GeoJSON FeatureCollection containing all 1,513 road segments with dynamic flood risk time-series evolution embedded in `properties`.

---

## 6. GET `/api/roads/hotspots/geojson`

Returns a standard GeoJSON FeatureCollection containing all 1,513 road segments with priority ranks and hotspot classifications embedded in `properties`.
