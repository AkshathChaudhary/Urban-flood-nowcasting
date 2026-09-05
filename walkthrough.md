# Walkthrough: Pair A Drainage Model & API

We have completed the entire **Pair A** portion of the Urban Flood Nowcasting project:
1. The **`DrainageGraph`** hydraulic simulation model in [`backend/models/drainage.py`](file:///c:/Users/aksha/urbanFlood/backend/models/drainage.py).
2. The **FastAPI Drainage Router** in [`backend/api/drainage.py`](file:///c:/Users/aksha/urbanFlood/backend/api/drainage.py) mounted to [`backend/main.py`](file:///c:/Users/aksha/urbanFlood/backend/main.py).
3. The **Unit & Integration Test Suite** in [`tests/test_drainage.py`](file:///c:/Users/aksha/urbanFlood/tests/test_drainage.py).

---

## Test Verification Results

All 10 physics and API test cases passed:

```
Ran 10 tests in 0.126s
OK
```

- ✅ **Manning's Equation**: Exactly matches analytical theoretical flow rate.
- ✅ **Blockage Simulation**: Verified that 40% sediment/debris blockage reduces conveyance by exactly 40%.
- ✅ **Mass Conservation**: Water entering the system equals water retained + water discharged at outfalls + surcharge overflow.
- ✅ **Pair B Contract**: Successfully tested 200×200 grid surface water absorption and overflow re-injection.
- ✅ **REST Endpoints**: `/api/drainage/summary`, `/nodes`, `/edges`, `/node/{id}`, `/blockage` return valid GeoJSON and JSON schemas.
