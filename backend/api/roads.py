"""
Backwards Compatibility Shim for backend.api.roads.
Canonical router relocated to backend.app.api.roads.
"""

from backend.app.api.roads import *  # noqa: F401, F403
from backend.app.api.roads import router, get_routing_engine
