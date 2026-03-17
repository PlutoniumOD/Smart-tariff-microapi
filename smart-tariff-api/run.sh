#!/usr/bin/env bash
set -euo pipefail

# Home Assistant add-on passes options at /data/options.json
if [ ! -f /data/options.json ]; then
  echo "Missing /data/options.json (add-on options)."
  exit 1
fi

# Make options path visible to the app
export ADDON_OPTIONS_PATH="/data/options.json"

# Ensure we're in /app so Python can import the "app" package
cd /app
export PYTHONPATH=/app

# Use the virtualenv we created in the Dockerfile
exec /app/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787 --log-level info
