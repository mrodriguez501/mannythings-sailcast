# Server scripts

## Environment (.env)

**Never overwrite an existing `.env`.** To create one from the example only when missing:

```bash
cp -n .env.example .env
```

Then edit `.env` and set `OPENAI_API_KEY` (and any other values). Deploy and automation should never run `cp .env.example .env` without `-n`.

## deploy.sh

Deploys the **server** app (FastAPI + uvicorn on port 8000). Used by CI/CD when the runner executes `/home/bitnami/deploy.sh`.

**Uvicorn is restarted on every deploy** so the new code (and any new static mounts like `/static-icons`) is loaded.

### Robust restart

The script kills the old uvicorn by PID file, then frees port 8000 with `fuser -k 8000/tcp` or `pkill -f 'uvicorn app.main:app'` so the new process can always bind. This avoids "address already in use" when the PID file was stale.

### On the Lightsail server

Use a **standalone** `/home/bitnami/deploy.sh` that contains the full script (with `REPO_ROOT=/home/bitnami/mannythings-sailcast`). That way the workflow does not depend on `server/scripts/deploy.sh` existing in the repo yet (avoiding exit 127 "command not found" on first deploy after adding the script).

- **Option A:** Copy the full contents of `server/scripts/deploy.sh` into `/home/bitnami/deploy.sh` and set the first line after `set -e` to `REPO_ROOT=/home/bitnami/mannythings-sailcast`.
- **Option B:** After cloning/pulling, run once: `bash /home/bitnami/mannythings-sailcast/server/scripts/deploy.sh` to confirm it works; keep `/home/bitnami/deploy.sh` as a copy of that script with `REPO_ROOT` set so the workflow always has a working script.
