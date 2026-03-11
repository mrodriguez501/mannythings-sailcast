# Refactor Summary

**Branch:** `refactor`

## What was done

### Phase 1: Code optimization (P1–P3)
- **server/main.py** — Single `root()` handler instead of two branches.
- **server/routes/report.py** — Single `_map_alert(d, ends_key)` replaces two mappers.
- **server/routes/forecast.py** — `_require_cached()` helper replaces four repeated if/raise blocks.
- **server/services/marine_service.py** — `_parse_marine_html()` extracted; improved to strip `<script>`/`<style>` blocks and handle all NWS period labels (THIS AFTERNOON, THIS EVENING, etc.).
- **server/static/app.js** — `_applySectionStates` + `_hideCanvas` helpers reduce repetition in `setLoading`/`setErrorState`.

### Phase 2: Retire sailcast/ (eliminate duplication)
- **`sailcast/`** was a duplicate app (same features, different architecture) that caused code to be maintained in two places.
- **`sailcast/static-icons/`** → moved to **`server/static-icons/`** (weather icon SVGs used by the frontend).
- **`sailcast/rag/`** → moved to **`server/app/data/rag/`** (club reference docs: bylaws, SIFs, skipper agreement, sailing-weather-rules).
- **`server/app/main.py`** — `STATIC_ICONS_DIR` now points to `server/static-icons` (no cross-directory dependency).
- **`sailcast/`** deleted entirely.

### Deferred (P4–P5, address later)
- `server/config.py` — Use `Path` instead of `os.path.join` for `.env` loading (style only).
- `server/nws_service.py` — Optional `_pluck_period_keys` helper (minor).
- `server/scheduler.py` — Named unpack for `asyncio.gather` result (readability only).
- `server/openai_service.py` — Budget-exceeded response helper (one call site).
- `server/budget_tracker.py` — `get_status` dict builder helper (low gain).
