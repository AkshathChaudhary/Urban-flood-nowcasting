"""
Drainage Network Simulation Model (Pair A - Urban Flood Nowcasting)
====================================================================

This module implements the physics-based hydraulic simulation model for urban drainage.
It uses a directed graph (NetworkX) representation of the subterranean stormwater pipe
network, applying civil engineering hydraulic equations (Manning's open/closed pipe flow)
to simulate water absorption from the surface, downstream gravity propagation, pipe conveyance
limits, debris blockage, and surface overflow (surcharge).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import networkx as nx
import numpy as np


class DrainageGraph:
    """
    Hydraulic graph simulation model for urban drainage networks.

    Attributes:
        graph (nx.DiGraph): NetworkX directed graph where nodes represent inlets,
            manholes, junctions, and outfalls, and edges represent pipes or open culverts.
        node_data (Dict[str, dict]): Fast lookup dictionary for node attributes.
        edge_data (Dict[str, dict]): Fast lookup dictionary for edge/pipe attributes.
        current_water_m3 (Dict[str, float]): Current volume of water stored at each node (m³).
        cell_size_m (float): DEM grid cell size in meters (default: 10.0m -> 100m² area).
        total_discharged_m3 (float): Cumulative volume of water safely discharged through outfalls (m³).
    """

    def __init__(
        self,
        nodes_path: Union[str, Path],
        edges_path: Union[str, Path],
        cell_size_m: float = 10.0,
    ) -> None:
        """
        Initializes the drainage network graph by loading nodes and edges from GeoJSON.

        Args:
            nodes_path: Filepath to the drainage_nodes.geojson file.
            edges_path: Filepath to the drainage_edges.geojson file.
            cell_size_m: Spatial resolution of each DEM grid cell in meters (10m default).
        """
        self.cell_size_m = float(cell_size_m)
        self.cell_area_m2 = self.cell_size_m * self.cell_size_m

        # Graph and attribute data structures
        self.graph = nx.DiGraph()
        self.node_data: Dict[str, Dict[str, Any]] = {}
        self.edge_data: Dict[str, Dict[str, Any]] = {}

        # Dynamic simulation state
        self.current_water_m3: Dict[str, float] = {}
        self.total_discharged_m3: float = 0.0
        self.elevation_sorted_nodes: List[str] = []

        # Load GeoJSON data into graph
        self._load_from_geojson(Path(nodes_path), Path(edges_path))
        
        # Precompute elevation-sorted node order once (avoids re-sorting on every timestep)
        self.elevation_sorted_nodes = sorted(
            self.graph.nodes(),
            key=lambda nid: self.node_data[nid]["elevation_m"],
            reverse=True,
        )

    def _load_from_geojson(self, nodes_path: Path, edges_path: Path) -> None:
        """
        Parses GeoJSON files and populates the NetworkX DiGraph.

        Args:
            nodes_path: Path to drainage_nodes.geojson
            edges_path: Path to drainage_edges.geojson
        """
        if not nodes_path.exists():
            raise FileNotFoundError(f"Nodes GeoJSON file not found: {nodes_path}")
        if not edges_path.exists():
            raise FileNotFoundError(f"Edges GeoJSON file not found: {edges_path}")

        # 1. Load Nodes
        with open(nodes_path, "r", encoding="utf-8") as f:
            nodes_geojson = json.load(f)

        for feature in nodes_geojson.get("features", []):
            props = feature.get("properties", {})
            node_id = props["id"]
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0])

            node_attr = {
                "id": node_id,
                "type": props.get("type", "junction"),  # 'inlet', 'junction', 'outfall'
                "elevation_m": float(props.get("elevation_m", 0.0)),
                "capacity_m3s": float(props.get("capacity_m3s", 1.0)),
                "grid_row": int(props.get("grid_row", 0)),
                "grid_col": int(props.get("grid_col", 0)),
                "coordinates": coords,
            }

            self.graph.add_node(node_id, **node_attr)
            self.node_data[node_id] = node_attr
            self.current_water_m3[node_id] = 0.0

        # 2. Load Edges
        with open(edges_path, "r", encoding="utf-8") as f:
            edges_geojson = json.load(f)

        for feature in edges_geojson.get("features", []):
            props = feature.get("properties", {})
            edge_id = props["id"]
            u = props["from_node"]
            v = props["to_node"]

            # Ensure endpoints exist in node set
            if u not in self.node_data or v not in self.node_data:
                continue

            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])

            edge_attr = {
                "id": edge_id,
                "from_node": u,
                "to_node": v,
                "length_m": float(props.get("length_m", 10.0)),
                "diameter_m": float(props.get("diameter_m", 1.0)),
                "slope": max(float(props.get("slope", 0.005)), 0.0001),  # minimum gravity slope
                "roughness_n": float(props.get("roughness_n", 0.013)),  # 0.013 concrete, 0.025 nala
                "blockage_pct": float(props.get("blockage_pct", 0.0)),  # 0.0 (clean) to 1.0 (blocked)
                "channel_type": props.get("channel_type", "pipe"),
                "coordinates": coords,
            }

            # Add directed edge: water flows from u -> v
            self.graph.add_edge(u, v, **edge_attr)
            self.edge_data[edge_id] = edge_attr

    def compute_pipe_capacity(self, edge_id: str) -> float:
        """
        Calculates the maximum flow rate capacity Q (m³/s) of a pipe using Manning's equation:

            Q = (1 / n) * A * R^(2/3) * S^(1/2) * (1 - blockage)

        Where:
            n = Manning roughness coefficient (dimensionless, 0.013 concrete, 0.025 earth/nala)
            A = Cross-sectional area of full circular pipe = π * (D / 2)² (m²)
            R = Hydraulic radius for full circular pipe = A / P = (π * D² / 4) / (π * D) = D / 4 (m)
            S = Pipe longitudinal hydraulic slope = max(slope, 0.0001) (m/m)
            blockage = Fractional reduction in conveyance capacity (0.0 to 1.0)

        Args:
            edge_id: Unique identifier of the pipe/edge.

        Returns:
            Effective conveyance capacity in cubic meters per second (m³/s).
        """
        edge = self.edge_data[edge_id]
        d = edge["diameter_m"]
        n = edge["roughness_n"]
        s = edge["slope"]
        blockage = edge.get("blockage_pct", 0.0)

        # Cross-sectional area A (m²)
        area = math.pi * ((d / 2.0) ** 2)

        # Hydraulic radius R (m)
        hydraulic_radius = d / 4.0

        # Theoretical Manning's gravity capacity Q (m³/s)
        q_theoretical = (1.0 / n) * area * (hydraulic_radius ** (2.0 / 3.0)) * math.sqrt(s)

        # Apply blockage reduction: effective capacity
        q_effective = q_theoretical * max(0.0, (1.0 - blockage))
        return float(q_effective)

    def absorb_surface_water(self, depth_grid: np.ndarray, dt: float) -> np.ndarray:
        """
        Absorbs standing surface floodwater into the inlet nodes of the drainage network.

        For each inlet node at cell (row, col):
        1. Identifies standing surface flood depth (meters).
        2. Computes available surface volume: depth * cell_area (m³).
        3. Computes max intake capacity of the inlet: capacity_m3s * dt (m³).
        4. Absorbs min(available_volume, max_intake_volume).
        5. Updates internal node storage and populates absorption_grid.

        Args:
            depth_grid: 2D numpy array (e.g. 200x200) representing surface water depth in meters.
            dt: Simulation timestep in seconds (e.g., 300.0s for 5 minutes).

        Returns:
            absorption_grid: 2D numpy array of same shape containing the water depth (in meters)
                absorbed and removed from each cell during this timestep.
        """
        absorption_grid = np.zeros_like(depth_grid, dtype=np.float32)
        rows, cols = depth_grid.shape

        for node_id, node in self.node_data.items():
            # Only intake surface water through designated inlets
            if node["type"] != "inlet":
                continue

            r, c = node["grid_row"], node["grid_col"]
            if not (0 <= r < rows and 0 <= c < cols):
                continue

            surface_depth_m = float(depth_grid[r, c])
            if surface_depth_m <= 1e-6:
                continue

            available_vol_m3 = surface_depth_m * self.cell_area_m2
            max_intake_vol_m3 = node["capacity_m3s"] * dt

            # Siphon the smaller of available water or inlet conveyance capacity
            absorbed_vol_m3 = min(available_vol_m3, max_intake_vol_m3)
            absorbed_depth_m = absorbed_vol_m3 / self.cell_area_m2

            absorption_grid[r, c] += absorbed_depth_m
            self.current_water_m3[node_id] += absorbed_vol_m3

        return absorption_grid

    def propagate_flow(self, dt: float) -> float:
        """
        Propagates accumulated water downstream through the pipe network for one timestep dt.

        Water moves from upstream nodes to downstream nodes in topological/elevation order.
        At outfalls, water leaves the model domain into creeks/sea.
        At junctions with multiple outgoing pipes, flow is split proportionally to pipe capacity.

        Args:
            dt: Simulation timestep in seconds (e.g. 300.0s).

        Returns:
            volume_discharged_this_step_m3: Total water volume safely discharged through outfalls.
        """
        # Determine processing sequence:
        # In a standard gravity drainage network, traversing from higher elevation to lower elevation
        # ensures upstream nodes transfer water before downstream nodes process it.
        # Uses precomputed sorted order to guarantee O(V + E) per timestep without re-sorting overhead.
        sorted_nodes = self.elevation_sorted_nodes

        volume_discharged_this_step = 0.0

        for node_id in sorted_nodes:
            water_to_move = self.current_water_m3.get(node_id, 0.0)
            if water_to_move <= 1e-6:
                continue

            out_edges = list(self.graph.out_edges(node_id, data=True))

            # Case A: Outfall / Sinks (No downstream pipes)
            if not out_edges or self.node_data[node_id]["type"] == "outfall":
                # Water safely discharges into receiving water body
                volume_discharged_this_step += water_to_move
                self.total_discharged_m3 += water_to_move
                self.current_water_m3[node_id] = 0.0
                continue

            # Case B: Internal Junction or Inlet with downstream pipes
            # Compute total conveyance capacity of all outgoing pipes in this timestep
            outgoing_capacities: List[Tuple[str, str, float]] = []
            total_conveyance_m3 = 0.0

            for u, v, edge_attrs in out_edges:
                edge_id = edge_attrs["id"]
                cap_m3s = self.compute_pipe_capacity(edge_id)
                pipe_max_vol = cap_m3s * dt
                outgoing_capacities.append((v, edge_id, pipe_max_vol))
                total_conveyance_m3 += pipe_max_vol

            if total_conveyance_m3 <= 1e-6:
                # All downstream pipes are 100% blocked or zero-capacity; water stays in node
                continue

            # Distribute water proportionally to pipe capacity
            transferred_total = 0.0
            for downstream_node, edge_id, pipe_max_vol in outgoing_capacities:
                share = pipe_max_vol / total_conveyance_m3
                allocated_water = water_to_move * share
                # Cannot exceed individual pipe carrying capacity
                actual_flow = min(allocated_water, pipe_max_vol)

                self.current_water_m3[downstream_node] = (
                    self.current_water_m3.get(downstream_node, 0.0) + actual_flow
                )
                transferred_total += actual_flow

            # Deduct the transferred volume from current node
            self.current_water_m3[node_id] = max(0.0, self.current_water_m3[node_id] - transferred_total)

        return volume_discharged_this_step

    def compute_overflow(self, dt: float = 300.0) -> Dict[str, float]:
        """
        Detects nodes where water volume exceeds maximum conveyance/retention capacity.
        Excess volume is returned as surcharge overflow to be placed back on the DEM surface.

        Args:
            dt: Simulation timestep in seconds (default: 300.0s).

        Returns:
            overflow: Dictionary mapping {node_id: overflow_volume_m3} for all overflowing nodes.
        """
        overflow: Dict[str, float] = {}

        for node_id, node in self.node_data.items():
            current_vol = self.current_water_m3.get(node_id, 0.0)
            if current_vol <= 1e-6:
                continue

            # Outfalls do not overflow (they discharge water freely)
            if node["type"] == "outfall":
                continue

            # Maximum holding capacity for this node over one timestep
            # Node capacity_m3s represents maximum volume it can sustain without surcharging
            max_holding_capacity_m3 = node["capacity_m3s"] * dt

            if current_vol > max_holding_capacity_m3:
                surcharge_volume = current_vol - max_holding_capacity_m3
                overflow[node_id] = surcharge_volume

                # The surcharged water has escaped to the surface, cap internal water
                self.current_water_m3[node_id] = max_holding_capacity_m3

        return overflow

    def set_blockage(self, edge_id: str, blockage_pct: float) -> None:
        """
        Updates the blockage percentage for a specific pipe/edge.

        Args:
            edge_id: Pipe identifier (e.g., 'DE-001').
            blockage_pct: Blockage ratio between 0.0 (completely clear) and 1.0 (completely blocked).
        """
        if edge_id not in self.edge_data:
            raise KeyError(f"Pipe edge {edge_id} does not exist in the network.")

        clamped = max(0.0, min(1.0, float(blockage_pct)))
        self.edge_data[edge_id]["blockage_pct"] = clamped

        # Update NetworkX edge attribute
        u = self.edge_data[edge_id]["from_node"]
        v = self.edge_data[edge_id]["to_node"]
        self.graph[u][v]["blockage_pct"] = clamped

    def set_global_blockage(self, blockage_pct: float) -> None:
        """
        Applies a uniform blockage percentage across all edges in the network
        (e.g., for Scenario 5: Extreme Rain + 40% Drainage Blockage).

        Args:
            blockage_pct: Blockage ratio between 0.0 and 1.0.
        """
        for edge_id in self.edge_data:
            self.set_blockage(edge_id, blockage_pct)

    def get_node_cell(self, node_id: str) -> Tuple[int, int]:
        """
        Returns the (grid_row, grid_col) DEM coordinate for a given node.

        Args:
            node_id: Node identifier.

        Returns:
            (row, col) grid coordinates on the 200x200 surface grid.
        """
        node = self.node_data[node_id]
        return node["grid_row"], node["grid_col"]

    def get_node(self, node_id: str) -> Dict[str, Any]:
        """
        Returns full attribute dictionary for a node, including dynamic water level.
        """
        if node_id not in self.node_data:
            raise KeyError(f"Node {node_id} not found.")

        data = dict(self.node_data[node_id])
        data["current_water_m3"] = round(self.current_water_m3.get(node_id, 0.0), 3)
        return data

    def get_edge(self, edge_id: str) -> Dict[str, Any]:
        """
        Returns full attribute dictionary for an edge, including dynamic Manning capacity.
        """
        if edge_id not in self.edge_data:
            raise KeyError(f"Edge {edge_id} not found.")

        data = dict(self.edge_data[edge_id])
        data["effective_capacity_m3s"] = round(self.compute_pipe_capacity(edge_id), 3)
        return data

    def get_network_summary(self) -> Dict[str, Any]:
        """
        Returns high-level statistics and operational state of the entire drainage network.
        """
        total_stored_water = sum(self.current_water_m3.values())
        inlets_count = sum(1 for n in self.node_data.values() if n["type"] == "inlet")
        outfalls_count = sum(1 for n in self.node_data.values() if n["type"] == "outfall")
        junctions_count = sum(1 for n in self.node_data.values() if n["type"] == "junction")

        return {
            "total_nodes": len(self.node_data),
            "total_edges": len(self.edge_data),
            "inlet_nodes": inlets_count,
            "outfall_nodes": outfalls_count,
            "junction_nodes": junctions_count,
            "current_water_stored_m3": round(total_stored_water, 2),
            "total_discharged_m3": round(self.total_discharged_m3, 2),
        }

    def reset_state(self) -> None:
        """
        Resets dynamic simulation state (stored water, discharge totals) to zero.
        """
        for node_id in self.current_water_m3:
            self.current_water_m3[node_id] = 0.0
        self.total_discharged_m3 = 0.0
