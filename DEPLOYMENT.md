# Deployment Guide: run locally and publish on Render

This is the **same application** (same interface, engine, policies, models, database, documents, reports). Deployment only adds launchers and hosting files. Entry point: `app/streamlit_app.py`.

## What was added (and the only two code edits)
| File | Purpose |
|---|---|
| `run_local.bat` / `run_local.sh` | one-step local start (Windows / macOS-Linux) |
| `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore` | container for Render (installs Tesseract for OCR; runs as a non-root user) |
| `render.yaml` | Render Blueprint: Docker service, persistent disk, health check, environment variables |
| `requirements.txt` (runtime) / `requirements-dev.txt` (tests) | dependencies; test tools split out |
| `.env.example`, `.gitignore`, `.gitattributes` | configuration template; keeps secrets and data out of Git |
| `tools/backup_data.py` | consistent backup of database + uploads + reports |
| `tests/deploy/` | 21 deployment tests |

Code edits: `app/config.py` (an empty environment variable now counts as "not set"; new opt-in `LOAN_APP_REQUIRE_ENV_PASSWORDS`) and `app/streamlit_app.py` (when that flag is on and the account passwords are missing, show a clear message instead of silently creating accounts with unknown passwords). With the flag off (the local default) behaviour is identical to before.

---
## 1. Run locally
### Windows
1. Install Python 3.10+ (3.12 recommended) from python.org, ticking **Add python.exe to PATH**.
2. Extract the ZIP, open the folder, and **double-click `run_local.bat`** (or run it in a terminal).
3. First run takes several minutes (it creates a virtual environment and installs the dependencies). It then creates the database and the two accounts and **prints the generated passwords once: write them down**. Press a key to continue.
4. Your browser opens at **http://localhost:8501**. Sign in as `admin` or `officer`. Close the window (Ctrl+C) to stop.
To choose your own passwords, copy `.env.example` to `.env`, replace the two `CHANGE_ME...` lines, and run the script (it reads `.env`). Optional OCR for images/scanned PDFs: install Tesseract for Windows and add it to PATH; without it the app still works and says OCR is unavailable.
### macOS / Linux
`./run_local.sh` (needs Python 3.10+; for OCR `sudo apt-get install tesseract-ocr tesseract-ocr-eng`).
### Manually
```bash
python -m venv ..\loan_intelligence_venv            # keep it OUTSIDE the project folder (see note below)
..\loan_intelligence_venv\Scripts\activate          # Windows   (macOS/Linux: python3 -m venv ../loan_intelligence_venv && source ../loan_intelligence_venv/bin/activate)
pip install -r requirements.txt
python -m app.bootstrap            # first time only: creates the database + accounts, prints passwords once
streamlit run app/streamlit_app.py # then open http://localhost:8501
```
Tests: `pip install -r requirements-dev.txt` then `python -m pytest -q`.
**Why the virtual environment is outside the project folder:** one of the original Phase 1/2 tests (`test_only_conftest_enables_test_mode`) scans every `.py` file under the project root, so a virtual environment *inside* the folder makes that test fail. The launchers therefore keep it in `%LOCALAPPDATA%\LoanIntelligence\venv` (Windows) or `~/.cache/loan_intelligence/venv` (macOS/Linux); override with `LOAN_APP_VENV`. The original tests were not modified.
Local data lives in `data/app/` (database `loan_app.db`, `uploads/`, `reports/`). Move it elsewhere with `LOAN_APP_DATA_DIR`.

---
## 2. Deploy on Render (public HTTPS URL)
**I could not deploy this for you: I have no access to your Render or GitHub accounts, so no public URL exists yet.** Follow these steps (about 20 minutes).

**You need:** (1) a GitHub account, (2) a Render account with a **paid** instance type: a persistent disk (which keeps your records) is not available on Render's free tier, (3) a card on Render. Approximate cost: the `starter` instance plus a 1 GB disk, a few US dollars a month; check Render's current pricing.

1. **Create a private GitHub repository** (private: this is a financial-data prototype) and push the extracted project:
   ```bash
   cd loan_intelligence
   git init && git add . && git commit -m "Loan Intelligence"
   git branch -M main && git remote add origin https://github.com/<you>/<repo>.git && git push -u origin main
   ```
   `.gitignore` already excludes `.env`, databases and `data/app`. Do not add real passwords to any file.
