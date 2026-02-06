# SailCast

**Coastal sailing safety advisories powered by NWS data and AI.**

SailCast is a web application that integrates National Weather Service (NWS) forecast data with OpenAI-powered analysis to provide actionable sailing safety advisories for the Potomac River near KDCA.

- **Live site**: [mannythings.us/sailcast](https://mannythings.us/sailcast) *(after deployment)*
- **White paper**: [`docs/SailCast_WhitePaper.md`](docs/SailCast_WhitePaper.md)

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Local Development Setup](#local-development-setup)
5. [Running Locally](#running-locally)
6. [API Endpoints](#api-endpoints)
7. [Configuration Reference](#configuration-reference)
8. [AWS Lightsail Deployment](#aws-lightsail-deployment)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React 19 + Vite 6 | UI for forecast display |
| Backend | Python 3.11+ / FastAPI | REST API, data processing |
| AI Engine | OpenAI Python SDK | Weather summaries, advisories |
| HTTP Client | httpx | Async NWS API calls |
| Scheduler | APScheduler | Hourly data refresh |
| Weather Data | NWS API | Official forecast source |
| Hosting | AWS Lightsail | Production server |

---

## Project Structure

```
mannythings-sailcast/
├── client/                        # React frontend (Vite)
│   ├── public/
│   │   └── sailcast-icon.svg
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx         # App header with branding
│   │   │   ├── AISummary.jsx      # AI-generated summary card
│   │   │   ├── WindForecast.jsx   # 24-hour wind table
│   │   │   ├── SevenDayOutlook.jsx# 7-day forecast cards
│   │   │   ├── Advisories.jsx     # Active NWS alerts
│   │   │   └── Footer.jsx         # Data attribution footer
│   │   ├── services/
│   │   │   └── api.js             # API client functions
│   │   ├── App.jsx                # Main app component
│   │   ├── App.css                # Global styles
│   │   └── main.jsx               # React entry point
│   ├── index.html
│   ├── vite.config.js             # Vite config with API proxy
│   └── package.json
├── server/                        # Python FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app entry + lifespan
│   │   ├── config.py              # Environment config loader
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   └── forecast.py        # /api/forecast/* endpoints
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── nws_service.py     # NWS API fetch + parse + cache
│   │   │   ├── openai_service.py  # OpenAI prompt + summary gen
│   │   │   └── scheduler.py       # APScheduler hourly jobs
│   │   └── data/
│   │       └── club_rules.md      # Sailing club safety rules
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Environment template
├── docs/
│   └── SailCast_WhitePaper.md     # Project white paper
├── deploy.sh                      # AWS Lightsail deploy script
├── .env.example                   # Root environment template
├── .gitignore
└── README.md                      # <-- You are here
```

---

## Prerequisites

Ensure you have the following installed on your local machine:

| Tool | Version | Check Command |
|------|---------|---------------|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| npm | 10+ | `npm --version` |
| Git | 2.x | `git --version` |

You will also need:
- An **OpenAI API key** with available tokens ([platform.openai.com](https://platform.openai.com/api-keys))

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/mrodriguez501/mannythings-sailcast.git
cd mannythings-sailcast
```

### 2. Set up the Python backend

```bash
cd server

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Create your environment file
cp .env.example .env
```

Edit `server/.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Set up the React frontend

```bash
cd ../client

# Install dependencies
npm install
```

---

## Running Locally

You need **two terminal windows** -- one for the backend and one for the frontend.

### Terminal 1: Start the backend

```bash
cd server
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will:
- Start the FastAPI server on `http://localhost:8000`
- Immediately fetch NWS data and generate an AI summary
- Begin the hourly refresh scheduler
- Serve API docs at `http://localhost:8000/docs` (Swagger UI)

### Terminal 2: Start the frontend

```bash
cd client
npm run dev
```

The frontend will:
- Start the Vite dev server on `http://localhost:5173`
- Proxy all `/api` requests to the backend at `localhost:8000`

### Access the app

Open **http://localhost:5173** in your browser.

---

## API Endpoints

All endpoints are prefixed with `/api/forecast`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/forecast/hourly` | 24-hour hourly wind forecast |
| GET | `/api/forecast/7day` | 7-day weather outlook |
| GET | `/api/forecast/alerts` | Active NWS alerts |
| GET | `/api/forecast/summary` | AI-generated summary + advisory |
| GET | `/api/forecast/budget` | OpenAI budget & usage status |
| GET | `/api/forecast/health` | System health check |
| GET | `/` | App info + docs link |
| GET | `/docs` | Swagger UI (auto-generated) |

### Example Response: `/api/forecast/summary`

```json
{
  "summary": "Partly cloudy with light winds from the south at 5-10 mph...",
  "advisory": "Conditions are favorable for sailing all boat classes...",
  "safetyLevel": "SAFE",
  "keyConcerns": [],
  "generatedAt": "2026-02-06T14:00:00Z",
  "model": "gpt-4o"
}
```

---

## Configuration Reference

All configuration is managed via environment variables in `server/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |
| `NWS_OFFICE` | `LWX` | NWS forecast office code |
| `NWS_GRIDPOINT_X` | `97` | NWS grid X coordinate |
| `NWS_GRIDPOINT_Y` | `74` | NWS grid Y coordinate |
| `NWS_USER_AGENT` | `SailCast/1.0 (...)` | Required by NWS API |
| `SERVER_HOST` | `0.0.0.0` | Backend bind address |
| `SERVER_PORT` | `8000` | Backend port |
| `CLIENT_URL` | `http://localhost:5173` | Frontend URL for CORS |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `OPENAI_MONTHLY_BUDGET` | `5.00` | Max spend per month (USD) |
| `OPENAI_DAILY_BUDGET` | `0.50` | Max spend per day (USD) |
| `OPENAI_MAX_REQUESTS_PER_HOUR` | `5` | Max OpenAI API calls per hour |

### Budget Protection

SailCast includes a built-in budget tracker that prevents runaway API costs:

- **Monthly cap**: $5.00/month (configurable). At gpt-5-nano pricing (~$0.0003/request), this allows ~17,500 requests.
- **Daily cap**: $0.50/day. Safety net so one bad day can't eat the whole month.
- **Hourly rate limit**: 5 requests/hour. Prevents burst spending from bugs or restarts.

When any limit is hit, the AI service gracefully degrades:
- Returns the last cached summary if available
- Flags the response with a `budgetNotice` field
- NWS raw data (wind, alerts, 7-day) continues to work normally -- only AI calls stop

**Monitor usage** via the budget endpoint:
```
GET /api/forecast/budget
```

Usage data persists across server restarts in `server/app/data/usage.json` (gitignored).

### Changing the sailing location

To target a different NWS gridpoint:
1. Go to `https://api.weather.gov/points/{lat},{lon}` with your coordinates
2. Note the `gridId`, `gridX`, and `gridY` from the response
3. Update `NWS_OFFICE`, `NWS_GRIDPOINT_X`, `NWS_GRIDPOINT_Y` in `.env`

---

## AWS Lightsail Deployment

> **Note**: Complete local testing before deploying to production.

### 1. Lightsail instance setup

```bash
# SSH into your Lightsail instance
ssh ubuntu@your-lightsail-ip

# Install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install python3.11 python3.11-venv nginx certbot python3-certbot-nginx -y

# Install Node.js (for building the frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
```

### 2. Configure nginx

Create `/etc/nginx/sites-available/sailcast`:
```nginx
server {
    listen 80;
    server_name mannythings.us;

    location /sailcast {
        alias /home/ubuntu/mannythings-sailcast/client/dist;
        try_files $uri $uri/ /sailcast/index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Create systemd service

Create `/etc/systemd/system/sailcast.service`:
```ini
[Unit]
Description=SailCast FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/mannythings-sailcast/server
Environment=PATH=/home/ubuntu/mannythings-sailcast/server/venv/bin
ExecStart=/home/ubuntu/mannythings-sailcast/server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Deploy

```bash
# From your local machine
chmod +x deploy.sh
./deploy.sh
```

Or manually:
```bash
git push origin main
# SSH into Lightsail, then:
cd /home/ubuntu/mannythings-sailcast
git pull
cd client && npm run build && cd ..
cd server && source venv/bin/activate && pip install -r requirements.txt && cd ..
sudo systemctl restart sailcast
```

### 5. Enable HTTPS

```bash
sudo certbot --nginx -d mannythings.us
```

---

## Troubleshooting

### Backend won't start
- Check that `server/.env` exists and has a valid `OPENAI_API_KEY`
- Ensure the virtual environment is activated: `source server/venv/bin/activate`
- Check Python version: `python3 --version` (needs 3.11+)

### NWS data returns 503
- The NWS API occasionally has outages. The scheduler will retry on the next hour.
- Check NWS API status: https://api.weather.gov

### AI summary not generating
- Verify your OpenAI API key has available credits
- Check the model name in `.env` is valid (e.g., `gpt-4o`, `gpt-3.5-turbo`)
- Check server logs for error messages

### Frontend shows "Loading..."
- Ensure the backend is running on port 8000
- Check the browser console for API errors
- Verify the Vite proxy is configured in `client/vite.config.js`

### CORS errors
- In development, the Vite proxy handles CORS (no direct cross-origin requests)
- In production, ensure `CLIENT_URL` in `.env` matches your actual domain

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test locally
3. Commit with clear messages
4. Push and create a pull request

---

*This README is the primary reference document for the SailCast project. It should be updated whenever the project structure, configuration, or deployment process changes.*
