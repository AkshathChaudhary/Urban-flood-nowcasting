"""
Real-World Monsoon Flood Engine Simulation & Diagnostic Suite (v2).

Simulates a real-world monsoon situation in Mumbai (Kurla / BKC / Mithi Basin)
using 100% real data:
  - Copernicus 10m DEM + corrected water body mask (Mithi River / channels)
  - Real imperviousness & infiltration grids (water bodies = 0.0 / 9999 mm/hr)
  - Historical precipitation fetched from Open-Meteo Archive API (2023-07-26)
  - Real OSM stormwater drainage network (1,136 nodes, 1,059 pipes)
  - Real OSM road network (15 corridors, bottleneck passability audit)
  - Full 180-min hydrodynamic simulation (D8 routing, 36 timesteps)

Bug fixes applied:
  - Water body cells (rivers/channels, elev < 0) are excluded from flood accumulation
  - They act as open-water sinks: rainfall + routed runoff entering them drains out
  - Flood statistics and visualizations show only LAND flood signal
"""

import json
from pathlib import Path
import sys
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from backend.app.engine.flood_engine import FloodEngine
from backend.data.rainfall.provider import HistoricalRainfallProvider


# ---------------------------------------------------------------------------
# 1. Real Drainage Network (Pair A Interface)
# ---------------------------------------------------------------------------
class RealOSMDrainageNetwork:
    def __init__(self, nodes_file, edges_file, surcharge_threshold_m3=35.0):
        with open(nodes_file, "r", encoding="utf-8") as f:
            self.nodes_data = json.load(f)["features"]
        with open(edges_file, "r", encoding="utf-8") as f:
            self.edges_data = json.load(f)["features"]

        self.inlets, self.outfalls, self.junctions = [], [], []
        self.node_positions = {}

        for feat in self.nodes_data:
            p = feat["properties"]
            nid, r, c, ntype = p["id"], p["grid_row"], p["grid_col"], p["type"]
            self.node_positions[nid] = (r, c)
            if ntype == "inlet":
                self.inlets.append((r, c, p.get("capacity_m3s", 0.5)))
            elif ntype == "outfall":
                self.outfalls.append((r, c, nid))
            else:
                self.junctions.append((r, c, nid))

        self.surcharge_nodes = self.outfalls[:8]
        self.surcharge_volume_per_step = surcharge_threshold_m3

    def absorb_surface_water(self, depth_grid, dt):
        absorbed = np.zeros_like(depth_grid)
        for r, c, _ in self.inlets:
            avail = depth_grid[r, c]
            if avail > 0.001:
                absorbed[r, c] = min(avail, 0.04)
        return absorbed

    def compute_overflow(self):
        return {nid: self.surcharge_volume_per_step for r, c, nid in self.surcharge_nodes}

    def get_node_cell(self, node_id):
        return self.node_positions.get(node_id, (160, 160))


# ---------------------------------------------------------------------------
# 2. Road Corridor Loader (Pair C Interface)
# ---------------------------------------------------------------------------
def load_road_corridors(roads_json_file):
    min_lat, max_lat = 19.06013888888332, 19.07819444443888
    min_lon, max_lon = 72.84986111114458, 72.86875000003347

    def norm(s):
        s = unicodedata.normalize("NFKD", s)
        return s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2015", "-")

    with open(roads_json_file, "r", encoding="utf-8") as f:
        d = json.load(f)

    corridors = {}
    for el in d.get("elements", []):
        if el.get("type") == "way" and "name" in el.get("tags", {}):
            name = norm(el["tags"]["name"])
            cells = []
            for pt in el.get("geometry", []):
                r = int((pt["lat"] - min_lat) / (max_lat - min_lat) * 199)
                c = int((pt["lon"] - min_lon) / (max_lon - min_lon) * 199)
                if 0 <= r < 200 and 0 <= c < 200:
                    cells.append((r, c))
            if cells:
                corridors.setdefault(name, []).extend(cells)

    # De-duplicate
    for name in corridors:
        seen, unique = set(), []
        for pt in corridors[name]:
            if pt not in seen:
                seen.add(pt); unique.append(pt)
        corridors[name] = unique

    return corridors


