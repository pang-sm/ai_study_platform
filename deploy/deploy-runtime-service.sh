#!/usr/bin/env bash
# Deploy the Scientific Runtime Service (zhixue-runtime) to /opt/zhixue-runtime.
#
# Idempotent. Run on the production host as the deploy user (sudo for systemd/opt).
#
# The service code (scientific_runtime_service/) is deployed from the repo.
# The frozen scientific closure (zhixue-runtime-v1-phase1gr-student-twin: the
# zhixue_runtime package + student_twin source, NO heavy model assets) is a separate
# one-time upload; pass its path via CLOSURE_SRC. If it is already installed under
# $RUNTIME_HOME, CLOSURE_SRC can be omitted.
set -euo pipefail

RUNTIME_HOME=/opt/zhixue-runtime
REPO_ROOT="${REPO_ROOT:-$HOME/ai_study_platform}"
CLOSURE_SRC="${CLOSURE_SRC:-}"

echo "[zhixue-runtime] install service code"
sudo mkdir -p "$RUNTIME_HOME"
sudo rsync -a --delete "$REPO_ROOT/scientific_runtime_service/" "$RUNTIME_HOME/scientific_runtime_service/"

echo "[zhixue-runtime] install frozen closure (zhixue_runtime + student_twin source)"
if [ -n "$CLOSURE_SRC" ] && [ -d "$CLOSURE_SRC" ]; then
    sudo mkdir -p "$RUNTIME_HOME/zhixue-runtime-v1-phase1gr-student-twin"
    sudo rsync -a --delete "$CLOSURE_SRC/" "$RUNTIME_HOME/zhixue-runtime-v1-phase1gr-student-twin/"
fi
if [ ! -f "$RUNTIME_HOME/zhixue-runtime-v1-phase1gr-student-twin/src/zhixue_runtime/__init__.py" ]; then
    echo "[zhixue-runtime] ERROR: closure not present; upload zhixue-runtime-v1-phase1gr-student-twin first" >&2
    exit 1
fi

echo "[zhixue-runtime] create dedicated venv (numpy only; NOT backend/.venv)"
if [ ! -x "$RUNTIME_HOME/venv/bin/python" ]; then
    python3 -m venv "$RUNTIME_HOME/venv"
fi
"$RUNTIME_HOME/venv/bin/pip" install -q --upgrade pip
"$RUNTIME_HOME/venv/bin/pip" install -q -r "$RUNTIME_HOME/scientific_runtime_service/requirements.txt"

echo "[zhixue-runtime] install systemd unit"
sudo cp "$REPO_ROOT/deploy/zhixue-runtime.service" /etc/systemd/system/zhixue-runtime.service
sudo systemctl daemon-reload
sudo systemctl enable zhixue-runtime >/dev/null 2>&1 || true
sudo systemctl restart zhixue-runtime

echo "[zhixue-runtime] health check (loopback only)"
for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8101/health >/dev/null 2>&1; then
        echo "[zhixue-runtime] health ok"
        exit 0
    fi
    sleep 2
done
echo "[zhixue-runtime] health failed"
sudo journalctl -u zhixue-runtime -n 50 --no-pager || true
exit 1
