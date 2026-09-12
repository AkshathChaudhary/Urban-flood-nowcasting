"""
Main Unified FastAPI Application Entrypoint
===========================================

Orchestrates all three subsystem layers:
- Pair A: Subterranean Drainage Network (/api/drainage)
- Pair B: Overland 2D Flood Hydrodynamics & Radar Nowcasting (/api/flood-forecast, /api/rainfall, /api/simulate, /ws/flood-updates)
- Pair C: Road Graph & Resilient Evacuation Routing (/api/roads, /api/route)
"""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env file from project root or backend folder
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from backend.app.api.flood import router as flood_router
from backend.app.api.rainfall import router as rainfall_router
from backend.app.api.simulate import router as simulate_router
from backend.app.api.drainage import router as drainage_router
from backend.app.api.roads import router as roads_router
from backend.app.api.route import router as route_router
from backend.app.api.websocket import router as websocket_router

from backend.app.config import (
    CELL_SIZE_M,
    GRID_COLS,
    GRID_ROWS,
    ORIGIN_LAT,
    ORIGIN_LON,
)
from backend.app.engine_state import get_current_scenario, get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm coupled FloodEngine + DrainageGraph on startup
    print("[STARTUP] Pre-warming coupled FloodEngine and DrainageGraph with Mumbai terrain...")
    try:
        get_engine()
        print("[STARTUP] Simulation engines ready to serve API requests.")
    except Exception as e:
        print(f"[STARTUP] Warning during pre-warm: {e}")
    yield
    print("[SHUTDOWN] Cleaning up simulation resources.")


app = FastAPI(
    title="Urban Flood Nowcasting API",
    description="High-resolution coupled 2D hydrodynamic overland flood simulation, subterranean drainage, and resilient routing engine.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard (Next.js / Vite / React)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount All Subsystem Routers
app.include_router(flood_router)
app.include_router(simulate_router)
app.include_router(rainfall_router)
app.include_router(drainage_router)
app.include_router(roads_router)
app.include_router(route_router)
app.include_router(websocket_router)


@app.get("/", tags=["system"])
def root():
    return {
        "service": "Urban Flood Nowcasting API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "status": "online",
        "active_scenario": get_current_scenario(),
        "active_subsystems": {
            "pair_a_drainage": "mounted",
            "pair_b_flood_model": "mounted",
            "pair_c_roads_and_routing": "mounted",
            "realtime_websocket": "mounted",
        },
        "domain": {
            "rows": GRID_ROWS,
            "cols": GRID_COLS,
            "cell_size_m": CELL_SIZE_M,
            "origin_lat": ORIGIN_LAT,
            "origin_lon": ORIGIN_LON,
        },
    }


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
