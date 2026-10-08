#!/usr/bin/env bash
# SECURITY_S0B Stage 5A — runner IPC acceptance driver.
#
# Starts the runner as a TRANSIENT systemd unit under the exact hardening profile the
# installed unit file carries, on a TEST socket name, runs the protocol acceptance as
# zhixue-web, checks access control at the filesystem level, and tears everything down.
#
# Nothing here installs or enables the production unit, and the production socket name
# (runner.sock) is never created — the application's execution gate stays closed.
set -uo pipefail

TESTDIR=/run/zhixue-sandbox-test
SOCK="$TESTDIR/runner-test.sock"
UNIT=zhixue-runner-ipc-test
PASS=0; FAIL=0
ok()  { echo "  PASS  $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }

cleanup() {
  sudo systemctl stop "$UNIT" >/dev/null 2>&1 || true
  sudo systemctl reset-failed "$UNIT" >/dev/null 2>&1 || true
  sudo rm -rf "$TESTDIR"
}
trap cleanup EXIT

echo "── start the runner on a TEST socket under the final hardening profile ──"
sudo rm -rf "$TESTDIR"
sudo install -d -m 2750 -o zhixue-sandbox -g zhixue-ipc "$TESTDIR"
# rootless podman's per-user pause process outlives the unit that created it, and a stale
# one from a different sandbox context makes every container fail with an opaque error. The
# process's command line is bare ``podman``, so match the NAME. Killing the process is the
# whole reset — do NOT wipe /run/user/997/libpod, which holds user-namespace bookkeeping
# and, if removed, makes the next start fail with a misleading newuidmap error.
sudo pkill -x -u zhixue-sandbox podman 2>/dev/null || true
sleep 1
sudo systemd-run --unit="$UNIT" --collect \
  --uid=zhixue-sandbox --gid=zhixue-sandbox \
  --setenv=XDG_RUNTIME_DIR=/run/user/997 \
  --setenv=HOME=/var/lib/zhixue-sandbox \
  --setenv=SANDBOX_CONTAINER_RUNTIME=podman \
  --setenv=PYTHONUNBUFFERED=1 \
  --setenv=SANDBOX_RUNNER_SOCKET="$SOCK" \
  --setenv=TMPDIR=/var/lib/zhixue-sandbox/tmp \
  --property=WorkingDirectory=/opt/zhixue-sandbox-runner/app \
  --property=UMask=0007 \
  --property=NoNewPrivileges=no --property=RestrictSUIDSGID=no \
  --property=RestrictNamespaces=no --property=ProtectControlGroups=no \
  --property=ProtectSystem=strict --property=PrivateTmp=yes \
  --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes \
  --property=ProtectKernelLogs=yes --property=ProtectClock=yes \
  --property=LockPersonality=yes --property=RestrictRealtime=yes \
  --property=RestrictAddressFamilies="AF_UNIX AF_INET AF_INET6 AF_NETLINK" \
  --property=InaccessiblePaths="/home/ubuntu /root" \
  --property=ReadWritePaths="/var/lib/zhixue-sandbox $TESTDIR /run/user/997" \
  /opt/zhixue-sandbox-runner/venv/bin/uvicorn core.sandbox.runner.app:app --uds "$SOCK" \
  >/dev/null 2>&1
for _ in $(seq 1 50); do sudo test -S "$SOCK" && break; sleep 1; done
# The same tightening the unit's ExecStartPost performs — see zhixue-sandbox-runner.service
# for why it cannot live in the application (uvicorn binds after the lifespan startup).
sudo -u zhixue-sandbox chmod 0660 "$SOCK" 2>/dev/null || true
# sudo is required for these probes precisely BECAUSE the access control works: the deploy
# account is not in zhixue-ipc, so it cannot even stat inside the socket directory.
sudo test -S "$SOCK" && ok "runner is listening on the test socket" || { bad "runner never listened"; exit 1; }

echo "── socket path permissions (the access-control boundary) ──"
DIR_MODE="$(sudo stat -c '%a %U:%G' "$TESTDIR")"
SOCK_MODE="$(sudo stat -c '%a %U:%G' "$SOCK")"
echo "  note  dir=$DIR_MODE  socket=$SOCK_MODE"
[ "$DIR_MODE" = "2750 zhixue-sandbox:zhixue-ipc" ] && ok "socket directory is 2750 zhixue-sandbox:zhixue-ipc" || bad "socket dir is $DIR_MODE"
case "$SOCK_MODE" in
  *zhixue-ipc) ok "socket carries the shared IPC group" ;;
  *) bad "socket group is $SOCK_MODE" ;;
