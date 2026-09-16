#!/usr/bin/env bash
# Deploy the Scientific Runtime Service (zhixue-runtime) to /opt/zhixue-runtime.
#
# Uses the immutable artifact committed under deploy/artifacts/ — it does NOT require the
# production host to already hold the closure. Idempotent. Versioned release dir with a
# /opt/zhixue-runtime/current symlink so rollback never re-downloads scientific source.
set -euo pipefail

RUNTIME_HOME=/opt/zhixue-runtime
REPO_ROOT="${REPO_ROOT:-$HOME/ai_study_platform}"

ARTIFACT_ID="zhixue-runtime-v1-phase1gr-p1-student-twin"
ARTIFACT_DIR="$REPO_ROOT/deploy/artifacts"
ARTIFACT="$ARTIFACT_DIR/$ARTIFACT_ID.tar.gz"
ARTIFACT_SHA="$ARTIFACT_DIR/$ARTIFACT_ID.sha256"
RELEASE_DIR="$RUNTIME_HOME/releases/$ARTIFACT_ID"
CURRENT="$RUNTIME_HOME/current"

echo "[zhixue-runtime] install service code"
sudo mkdir -p "$RUNTIME_HOME/scientific_runtime_service"
sudo rsync -a --delete "$REPO_ROOT/scientific_runtime_service/" "$RUNTIME_HOME/scientific_runtime_service/"

echo "[zhixue-runtime] verify artifact SHA-256"
(cd "$ARTIFACT_DIR" && sha256sum -c "$ARTIFACT_ID.sha256")

echo "[zhixue-runtime] extract immutable artifact to versioned release dir"
if [ ! -f "$RELEASE_DIR/closure_manifest.json" ]; then
    sudo rm -rf "$RELEASE_DIR"
    sudo mkdir -p "$RELEASE_DIR"
    sudo tar -xzf "$ARTIFACT" -C "$RELEASE_DIR"
fi
sudo ln -sfn "$RELEASE_DIR" "$CURRENT"

echo "[zhixue-runtime] create dedicated venv (numpy only; NOT backend/.venv)"
sudo chown -R "$(whoami):$(whoami)" "$RUNTIME_HOME"
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
