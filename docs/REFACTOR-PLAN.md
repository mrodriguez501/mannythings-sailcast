# Refactor Plan: server/ and sailcast/

**Branch:** `refactor`  
**Goal:** Reduce code overhead without changing or losing functionality.  
**Priority scale:** 1 = highest, 5 = lowest. Tasks scored 1–3 are addressed now; 4–5 are noted for later.

---

## 1. server/

### 1.1 `app/main.py` — Priority: **2**
- **Unify root handler:** The `@sailcast_app.get("/")` is defined in two branches (`if STATIC_ICONS_DIR.exists()` vs `else`). Use a single `async def root()` and inside it check `(STATIC_DIR / "index.html").exists()` to return `FileResponse` or the JSON fallback. Removes ~8 lines and one duplicate handler.

### 1.2 `app/config.py` — Priority: **4** (deferred)
- **.env path:** Use `Path` instead of `os.path.join`. Style-only; no code saving. Address later.

### 1.3 `app/routes/report.py` — Priority: **2**
- **Alert mapping:** `_map_alert_from_feature` and `_map_alert_from_cached` differ only in `ends` key. Merge into a single `_map_alert(d, ends_key="ends")`. Removes ~12 lines.

### 1.4 `app/routes/forecast.py` — Priority: **2**
- **503 pattern:** All four data endpoints repeat `if data is None: raise HTTPException(503, …)`. Extract `_require_cached(data, detail)` helper. Removes ~8 lines.

### 1.5 `app/services/nws_service.py` — Priority: **4** (deferred)
- **Period parsing:** Minor; extracting `_pluck_period_keys` saves few lines and hurts readability. Address later.

### 1.6 `app/services/openai_service.py` — Priority: **5** (deferred)
- **Budget-exceeded return:** Only one call site today. Address if a second appears.

### 1.7 `app/services/marine_service.py` — Priority: **2**
- **Extract HTML parsing:** The ~25-line block that extracts forecast text from marine HTML → `_parse_marine_html(html)`. Reduces nesting, makes it testable.

### 1.8 `app/services/scheduler.py` — Priority: **4** (deferred)
- **Named unpacking:** Style-only readability tweak (`_, _` → `marine, tides`). Address later.

### 1.9 `app/services/budget_tracker.py` — Priority: **5** (deferred)
- **get_status helper:** Low gain. Address later.

### 1.10 `server/static/app.js` — Priority: **3**
- **setLoading / setErrorState:** Both iterate over elements. Extract `_setSectionStates(specs)` helper. ~15 lines saved.

---

## 2. sailcast/

### 2.1 `app/main.py` — Priority: **2**
- **Root handler:** Decouple `/` from icons dir existence. Single `root()` that checks `index.html` exists.

### 2.2 `app/api/report.py` — Priority: **5** (deferred)
- **Exception handling / boat_type:** Already clean. No change.

### 2.3 `app/api/report_adapter.py` — Priority: **1** (dead code removal)
- **Remove:** Imports server-only modules (`app.config`, `app.services.nws_service`); not included in sailcast `main.py`. Dead code.

### 2.4 `app/services/llm.py` — Priority: **5** (deferred)
- **Rate limit datetime:** Minor. Address later.

### 2.5 `app/services/weather.py` — Priority: **1**
- **NWS points + follow URL:** Both `get_points_forecast` and `get_hourly_forecast` duplicate the points→URL→fetch→parse pattern. Extract `_nws_points(client)` and `_forecast_from_points(client, points, url_key, keys)`. ~25 lines saved.

### 2.6 `app/services/retrieval.py` — Priority: **3**
- **Remove unused args:** `get_club_guidance(hourly, alerts)` → `get_club_guidance()`. Update call site in `report.py`.

### 2.7 `app/cache/hourly_cache.py` — Priority: **5** (deferred)
- No redundant code. No change.

### 2.8 `sailcast/app/static/app.js` — Priority: **3**
- **setSectionStates helper:** Same pattern as server. ~10 lines saved.

---

## 3. Summary table (scored)

| # | Area | Change | Priority | Lines saved |
|---|------|--------|----------|-------------|
| 1 | sailcast/report_adapter.py | Remove dead code | **1** | −101 (file) |
| 2 | sailcast/weather.py | Extract NWS points helpers | **1** | −25 |
| 3 | server/main.py | Single root() | **2** | −8 |
| 4 | server/report.py | Single _map_alert | **2** | −12 |
| 5 | server/forecast.py | _require_cached helper | **2** | −8 |
| 6 | server/marine_service.py | _parse_marine_html | **2** | −5 |
| 7 | sailcast/main.py | Single root() | **2** | −6 |
| 8 | server/static/app.js | setSectionStates helper | **3** | −15 |
| 9 | sailcast/retrieval.py | Remove unused args | **3** | −2 |
| 10 | sailcast/static/app.js | setSectionStates helper | **3** | −10 |
| — | server/config.py | Path-based .env load | **4** | 0 |
| — | server/nws_service.py | _pluck_period_keys | **4** | minor |
| — | server/scheduler.py | Named unpack | **4** | 0 |
| — | server/openai_service.py | Budget-exceeded helper | **5** | minor |
| — | server/budget_tracker.py | get_status helper | **5** | minor |

**Active (P1–P3):** ~190 lines removed. **Deferred (P4–P5):** noted for future.

---

## 4. Execution order

**Step-by-step: one change → test → approve → next.**

1. sailcast/report_adapter.py — remove (P1)
2. sailcast/weather.py — extract helpers (P1)
3. server/main.py — single root() (P2)
4. server/report.py — single _map_alert (P2)
5. server/forecast.py — _require_cached (P2)
6. server/marine_service.py — _parse_marine_html (P2)
7. sailcast/main.py — single root() (P2)
8. server/static/app.js — setSectionStates (P3)
9. sailcast/retrieval.py + report.py call site (P3)
10. sailcast/static/app.js — setSectionStates (P3)

---

## 5. Out of scope (no change in this refactor)

- Adding or removing API endpoints or response fields.
- Sharing a single frontend bundle between server and sailcast.
- Changing deploy scripts, systemd, or Apache config.
- Altering budget logic, pricing, or rate limits.
- Merging server and sailcast into one codebase.
