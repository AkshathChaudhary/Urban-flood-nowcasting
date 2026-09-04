"""
Urban Flood Nowcasting - Central FastAPI Application
=====================================================

Aggregates API routers from:
- Pair A: Subterranean Drainage Network (backend/api/drainage.py)
- Pair B: Rainfall Nowcasting & 2D Flood Simulation Engine (to be integrated)
- Pair C: Road Graph & Dynamic Flood-Resilient Routing (to be integrated)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.drainage import router as drainage_router

app = FastAPI(
    title="Urban Flood Nowcast API",
    description="Physics-based urban drainage, flood simulation, and resilient routing backend.",
    version="1.0.0",
)

# Enable CORS for frontend dashboard (Next.js / Vite / React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Pair A Router
app.include_router(drainage_router)


@app.get("/")
def root():
    return {
        "project": "Urban Flood Nowcasting System",
        "status": "online",
        "docs_url": "/docs",
        "active_modules": {
            "pair_a_drainage": "mounted",
            "pair_b_flood_model": "pending_integration",
            "pair_c_routing": "pending_integration",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
