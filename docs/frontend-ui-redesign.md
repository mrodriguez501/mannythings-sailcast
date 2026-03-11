# Frontend UI Redesign Plan

## Current State

Three files make up the entire frontend, all in `server/static/`:

- **index.html** (79 lines) -- flat list of 7 sections, Pico CSS + Chart.js CDN
- **app.js** (531 lines) -- fetches `api/report` once/hour, renders each section
- **styles.css** (219 lines) -- Pico overrides, cards grid, alerts, accordion

The API returns a single JSON object with: `location`, `recommendation` (string), `hourly` (array), `alerts` (array), `marine_forecast` (object), `tides` (array), `forecast_3day` (array).

The OpenAI service already returns structured JSON with `safetyLevel` (SAFE/CAUTION/UNSAFE), `summary`, `advisory`, `keyConcerns` -- but `report.py` flattens it into a plain text `recommendation` string before sending to the frontend.

## Key Architectural Decisions

### 1. Expose structured AI data to the frontend

Currently `server/app/routes/report.py` collapses the OpenAI JSON into a single `recommendation` string. To power the Smart Sailing Advice card, we need to pass the structured fields through.

**Change:** Add a new `advice` object to the report response (alongside the existing `recommendation` string for backward compat):

```json
"advice": {
    "safetyLevel": "SAFE",
    "summary": "...",
    "advisory": "...",
    "keyConcerns": [...],
    "generatedAt": "..."
}
```

When OpenAI data is unavailable, the frontend computes a basic `safetyLevel` from wind/gust/alert data using the SCOW club rule thresholds:

| Condition | Result |
|-----------|--------|
| Any severe/extreme alert | **UNSAFE** (red) |
| Wind > 23 mph OR gust > 29 mph | **UNSAFE** (red) — exceeds daysailer max |
| Wind > 17 mph OR gust > 23 mph | **CAUTION** (yellow) — daysailer restrictions apply (reef, lagoon only, PFDs) |
| Wind ≤ 17 mph | **SAFE** (green) — no restrictions |

Reference: `server/app/data/rag/club_rules.md`
- **17 MPH** (15 kt): Daysailers must reef, stay in lagoon, all aboard wear PFDs
- **23 MPH** (20 kt): Daysailers shall not leave the dock
- **29 MPH** (25 kt): No boats (including cruisers) leave the dock

### 2. Client-side wind parsing for conditions cards

The first hourly period already has `windSpeed` (string like "14 mph"), `windGust`, `windDirection`, `temp`, `shortForecast`. Parse these in JS to populate the Current Conditions metric cards. No backend changes needed.

### 3. Time filter is JS-only

The time filter buttons (Now / 2hr / 6hr / Today / Tomorrow) will filter which hourly periods are visible in the Next Hours section and 24-hour cards. No API changes -- just slice the existing `hourly` array in JS.

## Backup Step

Before any edits:

- Copy `server/static/index.html` to `server/static/index_original.html`
- Copy `server/static/app.js` to `server/static/app_original.js`
- Copy `server/static/styles.css` to `server/static/styles_original.css`

## New Page Structure

```
+-----------------------------------------------+
| HEADER: SailCast / Location / Last updated     |
+-----------------------------------------------+
| WEATHER ALERTS (if any, always visible on top) |
+-----------------------------------------------+
| SMART SAILING ADVICE CARD                      |
| [status badge] [best window] [why bullets]     |
| [club rule checks] [confidence]                |
+-----------------------------------------------+
| CURRENT CONDITIONS (metric cards grid)         |
| Wind | Gust | Temp | Direction | Next Tide     |
+-----------------------------------------------+
| TIME FILTER: [Now] [2hr] [6hr] [Today] [Tmrw] |
+-----------------------------------------------+
| NEXT HOURS: wind bar chart + compact table     |
+-----------------------------------------------+
| TIDES: chart + next high/low summary           |
+-----------------------------------------------+
| DETAILS (collapsible accordion sections):      |
|   > 24-Hour Forecast Cards                     |
|   > Marine Forecast (ANZ535)                   |
|   > 3-Day Outlook                              |
|   > 24-Hour Wind Table                         |
+-----------------------------------------------+
| FOOTER                                         |
+-----------------------------------------------+
```

## Files to Modify

### A. `server/app/routes/report.py` -- expose structured AI advice

Add `advice` dict to the report response. Keep `recommendation` string for compat. When `summary_data` is a dict with `safetyLevel`, pass it through as `advice`.

### B. `server/static/index.html` -- restructure HTML sections

