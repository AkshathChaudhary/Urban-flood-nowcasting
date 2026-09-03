"""
C1.10 — Road Data Engineer: Road Flood Risk Flask API Blueprint
Urban Flood Nowcast Project

This module exposes the C1 road network flood risk, time-series, hotspot rankings,
and GeoJSON layers through RESTful Flask API endpoints for frontend consumption.

Endpoints:
- GET /api/roads/summary
- GET /api/roads/hotspots (with optional ?limit=N)
- GET /api/roads/<road_id>
- GET /api/roads/<road_id>/timeseries
- GET /api/roads/geojson
- GET /api/roads/hotspots/geojson
"""

import os
import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from flask import Blueprint, jsonify, request, Response

# Define Blueprint
road_risk_bp = Blueprint("road_risk", __name__, url_prefix="/api/roads")

# Base directory paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
ROADS_DATA_DIR = PROJECT_ROOT / "backend" / "data" / "roads"

DYNAMIC_RISK_CSV = ROADS_DATA_DIR / "road_dynamic_risk.csv"
DYNAMIC_RISK_GEOJSON = ROADS_DATA_DIR / "road_dynamic_risk.geojson"
HOTSPOTS_CSV = ROADS_DATA_DIR / "road_hotspots.csv"
HOTSPOTS_GEOJSON = ROADS_DATA_DIR / "road_hotspots.geojson"
TOP_HOTSPOTS_JSON = ROADS_DATA_DIR / "top_road_hotspots.json"
GRAPH_WITH_RISK_JSON = ROADS_DATA_DIR / "road_graph_with_risk.json"
FLOOD_FEATURES_CSV = ROADS_DATA_DIR / "road_flood_features.csv"
SUSCEPTIBILITY_CSV = ROADS_DATA_DIR / "road_flood_susceptibility.csv"


