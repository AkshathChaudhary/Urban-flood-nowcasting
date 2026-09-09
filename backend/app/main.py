"""
Main FastAPI Application Entrypoint.

Orchestrates Pair B Flood Nowcasting endpoints, CORS middleware,
and mounts extension points for Pair A (Drainage) and Pair C (Routing).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.flood import router as flood_router
from backend.app.api.rainfall import router as rainfall_router
from backend.app.api.simulate import router as simulate_router
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
    # Pre-warm FloodEngine singleton and initial forecast on startup
    print("[STARTUP] Pre-warming FloodEngine with default Mumbai terrain...")
    get_engine()
    print("[STARTUP] FloodEngine ready to serve API requests.")
    yield
    print("[SHUTDOWN] Cleaning up simulation resources.")


app = FastAPI(
    title="Urban Flood Nowcasting API",
    description="High-resolution overland hydrodynamic flood simulation and 3-hour nowcast engine.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard (Vite/React typically on port 5173 or 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Pair B API Routers
app.include_router(flood_router)
app.include_router(simulate_router)
app.include_router(rainfall_router)


@app.get("/", tags=["system"])
def root():
    return {
        "service": "Urban Flood Nowcasting API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "status": "online",
        "active_scenario": get_current_scenario(),
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
