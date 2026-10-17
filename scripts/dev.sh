#!/usr/bin/env bash
# Start the API (port 8000) and the web app (port 3000) together; Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
(cd server && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
API=$!
trap 'kill $API 2>/dev/null' EXIT INT TERM
npm --prefix client run dev