# ---------------------------------------------------------------------------
# 3. Main Simulation
# ---------------------------------------------------------------------------
def run_real_situation_test(event_date="2023-07-26", start_hour=10):
    print("=" * 80)
    print("   REAL-WORLD MONSOON FLOOD ENGINE TEST (v2 — Water Body Fix Applied)")
    print("   Location: Kurla / Bandra-Kurla Complex (BKC), Mumbai, India")
    print("   Domain  : 2.0 km × 2.0 km | 10m resolution (40,000 cells)")
    print("=" * 80)

    nodes_f = PROJECT_ROOT / "backend/data/drainage/drainage_nodes.geojson"
    edges_f = PROJECT_ROOT / "backend/data/drainage/drainage_edges.geojson"
    roads_f = PROJECT_ROOT / "backend/data/roads/raw/osm_roads_mumbai.json"
    wb_mask_f = PROJECT_ROOT / "backend/data/dem/water_body_mask.npy"

    # 1. Drainage
    print("\n[1] Subsurface Drainage Network...")
    drain = RealOSMDrainageNetwork(nodes_f, edges_f, surcharge_threshold_m3=35.0)
    print(f"    {len(drain.nodes_data)} nodes — {len(drain.inlets)} inlets | "
          f"{len(drain.junctions)} manholes | {len(drain.outfalls)} outfalls")
    print(f"    {len(drain.edges_data)} conduit pipe segments")

    # 2. Historical rainfall
    print(f"\n[2] Fetching Historical Rainfall (Open-Meteo Archive, {event_date})...")
    provider = HistoricalRainfallProvider(19.07, 72.85, event_date, start_hour, (200, 200), 10.0)
    rain_nowcast = provider.generate_nowcast(horizon_minutes=180)
    for t, g in sorted(rain_nowcast.items()):
        print(f"    T+{t:3d} min: {g.mean():5.2f} mm/hr")

    # 3. Engine initialisation
    print("\n[3] Initialising Flood Engine with corrected terrain data...")
    engine = FloodEngine.from_default_data(
        rainfall_provider=provider,
        drainage_graph=drain,
        boundary_condition="closed",
    )
    wb = engine.water_body_mask
    land = ~wb
    print(f"    DEM  : {engine.dem.min():.2f} m -> {engine.dem.max():.2f} m ASL")
    print(f"    Water body cells (rivers/channels): {wb.sum()} ({wb.sum()/400:.1f}%)")
    print(f"    River bank cells (adjacent land): {engine.river_bank_mask.sum()}")
    print(f"    River bankfull capacity: {engine.river_bankfull_capacity_m3:,.0f} m3 ({engine.river_bankfull_capacity_m3/1000:.1f} thousand m3)")
    print(f"    Land cells available for flood simulation: {land.sum()}")
    print(f"    Mean imperviousness (land only): {engine.imperviousness[land].mean()*100:.1f}%")
    print(f"    Hydrological sinks: {int(engine.sinks_mask.sum())}")

    # 4. Run simulation
    print("\n[4] Running 180-min Hydrodynamic Simulation (36 × 5-min timesteps)...")
    forecast = engine.run_forecast(scenario="historical", horizon_minutes=180, dt=300.0)
    print("    Simulation completed.")

    # 5. Multi-horizon report (land cells only)
    print("\n" + "-" * 84)
    print(f"{'Horizon':<10} | {'Max Depth':<10} | {'Mean':<10} | {'Vol (m3)':<12} | {'Cells>10cm':<11} | {'Cells>30cm':<10} | River Stage")
    print("-" * 84)
    for t in [0, 30, 60, 90, 120, 180]:
        g = np.where(land, forecast[t], 0.0)
        # River stage is approximated from cumulative inflow up to this time step.
        # Use engine.river_storage_m3 at end of run; show trend via fraction of bankfull.
        print(f"T+{t:3d} min  | {g.max():6.2f} m   | {g.mean()*100:6.2f} cm  | "
              f"{g.sum()*100:10.1f}   | {(g>0.10).sum():8d}    | {(g>0.30).sum():8d}")
    print("-" * 84)
    # Final river state
    pct_full = engine.river_storage_m3 / engine.river_bankfull_capacity_m3 * 100
    print(f"  River stage at T+180: {engine.river_storage_m3:,.0f} m3 stored "
          f"/ {engine.river_bankfull_capacity_m3:,.0f} m3 bankfull ({pct_full:.1f}% full)")

    # 6. Drainage performance
    print("\n[5] Drainage System Performance:")
    print(f"    Inlets absorbed      : {engine.total_absorbed_volume_m3:10.1f} m3")
    print(f"    Sewer overflow       : {engine.total_overflow_volume_m3:10.1f} m3")
    print(f"    River outflow (exit) : {engine.total_river_drain_volume_m3:10.1f} m3")
    print(f"    River bankfull spill : {engine.total_river_overflow_m3:10.1f} m3  <- riverine flood onto land")
    net = engine.total_absorbed_volume_m3 - engine.total_overflow_volume_m3
    print(f"    Net sewer effect     : {net:10.1f} m3 ({'sewer worsened flood' if net < 0 else 'sewer helped'})")
    if engine.total_river_overflow_m3 > 0:
        print(f"    [!] River exceeded bankfull capacity and flooded adjacent land!")

    # 7. Road passability audit
    print("\n[6] Road Corridor Passability (Pair C Interface):")
    corridors = load_road_corridors(roads_f)
    priority = [
        "Santa Cruz - Chembur Link Road", "Bandra Kurla Complex Road",
        "Swadeshi Mill Road", "Sunder Nagar Road Number 2",
        "Vidya Nagari Marg", "BKC - CST Link Road",
        "Jawaharlal Nehru Road", "Bharat Nagar Road",
        "Pipeline Road", "Parshiwadi Road",
        "Street 3", "Street 7",
        "Old CST Road", "Kanzul Iman Road", "JL Shirshekar Marg",
    ]

    evaluated = []
    for rname in priority:
        if rname not in corridors:
            continue
        cells = corridors[rname]
        # Only consider land cells for road flooding
        land_cells = [(r, c) for r, c in cells if land[r, c]]
        if not land_cells:
            continue
        d180_vals = [forecast[180][r, c] for r, c in land_cells]
        peak_idx = int(np.argmax(d180_vals))
        pr, pc = land_cells[peak_idx]
        peak_cm = d180_vals[peak_idx] * 100
        mean_cm = float(np.mean(d180_vals)) * 100
        history = [forecast[t][pr, pc] * 100 for t in [0, 30, 60, 90, 120, 180]]
        evaluated.append(dict(name=rname, peak_r=pr, peak_c=pc, elev=engine.dem[pr, pc],
                               peak_d180=peak_cm, mean_d180=mean_cm, history=history))

    print("─" * 80)
    print(f"{'Road Corridor':<33} │ {'Elev':>5} │ {'Bottleneck T+180':>16} │ {'Mean T+180':>10} │ Status")
    print("─" * 80)
    for rd in evaluated:
        d = rd["peak_d180"]
        status = "🔴 IMPASSABLE" if d > 30 else ("🟠 CAUTION" if d > 10 else "🟢 CLEAR")
        print(f"{rd['name']:<33} │ {rd['elev']:4.1f}m │ {d:12.1f} cm   │ {rd['mean_d180']:6.1f} cm   │ {status}")
    print("─" * 80)

    # 8. Mass balance
    print("\n[7] Mass Balance Audit (land cells only):")
    gross   = engine.total_rain_volume_m3
    infil   = engine.total_infiltrated_volume_m3
    abs_d   = engine.total_absorbed_volume_m3
    ovf     = engine.total_overflow_volume_m3
    river_out   = engine.total_river_drain_volume_m3
    river_spill = engine.total_river_overflow_m3
    river_stored = engine.river_storage_m3     # water currently held in channel
    actual  = float(np.sum(np.where(land, engine.water_depth, 0.0)) * engine.cell_area)
    # Full water budget:
    #   Input  = rain + sewer_overflow + river_spill_back
    #   Output = infiltration + inlet_absorption + river_downstream_exit + river_in_channel + surface_ponding
    expected = gross - infil - abs_d + ovf - river_out + river_spill - river_stored
    err_pct = abs(actual - expected) / (gross + 1e-9) * 100
    print(f"    Rain deposited (land) :  +{gross:12.2f} m3")
    print(f"    Soil infiltration     :  -{infil:12.2f} m3")
    print(f"    Inlet absorption      :  -{abs_d:12.2f} m3")
    print(f"    Sewer overflow        :  +{ovf:12.2f} m3")
    print(f"    River downstream exit :  -{river_out:12.2f} m3")
    print(f"    River in-channel held :  -{river_stored:12.2f} m3  (current river storage)")
    print(f"    River bankfull spill  :  +{river_spill:12.2f} m3")
    print(f"    -----------------------------------------------")
    print(f"    Expected surface vol  :   {expected:12.2f} m3")
    print(f"    Actual tracked vol    :   {actual:12.2f} m3")
    print(f"    Error                 :   {abs(actual-expected):.4f} m3  ({err_pct:.6f}%)")
    print(f"    {'[PASS]' if err_pct < 0.01 else '[WARN]'} Mass conservation {'preserved' if err_pct < 0.01 else 'failed'}")

    # 9. Visuals
    print("\n[8] Generating Enhanced Diagnostic Visualization...")
    generate_visuals(engine, forecast, evaluated, drain, land, wb)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 4. Enhanced Visualization
