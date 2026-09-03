"""
Utilities to load, plot, and analyze the drainage network produced by
build_comprehensive_real_drainage.py.

Covers three things you'll want out of this data:
  1. Static plot (matplotlib) - quick sanity check, good for reports/figures.
  2. Interactive map (folium) - zoomable, clickable, good for exploration
     and for sharing with non-technical stakeholders.
  3. Network analysis (networkx) - the actual point of building a graph:
     find capacity bottlenecks, trace flow paths from inlets to outfalls,
     and flag unreachable/orphaned nodes.

Usage:
    python analyze_drainage_network.py
"""

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import networkx as nx
import folium

NODES_PATH = Path("backend/data/drainage/drainage_nodes.geojson")
EDGES_PATH = Path("backend/data/drainage/drainage_edges.geojson")


# ---------------------------------------------------------------------------
# 1. Loading
# ---------------------------------------------------------------------------

def load_network(nodes_path=NODES_PATH, edges_path=EDGES_PATH):
    """Load nodes/edges GeoJSON into GeoDataFrames."""
    nodes_gdf = gpd.read_file(nodes_path)
    edges_gdf = gpd.read_file(edges_path)
    return nodes_gdf, edges_gdf


def build_graph(nodes_gdf, edges_gdf):
    """Build a directed graph (flow direction = from_node -> to_node, which
    is already downhill-oriented by the build script)."""
    G = nx.DiGraph()

    for _, row in nodes_gdf.iterrows():
        G.add_node(
            row["id"],
            type=row["type"],
            elevation_m=row["elevation_m"],
            capacity_m3s=row["capacity_m3s"],
            geometry=row.geometry,
        )

    for _, row in edges_gdf.iterrows():
        G.add_edge(
            row["from_node"],
            row["to_node"],
            id=row["id"],
            length_m=row["length_m"],
            diameter_m=row["diameter_m"],
            slope=row["slope"],
            roughness_n=row["roughness_n"],
            capacity_m3s=row["capacity_m3s"],
            blockage_pct=row.get("blockage_pct", 0.0),
            channel_type=row["channel_type"],
        )

    return G


# ---------------------------------------------------------------------------
# 2a. Static plot (matplotlib)
# ---------------------------------------------------------------------------

def plot_static(nodes_gdf, edges_gdf, color_by="capacity_m3s", save_path=None):
    """Quick static plot. color_by can be 'capacity_m3s' (bottleneck view)
    or 'elevation_m' (topography view) on edges."""
    fig, ax = plt.subplots(figsize=(10, 10))

    norm = mcolors.Normalize(vmin=edges_gdf[color_by].min(), vmax=edges_gdf[color_by].max())
    cmap = plt.get_cmap("RdYlGn" if color_by == "capacity_m3s" else "terrain")

    edges_gdf.plot(
        ax=ax,
        color=[cmap(norm(v)) for v in edges_gdf[color_by]],
        linewidth=1.5,
    )

    type_colors = {"inlet": "blue", "junction": "gray", "outfall": "red"}
    for node_type, color in type_colors.items():
        subset = nodes_gdf[nodes_gdf["type"] == node_type]
        if not subset.empty:
            subset.plot(ax=ax, color=color, markersize=15, label=node_type, zorder=5)

    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label=color_by, shrink=0.7)

    ax.legend(loc="upper right")
    ax.set_title(f"Drainage Network — colored by {color_by}")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved static plot -> {save_path}")
    return fig


# ---------------------------------------------------------------------------
# 2b. Interactive map (folium)
# ---------------------------------------------------------------------------

