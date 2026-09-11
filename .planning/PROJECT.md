# Urban Flood Nowcasting & Emergency Routing System

## What This Is

An urban flood nowcasting, subterranean drainage hydrodynamic modeling, and resilient evacuation routing platform. It empowers municipal emergency managers, first responders, and citizens to track real-time rainfall radar nowcasts, inspect surface water depth across high-resolution 10m grids, analyze underground drainage pipe saturation and backflow, and compute safe, flood-penalized emergency travel corridors.

## Core Value

Real-time, coupled overland and subterranean flood nowcasting that dynamically reroutes emergency vehicles around inundated streets before they become trapped.

## Business & Hackathon Context

- **Customer / Users**: Municipal disaster management authorities (MCGM/NDMA), emergency dispatchers (112/108), transit agencies, and affected urban citizens.
- **Hackathon Timeline**: Pre-hackathon (Sep 1–11: backend hydrodynamics, drainage graph, and A* routing built and integrated); Hackathon (Sep 12–13: unified frontend command center dashboard).
- **Stack**: Vite + React 18 / TypeScript, Tailwind CSS, Lucide React, Framer Motion / GSAP, Leaflet / React-Leaflet.
- **Design Inspiration**: 21st.dev cutting-edge component aesthetics (glow effects, glassmorphic HUD cards, dynamic telemetry badges) + motionsites.ai interactive storytelling landing experience transitioning into the live command center.
- **Success Metric**: High-impact first impression with 60fps animations, sub-second route recalculation avoiding flooded road edges, and fluid GIS visualization of radar & flood depth surfaces over 0–180min horizons.

## Requirements

### Validated
- [x] Subterranean drainage graph with Manning's hydraulic capacity and manhole overflow calculation (`backend/app/models/drainage.py`)
- [x] 2D shallow-water simplified overland flow simulation on 200x200 10m elevation grid (`backend/app/models/flood.py`)
- [x] Radar precipitation extrapolation and optical-flow nowcasting over 0–180 min (`backend/app/models/rainfall.py`)
- [x] OSM road network ingestion and flood-depth penalized A*/Dijkstra routing (`backend/app/models/road.py`)
- [x] Unified FastAPI REST & WebSocket endpoints (`backend/app/main.py`)

### Active (Frontend Command Center & Motion-Rich Experience)
- [ ] **FE-01**: Motion-rich product landing showcase (motionsites.ai style) with interactive animated telemetry, live radar preview, and seamless transition to the command center.
- [ ] **FE-02**: Interactive GIS map viewport (Leaflet) with dark Carto tiles, custom styling, road grid, and drainage layers.
- [ ] **FE-03**: Real-time 2D flood depth raster / contour heatmap layer with dynamic opacity and water depth legend.
- [ ] **FE-04**: Temporal nowcast playback scrubber (T+0m to T+180m at 5-minute increments) with 21st.dev styled glass controls.
- [ ] **FE-05**: Emergency corridor routing interface with origin/destination pins, vehicle clearance presets, and route elevation/depth profiles.
- [ ] **FE-06**: Drainage system diagnostic inspector highlighting saturated pipes, manhole overflow volumes, and pump status.
- [ ] **FE-07**: Live WebSocket telemetry panel streaming instant simulation state changes, weather warnings, and route hazards with glowing status indicators.

### Out of Scope
- Full 3D Navier-Stokes hydrodynamic turbulence modeling — computationally prohibitive for real-time 3-hour nowcasting.
- Citizen mobile app native builds (iOS/Android) — priority is the unified web command center dashboard.

## Context

- **Existing Architecture**: 3 decoupled pairs integrated via shared spatial contracts (200x200 grid, 10m cells, Mumbai coordinates 19.0600 N, 72.8500 E).
- **Design System**: Persisted in `design-system/urban-flood-command-center/MASTER.md` following `ui-ux-pro-max` intelligence (Cinematic Dark Mode, Glassmorphism, 9/10 high visual density, Inter typography, accessible status colors).

## Constraints

- Must communicate with existing backend via FastAPI endpoints on port 8000 and WebSocket `/ws/flood-updates`.
- WCAG AA accessibility compliance for critical emergency telemetry (4.5:1 text contrast minimum, keyboard navigable controls, reduced motion support).
