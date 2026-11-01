#!/usr/bin/env bash
# Loan Intelligence: local launcher for macOS / Linux. Starts the app at http://localhost:8501
# Creates a virtual environment (outside this folder), installs dependencies when requirements.txt changed, creates the first accounts on the first run.
set -euo pipefail
cd "$(dirname "$0")"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
PORT="${LOAN_APP_PORT:-8501}"

PY=""
for c in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "ERROR: Python 3.10 or newer was not found. Install Python 3.12 and run again." >&2; exit 1; }
echo "Using Python: $($PY --version)"

# The virtual environment lives OUTSIDE the project folder: the project's own test suite scans every .py file under the project root,
# so a virtual-environment folder inside it would make an original test fail. Override with LOAN_APP_VENV.
VENV="${LOAN_APP_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/loan_intelligence/venv}"
[ -x "$VENV/bin/python" ] || { echo "Creating virtual environment in $VENV ..."; "$PY" -m venv "$VENV"; }
if ! cmp -s requirements.txt "$VENV/requirements.installed" 2>/dev/null; then
  echo "Installing dependencies (the first run takes several minutes) ..."
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV/bin/python" -m pip install -r requirements.txt
  cp requirements.txt "$VENV/requirements.installed"
fi

if [ ! -f data/app/loan_app.db ] && [ -z "${LOAN_APP_DATA_DIR:-}" ]; then
  echo; echo "First run: creating the database and the administrator / officer accounts."
  "$VENV/bin/python" -m app.bootstrap
  echo; echo ">>> Write down the passwords above now. They are not stored anywhere in plain text. <<<"
  [ -t 0 ] && read -r -p "Press Enter to start the application " _ || true
fi

if (command -v ss >/dev/null && ss -ltn 2>/dev/null | grep -q ":$PORT ") ; then
  echo "ERROR: port $PORT is already in use. Stop the other program or set LOAN_APP_PORT." >&2; exit 1
fi
if [ -n "${RUN_LOCAL_NO_LAUNCH:-}" ]; then echo "RUN_LOCAL_NO_LAUNCH is set: setup finished, not launching."; exit 0; fi
echo "Starting the application at http://localhost:$PORT  (Ctrl+C to stop)"
exec "$VENV/bin/python" -m streamlit run app/streamlit_app.py --server.address localhost --server.port "$PORT"
