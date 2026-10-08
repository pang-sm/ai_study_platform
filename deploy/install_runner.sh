#!/usr/bin/env bash
# Install the sandbox runner into its own tree — SECURITY_S0B-P1 / Stage 5A.
#
# The runner runs as `zhixue-sandbox` and owns a rootless container runtime. The web
# application must NOT be able to read its code, and the runner must NOT be able to read
# the application: that separation is the whole point of the split, so the two trees are
# installed separately from the same frozen source rather than one referencing the other.
#
#   source : <app-root>/backend/core/{__init__.py,sandbox/**}
#   target : /opt/zhixue-sandbox-runner/{app/..., venv/}
#   owner  : root:zhixue-sandbox, group read+execute, no write for anyone but root
#
# Idempotent. Installing the systemd unit is a SEPARATE, explicit step (`--install-unit`);
# preparing the tree must never enable execution as a side effect.
set -euo pipefail

RUNNER_HOME=/opt/zhixue-sandbox-runner
RUNNER_USER=zhixue-sandbox
RUNNER_GROUP=zhixue-sandbox
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(dirname "$SCRIPT_DIR")}"

INSTALL_UNIT=no
for arg in "$@"; do
  case "$arg" in
    --install-unit) INSTALL_UNIT=yes ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -d "$REPO_ROOT/backend/core/sandbox" ]; then
  echo "install_runner: no core/sandbox under $REPO_ROOT/backend" >&2
  exit 1
fi
id "$RUNNER_USER" >/dev/null 2>&1 || { echo "install_runner: missing user $RUNNER_USER" >&2; exit 1; }

# ── 1. code: exactly the runner's import closure ────────────────────────────────
sudo mkdir -p "$RUNNER_HOME/app/core"
sudo rsync -a --delete \
  "$REPO_ROOT/backend/core/__init__.py" \
  "$RUNNER_HOME/app/core/__init__.py"
sudo rsync -a --delete --exclude='__pycache__' \
  "$REPO_ROOT/backend/core/sandbox/" "$RUNNER_HOME/app/core/sandbox/"
# The web-side client lives in the same package but must not ship here — it is the other
# half of the IPC boundary and imports httpx, which this tree deliberately does not carry.
sudo rm -f "$RUNNER_HOME/app/core/sandbox/runner_client.py"
# The application's package __init__ is the web facade: it imports core.code_execution and
# core.config, so leaving it in place makes the runner fail to start with
# "No module named 'core.code_execution'". Replace it with the engine-only variant.
sudo cp "$SCRIPT_DIR/runner_package_init.py" "$RUNNER_HOME/app/core/sandbox/__init__.py"

# ── 2. venv: the three packages the closure actually needs ──────────────────────
if [ ! -x "$RUNNER_HOME/venv/bin/python" ]; then
  sudo python3 -m venv "$RUNNER_HOME/venv"
fi
sudo "$RUNNER_HOME/venv/bin/python" -m pip install --quiet --upgrade pip
sudo "$RUNNER_HOME/venv/bin/python" -m pip install --quiet -r "$SCRIPT_DIR/runner-requirements.txt"

# ── 2b. TMPDIR: the runner's own scratch, since ProtectSystem=strict makes /tmp read-only
# and the per-run directory is bind-mounted into the container, so it must live somewhere
# podman's rootless pause process can resolve.
sudo mkdir -p /var/lib/zhixue-sandbox/tmp
sudo chown "$RUNNER_USER:$RUNNER_GROUP" /var/lib/zhixue-sandbox/tmp
sudo chmod 0700 /var/lib/zhixue-sandbox/tmp

# ── 3. ownership: readable by the runner, writable only by root ─────────────────
sudo chown -R "root:$RUNNER_GROUP" "$RUNNER_HOME"
sudo find "$RUNNER_HOME" -type d -exec chmod u+rwx,g+rx,o-rwx {} +
sudo find "$RUNNER_HOME" -type f -exec chmod u+rw,g+r,o-rwx {} +
sudo find "$RUNNER_HOME" -type f -perm -u+x -exec chmod g+x {} +

echo "install_runner: $RUNNER_HOME installed"
echo "install_runner: runtime=$(sudo -u "$RUNNER_USER" -H bash -c "cd /tmp && XDG_RUNTIME_DIR=/run/user/$(id -u "$RUNNER_USER") podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null || echo unknown")"

if [ "$INSTALL_UNIT" = yes ]; then
  sudo cp "$SCRIPT_DIR/zhixue-sandbox-runner.service" /etc/systemd/system/zhixue-sandbox-runner.service
  sudo cp "$SCRIPT_DIR/zhixue-sandbox-runner.tmpfiles.conf" /etc/tmpfiles.d/zhixue-sandbox-runner.conf
  sudo systemd-tmpfiles --create /etc/tmpfiles.d/zhixue-sandbox-runner.conf
  # ── the pause warmup: a USER unit, because only the user manager's context can create the
  # rootless pause process on this host (see zhixue-sandbox-pause-warmup.service). It needs
  # a running, LINGERING user manager; linger is a host prerequisite (loginctl
  # enable-linger) that this script reports rather than silently assumes.
  RUNNER_UID="$(id -u "$RUNNER_USER")"
  sudo install -d -m 0755 -o "$RUNNER_USER" -g "$RUNNER_GROUP" /var/lib/zhixue-sandbox/.config/systemd/user
  sudo install -m 0644 -o "$RUNNER_USER" -g "$RUNNER_GROUP" \
    "$SCRIPT_DIR/zhixue-sandbox-pause-warmup.service" \
    /var/lib/zhixue-sandbox/.config/systemd/user/sandbox-pause-warmup.service
  if [ -d "/run/user/$RUNNER_UID" ]; then
    sudo -u "$RUNNER_USER" -H env XDG_RUNTIME_DIR="/run/user/$RUNNER_UID" systemctl --user daemon-reload
    sudo -u "$RUNNER_USER" -H env XDG_RUNTIME_DIR="/run/user/$RUNNER_UID" systemctl --user enable sandbox-pause-warmup.service
    echo "install_runner: pause warmup enabled for $RUNNER_USER (linger=$(loginctl show-user "$RUNNER_USER" --property=Linger --value 2>/dev/null || echo unknown))"
  else
    echo "install_runner: WARNING: /run/user/$RUNNER_UID is absent (linger off or user manager down);" >&2
    echo "install_runner: enable linger (loginctl enable-linger $RUNNER_USER) and re-run --install-unit" >&2
  fi
  sudo systemctl daemon-reload
  echo "install_runner: unit installed but NOT enabled (execution stays disabled)"
else
  echo "install_runner: systemd unit NOT installed (pass --install-unit to install it)"
fi
