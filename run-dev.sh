#!/usr/bin/env bash
# Starts backend (port 8000) and frontend dev server (port 5173). Ctrl+C stops both.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
[ -d .venv ] && PY=.venv/bin/python
trap 'kill 0' EXIT
(cd backend && ../"$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
(cd frontend && npm run dev) &
wait
