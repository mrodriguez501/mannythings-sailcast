#!/usr/bin/env bash
# SailCast deploy script for Lightsail (Docker).
# Run from repo root after git pull, e.g.: bash sailcast/scripts/deploy-lightsail.sh
# Requires: .env in sailcast/ on the server (not in git).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAILCAST_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SAILCAST_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: sailcast/.env not found. Create it from .env.example and set OPENAI_API_KEY, etc." >&2
  exit 1
fi

docker build -t sailcast .
docker stop sailcast 2>/dev/null || true
docker rm sailcast 2>/dev/null || true
docker run -d -p 8000:8000 --env-file .env --name sailcast sailcast
echo "SailCast container started at $(date)."
