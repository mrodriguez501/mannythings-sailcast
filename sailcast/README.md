# SailCast

Hourly sailing forecast and recommendation: **static HTML (Pico CSS)** frontend and **FastAPI** backend. Data from NWS (weather, marine, alerts) and NOAA (tides). Optional LLM-generated sailing recommendation.

## Features

- **Recommendation** – LLM-generated sailing summary (or fallback when no API key); uses club rules (RAG-lite) and weather.
- **24 hours forecast** – Cards with date/time, conditions, wind (speed + direction), and tide for the next 24 hours.
- **Weather alerts** – NWS active alerts in USWDS-style boxes (info/warning/error/emergency).
- **NWS Marine forecast** – Text-only marine zone forecast (e.g. ANZ535, Tidal Potomac) from marine.weather.gov.
- **2-day hourly wind** – Table of hourly temp, wind, gusts, conditions.
- **2-day tide predictions** – Chart.js line chart: tide height (ft) vs time; red line, high/low points.
- **3-day forecast** – Period-based forecast table at bottom of page.
- **Loading / no data / error** – Each section shows Loading…, No data available, or Error (with message) as appropriate.

## Run locally

```bash
cd sailcast
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**. The page fetches `/api/report` and refreshes every hour.

## Endpoints (primary flow)

| Endpoint | Description |
|----------|-------------|
| `GET /` | Static HTML frontend |
| `GET /api/report` | Full report: location, 3-day + hourly + alerts + marine + tides + recommendation (cached per UTC hour when enabled) |
| `GET /health` | Health check (for infra/CI) |

## Config

Copy `.env.example` to `.env`. Optional:

| Variable | Description |
|----------|-------------|
| `LOCATION_LAT`, `LOCATION_LON` | NWS point (default 38.8512, -77.0402) |
| `LOCATION_NAME` | Display name (default DCA / Washington DC) |
| `NOAA_TIDE_STATION` | NOAA tide station ID (default 8594900) |
| `MARINE_ZONE_ID` | NWS marine zone (default ANZ535) |
| `OPENAI_API_KEY` | For LLM recommendation; if unset, fallback text is used |
| `OPENAI_MODEL` | Model name (default gpt-4o-mini) |
| `ENV=dev` or `DISABLE_REPORT_CACHE=1` | Disable report cache (e.g. for local dev) |

## Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, httpx.
- **Frontend:** Static HTML, Pico CSS, vanilla JS, Chart.js (tide chart).
- **Data:** NWS (points, alerts, marine zone), NOAA CO-OPS (tides).

## Docker

```bash
docker build -t sailcast .
docker run -p 8000:8000 --env-file .env sailcast
```

## Repository structure

```
sailcast/
├── app/
│   ├── main.py           # FastAPI app, static mount, routes
│   ├── api/              # forecast, report
│   ├── services/         # weather, retrieval, llm
│   ├── cache/            # hourly report cache (optional)
│   └── static/           # index.html, app.js, styles.css
├── rag/                  # club_rules.md, other knowledge
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```
