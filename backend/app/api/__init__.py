"""API routes package."""
from backend.app.api.flood import router as flood_router
from backend.app.api.simulate import router as simulate_router
from backend.app.api.rainfall import router as rainfall_router
from backend.app.api.drainage import router as drainage_router
from backend.app.api.roads import router as roads_router
from backend.app.api.route import router as route_router
from backend.app.api.websocket import router as websocket_router

__all__ = [
    "flood_router",
    "simulate_router",
    "rainfall_router",
    "drainage_router",
    "roads_router",
    "route_router",
    "websocket_router",
]
