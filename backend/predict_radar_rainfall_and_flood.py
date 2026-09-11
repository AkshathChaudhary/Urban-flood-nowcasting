"""
3-Hour Radar-Driven Rainfall Nowcasting & Hydrodynamic Flood Prediction Engine.

Uses live Doppler weather radar data (RainViewer frames, Marshall-Palmer Z-R conversion,
and convective storm cell advection) combined with One Weather API nowcasting to predict
rainfall and subsequent urban street flooding with a 3-hour lead time (T+0 to T+180 min).

Outputs:
  - 3-hour rainfall prediction summary (rates, Doppler dBZ, storm trajectory)
  - 3-hour overland flood and street-depth inundation simulation
  - Critical corridor early warning alerts (lead time to 10cm Caution & 30cm Impassable)
  - High-resolution multi-panel radar & flood diagnostic graphics
"""

import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Optional, Tuple, Dict, Any, List

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.engine.flood_engine import FloodEngine
from backend.data.rainfall.provider import OneWeatherRadarNowcastProvider, RainfallProvider
from backend.run_real_situation_simulation import (
    RealOSMDrainageNetwork,
    load_road_corridors,
)


def run_radar_flood_prediction(
    lat: float = 19.07,
    lon: float = 72.85,
    storm_speed_kmh: float = 20.0,
    storm_heading_deg: float = 135.0,
    demo_fallback: bool = False,
    output_png_path: Optional[Path] = None,
):
    mode_label = "STRESS-TEST DEMO FALLBACK" if demo_fallback else "100% PURE LIVE RADAR & WEATHER"
    print("=" * 88)
    print(f"   3-HOUR RADAR-DRIVEN RAINFALL NOWCASTING & URBAN FLOOD PREDICTION")
    print(f"   Mode    : {mode_label}")
    print(f"   Location: Kurla / Bandra-Kurla Complex (BKC), Mumbai, India")
    print(f"   Domain  : 2.0 km × 2.0 km | 10m Resolution (40,000 cells)")
    print("=" * 88)

    nodes_f = PROJECT_ROOT / "backend/data/drainage/drainage_nodes.geojson"
    edges_f = PROJECT_ROOT / "backend/data/drainage/drainage_edges.geojson"
    roads_f = PROJECT_ROOT / "backend/data/roads/raw/osm_roads_mumbai.json"

    # 1. Drainage network
    print("\n[1] Loading Subsurface Stormwater Drainage Network...")
    drain = RealOSMDrainageNetwork(nodes_f, edges_f, surcharge_threshold_m3=35.0)
    print(f"    {len(drain.nodes_data)} nodes ({len(drain.inlets)} inlets, {len(drain.junctions)} manholes, {len(drain.outfalls)} outfalls)")
    print(f"    {len(drain.edges_data)} conduit pipe segments")

    # 2. Radar-based Rainfall Nowcasting Provider
    print(f"\n[2] Ingesting Live Doppler Radar & One Weather Nowcasting API...")
    radar_provider = OneWeatherRadarNowcastProvider(
        lat=lat,
        lon=lon,
        grid_shape=(200, 200),
        cell_size_m=10.0,
        use_radar=True,
        storm_speed_kmh=storm_speed_kmh,
        storm_heading_deg=storm_heading_deg,
        demo_fallback=demo_fallback,
    )

    radar_frames = radar_provider.get_radar_frames(limit=5)
    print(f"    Doppler radar feed: {len(radar_frames)} frames retrieved")
    for f in radar_frames[:3]:
        print(f"      Frame @ {f.get('time_iso', 'N/A')}: {f.get('tile_url', '')} (Est. Peak: {f.get('estimated_peak_dbz', 0)} dBZ)")

    print(f"    API Source: {radar_provider.api_source_used}")
    current_rain = radar_provider.get_current_rainfall()
    print(f"    Current instantaneous rain rate: {current_rain:.2f} mm/hr")

    print("\n[3] Computing 3-Hour Forward Rainfall Nowcast & Doppler Reflectivity...")
    rain_nowcast = radar_provider.generate_nowcast(horizon_minutes=180)
    
    dbz_grids = {}
    print("-" * 88)
    print(f"{'Horizon':<10} | {'Mean Rain (mm/h)':<18} | {'Peak Rain (mm/h)':<18} | {'Peak Reflectivity (dBZ)':<24} | {'Weather Category'}")
    print("-" * 88)
    for t in [0, 30, 60, 90, 120, 180]:
        grid = rain_nowcast[t]
        mean_r = float(grid.mean())
        max_r = float(grid.max())
        dbz = float(RainfallProvider.rain_rate_to_dbz(max_r))
        dbz_grids[t] = RainfallProvider.rain_rate_to_dbz(grid)

        if max_r > 80.0:
            category = "Extreme Cloudburst Core"
        elif max_r > 30.0:
            category = "Severe Convective Downpour"
        elif max_r > 10.0:
            category = "Heavy Monsoon Rain"
        elif max_r > 2.5:
            category = "Moderate Rain"
        elif max_r > 0.5:
            category = "Light Rain"
        else:
            category = "Dry / Traces"
        print(f"T+{t:<7} | {mean_r:16.2f}  | {max_r:16.2f}  | {dbz:20.1f} dBZ     | {category}")
    print("-" * 88)

    # 3. Initialize Hydrodynamic Engine
    print("\n[4] Initializing Hydrodynamic Simulation Engine...")
    INITIAL_MONSOON_RIVER_STORAGE_M3 = 80000.0
    UPSTREAM_CATCHMENT_INFLOW_M3_S = 15.0
    TIDAL_TAILWATER_STAGE_M = 0.5
    TIDAL_CYCLE_START_HOUR = 14.0
    ANTECEDENT_SOIL_SATURATION = 0.60
    DRAIN_BLOCKAGE_FACTOR = 0.65
    RETENTION_POND_CAPACITY_M3 = 25000.0
    PUMP_STATIONS = [
        {"name": "Kurla Car Shed Pump", "row": 135, "col": 85, "capacity_m3_s": 4.0, "operational": True, "radius_cells": 3},
        {"name": "Mahim Creek Outfall Pump", "row": 160, "col": 45, "capacity_m3_s": 6.0, "operational": True, "radius_cells": 3},
    ]

    engine = FloodEngine.from_default_data(
        rainfall_provider=radar_provider,
        drainage_graph=drain,
        boundary_condition="closed",
        initial_river_storage_m3=INITIAL_MONSOON_RIVER_STORAGE_M3,
        upstream_river_inflow_m3_s=UPSTREAM_CATCHMENT_INFLOW_M3_S,
        tidal_tailwater_stage_m=TIDAL_TAILWATER_STAGE_M,
        tidal_cycle_start_hour=TIDAL_CYCLE_START_HOUR,
        antecedent_saturation_fraction=ANTECEDENT_SOIL_SATURATION,
        drain_blockage_factor=DRAIN_BLOCKAGE_FACTOR,
        enable_retention_ponds=True,
        retention_pond_capacity_m3=RETENTION_POND_CAPACITY_M3,
        storm_surge_m=0.0,
        pump_stations=PUMP_STATIONS,
    )

    wb = engine.water_body_mask
    land = ~wb

    # 4. Run 3-Hour Simulation
    print("\n[5] Running 3-Hour Predictive Hydrodynamic Simulation (T+0 -> T+180 min)...")
    t0 = time.time()
    flood_forecast = engine.run_forecast(scenario="live", horizon_minutes=180, dt=300.0)
    sim_duration = time.time() - t0
    print(f"    Simulation finished in {sim_duration:.2f}s ({36} timesteps of 300s)")

    street_depth_grid = engine.get_street_depth()

    # 5. Road Corridor Inundation & Early Warning Analysis
    print("\n[6] 3-Hour Corridor Inundation & Early Warning Status:")
    corridors = load_road_corridors(roads_f)
    evaluated = []

    target_names = [
        "Santa Cruz - Chembur Link Road",
        "Bandra Kurla Complex Road",
        "Old CST Road",
        "BKC - CST Link Road",
        "Swadeshi Mill Road",
        "Jawaharlal Nehru Road",
        "Bharat Nagar Road",
        "Vidya Nagari Marg",
        "Ramakrishna Paramahansa Marg",
        "Parshiwadi Road",
        "Sunder Nagar Road Number 2",
    ]

    for name in target_names:
        if name not in corridors:
            # Fallback fuzzy match
            matched = [k for k in corridors if name.lower() in k.lower()]
            if matched:
                name = matched[0]
            else:
                continue
        cells = corridors[name]
        d180 = [street_depth_grid[r, c] * 100 for r, c in cells if land[r, c]]
        raw_d180 = [flood_forecast[180][r, c] * 100 for r, c in cells if land[r, c]]
        if not d180:
            continue

        # Depth progression across horizons [0, 30, 60, 90, 120, 180]
        history = [
            float(np.percentile([(flood_forecast[t][r, c] / engine.surface_porosity[r, c]) * 100 for r, c in cells if land[r, c]], 90))
            for t in [0, 30, 60, 90, 120, 180]
        ]
        elevs = [engine.dem[r, c] for r, c in cells]
        peak_idx = int(np.argmax(d180))

        # Determine early warning lead time:
        # Time when corridor exceeds 10 cm (Caution) and 30 cm (Impassable)
        t_caution = None
        t_impassable = None
        for idx, t_min in enumerate([0, 30, 60, 90, 120, 180]):
            d_val = history[idx]
            if d_val >= 10.0 and t_caution is None:
                t_caution = t_min
            if d_val >= 30.0 and t_impassable is None:
                t_impassable = t_min

        evaluated.append({
            "name": name,
            "peak_d180": float(np.max(d180)),
            "raw_peak_d180": float(np.max(raw_d180)),
            "mean_d180": float(np.mean(d180)),
            "peak_r": cells[peak_idx][0],
            "peak_c": cells[peak_idx][1],
            "elev": float(np.mean(elevs)),
            "history": history,
            "t_caution": t_caution,
            "t_impassable": t_impassable,
        })

    print("-" * 92)
    print(f"{'Corridor':<30} | {'Elev':<6} | {'Street Depth':<13} | {'Caution @':<10} | {'Impassable @':<12} | Status")
    print("-" * 92)
    for rd in evaluated:
        d = rd["peak_d180"]
        c_str = f"T+{rd['t_caution']}m" if rd['t_caution'] is not None else "None"
        i_str = f"T+{rd['t_impassable']}m" if rd['t_impassable'] is not None else "None"
        status = "[IMPASSABLE]" if d > 30 else ("[CAUTION]" if d > 10 else "[CLEAR]")
        print(f"{rd['name']:<30} | {rd['elev']:4.1f}m | {d:10.1f} cm  | {c_str:<10} | {i_str:<12} | {status}")
    print("-" * 92)

    # 6. Mass Balance Audit
    gross_rain = engine.total_rain_volume_m3
    infil = engine.total_infiltrated_volume_m3
    absorbed = engine.total_absorbed_volume_m3
    pumped = engine.total_pumped_volume_m3
    actual_land = float(np.sum(np.where(land, engine.water_depth, 0.0)) * engine.cell_area)
    print(f"\n[7] Hydraulic Mass Balance Audit:")
    print(f"    Radar-Predicted Rain Volume : +{gross_rain:12.2f} m³")
    print(f"    Soil Infiltration           : -{infil:12.2f} m³")
    print(f"    Sewer Drainage Absorption   : -{absorbed:12.2f} m³")
    print(f"    Pump Station Discharge      : -{pumped:12.2f} m³")
    print(f"    Active Overland Flood Volume:  {actual_land:12.2f} m³")

    # 7. Generate Radar Visuals
    print("\n[8] Generating High-Resolution Radar & Flood Visual Diagnostics...")
    if output_png_path is None:
        output_png_path = PROJECT_ROOT / "backend/data/radar_flood_prediction_3h.png"
    
    generate_radar_visuals(
        engine=engine,
        radar_provider=radar_provider,
        rain_nowcast=rain_nowcast,
        dbz_grids=dbz_grids,
        flood_forecast=flood_forecast,
        evaluated=evaluated,
        drain=drain,
        land_mask=land,
        wb_mask=wb,
        save_path=output_png_path,
    )
    print(f"    [OK] Visuals saved to: {output_png_path}")
    print("=" * 88)
    return engine, rain_nowcast, flood_forecast, evaluated


