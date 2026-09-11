"""
Backwards Compatibility Shim for backend.api.route.
Canonical router relocated to backend.app.api.route.
"""

from backend.app.api.route import *  # noqa: F401, F403
from backend.app.api.route import router, RouteRequest, FloodSimulationRouteRequest, NavigateRequest
