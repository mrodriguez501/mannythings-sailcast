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

**Option A – same stack as production (server):**

```bash
bash server/scripts/start-local.sh
```

Open **http://localhost:8000/sailcast/** (or http://localhost:8000 then follow redirect). See `server/scripts/README.md` for details.

**Option B – sailcast app (this directory):**

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
| `BASIC_AUTH_USER` + `BASIC_AUTH_PASSWORD` | Optional HTTP Basic Auth (password wall); set **only on production** (e.g. Lightsail) so local stays unprotected |

## Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, httpx.
- **Frontend:** Static HTML, Pico CSS, vanilla JS, Chart.js (tide chart).
- **Data:** NWS (points, alerts, marine zone), NOAA CO-OPS (tides).

## Repo layout and what runs where

- **`server/`** – App that runs in **production** (and for local dev). FastAPI serves the API and the static frontend from `server/static/`. The frontend calls `api/report` (same origin); the report route must return the payload shape the frontend expects (location, hourly, alerts, marine_forecast, tides, recommendation). Icons are served from `sailcast/static-icons/` (single source, no copy).
- **`sailcast/`** – Alternate app (Docker path, different structure). Shares assets (e.g. `sailcast/static-icons/`). Can be run locally; production currently uses **server/**.

Linking frontend to backend: ensure the report API URL is correct (relative `api/report` under the same base path, e.g. `/sailcast/api/report` in prod) and that the report response matches the frontend’s expected fields.

---

## Architecture diagrams

### Production (Lightsail)

```
                    GitHub (push to main)
                              │
                              ▼
                    GitHub Actions workflow
                    (self-hosted runner on Lightsail)
                              │
                              ▼
                    /home/bitnami/deploy.sh
                    (git pull → server/scripts/deploy.sh)
                              │
                              ▼
                    systemctl restart sailcast
                              │
    ┌─────────────────────────┴─────────────────────────┐
    │  systemd: sailcast.service                         │
    │  uvicorn app.main:app (server/app/main.py)         │
    │  port 8000, .env from server/.env                  │
    └─────────────────────────┬─────────────────────────┘
                              │
    Browser ◄─────────────────┴─────────────────────────► Apache (:80/:443)
    mannythings.us/sailcast/       ProxyPass /sailcast/ → http://127.0.0.1:8000/sailcast/
                                          │
                              ┌───────────┴───────────┐
                              │  FastAPI (root_app)   │
                              │  mount /sailcast →    │
                              │  sailcast_app         │
                              │  (/, /api/report,     │
                              │   /static, /static-   │
                              │   icons)              │
                              └───────────┬───────────┘
                                          │
                    NWS, NOAA CO-OPS, OpenAI (data sources)
```

### Local

```
    Browser
    http://localhost:8000/sailcast/
              │
              ▼
    uvicorn app.main:app (server/)
    --reload, port 8000
    Started by: server/scripts/start-local.sh
              │
    ┌─────────┴─────────┐
    │  FastAPI          │
    │  /sailcast →      │
    │  sailcast_app     │
    │  (/, api/report,  │
    │   static, static- │
    │   icons from      │
    │   ../sailcast/    │
    │   static-icons)   │
    └─────────┬─────────┘
              │
    NWS, NOAA CO-OPS, OpenAI (same .env in server/)
```

---

## Docker

```bash
docker build -t sailcast .
docker run -p 8000:8000 --env-file .env sailcast
```

## CI/CD (GitHub Actions → Lightsail)

Pushing to `main` deploys SailCast to your Lightsail instance using a **self-hosted runner** and a deploy script on the server (see [this guide](https://medium.com/@abdul-hadi/your-first-ci-cd-pipeline-in-5-minutes-github-actions-to-aws-lightsail-aeb200093934)). The workflow runs on the server and executes `deploy.sh`, which pulls the repo and runs the Docker build/restart.

### What you need

- GitHub repo (this repo) with branch `main`.
- Lightsail instance (e.g. Bitnami) with Docker installed.
- Repo cloned on the server at a known path (e.g. `/home/bitnami/mannythings-sailcast`). SailCast is in the `sailcast/` subdirectory (or at repo root if you have a sailcast-only repo).

### 1. Server auth (SSH key → Deploy key)

On the Lightsail instance (SSH in):

```bash
ssh-keygen -t rsa -b 4096
# Press Enter three times (no passphrase)
cat ~/.ssh/id_rsa.pub
```

Copy the output. On GitHub: **Settings → Deploy keys → Add deploy key**. Paste the key, title e.g. `lightsail-runner`. Do **not** check “Allow write access.”

Back on the server, go to your repo directory and set the remote to SSH (replace with your repo URL):

```bash
cd /home/bitnami/mannythings-sailcast
git remote set-url origin git@github.com:mrodriguez501/mannythings-sailcast.git
ssh -T git@github.com
# Type yes when prompted
```

### 2. Self-hosted runner

On GitHub: **Settings → Actions → Runners → New self-hosted runner**. Select Linux and your architecture (e.g. x64). You’ll see commands to download and configure the runner.

On the Lightsail server:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
# Run the curl and tar commands from the GitHub page to download the runner
# Run the ./config.sh command from the GitHub page (paste the token)
# Accept defaults (Enter for name, labels, work folder)

sudo ./svc.sh install
sudo ./svc.sh start
```

### 3. Deploy script on the server

Create the script the workflow will run (adjust `REPO_ROOT` if your clone is elsewhere):

```bash
nano /home/bitnami/deploy.sh
```

Paste (replace `REPO_ROOT` if your clone is elsewhere):

```bash
#!/bin/bash
REPO_ROOT=/home/bitnami/mannythings-sailcast
cd "$REPO_ROOT" || exit
git pull origin main
bash sailcast/scripts/deploy-lightsail.sh
echo "Deployment finished at $(date)" >> /home/bitnami/deploy.log
```

Save and exit. Make it executable:

```bash
chmod +x /home/bitnami/deploy.sh
```

### 4. App config on the server

Ensure SailCast has a `.env` in the sailcast directory (copy from `.env.example`, set `OPENAI_API_KEY`, etc.):

```bash
cd /home/bitnami/mannythings-sailcast/sailcast
cp .env.example .env
nano .env
```

Do **not** add `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` yet; add them after the first deploy (see “Production – password wall” below).

### 5. Workflow in the repo

The repo already contains `.github/workflows/deploy.yml`. It runs on every push to `main` and executes `/home/bitnami/deploy.sh`. If your deploy script path is different, edit the `run:` line in that file.

### 6. First push to prod

From your local machine:

```bash
git add .github/workflows/deploy.yml sailcast/scripts/deploy-lightsail.sh sailcast/README.md docs/LIGHTSAIL-CICD-PLAN.md
git commit -m "Add CI/CD: GitHub Actions deploy to Lightsail"
git push origin main
```

Open the repo’s **Actions** tab. The “Deploy to Lightsail” workflow should run and turn green. Your instance will have the latest SailCast running in Docker.

### 7. Troubleshooting

| Issue | Fix |
|-------|-----|
| Action stuck on “Waiting for a runner…” | Runner is offline. On server: `cd ~/actions-runner && sudo ./svc.sh start` |
| Permission denied running deploy.sh | `chmod +x /home/bitnami/deploy.sh` |
| Host key verification failed | Run `ssh -T git@github.com` on the server and type `yes` |
| Could not read from remote repository | Check Deploy key is added and `git remote set-url origin git@github.com:...` |
| .env not found | Create `sailcast/.env` on the server from `.env.example` |

---

## Production (Lightsail) – password wall only here

Do this **after** your first successful CI/CD deploy. The password wall is **off** unless both `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` are set. Keep them **out of your local `.env`**; set them **only on the Lightsail server**.

### 1. Deploy the latest code

Already done by CI/CD when you push to `main`, or deploy manually so the server has the auth middleware.

### 2. SSH into Lightsail

Use the Lightsail console “Connect using SSH” (or your own key). You’ll land in the bitnami user’s home (e.g. `/home/bitnami`).

### 3. Find where Sailcast runs and edit `.env`

```bash
# If you use the CI/CD setup, Sailcast is under the repo:
cd ~/mannythings-sailcast/sailcast
# Or e.g. ~/sailcast if you deployed there

# Backup and edit .env (use nano, vim, or your preferred editor)
cp .env .env.bak
nano .env
```

Add these two lines (use your own username and a strong password):

```env
BASIC_AUTH_USER=bitnami
BASIC_AUTH_PASSWORD=your-secret-password
```

Save and exit (in nano: Ctrl+O, Enter, Ctrl+X).

### 4. Restart the app so it picks up the new env

**If you run with Docker (CI/CD setup):**

```bash
git cd ~/mannythings-sailcast/sailcast
docker stop sailcast; docker rm sailcast
docker run -d -p 8000:8000 --env-file .env --name sailcast sailcast
```

Or use `docker compose` if you use that instead.

**If you run with systemd:**

```bash
sudo systemctl restart sailcast
# (or whatever your service name is, e.g. sailcast-app)
```

**If you run uvicorn manually** (e.g. in a screen/tmux session): stop that process and start it again from the same directory so it reloads `.env`.

### 5. Test

Open **http://&lt;your-instance-ip&gt;** (e.g. `http://52.90.117.72`). You should get a browser login prompt. After entering the username and password, only people with that password can see the site. Your local setup stays without a password as long as you don’t add these vars to your local `.env`.

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
├── scripts/
│   └── deploy-lightsail.sh   # Docker build/restart (used by CI/CD deploy script)
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```
