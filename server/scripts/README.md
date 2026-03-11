# Server scripts

## Restarting the app (server + frontend)

The backend and frontend are the same process: uvicorn serves both the API and the static files in `server/static/`. Restarting the server restarts both.

- **Local:** `bash server/scripts/start-local.sh` (kills anything on 8000, starts uvicorn with `--reload`). After editing HTML/JS/CSS, just refresh the browser (Cmd+Shift+R if cached).
- **Production:** Push to `main` (deploy runs `systemctl restart sailcast`) or SSH and run `sudo systemctl restart sailcast`.

## Linting

CI runs [ruff](https://docs.astral.sh/ruff/) on every push/PR to `main`. To run locally:

```bash
cd server
pip install ruff          # one-time (or: pip install -r requirements-dev.txt)
ruff check app/           # lint
ruff format --check app/  # format check
```

To auto-fix everything:

```bash
ruff check --fix app/ && ruff format app/
```

Config lives in `pyproject.toml` at the repo root.

## Environment (.env)

**Never overwrite an existing `.env`.** To create one from the example only when missing:

```bash
cp -n .env.example .env
```

Then edit `.env` and set `OPENAI_API_KEY` (and any other values). Deploy and automation should never run `cp .env.example .env` without `-n`.

## deploy.sh

Deploys the **server** app (FastAPI + uvicorn on port 8000). Used by CI/CD when the runner executes `/home/bitnami/deploy.sh`.

**Uvicorn is restarted on every deploy** so the new code (and any new static mounts like `/static-icons`) is loaded.

### systemd (recommended on the server)

When `sailcast.service` is present and `systemctl` is available, the script installs/updates the unit and runs `systemctl restart sailcast`. That way uvicorn is managed by systemd and **survives after the CI job exits** (otherwise the runner can kill the nohup process → 503). The unit file is in `server/scripts/sailcast.service`; install it once on the server (see comments in the file) or let the deploy script copy it.

### Fallback: nohup

The script kills the old uvicorn by PID file, then frees port 8000 with `fuser -k 8000/tcp` or `pkill -f 'uvicorn app.main:app'` so the new process can always bind. This avoids "address already in use" when the PID file was stale.

### On the Lightsail server

`/home/bitnami/deploy.sh` should pull the repo and then run this script so deploys use systemd and avoid 503:

```bash
#!/bin/bash
set -e
export REPO_ROOT=/home/bitnami/mannythings-sailcast
cd "$REPO_ROOT"
git fetch origin && git reset --hard origin/main
exec bash "$REPO_ROOT/server/scripts/deploy.sh"
```

Ensure the `sailcast` systemd unit is installed (the deploy script copies `server/scripts/sailcast.service` to `/etc/systemd/system/` and runs `systemctl restart sailcast`).