2. In Render: **New + > Blueprint**, connect GitHub, choose the repository. Render reads `render.yaml`.
3. When prompted, **enter the two secret values** `LOAN_APP_ADMIN_PASSWORD` and `LOAN_APP_OFFICER_PASSWORD` (at least 10 characters with upper-case, lower-case and a digit). They are stored in Render only.
4. Click **Apply**. The first build takes several minutes. Watch **Logs** for "You can now view your Streamlit app".
5. Open the URL Render shows (`https://loan-intelligence-xxxx.onrender.com`) and sign in as `admin` / `officer` with the passwords you entered.
6. Check: Dashboard opens; load the demonstration applicants; run an assessment; generate a report; then use **Manual Deploy > Restart** and confirm the records are still there.
Manual alternative to the Blueprint: New Web Service > Docker; instance type Starter or higher; add a **Disk** mounted at `/var/data` (1 GB); set `LOAN_APP_DATA_DIR=/var/data/loan_app`, `LOAN_APP_REQUIRE_ENV_PASSWORDS=1`, and the two password variables; health check path `/_stcore/health`.
If the app says **"Deployment configuration incomplete"**, a password variable is missing or empty: add it and restart. No accounts are created until both exist.
Memory: measured about 300 MB after one assessment, so the 512 MB `starter` size is tight. If you see restarts or slowness, switch to `standard` (2 GB).

---
## 3. Persistence (records and documents must survive restarts)
| Data | Location in the cloud | Survives restart / redeploy? |
|---|---|---|
| SQLite database | `/var/data/loan_app/loan_app.db` | yes (disk) |
| Uploaded documents | `/var/data/loan_app/uploads/<applicant>/` | yes |
| PDF reports | `/var/data/loan_app/reports/` | yes |
| Application code, models | container image | rebuilt each deploy (read-only data) |
Everything stored by the application goes under the one variable `LOAN_APP_DATA_DIR`, so nothing is written to the container's ephemeral filesystem. Local and cloud paths are independent (local default `data/app/`). Start-up never resets data: the schema uses `CREATE TABLE IF NOT EXISTS` and no step deletes or recreates the database (tested over repeated restarts). There is currently no schema migration because none has been needed; a future schema change must ship with an explicit, tested migration.
Limits: a Render disk attaches to **one** instance, so run exactly one instance (no scaling out); a deploy causes a short downtime; the free tier has no disk and **would lose all data**.
**Backups** (do this regularly; a disk is not a backup): open the service **Shell** in Render and run `python tools/backup_data.py /var/data/backups`, then copy the folder out (or enable Render disk snapshots). Locally: `python tools/backup_data.py`. **Restore:** stop the app, copy `loan_app.db`, `uploads/`, `reports/` from the backup into the data directory, start the app.
To move local data to the cloud: stop both, copy your local `data/app/*` into `/var/data/loan_app/` via the Render Shell (and `chown -R app:app` it), then restart. Never overwrite a live cloud database without a backup.

---
## 4. Security before making it public
Done: login is mandatory; no default credentials (accounts are created only from the passwords you supply, and cloud mode refuses to start without them); secrets only in Render environment variables; the container runs as a non-root user; error details are hidden in the browser; the database, uploads, reports, source and models are not reachable by URL (probed: every such path returns only the app shell); HTTPS is provided by Render; PAN stays masked; accounts lock after repeated failures; all actions are audited.
**Not done / your responsibility:** this is a prototype, **not production banking infrastructure**: no MFA/SSO, no encryption of the disk contents by the app, no IP allow-listing, no retention/deletion process, no intrusion monitoring, no independent security review or regulatory approval. **Do not put real customer data on it.** For a public demo use only the labelled synthetic demonstration applicants, change both passwords from anything you have shared, and take the service down when not needed. See `docs/SECURITY_AND_PRIVACY.md`.

---
## 5. What was and was not verified
Verified by running it: the local launcher (`run_local.sh`: fresh virtual environment, runtime-only install, first-run accounts, five separate starts with the full workflow in a real browser on http://localhost:8501: login, registration, document upload, assessment, SBI synthetic environment, ML risk, scenarios, PDF report, persistence across restarts); the container startup sequence simulated without Docker (the real `docker-entrypoint.sh` as root on a root-owned "disk", dropping to a non-root user, the exact Dockerfile start command on port 10000, cloud environment variables): refusal without passwords, login with passwords, assessment, report, persistence across a restart, data written only to the disk, web-exposure probes; the test suite.
**Not verified (no access / not available here):** building the Docker image; the deployment on Render itself; Render's disk, proxy and HTTPS behaviour; `run_local.bat` on Windows (written and statically checked, not executed); other operating systems and browsers.
