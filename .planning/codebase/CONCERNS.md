# Codebase Concerns

**Analysis Date:** 2026-09-11

## Tech Debt

**Missing Integrated Frontend Dashboard:**
- Issue: Pre-hackathon development (Sep 1–11) produced an advanced backend and API service, but the frontend dashboard described in `README.md` ("Hackathon Day Sep 12–13: All 6 -> FRONTEND TOGETHER") has not yet been built.
- Impact: Users must interact via raw curl/Postman or CLI scripts (`navigate.py`, `run_any_corridor.py`) rather than a real-time GIS command center.
- Fix approach: Design and build a state-of-the-art interactive GIS dashboard using modern web UI technologies, dark glassmorphism styling, and `ui-ux-pro-max` design intelligence.

**Data Coupling and Memory Footprint:**
- Issue: Large 2D numerical grids (200x200 floats for elevation, depth, rain, velocity) over multiple timesteps are held in-memory in the singleton state.
- Impact: Scaling to larger spatial extents (e.g. 1000x1000 or full-city scale) without chunking or spatial indexing will lead to memory pressure.
- Fix approach: Implement quadtree / tile-based spatial partitioning for multi-resolution grid handling.

## Known Bugs & Edge Cases

**Coordinate Transforms across Projections:**
- Symptoms: Occasional slight offsets when mapping WGS84 GPS coordinates to local 10m grid cells near the perimeter.
- Workaround: Clamping row/col indices to `[0, GRID_ROWS-1]` and `[0, GRID_COLS-1]`.
- Root cause: Planar approximation of geographic degrees at variable latitudes.

**Isolated Island Nodes during Severe Inundation:**
- Symptoms: When all surrounding road edges exceed vehicle clearance depth (e.g. >0.30m), A* graph search fails to find a path.
- Current mitigation: Emergency routing falls back to the least-penalized traversable corridor and annotates hazard warnings.

## Security Considerations

**Unrestricted CORS & Public API:**
- Risk: Currently configured with open CORS regex `r"https?://.*"` for local testing.
- Recommendation: Restrict CORS origins in production deployments and implement API token authorization for sensitive municipal pump control triggers.

## Performance Bottlenecks

**Coupled Simulation Step Compute Time:**
- Problem: Running full 2D hydrodynamic flow redistribution across 40,000 cells for multiple timesteps can take several seconds.
- Current mitigation: Vectorized NumPy array slicing and pre-warming in `lifespan` handler.
- Recommendation: Consider Numba JIT compilation or WebGPU/OpenCL acceleration for real-time sub-second nowcasting.

*Codebase concerns analysis: 2026-09-11*
