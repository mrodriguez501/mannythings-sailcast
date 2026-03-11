#!/usr/bin/env bash
# Local dev only. Start SailCast (kill anything on 8000 first). Not used in prod; prod uses systemd + deploy.sh.
cd "$(dirname "$0")/.."
# Free port 8000 (lsof works on macOS and Linux)
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
sleep 2
exec ./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
