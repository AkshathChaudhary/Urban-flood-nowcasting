"""
Urban Flood Nowcast Project — Flask Backend API Application
Main entry point and API factory for C1 Road Network Flood Risk services.
"""

import sys
from pathlib import Path
from flask import Flask, jsonify, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.road_risk import road_risk_bp


def create_app() -> Flask:
    """Application factory for the Urban Flood Nowcast backend API."""
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # Register Blueprints
    app.register_blueprint(road_risk_bp)

    # Global CORS headers
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    # API Root and Info
    @app.route("/", methods=["GET"])
    @app.route("/api", methods=["GET"])
    def api_info():
        return jsonify({
            "service": "Urban Flood Nowcast Backend API",
            "version": "1.0.0",
            "status": "healthy",
            "study_area": "Mumbai 2x2km",
            "endpoints": {
                "summary": "/api/roads/summary",
                "hotspots": "/api/roads/hotspots",
                "road_detail": "/api/roads/<road_id>",
                "road_timeseries": "/api/roads/<road_id>/timeseries",
                "roads_geojson": "/api/roads/geojson",
                "hotspots_geojson": "/api/roads/hotspots/geojson",
            }
        })

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "healthy",
            "study_area": "Mumbai 2x2km",
            "grid_dimensions": "200x200"
        })

    # Error Handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Not Found",
            "message": "The requested API resource was not found on this server."
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred."
        }), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