class RoadDataManager:
    """
    In-memory singleton cache to serve road risk datasets with zero disk I/O latency.
    """
    _instance: Optional["RoadDataManager"] = None

    def __init__(self):
        self._loaded: bool = False
        self.hotspots_list: List[Dict[str, Any]] = []
        self.hotspots_by_id: Dict[str, Dict[str, Any]] = {}
        self.timeseries_by_id: Dict[str, List[Dict[str, Any]]] = {}
        self.road_details_by_id: Dict[str, Dict[str, Any]] = {}
        self.dynamic_geojson_cache: Optional[Dict[str, Any]] = None
        self.hotspots_geojson_cache: Optional[Dict[str, Any]] = None
        self.summary_cache: Optional[Dict[str, Any]] = None
        self.load_all()

    @classmethod
    def get_instance(cls) -> "RoadDataManager":
        if cls._instance is None:
            cls._instance = RoadDataManager()
        return cls._instance

    def load_all(self):
        """Loads and indexes all road risk datasets in memory."""
        if self._loaded:
            return

        # 1. Load Hotspots
        if HOTSPOTS_CSV.exists():
            with open(HOTSPOTS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    entry = {
                        "rank": int(r["rank"]),
                        "road_id": r["road_id"],
                        "source": r["source"],
                        "target": r["target"],
                        "length_m": float(r["length_m"]),
                        "road_class": r["road_class"],
                        "hotspot_score": float(r["hotspot_score"]) if r["hotspot_score"] != "" else None,
                        "hotspot_class": r["hotspot_class"],
                        "peak_flood_depth_m": float(r["peak_flood_depth_m"]) if r["peak_flood_depth_m"] != "" else None,
                        "mean_flood_depth_m": float(r["mean_flood_depth_m"]) if r["mean_flood_depth_m"] != "" else None,
                        "peak_combined_risk": float(r["peak_combined_risk"]) if r["peak_combined_risk"] != "" else None,
                        "mean_combined_risk": float(r["mean_combined_risk"]) if r["mean_combined_risk"] != "" else None,
                        "risk_duration": int(r["risk_duration"]),
                        "high_risk_duration": int(r["high_risk_duration"]),
                        "very_high_risk_duration": int(r["very_high_risk_duration"]),
                        "fraction_of_time_high_risk": float(r["fraction_of_time_high_risk"]) if r["fraction_of_time_high_risk"] != "" else None,
                        "first_high_risk_timestamp": r["first_high_risk_timestamp"] if r["first_high_risk_timestamp"] != "" else None,
                        "first_critical_timestamp": r["first_critical_timestamp"] if r["first_critical_timestamp"] != "" else None,
                        "peak_risk_timestamp": r["peak_risk_timestamp"] if r["peak_risk_timestamp"] != "" else None,
                        "peak_flood_depth_timestamp": r["peak_flood_depth_timestamp"] if r["peak_flood_depth_timestamp"] != "" else None,
                        "number_of_timestamps": int(r["number_of_timestamps"]),
                    }
                    self.hotspots_list.append(entry)
                    self.hotspots_by_id[r["road_id"]] = entry

        # 2. Load Time Series
        if DYNAMIC_RISK_CSV.exists():
            with open(DYNAMIC_RISK_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    r_id = r["road_id"]
                    if r_id not in self.timeseries_by_id:
                        self.timeseries_by_id[r_id] = []
                    self.timeseries_by_id[r_id].append({
                        "timestamp": r["timestamp"],
                        "mean_flood_depth_m": float(r["mean_flood_depth_m"]) if r["mean_flood_depth_m"] != "" else None,
                        "max_flood_depth_m": float(r["max_flood_depth_m"]) if r["max_flood_depth_m"] != "" else None,
                        "static_susceptibility": float(r["static_susceptibility"]) if r["static_susceptibility"] != "" else None,
                        "dynamic_flood_factor": float(r["dynamic_flood_factor"]) if r["dynamic_flood_factor"] != "" else None,
                        "combined_risk": float(r["combined_risk"]) if r["combined_risk"] != "" else None,
                        "risk_class": r["risk_class"],
                    })

        # 3. Load Static Susceptibility & Road Attributes
        if SUSCEPTIBILITY_CSV.exists():
            with open(SUSCEPTIBILITY_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    r_id = r["road_id"]
                    hotspot_info = self.hotspots_by_id.get(r_id, {})
                    self.road_details_by_id[r_id] = {
                        "road_id": r_id,
                        "source": r["source"],
                        "target": r["target"],
                        "length_m": float(r["length_m"]),
                        "road_class": r["road_class"],
                        "static_susceptibility": float(r["flood_susceptibility_score"]) if r["flood_susceptibility_score"] != "" else None,
                        "static_risk_class": r["risk_class"],
                        "component_scores": {
                            "elevation": float(r["elevation_score"]) if r["elevation_score"] != "" else None,
                            "imperviousness": float(r["imperviousness_score"]) if r["imperviousness_score"] != "" else None,
                            "infiltration": float(r["infiltration_score"]) if r["infiltration_score"] != "" else None,
                            "flow_accumulation": float(r["flow_accumulation_score"]) if r["flow_accumulation_score"] != "" else None,
                            "twi": float(r["twi_score"]) if r["twi_score"] != "" else None,
                            "slope": float(r["slope_score"]) if r["slope_score"] != "" else None,
                        },
                        "hotspot_rank": hotspot_info.get("rank"),
                        "hotspot_score": hotspot_info.get("hotspot_score"),
                        "hotspot_class": hotspot_info.get("hotspot_class"),
                        "peak_flood_depth_m": hotspot_info.get("peak_flood_depth_m"),
                        "mean_flood_depth_m": hotspot_info.get("mean_flood_depth_m"),
                        "peak_combined_risk": hotspot_info.get("peak_combined_risk"),
                        "peak_risk_timestamp": hotspot_info.get("peak_risk_timestamp"),
                        "first_high_risk_timestamp": hotspot_info.get("first_high_risk_timestamp"),
                        "first_critical_timestamp": hotspot_info.get("first_critical_timestamp"),
                        "risk_duration_timesteps": hotspot_info.get("risk_duration"),
                        "high_risk_duration_timesteps": hotspot_info.get("high_risk_duration"),
                    }

        # 4. Load GeoJSON Cache
        if DYNAMIC_RISK_GEOJSON.exists():
            with open(DYNAMIC_RISK_GEOJSON, "r", encoding="utf-8") as f:
                self.dynamic_geojson_cache = json.load(f)

        if HOTSPOTS_GEOJSON.exists():
            with open(HOTSPOTS_GEOJSON, "r", encoding="utf-8") as f:
                self.hotspots_geojson_cache = json.load(f)

        # 5. Build Summary Statistics Cache
        total_roads = len(self.road_details_by_id)
        mapped_roads = sum(1 for d in self.road_details_by_id.values() if d["static_susceptibility"] is not None)
        unmapped_roads = total_roads - mapped_roads

        critical_hotspots = sum(1 for h in self.hotspots_list if h["hotspot_class"] == "CRITICAL")
        high_hotspots = sum(1 for h in self.hotspots_list if h["hotspot_class"] == "HIGH")
        moderate_hotspots = sum(1 for h in self.hotspots_list if h["hotspot_class"] == "MODERATE")
        low_hotspots = sum(1 for h in self.hotspots_list if h["hotspot_class"] == "LOW")

        sample_ts_list = next(iter(self.timeseries_by_id.values())) if self.timeseries_by_id else []
        timestamps = [item["timestamp"] for item in sample_ts_list]

        peak_depths = [h["peak_flood_depth_m"] for h in self.hotspots_list if h["peak_flood_depth_m"] is not None]
        scores = [h["hotspot_score"] for h in self.hotspots_list if h["hotspot_score"] is not None]

        self.summary_cache = {
            "study_area": "Mumbai 2x2km",
            "crs": "EPSG:4326",
            "total_roads": total_roads,
            "mapped_roads": mapped_roads,
            "unmapped_roads": unmapped_roads,
            "critical_hotspots": critical_hotspots,
            "high_hotspots": high_hotspots,
            "moderate_hotspots": moderate_hotspots,
            "low_hotspots": low_hotspots,
            "timestamps": timestamps,
            "number_of_timestamps": len(timestamps),
            "max_flood_depth_m": max(peak_depths) if peak_depths else 0.0,
            "mean_hotspot_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "hotspot_class_breakdown": {
                "CRITICAL": critical_hotspots,
                "HIGH": high_hotspots,
                "MODERATE": moderate_hotspots,
                "LOW": low_hotspots,
                "UNKNOWN": unmapped_roads,
            }
        }

        self._loaded = True


# -------------------------------------------------------------------------
# API ROUTES
# -------------------------------------------------------------------------

@road_risk_bp.route("/summary", methods=["GET"])
def get_roads_summary():
    """
    GET /api/roads/summary
    Returns aggregated metrics and counts for the road network.
    """
    manager = RoadDataManager.get_instance()
    return jsonify(manager.summary_cache)


@road_risk_bp.route("/hotspots", methods=["GET"])
def get_road_hotspots():
    """
    GET /api/roads/hotspots?limit=10
    Returns ranked road hotspots list with optional limit parameter.
    """
    manager = RoadDataManager.get_instance()

    limit_param = request.args.get("limit")
    if limit_param is not None:
        try:
            limit = int(limit_param)
            if limit <= 0:
                return jsonify({"error": "Limit must be a positive integer"}), 400
        except ValueError:
            return jsonify({"error": "Invalid limit parameter; must be an integer"}), 400
    else:
        limit = None

    # Filter only mapped hotspots for top ranking
    mapped_hotspots = [h for h in manager.hotspots_list if h["hotspot_score"] is not None]

    if limit is not None:
        results = mapped_hotspots[:limit]
    else:
        results = mapped_hotspots

    response_payload = {
        "total_ranked_hotspots": len(mapped_hotspots),
        "limit": limit if limit is not None else len(mapped_hotspots),
        "hotspots": results,
    }
    return jsonify(response_payload)


@road_risk_bp.route("/<string:road_id>", methods=["GET"])
def get_road_details(road_id: str):
    """
    GET /api/roads/<road_id>
    Returns comprehensive static, dynamic, and hotspot metrics for an individual road.
    """
    manager = RoadDataManager.get_instance()
    road_id_upper = road_id.strip()

    if road_id_upper in manager.road_details_by_id:
        return jsonify(manager.road_details_by_id[road_id_upper])

    # Check case-insensitive fallback
    for k, v in manager.road_details_by_id.items():
        if k.lower() == road_id_upper.lower():
            return jsonify(v)

    return jsonify({
        "error": "Road not found",
        "road_id": road_id,
        "message": f"Road segment '{road_id}' does not exist in the C1 road dataset."
    }), 404


@road_risk_bp.route("/<string:road_id>/timeseries", methods=["GET"])
def get_road_timeseries(road_id: str):
    """
    GET /api/roads/<road_id>/timeseries
    Returns dynamic risk time-series evolution across all forecast horizons for a road.
    """
    manager = RoadDataManager.get_instance()
    road_id_upper = road_id.strip()

    target_id = None
    if road_id_upper in manager.timeseries_by_id:
        target_id = road_id_upper
    else:
        for k in manager.timeseries_by_id.keys():
            if k.lower() == road_id_upper.lower():
                target_id = k
                break

    if target_id is None:
        return jsonify({
            "error": "Road not found",
            "road_id": road_id,
            "message": f"Time series for road segment '{road_id}' does not exist."
        }), 404

    ts_data = manager.timeseries_by_id[target_id]
    road_info = manager.road_details_by_id.get(target_id, {})

    return jsonify({
        "road_id": target_id,
        "road_class": road_info.get("road_class"),
        "static_susceptibility": road_info.get("static_susceptibility"),
        "hotspot_rank": road_info.get("hotspot_rank"),
        "hotspot_class": road_info.get("hotspot_class"),
        "number_of_timestamps": len(ts_data),
        "timeseries": ts_data,
    })


@road_risk_bp.route("/geojson", methods=["GET"])
def get_roads_geojson():
    """
    GET /api/roads/geojson
    Returns map-ready GeoJSON of the road network with dynamic flood risk properties.
    """
    manager = RoadDataManager.get_instance()
    if manager.dynamic_geojson_cache is not None:
        return jsonify(manager.dynamic_geojson_cache)
    return jsonify({"error": "Dynamic risk GeoJSON not loaded"}), 500


@road_risk_bp.route("/hotspots/geojson", methods=["GET"])
def get_hotspots_geojson():
    """
    GET /api/roads/hotspots/geojson
    Returns map-ready GeoJSON of the road network with hotspot priority rankings.
    """
    manager = RoadDataManager.get_instance()
    if manager.hotspots_geojson_cache is not None:
        return jsonify(manager.hotspots_geojson_cache)
    return jsonify({"error": "Hotspots GeoJSON not loaded"}), 500