- **Header:** unchanged (add `last-fetch` into the header area)
- **Alerts section:** move above advice card (always visible if active)
- **New `#advice-card` section:** status badge, best window, why bullets, club checks, confidence
- **New `#conditions-grid` section:** 5 metric cards (wind, gust, temp, direction, next tide)
- **New `#time-filter` bar:** 5 filter buttons
- **Wind section:** keep wind chart + hourly table accordion (already has `<details>`)
- **Tides section:** keep tide chart, add `#tide-summary` (next high/low text)
- **New `#details-accordion`:** wrap the following in `<details>` elements:
  - 24-Hour Forecast Cards (the existing hour-cards grid)
  - Marine Forecast
  - 3-Day Forecast
  - (24-Hour Wind Table is already in an accordion)

### C. `server/static/app.js` -- new render functions

- **`renderAdviceCard(data)`** -- parse `data.advice` or fall back to computing safety from `data.hourly` + `data.alerts` using SCOW club rule thresholds (17/23/29 mph for wind, severe alerts)
- **`renderConditionsGrid(hourly, tides)`** -- populate the 5 metric cards from `hourly[0]` and the next tide event
- **`renderTideSummary(tides)`** -- find next High and Low from tides array, display as text
- **`applyTimeFilter(hours)`** -- filter hourly data to N hours, re-render wind chart and compact table
- Keep all existing render functions (`render24HourCards`, `renderAlerts`, `renderMarineForecast`, `renderHourly`, `renderForecast3day`, `renderWindChart`, `renderTideChart`) unchanged -- they just render into different DOM positions now

### D. `server/static/styles.css` -- new styles

- **Advice card:** `.advice-card` with colored left border (green/yellow/red based on safetyLevel), status badge pill, rule check list with checkmarks/X marks
- **Conditions grid:** `.conditions-grid` -- CSS grid of 5 small metric cards, responsive (3 cols desktop, 2 cols tablet, 1 col phone)
- **Time filter bar:** `.time-filter` -- flex row of pill buttons, active state highlighted
- **Accordion sections:** `.details-section` -- reuse the existing `.accordion-hourly` pattern for all collapsible sections
- **Metric card:** `.metric-card` with label (small muted) and value (large bold)

## How Collapsible Sections Work

All use native `<details>`/`<summary>` (already proven with the hourly wind accordion). The existing `.accordion-hourly` CSS pattern will be generalized to a `.collapsible` class:

```html
<details class="collapsible">
  <summary>24-Hour Forecast Cards</summary>
  <div id="hour-cards" class="hour-cards-grid"></div>
</details>
```

The existing render functions write into the same element IDs -- they don't care that they're inside a `<details>`.

## How Existing Data Is Preserved

- Every existing data source renders into the same element IDs as before
- No render functions are deleted
- The 24-hour cards, marine forecast, 3-day table, hourly wind table, tide chart, and wind chart all remain
- They simply move into collapsible `<details>` wrappers or stay top-level if they're high priority (wind chart, tide chart)

## Smart Sailing Advice Card Logic (client-side fallback)

When `data.advice.safetyLevel` is available from OpenAI, use it directly. Otherwise, compute from raw data using SCOW club rule thresholds:

```
parseFloat(windSpeed) -> mph value (NWS returns mph)

- Any severe/extreme alert              -> UNSAFE (red)
- wind > 23 mph OR gust > 29 mph        -> UNSAFE (red)   [daysailer max / cruiser max]
- wind > 17 mph OR gust > 23 mph        -> CAUTION (yellow) [daysailer restrictions]
- else                                   -> SAFE (green)
```

SCOW club rule reference (from `club_rules.md`):
- **17 MPH** (15 kt): Daysailers must reef, remain in lagoon, PFDs required; social sail limited to 5 people + second skipper
- **23 MPH** (20 kt): Daysailers shall not be taken from the docks
- **29 MPH** (25 kt): Cruising boats shall not be taken from the docks

**Best sailing window:** scan hourly periods for the longest consecutive stretch where wind is in SAFE range during daylight (6am-7pm). Display as "11:00 AM - 3:30 PM" or "No safe window today".

## Data Source Links in Details Section

Add reference links in the details accordion for the external NWS/NOAA sources:

- Digital forecast: `forecast.weather.gov/MapClick.php?...`
- Marine forecast: `forecast.weather.gov/shmrn.php?mz=anz535`
- Tide data: `tide.arthroinfo.org/tideshow.cgi?...`
- Local forecast: `forecast.weather.gov/MapClick.php?lat=38.85...`

These go as small linked text at the bottom of each collapsible section.

## Responsive Behavior

- **Desktop (>768px):** Conditions grid = 5 columns, advice card full width, time filter horizontal
- **Tablet (480-768px):** Conditions grid = 3 columns, same layout otherwise
- **Phone (<480px):** Conditions grid = 2 columns, time filter wraps, charts stack full-width
