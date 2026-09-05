"""
FastAPI Drainage Router (Pair A - Urban Flood Nowcasting)
==========================================================

Exposes REST API endpoints for querying and controlling the subterranean
drainage network simulation, including node/pipe telemetry, capacity metrics,
debris blockage simulation, and overflow monitoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.models.drainage import DrainageGraph

# Initialize APIRouter
router = APIRouter(prefix="/api/drainage", tags=["Drainage Network"])

# Default paths to GeoJSON assets
DEFAULT_NODES_PATH = Path("backend/data/drainage/drainage_nodes.geojson")
DEFAULT_EDGES_PATH = Path("backend/data/drainage/drainage_edges.geojson")

# Singleton instance of the DrainageGraph
_drainage_graph: Optional[DrainageGraph] = None


def get_drainage_graph() -> DrainageGraph:
    """Lazy-initializes or returns the active DrainageGraph instance."""
    global _drainage_graph
    if _drainage_graph is None:
        if not DEFAULT_NODES_PATH.exists() or not DEFAULT_EDGES_PATH.exists():
            raise RuntimeError(
                f"Drainage GeoJSON files not found at {DEFAULT_NODES_PATH} and {DEFAULT_EDGES_PATH}"
            )
        _drainage_graph = DrainageGraph(DEFAULT_NODES_PATH, DEFAULT_EDGES_PATH)
    return _drainage_graph


# ---------------------------------------------------------------------------
# Pydantic Schemas for Request & Response validation
# ---------------------------------------------------------------------------

class BlockageUpdateRequest(BaseModel):
    """Request payload for updating pipe blockage levels."""
    edge_id: Optional[str] = Field(None, description="Specific pipe ID (e.g. 'DE-001'), or null to apply globally.")
    blockage_pct: float = Field(..., ge=0.0, le=1.0, description="Blockage fraction between 0.0 (clear) and 1.0 (blocked).")


class DrainageSummaryResponse(BaseModel):
    total_nodes: int
    total_edges: int
    inlet_nodes: int
    outfall_nodes: int
    junction_nodes: int
    current_water_stored_m3: float
    total_discharged_m3: float


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=DrainageSummaryResponse)
def get_drainage_summary():
    """
    Returns aggregated metrics of the drainage network including total nodes,
    pipes, active water volume in subterranean retention, and outfall discharge.
    """
    graph = get_drainage_graph()
    return graph.get_network_summary()


@router.get("/nodes")
def get_all_nodes(node_type: Optional[str] = Query(None, description="Filter by 'inlet', 'junction', or 'outfall'")):
    """
    Returns all drainage nodes formatted as a GeoJSON FeatureCollection,
    including current water volume and physical properties.
    """
    graph = get_drainage_graph()
    features = []

    for node_id, node in graph.node_data.items():
        if node_type and node["type"] != node_type:
            continue

        water_vol = graph.current_water_m3.get(node_id, 0.0)
        # Surcharge threshold over 300s
        max_cap = node["capacity_m3s"] * 300.0
        stress_ratio = round(water_vol / max_cap, 3) if max_cap > 0 else 0.0

        features.append({
            "type": "Feature",
            "properties": {
                **node,
                "current_water_m3": round(water_vol, 3),
                "stress_ratio": stress_ratio,
                "is_overflowing": water_vol >= max_cap and node["type"] != "outfall",
            },
            "geometry": {
                "type": "Point",
                "coordinates": node["coordinates"],
            },
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/node/{node_id}")
def get_single_node(node_id: str):
    """
    Returns detailed properties and real-time hydraulic state of a single node.
    """
    graph = get_drainage_graph()
    try:
        return graph.get_node(node_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Drainage node '{node_id}' not found.")


@router.get("/edges")
def get_all_edges():
    """
    Returns all drainage pipes formatted as a GeoJSON FeatureCollection,
    including pipe diameter, slope, Manning's roughness, effective capacity, and blockage.
    """
    graph = get_drainage_graph()
    features = []

    for edge_id, edge in graph.edge_data.items():
        eff_cap = graph.compute_pipe_capacity(edge_id)
        features.append({
            "type": "Feature",
            "properties": {
                **edge,
                "effective_capacity_m3s": round(eff_cap, 3),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": edge["coordinates"],
            },
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/edge/{edge_id}")
def get_single_edge(edge_id: str):
    """
    Returns physical parameters and calculated Manning capacity for a single pipe.
    """
    graph = get_drainage_graph()
    try:
        return graph.get_edge(edge_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Drainage edge '{edge_id}' not found.")


@router.post("/blockage")
def update_blockage(payload: BlockageUpdateRequest):
    """
    Updates the blockage percentage for an individual pipe, or across all pipes
    in the network if edge_id is omitted (e.g. for Scenario 5 testing).
    """
    graph = get_drainage_graph()
    if payload.edge_id:
        try:
            graph.set_blockage(payload.edge_id, payload.blockage_pct)
            return {
                "status": "success",
                "message": f"Blockage for edge {payload.edge_id} updated to {payload.blockage_pct * 100:.1f}%.",
                "edge": graph.get_edge(payload.edge_id),
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Edge '{payload.edge_id}' not found.")
    else:
        graph.set_global_blockage(payload.blockage_pct)
        return {
            "status": "success",
            "message": f"Global blockage across all {len(graph.edge_data)} pipes updated to {payload.blockage_pct * 100:.1f}%.",
        }


@router.post("/reset")
def reset_drainage():
    """
    Resets internal water levels, discharged counters, and dynamic state back to initial dry state.
    """
    graph = get_drainage_graph()
    graph.reset_state()
    return {"status": "success", "message": "Drainage network state reset to zero."}
