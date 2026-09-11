"""
FastAPI WebSocket Streaming Router (Task I4)
============================================

Provides live streaming updates via WebSocket:
- Endpoint: /ws/flood-updates
- Streams dynamic simulation progress, 3-hour nowcast timeline progression,
  and KPI metrics without requiring client polling.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.engine_state import compute_summary, get_current_scenario, get_engine

router = APIRouter(tags=["WebSocket Real-Time Streaming"])


class ConnectionManager:
    """Manages active WebSocket connections for live broadcast."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()


@router.websocket("/ws/flood-updates")
async def websocket_flood_updates(websocket: WebSocket):
    """
    WebSocket endpoint streaming live flood nowcast timeline updates.

    Message types emitted:
    - 'initial_state': Current scenario, domain info, and available time horizons.
    - 'horizon_snapshot': KPI metrics and max depths for each horizon.
    - 'ping': Heartbeat keeping connection alive.
    """
    await manager.connect(websocket)
    try:
        engine = get_engine()
        scenario = get_current_scenario()
        horizons = sorted(engine.forecast_grids.keys())

        # 1. Send initial state
        await websocket.send_text(
            json.dumps({
                "type": "initial_state",
                "scenario": scenario,
                "horizons": horizons,
                "domain": {
                    "rows": engine.rows,
                    "cols": engine.cols,
                    "cell_size_m": engine.cell_size,
                },
                "total_rain_volume_m3": round(engine.total_rain_volume_m3, 1),
            })
        )

        # 2. Cycle through forecast horizons with live KPI telemetry
        while True:
            for h in horizons:
                if h in engine.forecast_grids:
                    summary = compute_summary(engine.forecast_grids[h], h)

                    # Dynamic Road Passability Telemetry (Pair C)
                    road_status = None
                    try:
                        from backend.app.api.roads import get_routing_engine
                        routing_eng = get_routing_engine()
                        street_grid = engine.get_street_depth_grid(h) if hasattr(engine, "get_street_depth_grid") else engine.forecast_grids[h]
                        corridor_data = routing_eng.classify_corridors(street_grid)
                        road_status = corridor_data.get("summary")
                    except Exception:
                        pass

                    # Dynamic Subterranean Drainage Telemetry (Pair A)
                    drainage_data = None
                    try:
                        if hasattr(engine, "drainage_graph") and engine.drainage_graph is not None:
                            drainage_data = engine.drainage_graph.get_network_summary()
                    except Exception:
                        pass

                    await websocket.send_text(
                        json.dumps({
                            "type": "horizon_update",
                            "horizon_minutes": h,
                            "scenario": scenario,
                            "summary": summary.model_dump(),
                            "road_passability": road_status,
                            "drainage_telemetry": drainage_data,
                        })
                    )
                # 3-second cadence between timeline horizon frames for dashboard animation
                await asyncio.sleep(3.0)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
