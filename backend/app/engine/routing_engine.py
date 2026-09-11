"""
Routing Engine Module (Pair C)
==============================

Provides RoutingEngine flood-aware A* path planner.
"""

from backend.app.models.routing import (
    RoutingEngine,
    VEHICLE_THRESHOLDS,
    haversine_m,
)

__all__ = ["RoutingEngine", "VEHICLE_THRESHOLDS", "haversine_m"]
