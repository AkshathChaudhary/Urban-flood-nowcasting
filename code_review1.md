# Pair B Flood Engine — Principal Code Review

**Scope**: [`flood_engine.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py), [`surface_flow.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/surface_flow.py), [`provider.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/data/rainfall/provider.py), [`engine_state.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine_state.py), [`api/flood.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/api/flood.py), [`api/simulate.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/api/simulate.py), [`test_flood_engine.py`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/tests/test_flood_engine.py)

---

## 🚨 Critical Bugs & Logic Flaws

### B1. Mass Conservation Violation in `apply_rainfall` — Double-Counting Rain on Water Bodies

[`flood_engine.py:289-301`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L289-L301)

```python
# Line 290: adds net_addition_m to ALL cells including water body cells
self.water_depth += net_addition_m

# Line 299-301: ALSO adds the same water to river_storage_m3
if np.any(self.water_body_mask):
    direct_rain_on_river = float(np.sum(net_addition_m[self.water_body_mask]) * self.cell_area)
    self.river_storage_m3 += direct_rain_on_river
```

The water is added to `self.water_depth` on water body cells at L290, then `drain_water_bodies` at L584 overwrites `self.water_depth[water_body_mask]` with the depth derived from `river_storage_m3`. The rain-on-river volume is accounted for in `river_storage_m3` at L301. However, between L290 and the eventual call to `drain_water_bodies`, `calculate_surface_flow` at L334 reads `routed_depth[self.water_body_mask]` and **again** adds that volume to `river_storage_m3`. This means rainfall deposited on water body cells gets added to `river_storage_m3` **twice**: once explicitly at L301, and once via L334 when the routing output still carries that depth on water-body cells.

**Impact**: Inflates `river_storage_m3`, triggers premature bankfull overflow, produces excess flood depth on bank cells. The error compounds each timestep.

**Fix**: Either (a) zero out `net_addition_m` on water body cells before adding to `self.water_depth` at L290 and rely solely on the L301 river storage path, or (b) remove the L299-301 block entirely and let `calculate_surface_flow` handle the transfer:

```python
# Option (a): zero water body contribution from the grid update
net_addition_m[self.water_body_mask] = 0.0
self.water_depth += net_addition_m

# Then the L299-301 block correctly adds the gross_rain_m on water bodies to river storage:
if np.any(self.water_body_mask):
    direct_rain_on_river = float(np.sum(gross_rain_m[self.water_body_mask]) * self.cell_area)
    self.river_storage_m3 += direct_rain_on_river
```

---

### B2. `calculate_surface_flow` Silently Discards Overland Water That Routes Onto Channel Cells

[`flood_engine.py:322-338`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L322-L338)

```python
land_water = np.where(~self.water_body_mask, self.water_depth, 0.0)
routed_depth, boundary_outflow = route_surface_water(
    elevation=self.dem, water_depth=land_water, ...
)
# L334: captures routed water that landed on channel cells
runoff_into_channel = float(np.sum(routed_depth[self.water_body_mask]) * self.cell_area)
self.river_storage_m3 += runoff_into_channel
# L338: only land cells updated
self.water_depth[~self.water_body_mask] = routed_depth[~self.water_body_mask]
```

The `route_surface_water` function receives `land_water` (zero on water body cells), but routes water based on `elevation + water_depth`. Cells receiving inflow from land neighbors at water-body positions will have non-zero `routed_depth[water_body_mask]`, which is counted into `river_storage_m3` — good.

**But the problem**: `routed_depth` on water body cells is discarded from the grid (L338 only writes land). So the volume transfer at L334 is the *only* accounting. However, `route_surface_water` computed the outflow **from the source cell's depth**. The source land cell's depth was reduced by the outflow amount inside `route_surface_water`. But the destination (water body cell) gets the inflow added to `routed_depth`. When L338 only updates land cells from `routed_depth`, the source cell correctly has reduced depth, and the destination water-body cell's inflow is captured by L334. This is actually **correct** in isolation — but it breaks when combined with B1 above.

---

### B3. `_spill_river_overflow` Weir Fallback Division by Near-Zero

[`flood_engine.py:477-481`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L477-L481)

