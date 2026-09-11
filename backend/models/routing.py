"""
Backwards Compatibility Shim for backend.models.routing.
Canonical module relocated to backend.app.models.routing.
"""

from backend.app.models.routing import *  # noqa: F401, F403
from backend.app.models.routing import RoutingEngine, VEHICLE_THRESHOLDS