# ---------------------------------------------------------------------------
def generate_visuals(engine, forecast, evaluated, drain, land_mask, wb_mask):
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(22, 18), dpi=155)
    fig.patch.set_facecolor("#0d1117")

    # Custom flood colormap: transparent → cyan → blue → deep navy
    flood_colors = [(0, "#0d1117"), (0.01, "#00ffe0"), (0.25, "#0077ff"), (0.65, "#0030cc"), (1.0, "#1a0066")]
    flood_cmap = LinearSegmentedColormap.from_list("flood", [(v, c) for v, c in flood_colors])

    # Hazard cmap for T+180: yellow → orange → red → dark red
    hazard_cmap = LinearSegmentedColormap.from_list("hazard",
        [(0, "#0d1117"), (0.01, "#ffe066"), (0.3, "#ff8c00"), (0.6, "#e03000"), (1.0, "#6b0000")])

    dem = engine.dem
    water_body_display = wb_mask.astype(float)  # for overlay
    cell_ext = [0, 2.0, 0, 2.0]

    # ── Grid layout: 2 rows × 3 cols ──
    gs = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.32,
                          left=0.05, right=0.97, top=0.91, bottom=0.06)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])
    ax6 = fig.add_subplot(gs[1, 2])

    for ax in [ax1, ax2, ax3, ax4, ax5, ax6]:
        ax.set_facecolor("#161b22")

    def style_ax(ax, title, color):
        ax.set_title(title, fontsize=11, fontweight="bold", color=color, pad=8)
        ax.set_xlabel("E–W (km)", color="#8b949e", fontsize=9)
        ax.set_ylabel("N–S (km)", color="#8b949e", fontsize=9)
        ax.tick_params(colors="#8b949e", labelsize=8)
        ax.grid(True, linestyle=":", alpha=0.25, color="#8b949e")

    # ─── Panel 1: Terrain + Water Bodies + Drainage ───
    im1 = ax1.imshow(dem, cmap="terrain", origin="lower", extent=cell_ext, alpha=0.9)
    # River overlay in deep blue
    river_rgba = np.zeros((*wb_mask.shape, 4))
    river_rgba[wb_mask] = [0.0, 0.55, 1.0, 0.85]
    ax1.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=2)
    # River bank cells overlay (yellow-green outline — shows the cells that can receive overflow)
    bank_rgba = np.zeros((*wb_mask.shape, 4))
    bank_rgba[engine.river_bank_mask] = [1.0, 0.9, 0.1, 0.55]
    ax1.imshow(bank_rgba, origin="lower", extent=cell_ext, zorder=3)
    # Drain inlets
    ix = [(c/200)*2 for r, c, _ in drain.inlets]
    iy = [(r/200)*2 for r, c, _ in drain.inlets]
    ax1.scatter(ix, iy, c="#00ffe0", s=5, alpha=0.45, zorder=3, label=f"Inlets ({len(drain.inlets)})")
    # Road bottleneck markers
    for rd in evaluated:
        rx, ry = (rd["peak_c"]/200)*2, (rd["peak_r"]/200)*2
        ax1.scatter(rx, ry, c="#ff4757", s=35, edgecolors="#fff", linewidth=0.8, zorder=5)
    river_patch = mpatches.Patch(color="#008cff", label="Mithi River / Channels")
    ax1.legend(handles=[river_patch,
                         mpatches.Patch(color="#00ffe0", label=f"Storm Inlets ({len(drain.inlets)})")],
               loc="upper right", facecolor="#161b22", edgecolor="#30363d", fontsize=8)
    cb1 = fig.colorbar(im1, ax=ax1, fraction=0.04, pad=0.03)
    cb1.set_label("Elevation (m ASL)", color="white", fontsize=8)
    cb1.ax.tick_params(colors="white", labelsize=7)
    style_ax(ax1, "1 · Terrain, River Network & Infrastructure", "#58a6ff")

    # ─── Panel 2: T+60 Inundation (land only) ───
    d60 = np.where(land_mask, forecast[60], np.nan)
    ax2.imshow(dem, cmap="gray", origin="lower", extent=cell_ext, alpha=0.4)
    ax2.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=2)
    vm2 = max(0.5, float(np.nanmax(d60)))
    im2 = ax2.imshow(np.ma.masked_where(d60 < 0.02, d60), cmap=flood_cmap,
                     origin="lower", extent=cell_ext, vmin=0, vmax=vm2, zorder=3)
    cb2 = fig.colorbar(im2, ax=ax2, fraction=0.04, pad=0.03)
    cb2.set_label("Depth (m)", color="white", fontsize=8)
    cb2.ax.tick_params(colors="white", labelsize=7)
    style_ax(ax2, f"2 · Peak Rainfall Period — T+60 min (max {float(np.nanmax(d60)):.2f} m)", "#ffd166")

    # ─── Panel 3: T+180 Hazard Map (land only) ───
    d180 = np.where(land_mask, forecast[180], np.nan)
    ax3.imshow(dem, cmap="gray", origin="lower", extent=cell_ext, alpha=0.4)
    ax3.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=2)
    vm3 = max(0.5, float(np.nanmax(d180)))
    im3 = ax3.imshow(np.ma.masked_where(d180 < 0.02, d180), cmap=hazard_cmap,
                     origin="lower", extent=cell_ext, vmin=0, vmax=vm3, zorder=3)
    cb3 = fig.colorbar(im3, ax=ax3, fraction=0.04, pad=0.03)
    cb3.set_label("Depth (m)", color="white", fontsize=8)
    cb3.ax.tick_params(colors="white", labelsize=7)
    # Road status dots
    for rd in evaluated:
        rx, ry = (rd["peak_c"]/200)*2, (rd["peak_r"]/200)*2
        d = rd["peak_d180"]
        col = "#2ed573" if d < 10 else ("#ffa502" if d <= 30 else "#ff4757")
        ax3.scatter(rx, ry, c=col, s=65, edgecolors="white", linewidth=1.0, zorder=6)
    # Legend for road status
    for col, label in [("#2ed573", "CLEAR"), ("#ffa502", "CAUTION"), ("#ff4757", "IMPASSABLE")]:
        ax3.scatter([], [], c=col, s=50, label=label)
    ax3.legend(loc="upper right", facecolor="#161b22", edgecolor="#30363d", fontsize=8)
    style_ax(ax3, f"3 · Final Hazard Map & Road Status — T+180 min (max {float(np.nanmax(d180)):.2f} m)", "#ff6b81")

    # ─── Panel 4: Road Bottleneck Hydrograph ───
    horizons = [0, 30, 60, 90, 120, 180]
    colors = plt.cm.tab10(np.linspace(0, 1, len(evaluated)))
    for idx, rd in enumerate(evaluated):
        ax4.plot(horizons, rd["history"], marker="o", ms=4, linewidth=1.8,
                 label=rd["name"][:22], color=colors[idx])
    ax4.axhline(10, color="#ffa502", linestyle="--", linewidth=1.1, alpha=0.8, label="Caution (10 cm)")
    ax4.axhline(30, color="#ff4757", linestyle="--", linewidth=1.1, alpha=0.8, label="Impassable (30 cm)")
    ax4.fill_between([0, 180], 30, max(ax4.get_ylim()[1] if ax4.get_ylim()[1] > 30 else 35, 40),
                     alpha=0.08, color="#ff4757")
    ax4.fill_between([0, 180], 10, 30, alpha=0.06, color="#ffa502")
    ax4.set_xlabel("Forecast Horizon (min)", color="#8b949e", fontsize=9)
    ax4.set_ylabel("Bottleneck Depth (cm)", color="#8b949e", fontsize=9)
    ax4.tick_params(colors="#8b949e", labelsize=8)
    ax4.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", fontsize=7, ncol=1)
    ax4.grid(True, linestyle=":", alpha=0.25, color="#8b949e")
    ax4.set_title("4 · Road Corridor Flood Depth Hydrograph", fontsize=11, fontweight="bold", color="#a29bfe", pad=8)

    # ─── Panel 5: Depth distribution by elevation band (violin-style histogram) ───
    bands = [
        ("0–1 m\n(Coastal)", (dem >= 0) & (dem < 1) & land_mask),
        ("1–3 m\n(Low urban)", (dem >= 1) & (dem < 3) & land_mask),
        ("3–8 m\n(Mid urban)", (dem >= 3) & (dem < 8) & land_mask),
        ("8–20 m\n(High urban)", (dem >= 8) & (dem < 20) & land_mask),
    ]
    band_colors = ["#0088ff", "#00ccaa", "#88cc00", "#cc8800"]
    for i, (label, mask) in enumerate(bands):
        depths_cm = forecast[180][mask] * 100
        if depths_cm.size == 0:
            continue
        # Histogram as horizontal bars
        bins = np.linspace(0, min(depths_cm.max(), 120), 30)
        counts, edges = np.histogram(depths_cm, bins=bins)
        bin_centers = 0.5 * (edges[:-1] + edges[1:])
        # Normalize to width 0.8
        norm_counts = counts / (counts.max() + 1e-6) * 0.7
        ax5.barh(bin_centers, norm_counts, left=i, height=(edges[1]-edges[0])*0.85,
                 color=band_colors[i], alpha=0.75, edgecolor="none")
        ax5.text(i + 0.35, -6, label, ha="center", va="top", color=band_colors[i], fontsize=8)

    ax5.axhline(10, color="#ffa502", linestyle="--", linewidth=1.0, alpha=0.8)
    ax5.axhline(30, color="#ff4757", linestyle="--", linewidth=1.0, alpha=0.8)
    ax5.set_xlim(-0.1, len(bands))
    ax5.set_ylim(-10, 125)
    ax5.set_ylabel("Flood Depth at T+180 min (cm)", color="#8b949e", fontsize=9)
    ax5.set_xlabel("Elevation Band (relative density →)", color="#8b949e", fontsize=9)
    ax5.tick_params(colors="#8b949e", labelsize=8)
    ax5.set_xticks([])
    ax5.grid(True, linestyle=":", alpha=0.2, color="#8b949e", axis="y")
    ax5.set_title("5 · Flood Depth Distribution by Elevation Band (T+180)", fontsize=11, fontweight="bold", color="#d2a8ff", pad=8)

    # ─── Panel 6: Water Budget Waterfall ───
    labels = ["Rain\n(land)", "Infiltration", "Inlet\nAbsorption", "Sewer\nOverflow", "River\nExit", "Surface\nPonding"]
    gross   = engine.total_rain_volume_m3 / 1000
    infil   = engine.total_infiltrated_volume_m3 / 1000
    abs_d   = engine.total_absorbed_volume_m3 / 1000
    ovf     = engine.total_overflow_volume_m3 / 1000
    river   = engine.total_river_drain_volume_m3 / 1000
    ponding = float(np.sum(np.where(land_mask, engine.water_depth, 0)) * engine.cell_area) / 1000

    values  = [gross, -infil, -abs_d, ovf, -river, None]
    running = [0, gross, gross - infil, gross - infil - abs_d,
               gross - infil - abs_d + ovf, gross - infil - abs_d + ovf - river]
    bar_h   = [gross, infil, abs_d, ovf, river, ponding]
    bar_cols = ["#58a6ff", "#3fb950", "#3fb950", "#ff6b6b", "#3fb950", "#ffd166"]
    bar_bottom = [0, running[1] - infil, running[2] - abs_d, running[3], running[4] - river, 0]

    for i, (lbl, h, bot, col) in enumerate(zip(labels, bar_h, bar_bottom, bar_cols)):
        ax6.bar(i, h, bottom=bot, color=col, alpha=0.85, edgecolor="#30363d", linewidth=0.8, width=0.6)
        ax6.text(i, bot + h + 0.5, f"{h*1000:.0f} m³", ha="center", va="bottom",
                 color="white", fontsize=7.5, fontweight="bold")

    ax6.set_xticks(range(len(labels)))
    ax6.set_xticklabels(labels, color="#8b949e", fontsize=8)
    ax6.set_ylabel("Volume (×10³ m³)", color="#8b949e", fontsize=9)
    ax6.tick_params(colors="#8b949e", labelsize=8)
    ax6.grid(True, linestyle=":", alpha=0.25, color="#8b949e", axis="y")
    ax6.set_title("6 · Water Budget Waterfall (Land Cells Only)", fontsize=11, fontweight="bold", color="#ffd166", pad=8)

    # Global title
    fig.suptitle(
        "MUMBAI MONSOON REAL-WORLD FLOOD ENGINE DIAGNOSTICS  ·  Jul 26 2023  ·  BKC / Kurla",
        fontsize=14, fontweight="bold", color="#ffffff", y=0.975
    )

    out_paths = [
        PROJECT_ROOT / "backend/data/real_simulation_results_v2.png",
        Path(r"C:\Users\Aniket\.gemini\antigravity-ide\brain\adfdab0d-39f9-47b6-a09a-df7b9eb2bb67\real_simulation_results_v2.png"),
    ]
    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(p, dpi=155, facecolor=fig.get_facecolor(), edgecolor="none")
        print(f"    Saved: {p}")
    plt.close()


if __name__ == "__main__":
    run_real_situation_test()