def generate_radar_visuals(
    engine,
    radar_provider,
    rain_nowcast,
    dbz_grids,
    flood_forecast,
    evaluated,
    drain,
    land_mask,
    wb_mask,
    save_path: Path,
):
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(24, 18), dpi=160)
    fig.patch.set_facecolor("#0a0e14")

    # Colormaps
    # Doppler radar dBZ colormap: NWS/IMD standard radar color ladder
    # <15 dBZ transparent/dark -> 20-30 dBZ green -> 35 dBZ yellow -> 45 dBZ red -> 55+ dBZ magenta
    radar_colors = [
        (0.00, "#0a0e14"),
        (0.25, "#0a0e14"),  # < 15 dBZ dark/background
        (0.30, "#00e676"),  # 18 dBZ light green
        (0.45, "#00b0ff"),  # 27 dBZ cyan/blue
        (0.60, "#ffd600"),  # 36 dBZ yellow
        (0.72, "#ff6d00"),  # 43 dBZ orange
        (0.85, "#ff1744"),  # 51 dBZ red
        (1.00, "#d500f9"),  # 60 dBZ magenta cloudburst core
    ]
    radar_cmap = LinearSegmentedColormap.from_list("doppler_radar", radar_colors)

    # Flood Inundation Colormap (cm): Transparent -> Cyan -> Blue -> Purple
    flood_colors = [
        (0.0, "#0a0e14"),
        (0.01, "#00e5ff"),
        (0.20, "#2979ff"),
        (0.50, "#304ffe"),
        (0.80, "#6200ea"),
        (1.0, "#aa00ff"),
    ]
    flood_cmap = LinearSegmentedColormap.from_list("inundation", flood_colors)

    cell_ext = [0, 2.0, 0, 2.0]
    dem = engine.dem

    # Grid layout: 2 rows x 3 cols
    gs = fig.add_gridspec(2, 3, hspace=0.36, wspace=0.30, left=0.04, right=0.97, top=0.91, bottom=0.06)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])
    ax6 = fig.add_subplot(gs[1, 2])

    for ax in [ax1, ax2, ax3, ax4, ax5, ax6]:
        ax.set_facecolor("#121820")

    def style_ax(ax, title, color="#58a6ff"):
        ax.set_title(title, fontsize=11, fontweight="bold", color=color, pad=8)
        ax.set_xlabel("E–W (km)", color="#8b949e", fontsize=9)
        ax.set_ylabel("N–S (km)", color="#8b949e", fontsize=9)
        ax.tick_params(colors="#8b949e", labelsize=8)
        ax.grid(True, linestyle=":", alpha=0.25, color="#8b949e")

    # Water body mask overlay
    river_rgba = np.zeros((*wb_mask.shape, 4))
    river_rgba[wb_mask] = [0.0, 0.55, 1.0, 0.85]

    # ─── Panel 1: Doppler Radar Reflectivity Mosaic at T+60 ───
    dbz_60 = dbz_grids[60]
    # Underlay shaded terrain
    ax1.imshow(dem, cmap="gray", origin="lower", extent=cell_ext, alpha=0.3)
    im1 = ax1.imshow(dbz_60, cmap=radar_cmap, vmin=0, vmax=60, origin="lower", extent=cell_ext, alpha=0.9)
    ax1.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=2)
    # Draw storm cell centroid tracking vector
    y_c, x_c = np.unravel_index(np.argmax(dbz_60), dbz_60.shape)
    ax1.scatter((x_c / 200) * 2, (y_c / 200) * 2, c="#ffffff", marker="x", s=110, linewidth=2.5, zorder=5)
    ax1.text((x_c / 200) * 2 + 0.05, (y_c / 200) * 2, f"Storm Core: {dbz_60.max():.1f} dBZ", color="#ffffff", fontsize=8.5, fontweight="bold", zorder=6)
    # Storm motion arrow
    ax1.annotate("", xy=((x_c / 200) * 2 + 0.32, (y_c / 200) * 2 - 0.32),
                 xytext=((x_c / 200) * 2, (y_c / 200) * 2),
                 arrowprops=dict(arrowstyle="->", color="#ffff00", lw=2.5, mutation_scale=15), zorder=6)
    ax1.text((x_c / 200) * 2 + 0.12, (y_c / 200) * 2 - 0.18, f"{radar_provider.storm_speed_kmh} km/h (SE)", color="#ffff00", fontsize=8, fontweight="bold")
    cb1 = fig.colorbar(im1, ax=ax1, fraction=0.04, pad=0.03)
    cb1.set_label("Doppler Reflectivity (dBZ)", color="white", fontsize=8)
    cb1.ax.tick_params(colors="white", labelsize=7)
    style_ax(ax1, "1 · Doppler Radar Reflectivity & Storm Motion (T+60 min)", "#00e676")

    # ─── Panel 2: Radar-Derived Precipitation Intensity at T+60 (mm/hr) ───
    rain_60 = rain_nowcast[60]
    ax2.imshow(dem, cmap="gray", origin="lower", extent=cell_ext, alpha=0.3)
    im2 = ax2.imshow(rain_60, cmap="YlGnBu", vmin=0, vmax=max(40.0, float(rain_60.max())), origin="lower", extent=cell_ext, alpha=0.9)
    ax2.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=2)
    # Overlay 20mm/h and 40mm/h contours
    ax2.contour(rain_60, levels=[10.0, 25.0, 40.0], colors=["#00ffff", "#ffd700", "#ff0055"],
                origin="lower", extent=cell_ext, linewidths=1.2, linestyles="--")
    cb2 = fig.colorbar(im2, ax=ax2, fraction=0.04, pad=0.03)
    cb2.set_label("Precipitation Rate (mm/hr)", color="white", fontsize=8)
    cb2.ax.tick_params(colors="white", labelsize=7)
    style_ax(ax2, f"2 · Radar Precipitation Rate Map (Peak: {rain_60.max():.1f} mm/hr)", "#ffd600")

    # ─── Panel 3: 3-Hour Subsequent Overland Flooding (T+180 min) ───
    street_depth = engine.get_street_depth() * 100.0  # in cm
    street_depth_land = np.where(land_mask, street_depth, np.nan)
    ax3.imshow(dem, cmap="gray", origin="lower", extent=cell_ext, alpha=0.35)
    im3 = ax3.imshow(street_depth_land, cmap=flood_cmap, vmin=0, vmax=100.0, origin="lower", extent=cell_ext, zorder=2)
    ax3.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=3)
    # Overlay road status points
    for rd in evaluated:
        rx, ry = (rd["peak_c"] / 200) * 2, (rd["peak_r"] / 200) * 2
        d = rd["peak_d180"]
        c = "#ff1744" if d > 30 else ("#ffd600" if d > 10 else "#00e676")
        ax3.scatter(rx, ry, c=c, s=55, edgecolors="#ffffff", linewidth=1.2, zorder=5)
        ax3.text(rx + 0.04, ry - 0.02, f"{rd['name'][:10]}: {d:.0f}cm", color="#ffffff", fontsize=7, fontweight="bold", zorder=6)
    cb3 = fig.colorbar(im3, ax=ax3, fraction=0.04, pad=0.03)
    cb3.set_label("Street Flood Depth (cm)", color="white", fontsize=8)
    cb3.ax.tick_params(colors="white", labelsize=7)
    style_ax(ax3, "3 · Predicted Street Inundation & Passability (T+180 min)", "#ff1744")

    # ─── Panel 4: Doppler Radar Marshall-Palmer Z-R Relationship ───
    r_vals = np.linspace(0.1, 100.0, 300)
    z_vals = 200.0 * (r_vals ** 1.6)
    dbz_vals = 10.0 * np.log10(z_vals)
    ax4.plot(r_vals, dbz_vals, color="#00e5ff", lw=2.5, label=r"Marshall-Palmer: $Z = 200 \cdot R^{1.6}$")
    ax4.axhline(30.0, color="#ffd600", linestyle=":", alpha=0.7, label="30 dBZ (Moderate Rain)")
    ax4.axhline(40.0, color="#ff6d00", linestyle=":", alpha=0.7, label="40 dBZ (Heavy Rain)")
    ax4.axhline(50.0, color="#d500f9", linestyle=":", alpha=0.7, label="50 dBZ (Cloudburst Core)")
    # Plot nowcasted horizons with distinct offsets
    offsets = {
        0: (1.5, 0.5),
        30: (-12.0, 2.0),
        60: (2.0, -2.5),
        90: (1.5, -2.0),
        120: (1.5, 0.5),
        180: (1.5, -2.5),
    }
    for t in [0, 30, 60, 90, 120, 180]:
        max_r = float(rain_nowcast[t].max())
        dbz = float(RainfallProvider.rain_rate_to_dbz(max_r))
        ax4.scatter(max_r, dbz, color="#ff0055", s=60, zorder=5)
        dx, dy = offsets.get(t, (1.5, 0.0))
        ax4.text(max_r + dx, dbz + dy, f"T+{t}m", color="#ffffff", fontsize=8, fontweight="bold")
    ax4.set_title("4 · Doppler Radar Z-R Calibration Curve", fontsize=11, fontweight="bold", color="#00e5ff", pad=8)
    ax4.set_xlabel("Rain Rate R (mm/hr)", color="#8b949e", fontsize=9)
    ax4.set_ylabel("Radar Reflectivity (dBZ)", color="#8b949e", fontsize=9)
    ax4.tick_params(colors="#8b949e", labelsize=8)
    ax4.grid(True, linestyle=":", alpha=0.3, color="#8b949e")
    ax4.legend(loc="lower right", facecolor="#161b22", edgecolor="#30363d", fontsize=8)

    # ─── Panel 5: 3-Hour Early Warning Hydrographs ───
    horizons = [0, 30, 60, 90, 120, 180]
    # Filter for top flooded corridors with max depth > 10cm
    flooded_roads = [r for r in evaluated if r["peak_d180"] > 10.0]
    if not flooded_roads:
        flooded_roads = evaluated[:6]
    palette = ["#ff5252", "#ff793f", "#ffb142", "#33d9b2", "#34ace0", "#706fd3", "#e056fd"]
    for idx, rd in enumerate(flooded_roads[:7]):
        c = palette[idx % len(palette)]
        ax5.plot(horizons, rd["history"], marker="o", lw=2.2, color=c, label=f"{rd['name'][:22]}")
    ax5.axhline(10.0, color="#ffd600", linestyle="--", lw=1.5, label="Caution Threshold (10 cm)")
    ax5.axhline(30.0, color="#ff1744", linestyle="--", lw=1.8, label="Impassable Threshold (30 cm)")
    ax5.set_title("5 · Corridor Flood Evolution & 3-Hour Lead Time", fontsize=11, fontweight="bold", color="#ff793f", pad=8)
    ax5.set_xlabel("Forecast Horizon (minutes)", color="#8b949e", fontsize=9)
    ax5.set_ylabel("Street Water Depth (cm)", color="#8b949e", fontsize=9)
    ax5.tick_params(colors="#8b949e", labelsize=8)
    ax5.grid(True, linestyle=":", alpha=0.3, color="#8b949e")
    ax5.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", fontsize=7.5)

    # ─── Panel 6: Radar Storm Trajectory & Urban Protection Assets ───
    ax6.imshow(dem, cmap="terrain", origin="lower", extent=cell_ext, alpha=0.75)
    ax6.imshow(river_rgba, origin="lower", extent=cell_ext, zorder=2)
    # Retention pond
    pond_rgba = np.zeros((*wb_mask.shape, 4))
    pond_rgba[engine.retention_pond_mask] = [0.0, 0.95, 0.45, 0.9]
    ax6.imshow(pond_rgba, origin="lower", extent=cell_ext, zorder=3)

    # Continuous kinematics storm trajectory
    traj_x, traj_y = [], []
    center_r = int(engine.rows * 0.45)
    center_c = int(engine.cols * 0.45)
    speed_cells_per_min = (radar_provider.storm_speed_kmh * 1000.0 / 3600.0 * 60.0) / radar_provider.cell_size_m / 60.0
    heading_rad = math.radians(radar_provider.storm_heading_deg)
    for t in horizons:
        shift_r = int(t * speed_cells_per_min * math.cos(heading_rad))
        shift_c = int(t * speed_cells_per_min * math.sin(heading_rad))
        cr = (center_r + shift_r) % engine.rows
        cc = (center_c + shift_c) % engine.cols
        traj_x.append((cc / 200) * 2)
        traj_y.append((cr / 200) * 2)

    ax6.plot(traj_x, traj_y, color="#ffff00", lw=3.0, linestyle="-", marker="D", markersize=7, label="Radar Storm Track (T+0 -> T+180)")
    for i, t in enumerate(horizons):
        ax6.text(traj_x[i] + 0.04, traj_y[i] + 0.03, f"T+{t}", color="#ffff00", fontsize=8, fontweight="bold")
    # Pump stations
    for ps in engine.pump_stations:
        px, py = (ps["col"] / 200) * 2, (ps["row"] / 200) * 2
        ax6.scatter(px, py, c="#ff00ea", s=110, marker="^", edgecolors="#ffffff", linewidth=1.5, zorder=7)
        ax6.text(px + 0.04, py - 0.04, ps["name"][:14], color="#ff00ea", fontsize=8, fontweight="bold", zorder=8)
    # Drain inlets sample
    ix = [(c / 200) * 2 for r, c, _ in drain.inlets[::4]]
    iy = [(r / 200) * 2 for r, c, _ in drain.inlets[::4]]
    ax6.scatter(ix, iy, c="#00ffe0", s=5, alpha=0.4, zorder=4, label=f"Drain Inlets ({len(drain.inlets)})")
    ax6.set_title("6 · Radar Storm Trajectory & Critical Infrastructure", fontsize=11, fontweight="bold", color="#ff00ea", pad=8)
    ax6.set_xlabel("E–W (km)", color="#8b949e", fontsize=9)
    ax6.set_ylabel("N–S (km)", color="#8b949e", fontsize=9)
    ax6.tick_params(colors="#8b949e", labelsize=8)
    ax6.grid(True, linestyle=":", alpha=0.25, color="#8b949e")
    ax6.legend(loc="upper right", facecolor="#161b22", edgecolor="#30363d", fontsize=7.5)

    # Super title & Header
    fig.suptitle(
        "MUMBAI URBAN FLOOD NOWCASTING PLATFORM — 3-HOUR RADAR & FLOOD PREDICTION SUITE\n"
        "Doppler Radar Storm Motion Advection • Marshall-Palmer Z-R Inversion • Hydrodynamic Street Inundation (Kurla/BKC)",
        fontsize=14, fontweight="bold", color="#f0f6fc", y=0.97
    )

    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(save_path), facecolor=fig.get_facecolor(), edgecolor="none", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    stress_test = ("--stress-test" in sys.argv or "--cloudburst" in sys.argv or "--demo" in sys.argv)
    output_dir = PROJECT_ROOT / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = "radar_flood_prediction_stress_test.png" if stress_test else "radar_flood_prediction_3h.png"
    artifact_png = output_dir / filename
    run_radar_flood_prediction(demo_fallback=stress_test, output_png_path=artifact_png)