```python
p20 = float(np.percentile(bank_elev, 20))
low_bank_mask = bank_elev <= p20
min_z = float(np.min(bank_elev))
inv_dist = np.where(low_bank_mask, 1.0 / (bank_elev - min_z + 0.1), 0.0)
```

When `p20 == min_z` (common on flat terrain or terraces), **all** `low_bank_mask` cells have `bank_elev == min_z`, yielding `inv_dist = 1.0 / 0.1` uniformly, which then normalizes to equal weights. This is numerically safe but physically wrong — it equally distributes overflow across 20% of bank cells regardless of hydraulic connectivity.

More critically, if the river bank mask contains only 1-4 cells (narrow channel edge), `np.percentile(bank_elev, 20)` on a tiny array can produce pathological results, and dividing `overflow_vol_m3` over 1-2 cells creates unrealistically large point depths.

---

### B4. `drain_water_bodies` Missing Storm Surge Volume from Mass Balance

[`flood_engine.py:549-589`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L549-L589)

`apply_storm_surge` adds water to `river_bank_mask` cells (L651), incrementing `total_surge_intrusion_m3`. But the mass balance equations in the test at [`test_flood_engine.py:165-175`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/tests/test_flood_engine.py#L165-L175) do **not** account for `total_surge_intrusion_m3`, `total_pumped_volume_m3`, `total_pond_storage_inflow_m3`, or `total_pond_spill_m3`:

```python
expected_surface = (
    engine.total_rain_volume_m3
    + engine.total_upstream_inflow_m3
    + engine.initial_river_storage_m3
    - engine.total_infiltrated_volume_m3
    - engine.total_absorbed_volume_m3
    + engine.total_overflow_volume_m3
    - engine.total_river_drain_volume_m3
)
```

This equation will fail (and does fail silently by never being exercised with non-zero storm surge) when storm surge, pump stations, or retention ponds are active. The mass conservation "proof" in tests is incomplete.

---

### B5. `run_forecast` Capture Horizon Tolerance Is dt-Dependent and Fragile

[`flood_engine.py:836`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L836)

```python
if abs(current_time_min - target_min) < (dt / 120.0):
```

With `dt = 300`, the tolerance is `300/120 = 2.5 minutes`. With `dt = 60` (valid per the schema `ge=60`), tolerance shrinks to `0.5 minutes`. Since `current_time_min` advances in increments of `dt/60`, whether a capture aligns within tolerance depends on the interplay of `dt` and `target_min`. For `dt = 120` (2 min steps) and `target_min = 30`: step 15 yields `current_time_min = 30.0`, tolerance is `1.0`, match succeeds. But for `dt = 180` (3 min steps): step 10 yields `30.0`, tolerance is `1.5`, match succeeds. For `dt = 420` (7 min steps): step 4 yields `28.0`, step 5 yields `35.0`, tolerance is `3.5` — 28.0 is 2.0 away from 30 (within tolerance), so it works. But many `dt` values cause step timestamps to straddle a horizon with residuals larger than `dt/120`, resulting in silently missed captures. The L841-843 fallback fills with the final depth — which may be minutes to tens of minutes stale for early horizons.

**Fix**: Use a robust `>=` threshold with a flag:

```python
if next_capture_idx is not None and next_capture_idx < len(capture_horizons):
    target_min = capture_horizons[next_capture_idx]
    if current_time_min >= target_min - 1e-6:
        self.forecast_grids[target_min] = self.water_depth.copy()
        next_capture_idx += 1
```

---

### B6. `engine_state.get_engine` Blocks Async Event Loop on Startup

[`engine_state.py:23-30`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine_state.py#L23-L30)

```python
def get_engine() -> FloodEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = FloodEngine.from_default_data()
        _engine_instance.run_forecast(scenario=_current_scenario, horizon_minutes=180)
    return _engine_instance
```

`run_forecast` is a 36-step (180 min / 5 min) compute-intensive loop. When called from [`main.py:28`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/main.py#L28) inside the `async def lifespan` context manager, it blocks the uvicorn async event loop. For a 200×200 grid this is tolerable (~1-2s), but at any larger grid size or with drainage graph attached, it will stall the ASGI server during startup and potentially trigger health check timeouts in orchestrators.

Additionally, `get_engine()` is not thread-safe. Two concurrent API requests hitting it before initialization completes will race on `_engine_instance`, potentially creating two engines or returning a partially initialized one.

---

## 📉 Performance & Resource Optimization

### P1. `route_surface_water` 8-Direction Slope Computation: O(8×N²) Repeated Per Sub-Pass

[`surface_flow.py:143-167`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/surface_flow.py#L143-L167)

Each sub-pass allocates a `(8, rows, cols)` float32 array (`slopes`) plus another `(8, rows, cols)` float32 array (`outflow_grid`). For a 200×200 grid: `8 × 200 × 200 × 4 bytes × 2 arrays = 5.12 MB` allocated and GC'd **per sub-pass**.

With `sub_passes = 4`, this is ~20 MB of transient allocations per timestep, repeated 36 times per forecast = ~720 MB of GC churn per `run_forecast` call.

**Optimization**: Pre-allocate `slopes` and `outflow_grid` outside the sub-pass loop and reuse via `.fill(0)`:

```python
slopes = np.full((8, rows, cols), -np.inf, dtype=np.float32)
outflow_grid = np.zeros((8, rows, cols), dtype=np.float32)

for _ in range(sub_passes):
    slopes.fill(-np.inf)
    outflow_grid.fill(0.0)
    # ... rest of loop body unchanged
```

---

### P2. `route_surface_water` MDD Branch Allocates Masked Arrays in Inner Loop

[`surface_flow.py:211-219`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/surface_flow.py#L211-L219)

```python
for k in range(8):
    mask_steep_k = steep_mask & (best_dir == k) & (flux_depth > 0.0)
    outflow_grid[k, mask_steep_k] = flux_depth[mask_steep_k]

    if np.any(gentle_mask):
        k_fraction = pos_slopes[k, gentle_mask] / sum_pos_slopes[gentle_mask]
        outflow_grid[k, gentle_mask] = (flux_depth[gentle_mask] * k_fraction).astype(np.float32)
```

This creates 3 boolean mask arrays per direction × 8 directions × 4 sub-passes = 96 boolean allocations of size (200, 200). The `np.any(gentle_mask)` check is also repeated 8 times per sub-pass when it's invariant within the sub-pass.

**Optimization**: Hoist the `np.any(gentle_mask)` check, and vectorize the steep direction assignment without the inner loop:

```python
has_gentle = np.any(gentle_mask)

# Vectorized steep assignment: for each of the 8 directions, select cells
for k in range(8):
    steep_k = steep_mask & (best_dir == k)
    outflow_grid[k] = np.where(steep_k & (flux_depth > 0.0), flux_depth, 0.0)

    if has_gentle:
        safe_sum = np.where(sum_pos_slopes > 1e-6, sum_pos_slopes, 1.0)
        k_frac = pos_slopes[k] / safe_sum
        outflow_grid[k] += np.where(gentle_mask, flux_depth * k_frac, 0.0)
```

This eliminates all fancy-indexed temporaries.

---

### P3. `_spill_river_overflow` Recomputes `np.mean(self.dem[self.water_body_mask])` Every Timestep

[`flood_engine.py:457`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L457)

The river bed elevation is a static property of the DEM. Computing `np.mean(self.dem[self.water_body_mask])` every timestep that overflow occurs is wasteful masked-array computation.

**Fix**: Precompute in `initialize()` and cache as `self._river_bed_elev`.

---

### P4. `FloodGridResponse.depth_grid` Serializes 200×200 Float Grid as `List[List[float]]`

[`api/flood.py:82`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/api/flood.py#L82)

```python
depth_grid=np.round(grid, 3).tolist(),
```

This converts 40,000 floats into a nested Python list-of-lists, then JSON-serializes each individually. The response payload is ~800KB+ of JSON text. For a dashboard polling every few seconds, this is bandwidth-catastrophic.

**Recommendation**: Return a base64-encoded binary blob (e.g., `np.save` to buffer → base64) or use a more compact serialization (MessagePack, CBOR). At minimum, flatten to `List[float]` to save ~200KB of bracket overhead.

---

### P5. `compute_d8_flow_directions` Is Called Twice on Construction

[`flood_engine.py:201-202`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L201-L202)

```python
self.flow_directions = compute_d8_flow_directions(self.dem, self.cell_size)
self.sinks_mask = identify_sinks(self.dem, self.flow_directions, self.cell_size)
```

`identify_sinks` receives `flow_directions` and simply returns `flow_directions == -1`. But if `flow_directions is None`, it recomputes D8 internally. Here it's passed, so no double-compute. **However**, `flow_directions` and `sinks_mask` are computed in `initialize()`, which is called from `__init__` at L195. If `from_default_data` or user code ever calls `initialize()` again, these are recomputed — this is intentional by design (reset), but `compute_d8_flow_directions` on the DEM is expensive and the DEM never changes. Consider memoizing the flow directions with a DEM hash.

---

## 🛡️ Security & Resilience

### S1. `LiveRainfallProvider` and `HistoricalRainfallProvider` — Unvalidated URL Construction

[`provider.py:99`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/data/rainfall/provider.py#L99), [`provider.py:157-162`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/data/rainfall/provider.py#L157-L162)

```python
url = f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}&current=precipitation"
```

`self.lat` and `self.lon` originate from the `SimulateRequest` Pydantic model, which validates only `ge=18.0, le=20.0` and `ge=72.0, le=74.0`. This is fine for Mumbai-scoped use. But if these constraints are relaxed, or if `date_str` (which is `Optional[str]` with no regex validation) is injected with URL-encoded characters, the `urllib.request.urlopen` call could hit unexpected URLs. This is low-severity because it's hitting a trusted API, but `date_str` should have a `pattern=r"^\d{4}-\d{2}-\d{2}$"` Pydantic field validator.

---

### S2. `api/simulate.py` — Blanket `except Exception` Swallows All Errors

[`simulate.py:68-69`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/api/simulate.py#L68-L69)

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")
```

This catches `KeyboardInterrupt`, `SystemExit`, `MemoryError` — all of which should propagate. Use `except (ValueError, RuntimeError, IOError)` or at minimum `except Exception` with a re-raise for `SystemExit`/`KeyboardInterrupt` (which are `BaseException` subclasses in Python 3, so this is technically safe — but `MemoryError` is still `Exception`).

More importantly, `str(e)` may leak internal stack trace details or filesystem paths to the API consumer in production.

---

### S3. CORS `allow_origins=["*"]` in Production

[`main.py:43-44`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/main.py#L43-L44)

Wildcard CORS origin with `allow_credentials=True` is a browser security anti-pattern. If credentials (cookies, auth headers) are ever added, browsers will reject the response. Either drop `allow_credentials=True` or restrict origins to the actual frontend domain.

---

### S4. `get_engine()` Global Singleton — No Concurrent Request Safety

[`engine_state.py:19-30`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine_state.py#L19-L30)

The `/api/simulate` endpoint mutates `engine.rainfall_provider` and calls `engine.run_forecast()` which calls `engine.reset_state()`, zeroing all water depth and counters. If two `/api/simulate` POST requests arrive concurrently (uvicorn worker pool), one will corrupt the other's simulation mid-run. The `GET` endpoints will also return partially-reset data during a simulation.

**Minimum fix**: Use `threading.Lock` around `run_forecast` and `set_engine`. Proper fix: instantiate a fresh `FloodEngine` per simulation request instead of mutating the shared singleton.

---

## 🧱 Clean Architecture & Maintainability

### A1. `FloodEngine.__init__` Is a 200-Line God Constructor

[`flood_engine.py:49-196`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L49-L196)

20 constructor parameters, with deeply coupled terrain initialization, mask computation, soil model setup, and boundary condition configuration all inlined. This violates SRP and makes unit testing individual subsystems (e.g., soil model, retention ponds, pump stations) impossible without constructing the entire engine.

**Recommendation**: Extract into dataclass configurations:

```python
@dataclass
class TerrainConfig:
    dem: np.ndarray
    imperviousness: Optional[np.ndarray] = None
    infiltration: Optional[np.ndarray] = None
    water_body_mask: Optional[np.ndarray] = None

@dataclass
class BoundaryConfig:
    boundary_condition: str = "closed"
    upstream_river_inflow_m3_s: float = 0.0
    tidal_lock: bool = False
    ...
```

---

### A2. `drainage_graph` Interface Relies on `hasattr` Duck Typing

[`flood_engine.py:351-401`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/app/engine/flood_engine.py#L351-L401)

```python
if self.drainage_graph is None or not hasattr(self.drainage_graph, "absorb_surface_water"):
    ...
if hasattr(self.drainage_graph, "set_river_submergence"):
    ...
if hasattr(self.drainage_graph, "get_node_cell"):
    ...
elif hasattr(self.drainage_graph, "get_node_grid_position"):
    ...
```

Five different `hasattr` probes scatter the Pair A interface contract across the codebase with no formal definition. Any Pair A refactor silently breaks Pair B with no type checker or test catching it.

**Recommendation**: Define a `Protocol` (PEP 544):

```python
from typing import Protocol

class DrainageInterface(Protocol):
    def absorb_surface_water(self, depth_grid: np.ndarray, dt: float) -> np.ndarray: ...
    def compute_overflow(self) -> Dict[str, float]: ...
    def get_node_cell(self, node_id: str) -> Tuple[int, int]: ...
    def set_river_submergence(self, stage_m: float, depth_grid: np.ndarray) -> None: ...
```

---

### A3. `engine_state.py` — Module-Level Mutable Global State

The entire simulation state is managed via module-global `_engine_instance` and `_current_scenario`. This makes testing require monkeypatching, prevents parallel test execution, and creates implicit coupling between API endpoints. Use FastAPI dependency injection (`Depends(get_engine)`) with a proper lifecycle-managed singleton.

---

### A4. Test Mass Conservation Equation Is Incomplete and Passes by Accident

[`test_flood_engine.py:165-175`](file:///Users/minim/PycharmProjects/sih26.1/Urban-flood-nowcasting/backend/tests/test_flood_engine.py#L165-L175)

The mass balance equation omits `total_surge_intrusion_m3`, `total_pumped_volume_m3`, `retention_pond_storage_m3`, `total_pond_storage_inflow_m3`, `total_river_overflow_m3`, and `total_boundary_outflow_m3`. It only passes because those features are not activated in the default test fixture. Any test adding pump stations, storm surge, or retention ponds will expose the gap. The correct equation is:

```python
surface_water = (
    rain + upstream_inflow + initial_river_storage + sewer_overflow + surge_intrusion
    - infiltrated - absorbed - river_drain - pumped - boundary_outflow
    - retention_pond_storage
)
```

---

## 🛠️ Refactored Recommendations

### R1. Fix Mass Conservation Violation (B1)

```diff
 # flood_engine.py — apply_rainfall()
 
     net_addition_m = np.maximum(gross_rain_m - actual_infil_m, 0.0)
 
-    # Update grid state
-    self.water_depth += net_addition_m
+    # Track direct rain on open water → river storage (before grid update)
+    if np.any(self.water_body_mask):
+        direct_rain_on_river = float(
+            np.sum(net_addition_m[self.water_body_mask]) * self.cell_area
+        )
+        self.river_storage_m3 += direct_rain_on_river
+
+    # Zero out water body contribution from grid (channel stage set by drain_water_bodies)
+    net_addition_m_land = net_addition_m.copy()
+    net_addition_m_land[self.water_body_mask] = 0.0
+
+    # Update grid state (land cells only)
+    self.water_depth += net_addition_m_land
     self.cumulative_rain_m += gross_rain_m
     self.cumulative_infiltrated_m += actual_infil_m
 
     self.total_rain_volume_m3 += float(np.sum(gross_rain_m) * self.cell_area)
     self.total_infiltrated_volume_m3 += float(np.sum(actual_infil_m) * self.cell_area)
 
-    if np.any(self.water_body_mask):
-        direct_rain_on_river = float(np.sum(net_addition_m[self.water_body_mask]) * self.cell_area)
-        self.river_storage_m3 += direct_rain_on_river
-
-    return net_addition_m
+    return net_addition_m_land
```

---

### R2. Robust Horizon Capture (B5)

```diff
 # flood_engine.py — run_forecast()
 
         for step in range(1, total_steps + 1):
             current_time_min = (step * dt) / 60.0
             ...
             self.simulate_timestep(...)
 
-            if next_capture_idx is not None and next_capture_idx < len(capture_horizons):
-                target_min = capture_horizons[next_capture_idx]
-                if abs(current_time_min - target_min) < (dt / 120.0):
-                    self.forecast_grids[target_min] = self.water_depth.copy()
-                    next_capture_idx += 1
+            # Capture all horizons whose target time has been reached or passed
+            while (
+                next_capture_idx is not None
+                and next_capture_idx < len(capture_horizons)
+                and current_time_min >= capture_horizons[next_capture_idx] - 1e-9
+            ):
+                target_min = capture_horizons[next_capture_idx]
+                self.forecast_grids[target_min] = self.water_depth.copy()
+                next_capture_idx += 1
```

This uses a `while` loop so that if `dt` is large enough to skip past multiple horizons in a single step, all of them are captured at the closest available time.

---

### R3. Pre-Allocate Routing Buffers (P1)

```diff
 # surface_flow.py — route_surface_water()
 
+    # Pre-allocate reusable buffers (avoids ~5 MB GC churn per sub-pass)
+    slopes = np.empty((8, rows, cols), dtype=np.float32)
+    outflow_grid = np.empty((8, rows, cols), dtype=np.float32)
+    inflow = np.empty((rows, cols), dtype=np.float32)
+
     for _ in range(sub_passes):
+        slopes.fill(-np.inf)
+        outflow_grid.fill(0.0)
+        inflow.fill(0.0)
         head = elevation + depth
-        slopes = np.full((8, rows, cols), -np.inf, dtype=np.float32)
         ...
-        outflow_grid = np.zeros((8, rows, cols), dtype=np.float32)
         ...
-        inflow = np.zeros((rows, cols), dtype=np.float32)
```

---

### R4. Thread-Safe Engine State (S4)

```diff
 # engine_state.py
 
+import threading
+
+_engine_lock = threading.Lock()
 _engine_instance: Optional[FloodEngine] = None
 _current_scenario: str = "moderate"
 
 
 def get_engine() -> FloodEngine:
     global _engine_instance
-    if _engine_instance is None:
-        _engine_instance = FloodEngine.from_default_data()
-        _engine_instance.run_forecast(scenario=_current_scenario, horizon_minutes=180)
+    with _engine_lock:
+        if _engine_instance is None:
+            _engine_instance = FloodEngine.from_default_data()
+            _engine_instance.run_forecast(scenario=_current_scenario, horizon_minutes=180)
     return _engine_instance
```

---

### R5. Cache Static River Bed Elevation (P3)

```diff
 # flood_engine.py — initialize()
 
     self.river_bankfull_capacity_m3 = max(
         n_water_cells * self.cell_area * BANKFULL_DEPTH_M, 1.0
     )
+    # Cache static river bed mean elevation
+    if np.any(self.water_body_mask):
+        self._river_bed_elev = float(np.mean(self.dem[self.water_body_mask]))
+    else:
+        self._river_bed_elev = float(np.min(self.dem))
 
 # flood_engine.py — _spill_river_overflow()
 
-    if np.any(self.water_body_mask):
-        river_bed_elev = float(np.mean(self.dem[self.water_body_mask]))
-    else:
-        river_bed_elev = float(np.min(self.dem))
+    river_bed_elev = self._river_bed_elev
```

---

### R6. Validate `date_str` Format (S1)

```diff
 # models/flood.py
 
+from pydantic import Field, field_validator
+
 class SimulateRequest(BaseModel):
     ...
-    date_str: Optional[str] = Field(default="2023-07-26", description="YYYY-MM-DD for historical query")
+    date_str: Optional[str] = Field(
+        default="2023-07-26",
+        description="YYYY-MM-DD for historical query",
+        pattern=r"^\d{4}-\d{2}-\d{2}$"
+    )
```
