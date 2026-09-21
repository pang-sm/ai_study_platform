#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6 §F
# Production topology verification — READ ONLY.
#
# WHY THIS EXISTS
# ---------------
# P5 could only INFER the topology from the repository (one systemd service, one nginx
# upstream, no `--workers` anywhere in deploy/). Two runtime facts depend on that inference
# being TRUE, and both are deployment blockers if it is not:
#
#   * ai.health  — the Router V1 availability registry is PROCESS-LOCAL. With more than one
#                  backend worker, "model X is degraded" is true in one process and unknown in
#                  the next, so the router would keep selecting a degraded model at random.
#   * the in-process Docker execution semaphore and the code-run rate limiter make the same
#                  single-process assumption.
#
# WHAT IT DOES
# ------------
# Reads and prints. It starts nothing, restarts nothing, edits nothing, and needs no
# credentials. Run it ON the server, or over SSH AFTER that access is explicitly authorized:
#
#     bash deploy/verify_production_topology.sh            # full checklist
#     bash deploy/verify_production_topology.sh --remote HOST
#
# EXIT CODE
# ---------
#   0  single-process topology confirmed (the P5 assumption holds)
#   1  MULTI-WORKER or UNKNOWN — the availability shared-state requirement escalates to a
#      deployment blocker; do not treat the AI ops availability view as exact
# ---------------------------------------------------------------------------
set -uo pipefail

REMOTE=""
if [ "${1:-}" = "--remote" ]; then
  REMOTE="${2:?usage: $0 [--remote HOST]}"
fi

run() {
  if [ -n "$REMOTE" ]; then
    ssh -o BatchMode=yes "$REMOTE" "$@"
  else
    bash -c "$*"
  fi
}

VERDICT="UNKNOWN"
WORKER_FINDING=""
say() { printf '\n=== %s ===\n' "$1"; }

say "1. systemd unit — ExecStart (the authority on worker count)"
UNIT="$(run "systemctl cat ai-backend 2>/dev/null" || true)"
if [ -z "$UNIT" ]; then
  echo "FAIL  ai-backend.service not readable (not the backend host, or no permission)"
  VERDICT="UNKNOWN"
else
  echo "$UNIT" | grep -E '^(#|\[|ExecStart|WorkingDirectory|Environment)' | sed 's/^/  /'
  EXEC_START="$(echo "$UNIT" | grep -E '^ExecStart=' || true)"
  echo "  ExecStart line: ${EXEC_START:-<none>}"
  if echo "$EXEC_START" | grep -Eq -- '--workers[= ]([2-9]|[1-9][0-9])'; then
    WORKER_FINDING="ExecStart declares multiple uvicorn workers"
  elif echo "$EXEC_START" | grep -Eq -- 'gunicorn|uvicorn.*--workers'; then
    WORKER_FINDING="ExecStart uses a worker-managing launcher"
  fi
fi

say "2. live process tree (what is actually running)"
PIDS="$(run "systemctl show ai-backend -p MainPID --value 2>/dev/null" || true)"
echo "  MainPID: ${PIDS:-unknown}"
if [ -n "${PIDS:-}" ] && [ "${PIDS:-0}" != "0" ]; then
  echo "  --- MainPID children (one uvicorn child = one worker) ---"
  run "ps -o pid,ppid,etime,cmd --ppid $PIDS 2>/dev/null" || true
  echo "  --- uvicorn / gunicorn processes owned by this unit ---"
  run "pgrep -a -f 'uvicorn|gunicorn' 2>/dev/null" || true
  CHILDREN="$(run "ps -o pid= --ppid $PIDS 2>/dev/null | wc -l" || echo 0)"
  echo "  child process count: $CHILDREN"
  if [ "${CHILDREN:-0}" -gt 1 ]; then
    WORKER_FINDING="${WORKER_FINDING:+$WORKER_FINDING; }$CHILDREN child processes under MainPID"
  fi
fi

say "3. nginx upstream(s) for the API"
NGINX="$(run "nginx -T 2>/dev/null || cat /etc/nginx/sites-enabled/* 2>/dev/null" || true)"
if [ -z "$NGINX" ]; then
  echo "FAIL  nginx configuration not readable"
else
  echo "$NGINX" | grep -nE 'upstream |proxy_pass|server 127\.0\.0\.1:8000' | sed 's/^/  /'
  UPSTREAM_SERVERS="$(echo "$NGINX" | grep -cE '^\s*server\s+[0-9.]+:8000' || true)"
  echo "  upstream server count for :8000 = ${UPSTREAM_SERVERS:-0}"
  if [ "${UPSTREAM_SERVERS:-0}" -gt 1 ]; then
    WORKER_FINDING="${WORKER_FINDING:+$WORKER_FINDING; }nginx load-balances across multiple :8000 backends"
  fi
fi

say "4. backend health"
run "curl -sS -m 5 http://127.0.0.1:8000/api/health" || echo "  FAIL  /api/health unreachable"
echo
run "curl -sS -m 5 -o /dev/null -w '  /api/health HTTP %{http_code}\n' http://127.0.0.1:8000/api/health" || true

say "5. scientific runtime health"
run "systemctl is-active zhixue-runtime 2>/dev/null" || echo "  (unit not present)"
run "curl -sS -m 5 http://127.0.0.1:8101/health" || echo "  FAIL  scientific runtime unreachable"
echo

say "6. VERDICT"
if [ -n "$WORKER_FINDING" ]; then
  VERDICT="MULTI_WORKER"
  echo "  MULTI-WORKER SIGNALS: $WORKER_FINDING"
  echo "  → ai.health's process_local availability is NOT exact on this host."
  echo "  → ESCALATE: the Router availability shared-state requirement becomes a deployment"
  echo "    blocker (a shared store, or a pinned single worker, is required before relying on"
  echo "    /admin/ai-operations/summary availability or on fallback ordering under degradation)."
elif [ "$VERDICT" = "UNKNOWN" ]; then
  echo "  UNKNOWN — the unit file or the process tree could not be read."
  echo "  → Treat the AI availability view as advisory until this script reports SINGLE_PROCESS."
else
  echo "  SINGLE_PROCESS — the P5 assumption is confirmed on this host."
fi

if [ -n "$WORKER_FINDING" ] || [ "$VERDICT" = "UNKNOWN" ]; then
  exit 1
fi
exit 0
