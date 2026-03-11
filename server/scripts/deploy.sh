#!/usr/bin/env bash
# SailCast deploy script (uvicorn on port 8000).
# Run from repo root, e.g.: bash server/scripts/deploy.sh
# On Lightsail, copy to /home/bitnami/deploy.sh or run: bash /home/bitnami/mannythings-sailcast/server/scripts/deploy.sh
#
# Yes, uvicorn must be restarted on every deploy so the new code (and mounts like /static-icons) is loaded.
set -e

# If copied to /home/bitnami/deploy.sh, set REPO_ROOT there; otherwise derive from script path.
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$REPO_ROOT"
git fetch origin && git reset --hard origin/main

cd server || exit
[[ -d venv ]] || python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt

# Restart uvicorn (port 8000). Kill by PID file first, then ensure nothing is left on the port.
PIDFILE="$REPO_ROOT/server/sailcast.pid"
if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE")
  kill "$OLD_PID" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
# In case PID file was stale or process didn't exit, free port 8000 so the new process can bind
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
else
  pkill -f 'uvicorn app.main:app' 2>/dev/null || true
fi
sleep 2

nohup ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$REPO_ROOT/server/uvicorn.log" 2>&1 &
echo $! > "$PIDFILE"
echo "Deployment finished at $(date). SailCast running on port 8000."
