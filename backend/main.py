"""
Urban Flood Nowcasting - Central FastAPI Application
=====================================================

Aggregates API routers from:
- Pair A: Subterranean Drainage Network (backend/api/drainage.py)
- Pair B: Rainfall Nowcasting & 2D Flood Simulation Engine (to be integrated)
- Pair C: Road Graph & Dynamic Flood-Resilient Routing (backend/api/roads.py, backend/api/route.py)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.drainage import router as drainage_router
from backend.api.roads import router as roads_router
from backend.api.route import router as route_router

app = FastAPI(
    title="Urban Flood Nowcast API",
    description="Physics-based urban drainage, 2D flood simulation, and flood-resilient routing backend.",
    version="1.0.0",
)

# Enable CORS for frontend dashboard (Next.js / Vite / React)
# Uses regex to echo exact requesting origin when credentials are enabled (W3C CORS spec compliant)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(drainage_router)
app.include_router(roads_router)
app.include_router(route_router)


@app.get("/")
def root():
    return {
        "project": "Urban Flood Nowcasting System",
        "status": "online",
        "docs_url": "/docs",
        "active_modules": {
            "pair_a_drainage": "mounted",
            "pair_b_flood_model": "pending_integration",
            "pair_c_roads_and_routing": "mounted",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
