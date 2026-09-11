"""
Urban Flood Nowcasting - Central FastAPI Application Entrypoint
===============================================================

Backwards-compatible entrypoint forwarding to `backend.app.main:app`.
"""

from backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
