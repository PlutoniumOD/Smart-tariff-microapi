#!/usr/bin/env bash
set -euo pipefail

if [ ! -f /data/options.json ]; then
  echo "Missing /data/options.json (add-on options)."
  exit 1
fi

export ADDON_OPTIONS_PATH="/data/options.json"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
