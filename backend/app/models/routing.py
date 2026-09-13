"""
Dynamic Flood-Resilient Routing Engine (Pair C - Task C2.1 to C2.6)
===================================================================

Provides A* flood-aware shortest path routing that dynamically avoids submerged streets,
penalizes waterlogged corridors based on vehicle-specific clearance depths, and generates
safe alternative routes.

Thread-Safe & Zero-Copy Architecture:
- Uses NetworkX subgraph views (nx.subgraph_view) rather than deep-copying graphs.
- Edge penalty states are evaluated per-query to prevent multi-user race conditions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import networkx as nx
import numpy as np

from backend.app.services.traffic import traffic_service

# Vehicle clearance limits in meters (IRC / Emergency Management Standards)
VEHICLE_THRESHOLDS: Dict[str, float] = {
    "pedestrian": 0.12,  # Ankle-to-shin depth (fast flowing water > 12cm sweeps pedestrians)
    "bike": 0.18,        # Bottom bracket / pedal axle clearance (18cm)
    "motorcycle": 0.20,  # Exhaust pipe and air intake (~20cm)
    "car": 0.30,         # Standard sedan exhaust/chassis clearance (30cm)
    "suv": 0.45,         # High ground clearance SUV (45cm)
    "ambulance": 0.45,   # Critical emergency life-support van (45cm)
    "rescue": 0.60,      # Heavy rescue truck / military unimog (60cm)
    "truck": 0.60,       # Heavy goods vehicle (60cm)
}

# Mode-specific nominal base speeds (km/h)
MODE_NOMINAL_SPEEDS_KMH: Dict[str, float] = {
    "pedestrian": 5.0,   # ~1.39 m/s brisk walking
    "bike": 16.0,        # ~4.44 m/s cycling speed
    "motorcycle": 35.0,  # ~9.72 m/s city two-wheeler
    "car": 35.0,
    "ambulance": 45.0,
    "rescue": 30.0,
    "truck": 30.0,
    "suv": 40.0,
}

# Flood Risk Depth Thresholds
PONDING_FREE_FLOW_DEPTH_M: float = 0.05
PONDING_SEVERE_DELAY_DEPTH_M: float = 0.15
MODERATE_DELAY_MULTIPLIER: float = 2.0
SEVERE_DELAY_MULTIPLIER: float = 5.0
AMBULANCE_PRIORITY_FACTOR: float = 0.85

# Maximum network speed in m/s for A* admissible heuristic (80 km/h ~ 22.22 m/s)
MAX_NETWORK_SPEED_MPS: float = 80.0 / 3.6


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Computes great-circle distance between two coordinates in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class RoutingEngine:
    """
    Graph routing engine backed by NetworkX DiGraph, integrating DEM elevation
    and 2D hydrodynamic flood depth grids to route emergency and civilian vehicles.
    """

    def __init__(
        self,
        geojson_path: Optional[Union[str, Path]] = None,
        graph_path: Optional[Union[str, Path]] = None,
    ):
        base_dir = Path(__file__).resolve().parents[2]
        self.geojson_path = Path(geojson_path) if geojson_path else base_dir / "backend" / "data" / "roads" / "road_network.geojson"
        self.graph_path = Path(graph_path) if graph_path else base_dir / "backend" / "data" / "roads" / "road_graph.json"
        
        self.graph = nx.DiGraph()
        self.node_positions: Dict[str, Tuple[float, float]] = {}  # nid -> (lon, lat)
        self.node_coords_list: List[Tuple[float, float]] = []
        self.node_id_list: List[str] = []
        self.node_coords_array: Optional[np.ndarray] = None
        self.edge_attributes: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.roads_by_id: Dict[str, Dict[str, Any]] = {}
        
        self.load_roads()

    def load_roads(self) -> None:
        """
        Builds the NetworkX DiGraph from serialized graph JSON or GeoJSON.
        Initializes spatial indexing array for nearest-node snap.
        """
        if self.graph_path.exists():
            with open(self.graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            nodes_data = graph_data["nodes"]
            if isinstance(nodes_data, dict):
                nodes_items = nodes_data.items()
            else:
                nodes_items = [(item["id"], item) for item in nodes_data]

            for nid, attrs in nodes_items:
                self.graph.add_node(
                    nid,
                    coordinates=attrs["coordinates"],
                    elevation_m=attrs.get("elevation_m", 5.0),
                    grid_row=attrs.get("grid_row", 0),
                    grid_col=attrs.get("grid_col", 0),
                )
                lon, lat = attrs["coordinates"][0], attrs["coordinates"][1]
                self.node_positions[nid] = (lon, lat)
                self.node_coords_list.append((lon, lat))
                self.node_id_list.append(nid)

            for edge in graph_data["edges"]:
                u, v = edge["u"], edge["v"]
                speed_mps = max(1.0, edge.get("maxspeed_kmh", 30) / 3.6)
                length_m = edge.get("length_m", 10.0)
                base_travel_time_s = length_m / speed_mps

                edge_dict = {
                    "id": edge["id"],
                    "name": edge.get("name", "Unnamed Road"),
                    "highway_type": edge.get("highway_type", "residential"),
                    "length_m": length_m,
                    "maxspeed_kmh": edge.get("maxspeed_kmh", 30),
                    "lanes": edge.get("lanes", 2),
                    "width_m": edge.get("width_m", 6.0),
                    "midpoint_grid_row": edge.get("midpoint_grid_row", 0),
                    "midpoint_grid_col": edge.get("midpoint_grid_col", 0),
                    "elevation_m": edge.get("elevation_m", 5.0),
                    "coordinates": edge.get("coordinates", []),
                    "base_weight": base_travel_time_s,
                    "weight": base_travel_time_s,
                    "flood_depth_m": 0.0,
                    "status": "PASSABLE",
                }
                self.graph.add_edge(u, v, **edge_dict)
                self.edge_attributes[(u, v)] = edge_dict
                self.roads_by_id[edge["id"]] = edge_dict

        elif self.geojson_path.exists():
            with open(self.geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            for feat in geojson_data.get("features", []):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [])
                if len(coords) < 2:
                    continue

                u = props.get("start_node")
                v = props.get("end_node")
                if not u or not v:
                    continue

                if u not in self.node_positions:
                    self.node_positions[u] = (coords[0][0], coords[0][1])
                    self.node_coords_list.append((coords[0][0], coords[0][1]))
                    self.node_id_list.append(u)
                    self.graph.add_node(u, coordinates=coords[0])

                if v not in self.node_positions:
                    self.node_positions[v] = (coords[-1][0], coords[-1][1])
                    self.node_coords_list.append((coords[-1][0], coords[-1][1]))
                    self.node_id_list.append(v)
                    self.graph.add_node(v, coordinates=coords[-1])

                speed_mps = max(1.0, props.get("maxspeed_kmh", 30) / 3.6)
                length_m = props.get("length_m", 10.0)
                base_time = length_m / speed_mps

                edge_dict = {
                    "id": props.get("id"),
                    "name": props.get("name", "Unnamed Road"),
                    "highway_type": props.get("highway_type", "residential"),
                    "length_m": length_m,
                    "maxspeed_kmh": props.get("maxspeed_kmh", 30),
                    "lanes": props.get("lanes", 2),
                    "width_m": props.get("width_m", 6.0),
                    "midpoint_grid_row": props.get("midpoint_grid_row", 0),
                    "midpoint_grid_col": props.get("midpoint_grid_col", 0),
                    "elevation_m": props.get("elevation_m", 5.0),
                    "coordinates": coords,
                    "base_weight": base_time,
                    "weight": base_time,
                    "flood_depth_m": 0.0,
                    "status": "PASSABLE",
                }
                self.graph.add_edge(u, v, **edge_dict)
                self.edge_attributes[(u, v)] = edge_dict
                self.roads_by_id[props["id"]] = edge_dict

        if self.node_coords_list:
            self.node_coords_array = np.array(self.node_coords_list, dtype=np.float64)

        # Precompute the giant strongly connected component (SCC) to prevent snapping to one-way dead-ends
        sccs = list(nx.strongly_connected_components(self.graph))
        if sccs:
            sccs.sort(key=len, reverse=True)
            self.primary_scc: Set[str] = set(sccs[0])
        else:
            self.primary_scc: Set[str] = set(self.graph.nodes())

    def snap_to_nearest_node(self, lon: float, lat: float, prefer_connected: bool = True) -> str:
        """
        Finds closest node in road network using vectorized Euclidean distance.
        Prioritizes nodes in the primary strongly connected component to avoid unreachable dead-ends/one-ways.
        """
        if self.node_coords_array is None or len(self.node_coords_array) == 0:
            raise RuntimeError("Road graph is empty; cannot snap coordinates.")
        diffs = self.node_coords_array - np.array([lon, lat])
        sq_dists = np.sum(diffs ** 2, axis=1)

        if prefer_connected and hasattr(self, "primary_scc") and self.primary_scc:
            # Check top 35 closest candidate nodes to find one in the primary network
            closest_indices = np.argsort(sq_dists)[:35]
            for idx in closest_indices:
                nid = self.node_id_list[idx]
                if nid in self.primary_scc:
                    return nid

        idx = int(np.argmin(sq_dists))
        return self.node_id_list[idx]

    def evaluate_query_weights(
        self,
        depth_grid: Optional[np.ndarray] = None,
        vehicle_type: str = "car",
        blocked_road_ids: Optional[List[str]] = None,
        traffic_mode: str = "peak_monsoon",
    ) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], float], Dict[Tuple[str, str], str], List[Dict[str, Any]]]:
        """
        Thread-safe, functional weight evaluator. Computes dynamic weights per query without mutating the shared graph.
        Returns:
            (weights_dict, depths_dict, status_dict, blocked_roads_list)
        """
        v_mode = vehicle_type.lower()
        threshold = VEHICLE_THRESHOLDS.get(v_mode, VEHICLE_THRESHOLDS["car"])
        blocked_set = set(blocked_road_ids or [])
        is_ambulance = v_mode == "ambulance"
        is_pedestrian = v_mode == "pedestrian"
        is_bike = v_mode in ["bike", "motorcycle"]
        nom_speed_kmh = MODE_NOMINAL_SPEEDS_KMH.get(v_mode, 35.0)

        weights: Dict[Tuple[str, str], float] = {}
        depths: Dict[Tuple[str, str], float] = {}
        statuses: Dict[Tuple[str, str], str] = {}
        blocked_roads: Dict[str, Dict[str, Any]] = {}

        for (u, v), edge in self.edge_attributes.items():
            depth = 0.0
            if depth_grid is not None:
                r = edge["midpoint_grid_row"]
                c = edge["midpoint_grid_col"]
                if 0 <= r < depth_grid.shape[0] and 0 <= c < depth_grid.shape[1]:
                    depth = float(depth_grid[r, c])

            depth_rounded = round(depth, 3)
            depths[(u, v)] = depth_rounded

            hw_type = edge.get("highway_type", "residential")
            length_m = edge.get("length_m", 10.0)
            road_id = edge["id"]

            # Mode-specific access restrictions:
            # Pedestrians and bikes cannot travel on controlled-access motorways/trunks without footpaths
            if (is_pedestrian or is_bike) and hw_type in ["motorway", "motorway_link"]:
                weights[(u, v)] = float("inf")
                statuses[(u, v)] = "RESTRICTED"
                continue

            # Hydrodynamic flood clearance check
            if road_id in blocked_set or depth >= threshold:
                weights[(u, v)] = float("inf")
                statuses[(u, v)] = "BLOCKED"
                if road_id not in blocked_roads:
                    blocked_roads[road_id] = {
                        "id": road_id,
                        "name": edge["name"],
                        "highway_type": hw_type,
                        "flood_depth_m": depth_rounded,
                    }
                continue

            # Calculate vehicle-calibrated base edge travel time
            # For pedestrian/bike, travel speed is governed by human/cycling physiology rather than highway maxspeed
            if is_pedestrian:
                mode_speed_mps = nom_speed_kmh / 3.6  # ~1.39 m/s
                base_time = length_m / mode_speed_mps
                # Walking through even 5cm of water drastically slows a person down (wading resistance)
                if depth >= 0.05:
                    w = base_time * (2.5 + (depth / threshold) * 3.0)
                    statuses[(u, v)] = "HIGH_RISK"
                else:
                    w = base_time
                    statuses[(u, v)] = "PASSABLE"
            elif is_bike:
                mode_speed_mps = nom_speed_kmh / 3.6  # ~4.44 m/s
                base_time = length_m / mode_speed_mps
                # Cycling through water > 6cm risks slippage and drivetrain resistance
                if depth >= 0.08:
                    w = base_time * (2.2 + (depth / threshold) * 2.5)
                    statuses[(u, v)] = "HIGH_RISK"
                elif depth >= 0.03:
                    w = base_time * 1.5
                    statuses[(u, v)] = "CAUTION"
                else:
                    w = base_time
                    statuses[(u, v)] = "PASSABLE"
            else:
                # Motor vehicles (car, ambulance, rescue, truck)
                base_time = edge["base_weight"]
                if depth >= PONDING_SEVERE_DELAY_DEPTH_M:
                    w = base_time * SEVERE_DELAY_MULTIPLIER
                    statuses[(u, v)] = "HIGH_RISK"
                elif depth >= PONDING_FREE_FLOW_DEPTH_M:
                    w = base_time * MODERATE_DELAY_MULTIPLIER
                    statuses[(u, v)] = "CAUTION"
                else:
                    w = base_time
                    statuses[(u, v)] = "PASSABLE"

                if is_ambulance and hw_type in ["motorway", "trunk", "primary"]:
                    w *= AMBULANCE_PRIORITY_FACTOR

            # Traffic impedance integration (multi-modal: pedestrians unaffected, bikes 35%, vehicles 100%)
            if traffic_mode:
                u_pt = self.node_positions.get(u, (0.0, 0.0))
                v_pt = self.node_positions.get(v, (0.0, 0.0))
                mid_lon = (u_pt[0] + v_pt[0]) / 2.0
                mid_lat = (u_pt[1] + v_pt[1]) / 2.0
                flow = traffic_service.get_flow_for_point(
                    mid_lat, mid_lon, edge.get("maxspeed_kmh", 40.0), traffic_mode=traffic_mode, allow_network=False
                )
                delay_factor = flow.get("delay_factor", 1.0)
                if is_bike:
                    w *= (1.0 + (delay_factor - 1.0) * 0.35)
                elif not is_pedestrian:
                    w *= delay_factor

            weights[(u, v)] = w

        return weights, depths, statuses, list(blocked_roads.values())

    def apply_flood_weights(
        self,
        depth_grid: Optional[np.ndarray] = None,
        vehicle_type: str = "car",
        blocked_road_ids: Optional[List[str]] = None,
        traffic_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Maintains backward compatibility by evaluating weights and updating graph attributes.
        """
        weights, depths, statuses, blocked_roads = self.evaluate_query_weights(
            depth_grid=depth_grid,
            vehicle_type=vehicle_type,
            blocked_road_ids=blocked_road_ids,
            traffic_mode=traffic_mode,
        )
        threshold = VEHICLE_THRESHOLDS.get(vehicle_type.lower(), VEHICLE_THRESHOLDS["car"])
        blocked_count = 0
        penalized_count = 0
        passable_count = 0

        for (u, v), w in weights.items():
            edge = self.edge_attributes[(u, v)]
            edge["weight"] = w
            edge["flood_depth_m"] = depths[(u, v)]
            edge["status"] = statuses[(u, v)]

            if math.isinf(w):
                blocked_count += 1
            elif statuses[(u, v)] in ["HIGH_RISK", "CAUTION"]:
                penalized_count += 1
            else:
                passable_count += 1

            if self.graph.has_edge(u, v):
                self.graph[u][v]["weight"] = w
                self.graph[u][v]["flood_depth_m"] = depths[(u, v)]
                self.graph[u][v]["status"] = statuses[(u, v)]

        return {
            "vehicle_type": vehicle_type,
            "clearance_threshold_m": threshold,
            "blocked_segments": blocked_count,
            "penalized_segments": penalized_count,
            "passable_segments": passable_count,
        }

    def _heuristic(self, u: str, target: str) -> float:
        """Admissible A* heuristic: Geodesic distance divided by max network speed."""
        u_lon, u_lat = self.node_positions[u]
        t_lon, t_lat = self.node_positions[target]
        dist_m = haversine_m(u_lon, u_lat, t_lon, t_lat)
        return dist_m / MAX_NETWORK_SPEED_MPS

    def find_route(
        self,
        src: Tuple[float, float],
        dst: Tuple[float, float],
        vehicle_type: str = "car",
        depth_grid: Optional[np.ndarray] = None,
        avoid_edges: Optional[List[Tuple[str, str]]] = None,
        blocked_road_ids: Optional[List[str]] = None,
        traffic_mode: str = "peak_monsoon",
    ) -> Dict[str, Any]:
        """
        Zero-copy, thread-safe shortest path computation using NetworkX subgraph views.
        """
        # Prefetch live TomTom telemetry for corridor coordinates between src and dst
        if traffic_mode == "live" and traffic_service.is_api_key_configured():
            corridor_pts = []
            steps = 4
            for s in range(steps + 1):
                frac = s / float(steps)
                c_lon = src[0] + frac * (dst[0] - src[0])
                c_lat = src[1] + frac * (dst[1] - src[1])
                corridor_pts.append((c_lat, c_lon))
            traffic_service.prefetch_flow_for_points(corridor_pts, max_points=5)

        # 1. Compute dynamic weights for this specific query
        weights, depths, statuses, blocked_roads = self.evaluate_query_weights(
            depth_grid=depth_grid,
            vehicle_type=vehicle_type,
            blocked_road_ids=blocked_road_ids,
            traffic_mode=traffic_mode,
        )

        # 2. Snap coordinates
        src_node = self.snap_to_nearest_node(src[0], src[1])
        dst_node = self.snap_to_nearest_node(dst[0], dst[1])

        # Handle identical source and destination
        if src_node == dst_node:
            return {
                "route_found": True,
                "src_node": src_node,
                "dst_node": dst_node,
                "distance_m": 0.0,
                "travel_time_s": 0.0,
                "travel_time_min": 0.0,
                "max_flood_depth_m": 0.0,
                "avg_flood_depth_m": 0.0,
                "flood_risk": "SAFE",
                "segment_count": 0,
                "roads_traversed": [],
                "roads_avoided": blocked_roads,
                "traffic_mode": traffic_mode,
                "geojson": {
                    "type": "Feature",
                    "properties": {"status": "Already at destination", "traffic_mode": traffic_mode},
                    "geometry": {"type": "LineString", "coordinates": [[src[0], src[1]], [dst[0], dst[1]]]},
                },
            }

        # 3. Create Zero-Copy Subgraph View filtering impassable edges
        avoid_set = set(avoid_edges or [])

        def filter_edge(u: str, v: str) -> bool:
            if (u, v) in avoid_set:
                return False
            w = weights.get((u, v), float("inf"))
            return not math.isinf(w)

        subgraph_view = nx.subgraph_view(self.graph, filter_edge=filter_edge)

        def weight_func(u: str, v: str, edge_data: Dict[str, Any]) -> float:
            return weights.get((u, v), edge_data.get("base_weight", 10.0))

        path_nodes = None
        is_compromised = False
        try:
            path_nodes = nx.astar_path(
                subgraph_view,
                source=src_node,
                target=dst_node,
                heuristic=self._heuristic,
                weight=weight_func,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        # 3b. SAFEST CONTINGENCY ROUTE FALLBACK:
        # If all strictly passable corridors are submerged above vehicle wading depth,
        # find the route that MINIMIZES cumulative water depth and flood risk rather than failing.
        if path_nodes is None:
            v_thresh = VEHICLE_THRESHOLDS.get(vehicle_type.lower(), 0.30)
            blocked_set = set(blocked_road_ids or [])

            def fallback_weight(u: str, v: str, edge_data: Dict[str, Any]) -> float:
                if (u, v) in avoid_set:
                    return float("inf")
                edge_id = edge_data.get("id")
                if edge_id in blocked_set:
                    return float("inf")
                base = edge_data.get("base_weight", 10.0)
                d = depths.get((u, v), 0.0)
                if d < v_thresh:
                    return weights.get((u, v), base)
                # Exponential penalty for water depth above threshold: prioritizes the shallowest path
                excess = d - v_thresh
                return base + 1000.0 + (excess * 5000.0) + ((d / max(0.01, v_thresh)) ** 2) * 200.0

            try:
                path_nodes = nx.dijkstra_path(
                    self.graph,
                    source=src_node,
                    target=dst_node,
                    weight=fallback_weight,
                )
                is_compromised = True
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                # Fallback to bidirectional graph view if one-way constraints prevent reaching destination
                try:
                    undir = self.graph.to_undirected(as_view=True)
                    path_nodes = nx.dijkstra_path(
                        undir,
                        source=src_node,
                        target=dst_node,
                        weight=fallback_weight,
                    )
                    is_compromised = True
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    return {
                        "route_found": False,
                        "reason": "All viable corridors are completely disconnected or impassable.",
                        "src_node": src_node,
                        "dst_node": dst_node,
                        "vehicle_type": vehicle_type,
                        "roads_avoided": blocked_roads,
                        "traffic_mode": traffic_mode,
                    }

        # 4. Build response using query-local weight states
        return self._build_route_response(
            path_nodes,
            vehicle_type,
            weights,
            depths,
            statuses,
            blocked_roads,
            traffic_mode=traffic_mode,
            is_compromised=is_compromised,
        )

    def find_alternative_routes(
        self,
        src: Tuple[float, float],
        dst: Tuple[float, float],
        vehicle_type: str = "car",
        depth_grid: Optional[np.ndarray] = None,
        max_alternatives: int = 2,
        traffic_mode: str = "peak_monsoon",
    ) -> List[Dict[str, Any]]:
        """
        Finds primary route plus up to `max_alternatives` distinct safe alternatives.
        """
        routes: List[Dict[str, Any]] = []

        primary = self.find_route(
            src, dst, vehicle_type=vehicle_type, depth_grid=depth_grid, traffic_mode=traffic_mode
        )
        if not primary.get("route_found"):
            return [primary]

        routes.append(primary)
        excluded_edges: List[Tuple[str, str]] = []

        for alt_idx in range(max_alternatives):
            prev_route = routes[-1]
            traversed = prev_route.get("roads_traversed", [])
            if not traversed:
                break

            worst_edge = max(traversed, key=lambda e: (e.get("flood_depth_m", 0.0), e.get("length_m", 0.0)))
            u, v = worst_edge.get("u"), worst_edge.get("v")
            if u and v:
                excluded_edges.append((u, v))

            alt_route = self.find_route(
                src,
                dst,
                vehicle_type=vehicle_type,
                depth_grid=depth_grid,
                avoid_edges=excluded_edges,
                traffic_mode=traffic_mode,
            )

            if alt_route.get("route_found"):
                if alt_route.get("distance_m") != primary.get("distance_m"):
                    routes.append(alt_route)

        return routes

    def _build_route_response(
        self,
        path_nodes: List[str],
        vehicle_type: str,
        weights: Dict[Tuple[str, str], float],
        depths: Dict[Tuple[str, str], float],
        statuses: Dict[Tuple[str, str], str],
        blocked_roads: List[Dict[str, Any]],
        traffic_mode: str = "peak_monsoon",
        is_compromised: bool = False,
    ) -> Dict[str, Any]:
        """Constructs response payload from path nodes and query-local weight evaluation."""
        route_coords: List[List[float]] = []
        traversed_edges: List[Dict[str, Any]] = []
        traffic_segments: List[Dict[str, Any]] = []
        total_dist_m = 0.0
        total_time_s = 0.0
        total_free_flow_time_s = 0.0
        total_traffic_delay_s = 0.0
        flood_depths: List[float] = []

        v_mode = vehicle_type.lower()
        v_thresh = VEHICLE_THRESHOLDS.get(v_mode, 0.30)
        nom_spd = MODE_NOMINAL_SPEEDS_KMH.get(v_mode, 35.0)

        # Prefetch live TomTom telemetry in parallel for traversed route segments (sampled along corridor)
        if traffic_mode == "live" and traffic_service.is_api_key_configured():
            route_midpoints = []
            step = max(1, (len(path_nodes) - 1) // 6)
            for i in range(0, len(path_nodes) - 1, step):
                u_node = path_nodes[i]
                v_node = path_nodes[i + 1]
                u_coord = self.node_positions.get(u_node, (0.0, 0.0))
                v_coord = self.node_positions.get(v_node, (0.0, 0.0))
                route_midpoints.append(((u_coord[1] + v_coord[1]) / 2.0, (u_coord[0] + v_coord[0]) / 2.0))
            traffic_service.prefetch_flow_for_points(route_midpoints, max_points=6)

        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            edge_data = self.edge_attributes.get((u, v), self.graph[u][v] if self.graph.has_edge(u, v) else self.graph[v][u])

            w = weights.get((u, v), edge_data.get("base_weight", 10.0))
            d = depths.get((u, v), 0.0)
            st = statuses.get((u, v), "PASSABLE")
            length_m = edge_data.get("length_m", 10.0)

            total_dist_m += length_m
            flood_depths.append(d)

            coords = edge_data.get("coordinates", [])
            if coords:
                if not route_coords:
                    route_coords.extend(coords)
                else:
                    route_coords.extend(coords[1:])

            u_pt = self.node_positions.get(u, (0.0, 0.0))
            v_pt = self.node_positions.get(v, (0.0, 0.0))
            mid_lon = (u_pt[0] + v_pt[0]) / 2.0
            mid_lat = (u_pt[1] + v_pt[1]) / 2.0
            maxspd = edge_data.get("maxspeed_kmh", 40.0)

            flow = traffic_service.get_flow_for_point(mid_lat, mid_lon, maxspd, traffic_mode=traffic_mode, allow_network=False)
            curr_spd = flow["current_speed_kmh"]
            free_spd = flow["free_flow_speed_kmh"]
            c_level = flow["congestion_level"]
            delay_factor = flow.get("delay_factor", 1.0)

            if v_mode == "pedestrian":
                edge_free_time = length_m / (nom_spd / 3.6)
                ped_traffic_factor = 1.05 if c_level == "HEAVY" else 1.0
                edge_traffic_time = edge_free_time * ped_traffic_factor
                edge_traffic_delay = max(0.0, edge_traffic_time - edge_free_time)
                if math.isinf(w):
                    total_time_s += edge_traffic_time * (3.0 + (d / max(0.01, v_thresh)) * 3.0)
                else:
                    total_time_s += w * ped_traffic_factor
            elif v_mode in ["bike", "motorcycle"]:
                edge_free_time = length_m / (nom_spd / 3.6)
                bike_traffic_factor = 1.0 + (delay_factor - 1.0) * 0.35
                edge_traffic_time = edge_free_time * bike_traffic_factor
                edge_traffic_delay = max(0.0, edge_traffic_time - edge_free_time)
                if math.isinf(w):
                    total_time_s += edge_traffic_time * (3.0 + (d / max(0.01, v_thresh)) * 3.0)
                else:
                    total_time_s += w * bike_traffic_factor
            else:
                edge_free_time = length_m / max(2.0, (free_spd / 3.6))
                edge_traffic_time = length_m / max(1.5, (curr_spd / 3.6))
                edge_traffic_delay = max(0.0, edge_traffic_time - edge_free_time)
                if math.isinf(w):
                    total_time_s += edge_traffic_time * (4.0 + (d / max(0.01, v_thresh)) * 4.0)
                else:
                    total_time_s += w * delay_factor

            total_free_flow_time_s += edge_free_time
            total_traffic_delay_s += edge_traffic_delay

            traversed_edges.append({
                "u": u,
                "v": v,
                "id": edge_data.get("id"),
                "name": edge_data.get("name"),
                "highway_type": edge_data.get("highway_type"),
                "length_m": length_m,
                "maxspeed_kmh": maxspd,
                "current_speed_kmh": curr_spd,
                "free_flow_speed_kmh": free_spd,
                "congestion_level": c_level,
                "traffic_delay_s": round(edge_traffic_delay, 1),
                "flood_depth_m": d,
                "status": st if not math.isinf(w) else "SUBMERGED_CAUTION",
            })

            if coords:
                traffic_segments.append({
                    "coordinates": coords,
                    "congestion_level": c_level,
                    "current_speed_kmh": curr_spd,
                    "is_flood_affected": d >= PONDING_FREE_FLOW_DEPTH_M,
                })

        max_depth = max(flood_depths) if flood_depths else 0.0
        avg_depth = sum(flood_depths) / len(flood_depths) if flood_depths else 0.0

        compromised_state = is_compromised or (max_depth >= v_thresh)

        if max_depth >= v_thresh:
            risk_level = "CRITICAL"
        elif max_depth >= PONDING_SEVERE_DELAY_DEPTH_M:
            risk_level = "ELEVATED"
        elif max_depth >= PONDING_FREE_FLOW_DEPTH_M:
            risk_level = "MODERATE"
        else:
            risk_level = "SAFE"

        overall_traffic = (
            "HEAVY_CONGESTION" if total_traffic_delay_s > 300
            else "MODERATE_DELAY" if total_traffic_delay_s > 90
            else "OPTIMAL"
        )

        advisory = None
        if compromised_state:
            advisory = (
                f"CAUTION: Water depth ({int(max_depth * 100)} cm) on sections of this corridor exceeds "
                f"nominal {vehicle_type} wading threshold ({int(v_thresh * 100)} cm). "
                f"Showing safest contingency path minimizing flood exposure. Drive with extreme caution."
            )

        return {
            "route_found": not compromised_state,
            "is_compromised": compromised_state,
            "advisory": advisory,
            "vehicle_type": vehicle_type,
            "distance_m": round(total_dist_m, 1),
            "travel_time_s": round(total_time_s, 1),
            "travel_time_min": round(total_time_s / 60.0, 1),
            "free_flow_travel_time_min": round(total_free_flow_time_s / 60.0, 1),
            "traffic_delay_min": round(total_traffic_delay_s / 60.0, 1),
            "traffic_status": overall_traffic,
            "max_flood_depth_m": round(max_depth, 3),
            "avg_flood_depth_m": round(avg_depth, 3),
            "flood_risk": risk_level,
            "segment_count": len(traversed_edges),
            "roads_traversed": traversed_edges,
            "roads_avoided": blocked_roads,
            "traffic_segments": traffic_segments,
            "traffic_mode": traffic_mode,
            "geojson": {
                "type": "Feature",
                "properties": {
                    "distance_m": round(total_dist_m, 1),
                    "travel_time_min": round(total_time_s / 60.0, 1),
                    "free_flow_travel_time_min": round(total_free_flow_time_s / 60.0, 1),
                    "traffic_delay_min": round(total_traffic_delay_s / 60.0, 1),
                    "traffic_status": overall_traffic,
                    "max_flood_depth_m": round(max_depth, 3),
                    "flood_risk": risk_level,
                    "vehicle_type": vehicle_type,
                    "traffic_mode": traffic_mode,
                    "is_compromised": compromised_state,
                    "advisory": advisory,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": route_coords,
                },
            },
        }

    def get_road_details(self, road_id: str, depth_grid: Optional[np.ndarray] = None) -> Optional[Dict[str, Any]]:
        """Returns physical attributes, current flood depth, and vehicle passability for a road segment."""
        if road_id not in self.roads_by_id:
            return None

        road = dict(self.roads_by_id[road_id])
        depth = 0.0
        if depth_grid is not None:
            r = road.get("midpoint_grid_row", 0)
            c = road.get("midpoint_grid_col", 0)
            if 0 <= r < depth_grid.shape[0] and 0 <= c < depth_grid.shape[1]:
                depth = float(depth_grid[r, c])

        passability = {
            vtype: depth < thresh
            for vtype, thresh in VEHICLE_THRESHOLDS.items()
        }

        road["current_flood_depth_m"] = round(depth, 3)
        road["passability"] = passability
        road["risk_category"] = "CRITICAL" if depth >= 0.30 else ("HIGH" if depth >= PONDING_SEVERE_DELAY_DEPTH_M else "NORMAL")
        return road

    def get_network_summary(self) -> Dict[str, Any]:
        """Aggregated summary of graph nodes, edges, road classifications, and total length."""
        type_counts: Dict[str, int] = {}
        total_len_m = 0.0
        for edge in self.edge_attributes.values():
            ht = edge.get("highway_type", "other")
            type_counts[ht] = type_counts.get(ht, 0) + 1
            total_len_m += edge.get("length_m", 0.0)

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_directed_edges": self.graph.number_of_edges(),
            "total_unique_road_segments": len(self.roads_by_id),
            "total_length_km": round(total_len_m / 1000.0, 2),
            "highway_type_breakdown": type_counts,
            "vehicle_clearance_specs_m": VEHICLE_THRESHOLDS,
        }

    def classify_corridors(self, depth_grid: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Classifies all road corridors based on flood passability thresholds (architecture.md):
        - CLEAR: depth < 10 cm (< 0.10 m)
        - CAUTION: 10 cm <= depth < 30 cm (0.10 - 0.30 m)
        - IMPASSABLE: depth >= 30 cm (>= 0.30 m)

        Returns summary counts and GeoJSON features with dynamic status.
        """
        clear_count = 0
        caution_count = 0
        impassable_count = 0
        max_d = 0.0

        features = []
        for road_id, edge in self.roads_by_id.items():
            depth = 0.0
            if depth_grid is not None:
                r = edge.get("midpoint_grid_row", 0)
                c = edge.get("midpoint_grid_col", 0)
                if 0 <= r < depth_grid.shape[0] and 0 <= c < depth_grid.shape[1]:
                    depth = float(depth_grid[r, c])

            if depth > max_d:
                max_d = depth

            if depth >= 0.30:
                status = "IMPASSABLE"
                impassable_count += 1
            elif depth >= 0.10:
                status = "CAUTION"
                caution_count += 1
            else:
                status = "CLEAR"
                clear_count += 1

            coords = edge.get("coordinates", [])
            features.append({
                "type": "Feature",
                "properties": {
                    "id": road_id,
                    "name": edge.get("name", "Unnamed Road"),
                    "highway_type": edge.get("highway_type", "residential"),
                    "length_m": edge.get("length_m", 0.0),
                    "flood_depth_m": round(depth, 3),
                    "status": status,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
            })

        return {
            "summary": {
                "total_corridors": len(self.roads_by_id),
                "clear_count": clear_count,
                "caution_count": caution_count,
                "impassable_count": impassable_count,
                "max_flood_depth_m": round(max_d, 3),
            },
            "geojson": {
                "type": "FeatureCollection",
                "features": features,
            },
        }
