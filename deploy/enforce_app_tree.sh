#!/usr/bin/env bash
# Enforce the immutable application-tree permission model — SECURITY_S0B-P1 / Stage 5A.
#
# The runtime tree must be readable and executable by the web identity, and writable by
# nobody else. That is not cosmetic: the SECURITY_S0B privilege separation rests on the
# sandbox runner being unable to read the application tree at all, because the tree holds
# backend/.env and every source file from which a bypass could be reconstructed.
#
#   directory : owner rwx · group r-x · setgid · NO group write · no world
#   file      : owner rw  · group r   · no world   (group execute mirrors owner execute)
#   .env      : 0640 — the application calls load_dotenv() during import, so the web
#               identity MUST be able to read it. An existing-but-unreadable .env raises
#               PermissionError inside that call and the service never starts.
#
# The deploy account owns the tree and therefore keeps write access through its OWNER
# bits; nothing here needs group write. That is precisely what makes "the web identity
# cannot write the code tree" true while the deploy can still update it.
#
# Required on every deploy, not just the first: `rsync -a` restores the SOURCE file modes
# (0644/0755), so other-read reappears with every release unless it is stripped again.
set -euo pipefail

ROOT="${1:?usage: enforce_app_tree.sh <app-root> [group]}"
GROUP="${2:-zhixue-app}"

if [ ! -d "$ROOT" ]; then
  echo "enforce_app_tree: missing app root: $ROOT" >&2
  exit 1
fi
if ! getent group "$GROUP" >/dev/null 2>&1; then
  echo "enforce_app_tree: missing group: $GROUP" >&2
  exit 1
fi

# chgrp -R does not follow symlinks, so the uploads/backups links into /var/lib are left
# pointing at data that enforce_shared_state.sh owns the permissions of.
chgrp -R "$GROUP" "$ROOT"
find "$ROOT" -type d -exec chmod u+rwx,g+rx,g-w,g+s,o-rwx {} +
find "$ROOT" -type f -exec chmod u+rw,g+r,g-w,o-rwx {} +
# pip-created console scripts and deploy/*.sh already carry owner execute; mirror it so
# the web identity can execute them too.
find "$ROOT" -type f -perm -u+x -exec chmod g+x {} +
chmod 2750 "$ROOT"

if [ -f "$ROOT/backend/.env" ]; then
  chmod 0640 "$ROOT/backend/.env"
fi

echo "enforce_app_tree: $ROOT — dirs 2750, files 0640/0750, group=$GROUP, owner preserved"