esac
case "$SOCK_MODE" in
  7?0\ *|6?0\ *) ok "socket has no world permissions" ;;
  *) bad "socket may be world-reachable ($SOCK_MODE)" ;;
esac

echo "── who may connect ──"
cat > /tmp/connect_probe.py <<'PYEOF'
import socket, sys
s = socket.socket(socket.AF_UNIX)
s.settimeout(5)
try:
    s.connect(sys.argv[1])
    print("CONNECTED")
except Exception as exc:  # noqa: BLE001
    print("DENIED", type(exc).__name__)
PYEOF
chmod 644 /tmp/connect_probe.py
WEB_OUT=$(sudo -u zhixue-web -H bash -c "env HOME=/tmp python3 /tmp/connect_probe.py '$SOCK'" 2>&1 | tail -1)
[ "$WEB_OUT" = "CONNECTED" ] && ok "zhixue-web CONNECTS to the runner socket" || bad "zhixue-web denied: $WEB_OUT"
NOBODY_OUT=$(sudo -u nobody -H bash -c "env HOME=/tmp python3 /tmp/connect_probe.py '$SOCK'" 2>&1 | tail -1)
[ "$NOBODY_OUT" = "CONNECTED" ] && bad "an unrelated account CONNECTED (must be denied)" || ok "unrelated account DENIED ($NOBODY_OUT)"
# The runner's own socket must not be replaceable or impersonable by the web identity.
if sudo -u zhixue-web bash -c "rm -f '$SOCK'" 2>/dev/null; then bad "zhixue-web could DELETE the socket"; else ok "zhixue-web cannot delete or replace the socket"; fi
if sudo -u zhixue-web bash -c "touch '$TESTDIR/fake.sock'" 2>/dev/null; then bad "zhixue-web could CREATE entries in the socket dir"; sudo rm -f "$TESTDIR/fake.sock"; else ok "zhixue-web cannot create entries in the socket directory"; fi

echo "── protocol acceptance as zhixue-web ──"
sudo -u zhixue-web -H bash -c \
  "cd /opt/ai_study_platform/backend && env HOME=/tmp SANDBOX_RUNNER_SOCKET='$SOCK' \
   /opt/ai_study_platform/backend/.venv/bin/python /tmp/_stage5a_ipc_protocol.py"
[ $? -eq 0 ] && ok "protocol suite passed" || bad "protocol suite reported failures"

echo "── isolation ──"
sudo -u zhixue-web test -r /var/run/docker.sock 2>/dev/null && bad "web can read the rootful docker socket" || ok "web CANNOT read the rootful docker socket"
sudo -u zhixue-web docker ps >/dev/null 2>&1 && bad "web can run docker" || ok "web CANNOT run docker"
sudo -u zhixue-web podman ps >/dev/null 2>&1 && bad "web can run podman" || ok "web CANNOT run podman"
sudo -u zhixue-web test -r /var/lib/ai_study_platform/app.db 2>/dev/null && echo "  note  web DOES have DB access (correct: it is the application)" || bad "web lost its own DB access"
sudo -u zhixue-sandbox test -r /var/lib/ai_study_platform/app.db 2>/dev/null && bad "runner can read the production database" || ok "runner CANNOT read the production database"
sudo -u zhixue-sandbox head -c1 /opt/ai_study_platform/backend/.env >/dev/null 2>&1 && bad "runner can read backend/.env" || ok "runner CANNOT read backend/.env"
sudo -u zhixue-sandbox ls /opt/ai_study_platform/backend >/dev/null 2>&1 && bad "runner can read the application tree" || ok "runner CANNOT read the application tree"
sudo -u zhixue-web ls /opt/zhixue-sandbox-runner >/dev/null 2>&1 && bad "web can read the runner tree" || ok "web CANNOT read the runner tree"
[ -S /run/zhixue-sandbox/runner.sock ] && bad "PRODUCTION socket exists" || ok "production socket runner.sock was never created"
echo "  note  the deploy account itself cannot stat inside the socket directory (2750 zhixue-ipc): $(sudo -u ubuntu stat -c '%n' "$SOCK" 2>&1 | tail -1)"

echo
echo "══ IPC RESULT: PASS=$PASS FAIL=$FAIL ══"
[ "$FAIL" -eq 0 ] || exit 1