def plot_interactive(nodes_gdf, edges_gdf, save_path="drainage_map.html"):
    """Interactive, zoomable map with popups showing edge/node properties.
    Best for exploring the network or sharing with stakeholders."""
    center = [nodes_gdf.geometry.y.mean(), nodes_gdf.geometry.x.mean()]
    m = folium.Map(location=center, zoom_start=15, tiles="cartodbpositron")

    # color edges by how close they are to capacity limits (low capacity = red)
    max_cap = edges_gdf["capacity_m3s"].max() or 1.0
    for _, row in edges_gdf.iterrows():
        coords = [(lat, lon) for lon, lat in row.geometry.coords]
        frac = row["capacity_m3s"] / max_cap if max_cap else 0
        color = mcolors.to_hex(plt.get_cmap("RdYlGn")(frac))
        folium.PolyLine(
            coords,
            color=color,
            weight=3,
            opacity=0.8,
            popup=(
                f"<b>{row['id']}</b> ({row['channel_type']})<br>"
                f"Capacity: {row['capacity_m3s']} m³/s<br>"
                f"Diameter: {row['diameter_m']} m | Slope: {row['slope']}<br>"
                f"Length: {row['length_m']} m"
            ),
        ).add_to(m)

    type_colors = {"inlet": "blue", "junction": "gray", "outfall": "red"}
    for _, row in nodes_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4,
            color=type_colors.get(row["type"], "black"),
            fill=True,
            fill_opacity=0.9,
            popup=(
                f"<b>{row['id']}</b> ({row['type']})<br>"
                f"Elevation: {row['elevation_m']} m<br>"
                f"Capacity: {row['capacity_m3s']} m³/s"
            ),
        ).add_to(m)

    m.save(save_path)
    print(f"Saved interactive map -> {save_path}")
    return m


# ---------------------------------------------------------------------------
# 3. Network analysis
# ---------------------------------------------------------------------------

def find_bottlenecks(G, percentile=10):
    """Return edges whose capacity is in the bottom N-percentile — these are
    the segments most likely to surcharge/flood first under heavy rainfall."""
    caps = [d["capacity_m3s"] for _, _, d in G.edges(data=True)]
    if not caps:
        return []
    threshold = sorted(caps)[max(0, int(len(caps) * percentile / 100) - 1)]
    bottlenecks = [
        (u, v, d) for u, v, d in G.edges(data=True) if d["capacity_m3s"] <= threshold
    ]
    bottlenecks.sort(key=lambda e: e[2]["capacity_m3s"])
    return bottlenecks


def trace_flow_paths(G):
    """For each inlet, trace the downhill path to whichever outfall it
    reaches (if any). Returns a dict: inlet_id -> [path of node ids] or None
    if it never reaches an outfall (a sign of a dead-end / data gap)."""
    inlets = [n for n, d in G.nodes(data=True) if d["type"] == "inlet"]
    outfalls = set(n for n, d in G.nodes(data=True) if d["type"] == "outfall")

    paths = {}
    for inlet in inlets:
        reached = None
        for outfall in outfalls:
            if nx.has_path(G, inlet, outfall):
                reached = nx.shortest_path(G, inlet, outfall, weight="length_m")
                break
        paths[inlet] = reached
    return paths


def report_unreachable_inlets(paths):
    dead_ends = [inlet for inlet, path in paths.items() if path is None]
    print(f" - {len(dead_ends)} of {len(paths)} inlets never reach an outfall.")
    if dead_ends:
        print(f"   Examples: {dead_ends[:10]}")
    return dead_ends


def summarize_network(G):
    print("=== Network Summary ===")
    print(f" - Nodes: {G.number_of_nodes()}")
    print(f" - Edges: {G.number_of_edges()}")
    n_components = nx.number_weakly_connected_components(G)
    print(f" - Weakly connected components: {n_components}")

    caps = [d["capacity_m3s"] for _, _, d in G.edges(data=True)]
    if caps:
        print(f" - Capacity range: {min(caps):.3f} - {max(caps):.3f} m³/s "
              f"(median {sorted(caps)[len(caps)//2]:.3f})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    nodes_gdf, edges_gdf = load_network()
    G = build_graph(nodes_gdf, edges_gdf)

    summarize_network(G)

    bottlenecks = find_bottlenecks(G, percentile=10)
    print(f"\n=== Bottleneck edges (bottom 10% capacity) ===")
    for u, v, d in bottlenecks[:10]:
        print(f"   {d['id']} ({d['channel_type']}): {d['capacity_m3s']} m³/s, "
              f"dia={d['diameter_m']}m, slope={d['slope']}")

    paths = trace_flow_paths(G)
    print(f"\n=== Flow path tracing ===")
    report_unreachable_inlets(paths)

    plot_static(nodes_gdf, edges_gdf, color_by="capacity_m3s",
                save_path="drainage_capacity_map.png")
    plot_interactive(nodes_gdf, edges_gdf, save_path="drainage_map.html")


if __name__ == "__main__":
    main()