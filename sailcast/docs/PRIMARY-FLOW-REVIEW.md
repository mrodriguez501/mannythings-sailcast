# Review: Implementation vs Primary Directive

**Primary directive (updated-README.md §2):**  
Browser → GET / → Static HTML → fetch /api/report every hour → (1) weather, (2) club knowledge, (3) LLM report → JSON (raw forecast + recommendation) → Rendered sailing report.

---

## What Already Matches

| Flow step | Implementation | Status |
|-----------|----------------|--------|
| GET / | `main.py`: serves `static/index.html` | ✓ |
| fetch every hour | `app.js`: `REPORT_URL = '/api/report'`, `REFRESH_INTERVAL_MS` | ✓ (currently 30 min; doc says hour) |
| /api/report | `report.py`: `get_all_weather_data()` → `get_club_guidance()` → `generate_report()` | ✓ |
| JSON: raw forecast + recommendation | Response has `hourly`, `forecast_3day`, `alerts`, `tides`, `recommendation`, etc. | ✓ |
| Rendered report | `app.js` renders all sections from one report payload | ✓ |

---

## Noise (Not in Primary Flow)

1. **`GET /api/forecast`** – Returns only hourly forecast. The frontend never calls it; it only calls `/api/report`. So this endpoint is unused surface area. **Simplify:** remove it and the forecast router.
2. **`GET /health`** – Not in the user flow; needed for Lightsail/CI. Keep for infra but treat as out-of-scope for the “user-facing” flow.
3. **Refresh interval** – README says “every hour”; app uses 30 minutes. **Simplify:** align to one rule (e.g. “every hour” in both README and frontend, or document “every 30 minutes” in README).

---

## Simplifying Changes Applied

- **Remove `/api/forecast`** and `app/api/forecast.py`; drop the forecast router from `main.py`. Single user-facing API: `/api/report`.
- **Align refresh with directive:** set frontend refresh to 1 hour (README says “every hour”).
- **Docs:** `main.py` and README list only the flow-relevant surface: `/`, `/api/report`; `/health` noted as infra-only.

Anything else (cache, BOAT_TYPE, env, multiple static mounts) is implementation detail that supports the flow and is not “noise” as long as the single flow above is the only user-facing contract.
