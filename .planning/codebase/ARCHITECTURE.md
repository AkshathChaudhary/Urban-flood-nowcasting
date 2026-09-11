# Architecture

**Analysis Date:** 2026-09-11

## Pattern Overview

**Overall:** Coupled Multi-Domain Hydrodynamic Simulation and Micro-Service API Architecture

**Key Characteristics:**
- **Decoupled Pair Subsystems:** Developed across 3 developer pairs (Pair A: Subterranean Drainage, Pair B: Overland Flood + Rainfall Nowcast, Pair C: Road Graph + Routing)
- **Shared Spatial Grid Contract:** 200x200 grid (10m x 10m resolution) mapping a 2km x 2km urban quadrant
- **Coupled Physics Loop:** Overland surface runoff flows into subterranean drainage via inlet nodes; drainage capacity saturation triggers backflow/overflow back onto the overland surface grid; dynamic flood depth penalizes road edge traversal weights in real time
- **Unified Asynchronous Presentation Layer:** FastAPI routing layer providing REST endpoints and WebSocket broadcast streams to the frontend command center

## Subsystem Layers

```mermaid
flowchart TD
    subgraph Weather [Meteorology & Nowcast]
        Radar[Doppler Radar dBZ / IMD] --> RainEng[RainfallNowcaster]
        RainEng -->|Rainfall Grid (mm/hr)| FloodEng
    end

    subgraph Hydrology [Pair B: Overland 2D Hydrodynamics]
        DEM[Digital Elevation Model] --> FloodEng[FloodEngine 2D Surface Flow]
        FloodEng -->|Water Depth Grid h(x,y)| Coupling[Dual-Layer Coupling]
    end

    subgraph Drainage [Pair A: Subterranean Network]
        Inlets[Drainage Inlets] --> PipeGraph[NetworkX Drainage Graph]
        PipeGraph --> Pumps[Pump Stations & Outfalls]
        Coupling -->|Surface Water Absorption| PipeGraph
        PipeGraph -->|Manhole Surcharge / Overflow| Coupling
        Coupling -->|Net Surface Inundation| FloodEng
    end

    subgraph Routing [Pair C: Road Graph & Resilient Navigation]
        OSM[OSM Road Network] --> RoadGraph[NetworkX MultiDiGraph]
        FloodEng -->|Flood Depth at Midpoints| RoadGraph
        RoadGraph --> Router[A* / Dijkstra Routing Engine]
        Router --> SafeRoute[Safe Emergency Corridors]
    end

    subgraph API [FastAPI Service Layer]
        FloodEng --> API_Endpoints[/api/flood-forecast, /api/simulate]
        PipeGraph --> API_Drainage[/api/drainage]
        Router --> API_Route[/api/route, /api/roads]
        Coupling --> WebSocket[/ws/flood-updates]
    end
```

### 1. Subterranean Drainage Network (Pair A)
- **Location:** `backend/app/models/drainage.py`, `backend/app/api/drainage.py`
- **Responsibilities:**
  - Ingestion and graph modeling of pipes, culverts, junctions, and outfalls
  - Calculating pipe capacity using Manning's equation
  - Tracking node saturation and calculating overflow volume when pipe capacity is exceeded
  - Providing absorption logic to draw down overland surface water into drainage conduits

### 2. Rainfall Nowcasting & Overland 2D Hydrodynamic Engine (Pair B)
- **Location:** `backend/app/models/flood.py`, `backend/app/api/flood.py`, `backend/app/api/rainfall.py`, `backend/app/api/simulate.py`
- **Responsibilities:**
  - Radar-based precipitation nowcasting with optical flow tracking over 0 to 180 min
  - 2D simplified shallow water overland flow simulation using numerical flux transfer between adjacent grid cells based on water surface elevation (Z_dem + h_water)
  - Time-stepped coupled physics updates (5-minute timesteps)

### 3. Road Network Graph & Emergency Routing (Pair C)
- **Location:** `backend/app/models/road.py`, `backend/app/models/location.py`, `backend/app/api/roads.py`, `backend/app/api/route.py`, `navigate.py`
- **Responsibilities:**
  - Parsing and graph construction from OpenStreetMap data
  - Dynamic edge impedance adjustment: when flood depth exceeds vehicle thresholds (e.g. 0.15m for cars, 0.30m for emergency vehicles), edge travel speed is downgraded or severed
  - A* and Dijkstra resilient route calculation ensuring emergency vehicles bypass inundated corridors

### 4. Application Orchestrator & State Management
- **Location:** `backend/app/main.py`, `backend/app/engine_state.py`
- **Responsibilities:**
  - Lifecycle initialization and pre-warming of simulation models
  - Central singleton storage of active simulation runs and scenarios
  - REST and WebSocket interfaces for frontend dashboard integration

*Architecture analysis: 2026-09-11*
