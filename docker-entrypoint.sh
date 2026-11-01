#!/bin/sh
# Prepares the persistent data directory (a Render disk is mounted root-owned), then drops root privileges before starting the app.
set -e
DATA="${LOAN_APP_DATA_DIR:-/var/data/loan_app}"
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA"
  chown -R app:app "$DATA"
  chmod 700 "$DATA"
  export HOME=/home/app          # setpriv does not reset HOME; without this Streamlit tries to read /root/.streamlit and crashes
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
mkdir -p "$DATA"
exec "$@"
