#!/usr/bin/env bash
# Run the web dashboard; bind to all interfaces by default (Oracle / cloud hosts).
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  echo "No .venv — run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi
# shellcheck source=/dev/null
source .venv/bin/activate
export DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-8765}"
exec python main.py
