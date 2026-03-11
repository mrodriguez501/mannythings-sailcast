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

# Use systemd so uvicorn survives after the CI job exits (nohup is killed when the job ends -> 503).
if command -v systemctl >/dev/null 2>&1 && [[ -f "$REPO_ROOT/server/scripts/sailcast.service" ]]; then
  sudo cp "$REPO_ROOT/server/scripts/sailcast.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable sailcast 2>/dev/null || true
  sudo systemctl restart sailcast
  sleep 3
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf -o /dev/null "http://127.0.0.1:8000/sailcast/health"; then
      echo "Deployment finished at $(date). SailCast (systemd) running on port 8000."
      exit 0
    fi
    sleep 2
  done
  echo "ERROR: sailcast service did not respond. sudo journalctl -u sailcast -n 50" >&2
  exit 1
fi

# Fallback: nohup (may be killed when CI job ends; use systemd on the server to avoid 503)
PIDFILE="$REPO_ROOT/server/sailcast.pid"
if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE")
  kill "$OLD_PID" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
else
  pkill -f 'uvicorn app.main:app' 2>/dev/null || true
fi
sleep 4

nohup ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$REPO_ROOT/server/uvicorn.log" 2>&1 &
echo $! > "$PIDFILE"

for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf -o /dev/null "http://127.0.0.1:8000/sailcast/health"; then
    echo "Deployment finished at $(date). SailCast running on port 8000 (nohup)."
    exit 0
  fi
  sleep 2
done
echo "ERROR: uvicorn did not respond on port 8000. Check $REPO_ROOT/server/uvicorn.log" >&2
exit 1
