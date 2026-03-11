# SailCast → Lightsail CI/CD and password wall – plan

**Full step-by-step instructions are in [server/scripts/README.md](../server/scripts/README.md)**. This file is a short overview and checklist.

## Overview

1. **GitHub Actions pipeline** – Push to `main` triggers a deploy on your Lightsail instance using a **self-hosted runner** (the runner runs on the Lightsail server and executes a deploy script).
2. **Information needed** – See "Information needed from you" below; the workflow and README use sensible defaults (e.g. `main`, `/home/bitnami/mannythings`, systemd).
3. **First push to prod** – After the runner and deploy script are set up, you push a commit to `main`; the workflow runs and deploys.
4. **README** – All setup steps (runner, deploy script) are in the server scripts README.

---

## Information needed from you

Please confirm or fill in the following so the pipeline and docs match your setup:

| Item | Purpose | Example / notes |
|------|--------|------------------|
| **GitHub repo URL** | Deploy key and runner config | `https://github.com/YOUR_USER/mannythings` |
| **Branch to deploy** | Workflow trigger | Usually `main` |
| **Repo layout on server** | Path where you clone the repo on Lightsail | e.g. `/home/bitnami/mannythings` |
| **How you run SailCast** | Deploy script will use this | **systemd** (uvicorn) — see `server/scripts/sailcast.service` |
| **Deploy script path on server** | Where the runner will run the script | e.g. `/home/bitnami/deploy.sh` |

Optional (we can use defaults):

- **Runner work folder** – Default is `~/actions-runner`.

---

## Step-by-step execution order

| Step | Who | What |
|------|-----|------|
| 1 | You | Provide the info above (repo URL, branch, server path, deploy script path). |
| 2 | Repo | Add `.github/workflows/deploy.yml` and document the server setup in README. |
| 3 | You (on Lightsail) | One-time: SSH key → GitHub Deploy key, clone repo (if not already), set remote to SSH. |
| 4 | You (on Lightsail) | One-time: Install and configure the GitHub Actions self-hosted runner; install as service. |
| 5 | You (on Lightsail) | Create `deploy.sh` from README, make executable, ensure `.env` exists in `server/`. |
| 6 | You | Push a commit to `main` → workflow runs → first deploy to prod. |
| 7 | Repo | README already updated with CI/CD sections. |

---

## Notes

- **SailCast is Python/FastAPI**. The deploy script uses `systemctl restart sailcast` (see `server/scripts/deploy.sh`).
- The app is served at `/sailcast/` via Apache reverse proxy (see `docs/apache-sailcast-proxy.conf`).
