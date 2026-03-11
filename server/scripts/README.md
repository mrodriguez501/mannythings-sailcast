# Server scripts

## deploy.sh

Deploys the **server** app (FastAPI + uvicorn on port 8000). Used by CI/CD when the runner executes `/home/bitnami/deploy.sh`.

**Uvicorn is restarted on every deploy** so the new code (and any new static mounts like `/static-icons`) is loaded.

### Robust restart

The script kills the old uvicorn by PID file, then frees port 8000 with `fuser -k 8000/tcp` or `pkill -f 'uvicorn app.main:app'` so the new process can always bind. This avoids "address already in use" when the PID file was stale.

### On the Lightsail server

Either:

1. **Run the script from the repo** (recommended; updates when you pull):

   Set `/home/bitnami/deploy.sh` to:

   ```bash
   #!/bin/bash
   export REPO_ROOT=/home/bitnami/mannythings-sailcast
   exec bash "$REPO_ROOT/server/scripts/deploy.sh"
   ```

2. **Or copy the script** and set `REPO_ROOT` at the top:

   ```bash
   cp /home/bitnami/mannythings-sailcast/server/scripts/deploy.sh /home/bitnami/deploy.sh
   # Edit line: REPO_ROOT=/home/bitnami/mannythings-sailcast
   chmod +x /home/bitnami/deploy.sh
   ```
