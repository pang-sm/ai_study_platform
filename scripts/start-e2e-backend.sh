#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# P6.1 §H — ONE command: an isolated, authenticated E2E backend.
#
#     bash scripts/start-e2e-backend.sh --json
#
# Prints the bootstrap contract (base_url / port / username / password / …) and then serves
# until Ctrl+C. Everything it creates lives in a temp directory that it removes on exit.
#
# The frontend needs NO source change to use it — the app already reads VITE_API_BASE_URL:
#
#     VITE_API_BASE_URL=http://127.0.0.1:<port> npm run dev     # then run Playwright
#
# It never touches backend/app.db, real credentials or a paid provider. Implementation and
# the full contract: backend/scripts/e2e_harness.py
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY="$ROOT/backend/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$ROOT/backend/.venv/Scripts/python.exe"
fi
if [ ! -x "$PY" ]; then
  echo "No project venv found at backend/.venv (see CLAUDE.md — the system python is not it)" >&2
  exit 1
fi

exec "$PY" "$ROOT/backend/scripts/e2e_harness.py" "$@"
