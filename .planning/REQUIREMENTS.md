# Requirements: Urban Flood Command Center

**Defined:** 2026-09-11  
**Core Value:** Real-time, coupled overland and subterranean flood nowcasting that dynamically reroutes emergency vehicles around inundated streets before they become trapped.

## v1 Requirements

### Interactive GIS Map Viewport (MAP)
- [ ] **MAP-01**: Map viewport displays city baseline layers (Dark Carto / OSM vector tiles) centered on study domain.
- [ ] **MAP-02**: Toggleable layer controls for Road Network, Drainage Pipes/Inlets, Flood Depth Heatmap, and Doppler Radar Precipitation.
- [ ] **MAP-03**: Smooth pan, zoom (levels 12–18), and boundary bounds fitting for Mumbai and multi-city scenarios.

### Temporal Nowcast & Simulation Playback (SIM)
- [ ] **SIM-01**: Timeline scrubber spanning 0 to 180 minutes with 5-minute timestep steps and play/pause controls.
- [ ] **SIM-02**: Live color-scaled water depth visualization (`<0.05m` dry, `0.05–0.15m` caution, `0.15–0.30m` impassable for cars, `>0.30m` severe inundation).
- [ ] **SIM-03**: Precipitation intensity overlay synchronized with the active simulation timestamp.

### Resilient Evacuation & Emergency Routing (NAV)
- [ ] **NAV-01**: Interactive Origin (`A`) and Destination (`B`) pin placement on the road network.
- [ ] **NAV-02**: Vehicle profile selection (Standard Car: 0.15m max depth, Fire Truck/Ambulance: 0.30m max depth, High-Clearance Rescue: 0.60m max depth).
- [ ] **NAV-03**: Visual rendering of the primary safe corridor vs. flooded severed roads, including ETA, distance, and maximum water depth encountered along route.

### Drainage Telemetry & Network Diagnostics (DRN)
- [ ] **DRN-01**: Node click inspector displaying pipe flow rate, design capacity, and surcharge overflow rate in m³/s.
- [ ] **DRN-02**: Visual pulsing alert for manholes experiencing reverse backflow / surface flooding.

### Command Center Telemetry & Alerts (OPS)
- [ ] **OPS-01**: Top status bar streaming live WebSocket connection state, active simulation scenario, and computation latency.
- [ ] **OPS-02**: High-priority alert banner listing currently blocked arterial roads and flood severity warnings.
- [ ] **OPS-03**: WCAG AA compliance with dark mode contrast >=4.5:1, keyboard accessible map controls, and prefers-reduced-motion fallback.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MAP-01, MAP-02, MAP-03 | Phase 1: Core GIS Foundation | Pending |
| SIM-01, SIM-02, SIM-03 | Phase 2: Hydrodynamic & Radar Nowcast Engine | Pending |
| NAV-01, NAV-02, NAV-03 | Phase 3: Resilient Emergency Routing Engine | Pending |
| DRN-01, DRN-02 | Phase 4: Drainage Telemetry & Diagnostics | Pending |
| OPS-01, OPS-02, OPS-03 | Phase 5: Operations Center Integration & Polish | Pending |
