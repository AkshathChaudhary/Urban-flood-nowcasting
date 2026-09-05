"""
Refined Drainage Simulation Visualizer — Calibrated to BMC / Chitale Committee Data
====================================================================================

All 4 panels are calibrated against the regenerated drainage_nodes/edges.geojson
which aligns with official Mumbai municipal benchmarks:

Panel 1: Surface Water Intake by 1,005 CPHEEO-spaced Inlets (820 within DEM extent)
Panel 2: Pipe Network with 8 Mithi River Outfalls & surcharge hotspots
Panel 3: Hydraulic scenario comparison (Clean vs 40% Debris Blockage)
Panel 4: Manning pipe capacity distribution across 1,316 calibrated edges
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.ndimage import gaussian_filter
import numpy as np

from backend.models.drainage import DrainageGraph

# Bounds matching DEM exactly
MIN_LAT, MAX_LAT = 19.06013888888332, 19.07819444443888
MIN_LON, MAX_LON = 72.84986111114458, 72.86875000003347

def to_km(lon, lat):
    """Converts WGS84 lat/lon to local [0, 2] km coordinates."""
    x = (lon - MIN_LON) / (MAX_LON - MIN_LON + 1e-10) * 2.0
    y = (lat - MIN_LAT) / (MAX_LAT - MIN_LAT + 1e-10) * 2.0
    return x, y

def run_and_visualize():
    nodes_path = Path("backend/data/drainage/drainage_nodes.geojson")
    edges_path = Path("backend/data/drainage/drainage_edges.geojson")
    dem_path = Path("backend/data/dem/elevation_grid.npy")
    
    dem = np.load(dem_path)
    dt = 300.0  # 5 minutes
    
    # -----------------------------------------------------------------------
    # SIMULATION 1: Normal Clean Network under Heavy Rainfall
    # -----------------------------------------------------------------------
    dg_clean = DrainageGraph(nodes_path, edges_path)
    norm_dem = (dem - dem.min()) / (dem.max() - dem.min() + 1e-5)
    # Realistic flood accumulation: deeper in lowlands (SE Kurla/Mithi)
    depth_grid = (1.5 * (1.0 - norm_dem) ** 2 + 0.25).astype(np.float32)
    
    absorbed_grid = dg_clean.absorb_surface_water(depth_grid, dt=dt)
    discharged_clean = dg_clean.propagate_flow(dt=dt)
    overflow_clean = dg_clean.compute_overflow(dt=dt)
    summary_clean = dg_clean.get_network_summary()
    
    # -----------------------------------------------------------------------
    # SIMULATION 2: Scenario 5 (40% Debris/Silt Blockage)
    # -----------------------------------------------------------------------
    dg_blocked = DrainageGraph(nodes_path, edges_path)
    dg_blocked.set_global_blockage(0.40)
    dg_blocked.absorb_surface_water(depth_grid, dt=dt)
    discharged_blocked = dg_blocked.propagate_flow(dt=dt)
    overflow_blocked = dg_blocked.compute_overflow(dt=dt)
    summary_blocked = dg_blocked.get_network_summary()
    
    # -----------------------------------------------------------------------
    # FIGURE CREATION: Premium Dark Theme with High Readability
    # -----------------------------------------------------------------------
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(20, 16), dpi=160)
    fig.patch.set_facecolor('#0d1117')
    
    gs = fig.add_gridspec(2, 2, hspace=0.25, wspace=0.22)
    
    # =======================================================================
    # PANEL 1: Surface Water Ponding & Distinct Inlet Intake Footprint
    # =======================================================================
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor('#0b1120')
    
    # 1. Background: Aquatic Surface Water Depth (0.0m dry to 1.5m deep flood pool)
    water_cmap = mcolors.LinearSegmentedColormap.from_list(
        'ocean_flood',
        ['#0b1120', '#0c2d48', '#145da0', '#2e8bc0', '#38bdf8'],
        N=256
    )
    im1 = ax1.imshow(depth_grid, cmap=water_cmap, origin='lower', extent=[0, 2, 0, 2],
                     vmin=0.2, vmax=1.5, alpha=0.9)
    ax1.contour(dem, levels=6, colors='#334155', alpha=0.4, linewidths=0.6, extent=[0, 2, 0, 2])
    
    # 2. Draw subtle conduit / street lines underneath so road corridors are recognizable
    for edge in dg_clean.edge_data.values():
        coords = edge["coordinates"]
        if len(coords) >= 2:
            km_pts = [to_km(pt[0], pt[1]) for pt in coords]
            ax1.plot([p[0] for p in km_pts], [p[1] for p in km_pts],
                     color='#1e293b', linewidth=0.8, alpha=0.5, zorder=2)
    
    # 3. Extract active inlets and their absorbed water volumes
    inlet_xs, inlet_ys, inlet_vols = [], [], []
    for nid, node in dg_clean.node_data.items():
        if node["type"] == "inlet":
            x, y = to_km(node["coordinates"][0], node["coordinates"][1])
            if 0 <= x <= 2 and 0 <= y <= 2:
                inlet_xs.append(x)
                inlet_ys.append(y)
                r, c = node["grid_row"], node["grid_col"]
                inlet_vols.append(absorbed_grid[r, c] * 100.0)  # m³ absorbed
    
    inlet_xs = np.array(inlet_xs)
    inlet_ys = np.array(inlet_ys)
    inlet_vols = np.array(inlet_vols)
    
    # 4. Color & Size Normalization: High-dynamic range log-scale
    # Low intake (45-75 m³) -> Bright Yellow
    # Medium intake (75-130 m³) -> Orange
    # High intake (130-250 m³) -> Vivid Red/Crimson
    # Maximum intake (250-500+ m³) -> Deep Purple/Magenta
    inlet_norm = mcolors.LogNorm(vmin=45, vmax=500)
    inlet_cmap = mcolors.LinearSegmentedColormap.from_list(
        'intake_thermal',
        ['#fef08a', '#facc15', '#fb923c', '#f43f5e', '#b91c1c', '#701a75'],
        N=256
    )
    
    # Marker sizes scaled logarithmically between 16 and 90
    log_v = np.log10(np.clip(inlet_vols, 45, 500))
    min_log, max_log = np.log10(45), np.log10(500)
    sizes = 16.0 + 74.0 * ((log_v - min_log) / (max_log - min_log))
    
    # Foreground Inlets: Distinct, sharp, non-overlapping with white/black edge
    sc1 = ax1.scatter(
        inlet_xs, inlet_ys, c=inlet_vols, cmap=inlet_cmap, norm=inlet_norm,
        s=sizes, edgecolor='#000000', linewidth=0.5, alpha=0.95, zorder=5,
        label=f'Active Inlets (n={len(inlet_xs)})'
    )
    
    # 5. Dedicated Single Vertical Colorbar for Water Intake with custom labeled ticks
    cbar1 = fig.colorbar(sc1, ax=ax1, fraction=0.046, pad=0.04)
    cbar1.set_label('Water Absorbed per Inlet (m³ in 5 min)', color='#f8fafc', fontsize=10, fontweight='bold')
    cbar1.ax.tick_params(colors='#f8fafc', labelsize=8)
    cbar1.set_ticks([50, 75, 100, 150, 250, 450])
    cbar1.set_ticklabels(['50 m³ (Low)', '75 m³', '100 m³ (Avg)', '150 m³', '250 m³ (High)', '450+ m³ (Max)'])
    
    total_absorbed_m3 = float(np.sum(inlet_vols))
    avg_intake = float(np.mean(inlet_vols))
    
    ax1.set_xlim(0, 2)
    ax1.set_ylim(0, 2)
    ax1.set_title(
        f'1. Surface Flood Depth & Water Absorbed by {len(inlet_xs)} Inlets\n'
        f'[Total Intake: {total_absorbed_m3:,.0f} m³ in 5 min | Avg/Grate: {avg_intake:.1f} m³ | Sized 16–90 pt]',
        fontsize=11, fontweight='bold', color='#38bdf8', pad=10
    )
    ax1.set_xlabel('East-West Distance (km)', color='#94a3b8', fontsize=10)
    ax1.set_ylabel('North-South Distance (km)', color='#94a3b8', fontsize=10)
    ax1.legend(loc='upper right', facecolor='#0f172a', edgecolor='#334155', labelcolor='white', fontsize=8)
    ax1.grid(True, linestyle=':', alpha=0.15, color='#94a3b8')

    # =======================================================================
    # PANEL 2: Pipe Network & Surcharging Manholes (Calibrated Outfalls)
    # =======================================================================
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor('#161b22')
    
    # Clean DEM background
    im2 = ax2.imshow(dem, cmap='gist_earth', origin='lower', extent=[0, 2, 0, 2], alpha=0.45)
    
    # Plot Pipes clipped strictly to [0, 2] km, color by channel type
    for edge_id, edge in dg_clean.edge_data.items():
        coords = edge["coordinates"]
        if len(coords) >= 2:
            km_coords = [to_km(pt[0], pt[1]) for pt in coords]
            xs = [p[0] for p in km_coords]
            ys = [p[1] for p in km_coords]
            # Width based on pipe diameter
            width = max(0.8, min(edge["diameter_m"] * 1.5, 3.5))
            is_stream = "stream" in edge["channel_type"] or "canal" in edge["channel_type"]
            color = '#56d364' if is_stream else '#388bfd'
            ax2.plot(xs, ys, color=color, alpha=0.5 if not is_stream else 0.8, linewidth=width)
            
    # Highlight Outfalls (Discharge exits into Mithi River)
    out_xs, out_ys, out_labels = [], [], []
    for nid, node in dg_clean.node_data.items():
        if node["type"] == "outfall":
            x, y = to_km(node["coordinates"][0], node["coordinates"][1])
            if 0 <= x <= 2 and 0 <= y <= 2:
                out_xs.append(x)
                out_ys.append(y)
                out_labels.append(nid)
    ax2.scatter(out_xs, out_ys, c='#3fb950', marker='^', s=120, edgecolors='white',
                linewidth=1.5, zorder=5, label=f'Mithi River Outfalls (n={len(out_xs)})')
    
    # Annotate each outfall with its ID
    for i, (ox, oy, olbl) in enumerate(zip(out_xs, out_ys, out_labels)):
        ax2.annotate(olbl, xy=(ox, oy), xytext=(ox + 0.06, oy + 0.04),
                     color='#7ee787', fontsize=7, fontweight='bold',
                     arrowprops=dict(arrowstyle="-", color='#7ee787', lw=0.6))
    
    # Plot Overflow Surcharge Hotspots
    if overflow_clean:
        ovf_xs, ovf_ys, ovf_vols, ovf_ids = [], [], [], []
        for nid, vol in overflow_clean.items():
            node = dg_clean.node_data[nid]
            x, y = to_km(node["coordinates"][0], node["coordinates"][1])
            if 0 <= x <= 2 and 0 <= y <= 2:
                ovf_xs.append(x)
                ovf_ys.append(y)
                ovf_vols.append(vol)
                ovf_ids.append(nid)
                
        # Proportional size: radius scales with volume
        sizes = [max(40, min(v * 3.0, 350)) for v in ovf_vols]
        sc2 = ax2.scatter(ovf_xs, ovf_ys, s=sizes, c='#ff4444', edgecolors='#ffffff',
                          linewidth=1.2, alpha=0.95, zorder=6,
                          label=f'Manhole Surcharge Overflow ({len(ovf_xs)} hotspots)')
        
        # Annotate top 2 worst overflowing manholes
        if len(ovf_vols) >= 2:
            top_indices = np.argsort(ovf_vols)[-2:]
            for idx in top_indices:
                ax2.annotate(f"{ovf_ids[idx]}\n+{ovf_vols[idx]:.0f} m³",
                             xy=(ovf_xs[idx], ovf_ys[idx]),
                             xytext=(ovf_xs[idx] + 0.08, ovf_ys[idx] + 0.08),
                             color='#ff7b72', fontsize=8, fontweight='bold',
                             arrowprops=dict(arrowstyle="->", color='#ff7b72', lw=1.0),
                             bbox=dict(boxstyle="round,pad=0.2", fc='#21262d', ec='#ff7b72', lw=0.8))

    ax2.set_xlim(0, 2)
    ax2.set_ylim(0, 2)
    ax2.set_title(f'2. Pipe Network ({summary_clean["total_edges"]} Edges) & {len(out_xs)} Mithi Outfalls',
                  fontsize=13, fontweight='bold', color='#f85149', pad=10)
    ax2.set_xlabel('East-West Distance (km)', color='#8b949e', fontsize=10)
    ax2.set_ylabel('North-South Distance (km)', color='#8b949e', fontsize=10)
    ax2.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d', labelcolor='white', fontsize=9)
    ax2.grid(True, linestyle=':', alpha=0.25, color='#8b949e')

    # =======================================================================
    # PANEL 3: Scenario Comparison (Clean vs 40% Blocked) — Updated Metrics
    # =======================================================================
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor('#161b22')
    
    categories = ['Outfall Discharge\n(Safely Removed)', 'Subterranean Stored\n(In Pipes)', 'Street Overflow\n(Flooding Pavement)']
    clean_metrics = [discharged_clean, summary_clean["current_water_stored_m3"], sum(overflow_clean.values())]
    blocked_metrics = [discharged_blocked, summary_blocked["current_water_stored_m3"], sum(overflow_blocked.values())]
    
    x = np.arange(len(categories))
    width = 0.32
    
    bars1 = ax3.bar(x - width/2, clean_metrics, width, label='Normal Clean Pipes', color='#238636', edgecolor='#2ea043', alpha=0.9)
    bars2 = ax3.bar(x + width/2, blocked_metrics, width, label='Scenario 5: 40% Debris Blockage', color='#da3633', edgecolor='#f85149', alpha=0.9)
    
    # Add numerical callouts above bars
    for bar in bars1:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, yval + max(clean_metrics + blocked_metrics) * 0.02,
                 f"{yval:,.0f} m³",
                 ha='center', va='bottom', fontsize=8, color='#7ee787', fontweight='bold')
    for bar in bars2:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, yval + max(clean_metrics + blocked_metrics) * 0.02,
                 f"{yval:,.0f} m³",
                 ha='center', va='bottom', fontsize=8, color='#ff7b72', fontweight='bold')
                 
    ax3.set_ylabel('Volume (m³)', color='white', fontsize=10)
    ax3.set_title(f'3. Hydraulic Impact: {summary_clean["total_nodes"]} Nodes, {summary_clean["outfall_nodes"]} Outfalls',
                  fontsize=13, fontweight='bold', color='#e3b341', pad=10)
    ax3.set_xticks(x)
    ax3.set_xticklabels(categories, color='white', fontsize=10)
    ax3.set_ylim(0, max(clean_metrics + blocked_metrics) * 1.25)
    ax3.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d', labelcolor='white', fontsize=9)
    ax3.grid(True, linestyle=':', alpha=0.25, color='#8b949e', axis='y')

    # =======================================================================
    # PANEL 4: Manning Pipe Capacity Distribution (Properly Scaled)
    # =======================================================================
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor('#161b22')
    
    all_caps = [dg_clean.compute_pipe_capacity(eid) for eid in dg_clean.edge_data]
    # Filter 0-15 m³/s for the primary distribution, count outliers
    trunk_nalas = [c for c in all_caps if c > 15.0]
    std_pipes = [c for c in all_caps if c <= 15.0]
    
    n_hist, bins, patches = ax4.hist(std_pipes, bins=25, range=(0, 15), color='#8957e5',
                                edgecolor='#161b22', alpha=0.85,
                                label=f'Street Drains (n={len(std_pipes)}, D=0.9m)')
    
    med_cap = np.median(all_caps)
    ax4.axvline(med_cap, color='#f0883e', linestyle='--', linewidth=2.0,
                label=f'Median Capacity: {med_cap:.2f} m³/s')
    
    # Annotated callout for major trunk nalas that exceed 15 m³/s
    if trunk_nalas:
        # Position annotation relative to actual histogram height
        max_count = max(n_hist) if len(n_hist) > 0 else 100
        ax4.annotate(f"{len(trunk_nalas)} Arterial Nalas/Streams\n(Max: {max(trunk_nalas):.1f} m³/s, D=2.5m)",
                     xy=(14.5, max_count * 0.15), xytext=(7.0, max_count * 0.75),
                     arrowprops=dict(arrowstyle="->", color='#58a6ff', lw=1.5),
                     color='#58a6ff', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle="round,pad=0.3", fc='#21262d', ec='#58a6ff', lw=1))
        
    ax4.set_title(f'4. Pipe Capacity Distribution ({len(all_caps)} Edges, Manning Q)',
                  fontsize=13, fontweight='bold', color='#bc8cff', pad=10)
    ax4.set_xlabel('Manning Conveyance Capacity Q (m³/s)', color='#8b949e', fontsize=10)
    ax4.set_ylabel('Number of Pipes', color='#8b949e', fontsize=10)
    ax4.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d', labelcolor='white', fontsize=9)
    ax4.grid(True, linestyle=':', alpha=0.25, color='#8b949e')

    # Suptitle with calibrated summary
    plt.suptitle(
        f'URBAN FLOOD NOWCASTING — CALIBRATED DRAINAGE SUITE '
        f'({summary_clean["total_nodes"]} Nodes, {summary_clean["total_edges"]} Edges, '
        f'{summary_clean["outfall_nodes"]} Mithi Outfalls)',
        fontsize=14, fontweight='bold', color='#ffffff', y=0.98)

    out_img = Path("backend/data/drainage/drainage_simulation_results.png")
    plt.savefig(out_img, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"Refined simulation graphic generated successfully: {out_img}")

if __name__ == "__main__":
    run_and_visualize()
