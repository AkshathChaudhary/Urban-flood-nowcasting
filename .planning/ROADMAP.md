# Roadmap: Urban Flood Command Center

## Overview

A 5-phase delivery roadmap to transform the pre-hackathon Python hydrodynamic/routing backend into an interactive, real-time command center dashboard adhering to `ui-ux-pro-max` design guidelines (Cinematic Dark Mode, Glassmorphism, 9/10 high density, accessible telemetry).

## Phases

- [x] **Phase 1: Motion-Rich Frontend Foundation & Design System** - Scaffold Vite + React + TypeScript in `frontend/`, configure Tailwind with `MASTER.md` tokens, install Framer Motion, Lucide, and Leaflet, and build the motionsites.ai-inspired landing hero & bento showcase.
- [x] **Phase 2: Interactive GIS Map Viewport & Road Grid** - Full-screen Leaflet integration with Dark Carto tiles, custom glowing map HUD controls, OSM road network layer (`/api/roads`), and coordinate bounding box management.
- [x] **Phase 3: Hydrodynamic 2D Flood Inundation & Radar Scrubber** - 21st.dev styled glassmorphic temporal playback scrubber (0–180 min), dynamic 2D flood depth raster/contour overlay from `/api/flood-forecast`, and precipitation radar sync.
- [x] **Phase 4: Resilient Emergency Routing & Corridor Analytics** - Interactive origin/destination pin placement, vehicle clearance presets, `/api/route` integration, and 21st.dev styled route analytics HUD displaying travel time, distance, and flood depth profile.
- [x] **Phase 5: Drainage Diagnostics, Live WebSockets & Polish** - Subterranean drainage pipe network overlay, pulsing overflow warnings on saturated manholes, real-time `/ws/flood-updates` streaming, and UI/UX Pro Max accessibility audit.

## Phase Details

### Phase 1: Motion-Rich Frontend Foundation & Design System
**Goal**: Scaffold Vite + React 18 + TypeScript, configure Tailwind CSS with `MASTER.md` dark glassmorphism tokens, and implement the motionsites.ai-inspired animated landing hero & bento showcase with 21st.dev style components.
**Depends on**: Nothing (first phase)
**Requirements**: FE-01, MAP-01, MAP-02
**Success Criteria**:
  1. Full-screen command center loads with dark aesthetic (`#020617` background, `#0E1223` glass cards, Inter font).
  2. Leaflet/MapLibre map centers over Mumbai bounding box (19.06 N, 72.85 E) with smooth pan/zoom.
  3. Base layer switcher and HUD overlay panels are rendered cleanly without layout jitter.
**Plans**: 2 plans (01-01: Shell & Tokens, 01-02: Map & Bounds)

### Phase 2: Hydrodynamic & Radar Nowcast Playback
**Goal**: Visualize 2D flood depth grid and radar rainfall progression over the 3-hour forecast horizon.
**Depends on**: Phase 1
**Requirements**: SIM-01, SIM-02, SIM-03
**Success Criteria**:
  1. Timeline slider allows user to scrub between T+0m and T+180m in 5-minute increments.
  2. Flood depth grid updates with color-coded inundation levels (0m to >0.50m) and legend.
  3. Play/pause button smoothly steps through future forecast frames.
**Plans**: 2 plans (02-01: API Ingestion & Color Mesh, 02-02: Scrubber Controls)

### Phase 3: Resilient Emergency Routing Engine
**Goal**: Allow dispatchers to click origin and destination points to calculate and visualize flood-safe routes.
**Depends on**: Phase 1, Phase 2
**Requirements**: NAV-01, NAV-02, NAV-03
**Success Criteria**:
  1. User can click or drag Origin/Destination pins on the map.
  2. Route updates dynamically reflecting road flood penalties; severed roads highlighted in red.
  3. Side panel displays route distance, estimated travel time, and maximum water depth.
**Plans**: 2 plans (03-01: Pin Placement & Route Query, 03-02: Route Profile Panel)

### Phase 4: Drainage System Diagnostic Inspector
**Goal**: Visualize the subterranean pipe network and highlight points of failure/overflow.
**Depends on**: Phase 1
**Requirements**: DRN-01, DRN-02
**Success Criteria**:
  1. Underground drainage conduits and manholes can be toggled on the map.
  2. Saturated pipes and overflow nodes glow with amber/red status indicators.
  3. Clicking a node opens an inspection card with capacity and flow statistics.
**Plans**: 1 plan (04-01: Drainage Layer & Inspector)

### Phase 5: Operations Center Integration & Polish
**Goal**: WebSocket streaming, live scenario selector, accessibility checks, and final polish.
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: OPS-01, OPS-02, OPS-03
**Success Criteria**:
  1. WebSocket connection updates live simulation status in real time.
  2. Multi-city switch allows switching between Mumbai and Kolkata configurations.
  3. Passes UI/UX Pro Max checklist (contrast, keyboard navigation, SVG icons, touch targets).
**Plans**: 2 plans (05-01: WebSocket & Scenarios, 05-02: Accessibility & Polish)
