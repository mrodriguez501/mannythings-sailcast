# SailCast → Lightsail CI/CD and password wall – plan

**Full step-by-step instructions are in [sailcast/README.md](../sailcast/README.md)** (sections “CI/CD (GitHub Actions → Lightsail)” and “Production (Lightsail) – password wall”). This file is a short overview and checklist.

## Overview

1. **GitHub Actions pipeline** – Push to `main` triggers a deploy on your Lightsail instance using a **self-hosted runner** (the runner runs on the Lightsail server and executes a deploy script).
2. **Information needed** – See “Information needed from you” below; the workflow and README use sensible defaults (e.g. `main`, `/home/bitnami/mannythings`, Docker).
3. **First push to prod** – After the runner and deploy script are set up, you push a commit to `main`; the workflow runs and deploys.
4. **README** – All setup steps (runner, deploy script, password wall) are in the SailCast README.
5. **Password wall in prod** – After the first successful deploy, add `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` to the server’s `sailcast/.env` and restart the container.

---

## Information needed from you

Please confirm or fill in the following so the pipeline and docs match your setup:

| Item | Purpose | Example / notes |
|------|--------|------------------|
| **GitHub repo URL** | Deploy key and runner config | `https://github.com/YOUR_USER/mannythings` |
| **Branch to deploy** | Workflow trigger | Usually `main` |
| **Repo layout on server** | Path where you clone the repo on Lightsail | e.g. `/home/bitnami/mannythings` (repo root; SailCast is in `mannythings/sailcast`) |
| **How you run SailCast** | Deploy script will use this | **Docker** (recommended) or **systemd** (uvicorn) or **manual** |
| **Deploy script path on server** | Where the runner will run the script | e.g. `/home/bitnami/deploy.sh` |

Optional (we can use defaults):

- **Runner work folder** – Default is `~/actions-runner`.
- **Container name** – If Docker: default `sailcast`; port `8000`.

---

## Step-by-step execution order

| Step | Who | What |
|------|-----|------|
| 1 | You | Provide the info above (repo URL, branch, server path, Docker vs systemd, deploy script path). |
| 2 | Repo | Add `.github/workflows/deploy.yml` and document the server setup in README. |
| 3 | You (on Lightsail) | One-time: SSH key → GitHub Deploy key, clone repo (if not already), set remote to SSH. |
| 4 | You (on Lightsail) | One-time: Install and configure the GitHub Actions self-hosted runner; install as service. |
| 5 | You (on Lightsail) | Create `deploy.sh` from README, make executable, ensure `.env` exists in `sailcast/`. |
| 6 | You | Push a commit to `main` → workflow runs → first deploy to prod. |
| 7 | You (on Lightsail) | Add `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` to `sailcast/.env`, restart app (Docker or systemd). |
| 8 | Repo | README already updated with CI/CD and password-wall sections. |

---

## Notes

- **SailCast is Python/FastAPI**, not Node.js. The article’s pattern (self-hosted runner + deploy script) is the same; the deploy script will use `docker build`/`docker run` or `systemctl restart sailcast` instead of `npm install` and `pm2 restart`.
- **Password wall**: Enabled only when both `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` are set. Set them only on the Lightsail server so local stays unprotected.
