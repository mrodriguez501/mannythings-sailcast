#!/usr/bin/env bash
# Local dev only. Start SailCast (kill anything on 8000 first). Not used in prod; prod uses systemd + deploy.sh.
cd "$(dirname "$0")/.."

echo "────────────────────────────────────────────────"
echo "  SailCast – Local Development Server"
echo "────────────────────────────────────────────────"
echo "  App:   http://localhost:8000/sailcast/"
echo "  Docs:  http://localhost:8000/sailcast/docs"
echo ""
echo "  Lint:  cd server && pip install ruff && ruff check app/ && ruff format --check app/"
echo "  Fix:   ruff check --fix app/ && ruff format app/"
echo "────────────────────────────────────────────────"
echo ""

# Free port 8000 (lsof works on macOS and Linux)
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
sleep 2
exec ./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
