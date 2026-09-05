import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def generate_visualizations(output_paths: list[str]):
    # 1. Load DEM, Imperviousness, Infiltration
    dem = np.load("backend/data/dem/elevation_grid.npy")
    imperv = np.load("backend/data/dem/imperviousness.npy")
    infil = np.load("backend/data/dem/infiltration.npy")
    
    # 2. Load Drainage Nodes and Edges
    with open("backend/data/drainage/drainage_nodes.geojson", "r", encoding="utf-8") as f:
        nodes_data = json.load(f)
        
    with open("backend/data/drainage/drainage_edges.geojson", "r", encoding="utf-8") as f:
        edges_data = json.load(f)

    # Setup 2x2 multi-panel figure
    plt.style.use('dark_background')
    fig, axes = plt.subplots(2, 2, figsize=(16, 14), dpi=150)
    fig.patch.set_facecolor('#0d1117')
    for ax in axes.flat:
        ax.set_facecolor('#161b22')

    # ----------------- PANEL 1: Elevation DEM with Contours -----------------
    ax1 = axes[0, 0]
    im1 = ax1.imshow(dem, cmap='terrain', origin='lower', extent=[0, 2, 0, 2])
    contours = ax1.contour(dem, levels=8, colors='white', alpha=0.35, linewidths=0.8, extent=[0, 2, 0, 2])
    ax1.clabel(contours, inline=True, fontsize=8, fmt='%1.0fm')
    cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
    cbar1.set_label('Elevation (m ASL)', color='white')
    cbar1.ax.tick_params(colors='white')
    ax1.set_title('1. 2D Terrain Elevation Model (2x2 km, 10m Cells)', fontsize=13, fontweight='bold', pad=10, color='#58a6ff')
    ax1.set_xlabel('East-West Distance (km)', color='#8b949e')
    ax1.set_ylabel('North-South Distance (km)', color='#8b949e')
    ax1.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    # ----------------- PANEL 2: Imperviousness & Runoff Risk -----------------
    ax2 = axes[0, 1]
    im2 = ax2.imshow(imperv, cmap='magma', origin='lower', extent=[0, 2, 0, 2])
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.set_label('Runoff Imperviousness (0 = Permeable, 1 = Paved)', color='white')
    cbar2.ax.tick_params(colors='white')
    ax2.set_title('2. Urban Surface Imperviousness Matrix', fontsize=13, fontweight='bold', pad=10, color='#f0883e')
    ax2.set_xlabel('East-West Distance (km)', color='#8b949e')
    ax2.set_ylabel('North-South Distance (km)', color='#8b949e')
    ax2.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    # ----------------- PANEL 3: Drainage Graph Overlay on Terrain -----------------
    ax3 = axes[1, 0]
    # Subtle shaded background
    ax3.imshow(dem, cmap='bone', origin='lower', extent=[0, 200, 0, 200], alpha=0.6)
    
    # Map node IDs to grid coordinates
    node_coords = {}
    node_types = {}
    for feat in nodes_data["features"]:
        p = feat["properties"]
        node_coords[p["id"]] = (p["grid_col"], p["grid_row"])
        node_types[p["id"]] = p["type"]

    # Draw Edges (Pipes)
    for feat in edges_data["features"]:
        p = feat["properties"]
        u, v = p["from_node"], p["to_node"]
        if u in node_coords and v in node_coords:
            x1, y1 = node_coords[u]
            x2, y2 = node_coords[v]
            ax3.plot([x1, x2], [y1, y2], color='#38d430', linewidth=2.0, alpha=0.85, zorder=2)

    # Draw Nodes
    type_colors = {'inlet': '#00d2ff', 'junction': '#ffd166', 'outfall': '#ff4757'}
    type_labels_plotted = set()
    
    for n_id, (gx, gy) in node_coords.items():
        ntype = node_types.get(n_id, 'junction')
        label = ntype.capitalize() if ntype not in type_labels_plotted else None
        if label:
            type_labels_plotted.add(ntype)
        ax3.scatter(gx, gy, c=type_colors.get(ntype, '#ffd166'), s=45, edgecolors='black', linewidth=0.5, zorder=3, label=label)

    ax3.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d')
    ax3.set_title(f'3. Real Drainage Network Graph ({len(nodes_data["features"])} Nodes, {len(edges_data["features"])} Edges)', fontsize=13, fontweight='bold', pad=10, color='#3fb950')
    ax3.set_xlabel('DEM Grid Column (0-199)', color='#8b949e')
    ax3.set_ylabel('DEM Grid Row (0-199)', color='#8b949e')
    ax3.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    # ----------------- PANEL 4: Node Elevation & Hydraulic Distribution -----------------
    ax4 = axes[1, 1]
    elevations = [f["properties"]["elevation_m"] for f in nodes_data["features"]]
    lengths = [f["properties"]["length_m"] for f in edges_data["features"]]
    
    # Dual-axis histogram or elevation profile
    ax4.plot(range(1, len(elevations) + 1), sorted(elevations, reverse=True), color='#58a6ff', marker='o', markersize=4, linewidth=1.5, label='Node Elevation Profile (m)')
    ax4.set_xlabel('Node Index (Sorted Downstream)', color='#8b949e')
    ax4.set_ylabel('Elevation (m ASL)', color='#58a6ff')
    ax4.tick_params(axis='y', labelcolor='#58a6ff')
    ax4.grid(True, linestyle=':', alpha=0.3, color='#8b949e')

    ax4_twin = ax4.twinx()
    ax4_twin.hist(lengths, bins=15, color='#f0883e', alpha=0.45, rwidth=0.85, label='Pipe Length Distribution (m)')
    ax4_twin.set_ylabel('Number of Pipe Segments', color='#f0883e')
    ax4_twin.tick_params(axis='y', labelcolor='#f0883e')

    ax4.set_title('4. Hydraulic Profile & Pipe Lengths', fontsize=13, fontweight='bold', pad=10, color='#d2a8ff')

    plt.suptitle('URBAN FLOOD NOWCASTING — 2x2 KM STUDY AREA DIAGNOSTIC SUITE', fontsize=16, fontweight='heavy', color='#ffffff', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    for out_p in output_paths:
        Path(out_p).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out_p, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
        print(f"Generated visualization: {out_p}")
    plt.close()

if __name__ == "__main__":
    out_files = [
        "backend/data/dem/viz/terrain_and_drainage_overview.png",
        r"C:\Users\Aniket\.gemini\antigravity-ide\brain\197042d9-fb12-44b5-8541-e645216de6b9\terrain_and_drainage_overview.png",
    ]
    generate_visualizations(out_files)
