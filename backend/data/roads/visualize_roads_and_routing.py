"""
Road Network & Dynamic Resilient Routing Visualizer (Pair C - Task C1.9)
========================================================================

Generates a multi-panel publication-grade validation plot:
Panel 1: Road Network overlaid on 10m DEM Elevation Grid & Drainage Outfalls
Panel 2: Flood Hotspots & Vulnerable Intersections (z <= 4.0m) with Water Inundation Contours
Panel 3: Flood-Resilient A* Route Evasion (Baseline Dry Path vs Flood Detour vs Safe Alternatives)
Panel 4: Highway Hierarchy Distribution & Vehicle Clearance Limits
"""

import json
import sys
from pathlib import Path

# Ensure root directory is on path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from backend.models.routing import RoutingEngine, VEHICLE_THRESHOLDS

MIN_LAT, MAX_LAT = 19.06013888888332, 19.07819444443888
MIN_LON, MAX_LON = 72.84986111114458, 72.86875000003347


def to_local_km(lon: float, lat: float):
    """Maps WGS84 coordinates to local [0, 2] km space."""
    x = (lon - MIN_LON) / (MAX_LON - MIN_LON + 1e-10) * 2.0
    y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT + 1e-10) * 2.0
    return x, y


def generate_validation_plot(output_path: str = "backend/data/roads/roads_validation_plot.png"):
    dem_file = Path("backend/data/dem/elevation_grid.npy")
    road_geojson_file = Path("backend/data/roads/road_network.geojson")
    road_graph_file = Path("backend/data/roads/road_graph.json")
    hotspots_file = Path("backend/data/roads/flood_hotspots.geojson")
    drainage_nodes_file = Path("backend/data/drainage/drainage_nodes.geojson")

    # Load DEM
    dem = np.load(dem_file) if dem_file.exists() else np.full((200, 200), 5.0)

    # Initialize Engine
    engine = RoutingEngine(road_geojson_file, road_graph_file)

    # Load Hotspots
    hotspots = []
    if hotspots_file.exists():
        with open(hotspots_file, "r", encoding="utf-8") as f:
            hotspots = json.load(f).get("features", [])

    # Load Drainage outfalls
    outfalls = []
    if drainage_nodes_file.exists():
        with open(drainage_nodes_file, "r", encoding="utf-8") as f:
            dn_data = json.load(f)
            outfalls = [
                feat for feat in dn_data.get("features", [])
                if feat.get("properties", {}).get("type") == "outfall"
            ]

    # Style configuration
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 9
    fig, axes = plt.subplots(2, 2, figsize=(16, 14), facecolor="#0e1117")
    fig.subplots_adjust(hspace=0.28, wspace=0.22)

    # -------------------------------------------------------------------------
    # PANEL 1: Road Network Overlaid on DEM Topography
    # -------------------------------------------------------------------------
    ax1 = axes[0, 0]
    ax1.set_facecolor("#161b22")
    im1 = ax1.imshow(
        dem,
        extent=[0, 2, 0, 2],
        origin="lower",
        cmap="terrain",
        alpha=0.65,
        vmin=-2,
        vmax=25,
    )
    cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.03)
    cbar1.set_label("DEM Elevation (m ASL)", color="#c9d1d9")
    cbar1.ax.tick_params(colors="#8b949e")

    # Draw roads colored by hierarchy
    color_map = {
        "motorway": "#ff7b72",
        "trunk": "#ffa657",
        "primary": "#d2a8ff",
        "secondary": "#79c0ff",
        "tertiary": "#56d364",
        "residential": "#8b949e",
        "unclassified": "#6e7681",
    }

    for edge in engine.edge_attributes.values():
        coords = edge.get("coordinates", [])
        if len(coords) < 2:
            continue
        xs, ys = zip(*[to_local_km(pt[0], pt[1]) for pt in coords])
        ht = edge.get("highway_type", "residential")
        col = color_map.get(ht, "#8b949e")
        lw = 2.0 if ht in ["motorway", "trunk", "primary"] else (1.2 if ht == "secondary" else 0.8)
        ax1.plot(xs, ys, color=col, linewidth=lw, alpha=0.85)

    # Overlay Mithi River outfalls
    if outfalls:
        ox = [to_local_km(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])[0] for f in outfalls]
        oy = [to_local_km(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])[1] for f in outfalls]
        ax1.scatter(ox, oy, color="#00f2fe", s=60, edgecolors="white", linewidth=1.2, zorder=5, label=f"Drainage Outfalls ({len(outfalls)})")
        ax1.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9")

    ax1.set_title("1. Road Network Overlaid on 10m DEM & Drainage", color="#f0f6fc", fontsize=11, weight="bold")
    ax1.set_xlabel("E-W Distance (km)", color="#8b949e")
    ax1.set_ylabel("N-S Distance (km)", color="#8b949e")
    ax1.tick_params(colors="#8b949e")

    # -------------------------------------------------------------------------
    # PANEL 2: Flood Hotspots & Low-Elevation Inundation
    # -------------------------------------------------------------------------
    ax2 = axes[0, 1]
    ax2.set_facecolor("#161b22")

    # Simulated flood depth contour based on lowlands
    norm_elev = (dem - dem.min()) / (dem.max() - dem.min() + 1e-5)
    mock_depth = np.clip(0.60 * (1.0 - norm_elev) ** 2.5, 0.0, 0.70)
    im2 = ax2.imshow(
        mock_depth,
        extent=[0, 2, 0, 2],
        origin="lower",
        cmap="Blues",
        alpha=0.85,
        vmin=0.0,
        vmax=0.60,
    )
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.03)
    cbar2.set_label("Simulated Flood Ponding (m)", color="#c9d1d9")
    cbar2.ax.tick_params(colors="#8b949e")

    # Plot road graph background
    for edge in engine.edge_attributes.values():
        coords = edge.get("coordinates", [])
        if len(coords) < 2:
            continue
        xs, ys = zip(*[to_local_km(pt[0], pt[1]) for pt in coords])
        ax2.plot(xs, ys, color="#30363d", linewidth=0.7, alpha=0.6)

    # Plot hotspots
    if hotspots:
        hx = [to_local_km(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])[0] for f in hotspots]
        hy = [to_local_km(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])[1] for f in hotspots]
        crit_mask = [f["properties"].get("severity") == "CRITICAL" for f in hotspots]
        
        hx_crit = [hx[i] for i, m in enumerate(crit_mask) if m]
        hy_crit = [hy[i] for i, m in enumerate(crit_mask) if m]
        hx_high = [hx[i] for i, m in enumerate(crit_mask) if not m]
        hy_high = [hy[i] for i, m in enumerate(crit_mask) if not m]

        ax2.scatter(hx_high, hy_high, color="#e3b341", s=35, alpha=0.9, edgecolors="none", label="High Risk (z <= 4m)")
        ax2.scatter(hx_crit, hy_crit, color="#f85149", s=45, alpha=1.0, edgecolors="white", linewidth=0.8, label="Critical (z < 3m)")
        ax2.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9")

    ax2.set_title(f"2. Flood-Vulnerable Intersections ({len(hotspots)} Hotspots)", color="#f0f6fc", fontsize=11, weight="bold")
    ax2.set_xlabel("E-W Distance (km)", color="#8b949e")
    ax2.set_ylabel("N-S Distance (km)", color="#8b949e")
    ax2.tick_params(colors="#8b949e")

    # -------------------------------------------------------------------------
    # PANEL 3: Dynamic A* Flood Routing Evasion Comparison
    # -------------------------------------------------------------------------
    ax3 = axes[1, 0]
    ax3.set_facecolor("#161b22")

    # Faint road background
    for edge in engine.edge_attributes.values():
        coords = edge.get("coordinates", [])
        if len(coords) < 2:
            continue
        xs, ys = zip(*[to_local_km(pt[0], pt[1]) for pt in coords])
        ax3.plot(xs, ys, color="#21262d", linewidth=0.6, alpha=0.5)

    # Pick representative origin and destination
    node_ids = list(engine.node_positions.keys())
    src = engine.node_positions[node_ids[10]]
    dst = engine.node_positions[node_ids[100]]

    # 1. Baseline dry route
    dry_route = engine.find_route(src, dst, vehicle_type="car")
    if dry_route.get("route_found"):
        d_coords = dry_route["geojson"]["geometry"]["coordinates"]
        dx, dy = zip(*[to_local_km(pt[0], pt[1]) for pt in d_coords])
        ax3.plot(dx, dy, color="#79c0ff", linewidth=3.5, linestyle="--", alpha=0.8, label=f"Baseline Route ({dry_route['travel_time_min']:.1f}m / {dry_route['distance_m']:.0f}m)")

    # 2. Flooded route (with lowland inundation grid)
    flood_alts = engine.find_alternative_routes(src, dst, vehicle_type="car", depth_grid=mock_depth, max_alternatives=2)
    if flood_alts and flood_alts[0].get("route_found"):
        p_coords = flood_alts[0]["geojson"]["geometry"]["coordinates"]
        px, py = zip(*[to_local_km(pt[0], pt[1]) for pt in p_coords])
        ax3.plot(px, py, color="#56d364", linewidth=3.0, label=f"Flood Evasion Safe Route ({flood_alts[0]['travel_time_min']:.1f}m)")

    if len(flood_alts) > 1 and flood_alts[1].get("route_found"):
        a_coords = flood_alts[1]["geojson"]["geometry"]["coordinates"]
        ax, ay = zip(*[to_local_km(pt[0], pt[1]) for pt in a_coords])
        ax3.plot(ax, ay, color="#e3b341", linewidth=2.2, linestyle=":", label=f"Alternative Safe Detour ({flood_alts[1]['travel_time_min']:.1f}m)")

    # Origin and Destination Markers
    sx, sy = to_local_km(src[0], src[1])
    tx, ty = to_local_km(dst[0], dst[1])
    ax3.scatter([sx], [sy], color="#2ea043", s=120, edgecolors="white", linewidth=2.0, zorder=10, label="Origin")
    ax3.scatter([tx], [ty], color="#f85149", s=120, edgecolors="white", linewidth=2.0, zorder=10, label="Destination")

    ax3.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9")
    ax3.set_title("3. Dynamic A* Flood Evasion vs Baseline Routing", color="#f0f6fc", fontsize=11, weight="bold")
    ax3.set_xlabel("E-W Distance (km)", color="#8b949e")
    ax3.set_ylabel("N-S Distance (km)", color="#8b949e")
    ax3.tick_params(colors="#8b949e")

    # -------------------------------------------------------------------------
    # PANEL 4: Highway Classification & Clearance Limits
    # -------------------------------------------------------------------------
    ax4 = axes[1, 1]
    ax4.set_facecolor("#161b22")

    # Bar chart of vehicle wading clearance thresholds
    vtypes = list(VEHICLE_THRESHOLDS.keys())
    thresholds_cm = [VEHICLE_THRESHOLDS[v] * 100 for v in vtypes]
    bar_colors = ["#f85149", "#ffa657", "#e3b341", "#56d364", "#79c0ff"]

    bars = ax4.barh([v.capitalize() for v in vtypes], thresholds_cm, color=bar_colors, edgecolor="#30363d", height=0.55)
    for bar in bars:
        w = bar.get_width()
        ax4.text(w + 1.0, bar.get_y() + bar.get_height() / 2.0, f"{int(w)} cm", va="center", color="#f0f6fc", weight="bold")

    ax4.axvline(30, color="#f85149", linestyle="--", linewidth=1.2, alpha=0.7, label="Standard Car Clearance Limit (30cm)")
    ax4.set_xlim(0, 75)
    ax4.set_title("4. Vehicle Water Wading Clearance Limits (IRC Standards)", color="#f0f6fc", fontsize=11, weight="bold")
    ax4.set_xlabel("Maximum Passable Flood Depth (cm)", color="#8b949e")
    ax4.tick_params(colors="#8b949e")
    ax4.legend(loc="lower right", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9")

    # Save figure
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Validation plot generated and saved to: {out_file}")
    return str(out_file)


if __name__ == "__main__":
    generate_validation_plot()
