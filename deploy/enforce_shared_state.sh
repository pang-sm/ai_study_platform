#!/usr/bin/env bash
# Enforce the shared mutable-state permission model — SECURITY_S0B-P1 / Stage 5A.
#
# /var/lib/ai_study_platform holds everything the application writes: the SQLite database
# with its WAL/SHM, learner uploads, and deploy snapshots. Exactly two OS identities need
# access — the one running the web service and the deploy account — so the model is:
#
#     owner preserved · group zhixue-app · setgid dirs · group read+write · no world
#
# Three mistakes this script exists to prevent, each with a concrete failure mode:
#
#   * `chown -R` — reassigning the owner of the live database and of every learner upload.
#     The pre-Stage-5A deploy did this on every run, silently rewriting ownership of user
#     data that the application had created.
#   * `chmod 755` on the root — leaves the tree world-traversable, so an unrelated service
#     account (e.g. the sandbox runner) could open the production database.
#   * leaving the WAL/SHM to chance — SQLite recreates `app.db-wal` after every checkpoint,
#     and a file created without group write is unusable by the OTHER identity the moment
#     the service switches users, which is exactly what the Stage 5B cutover does.
#
# Idempotent by construction: it applies the same chgrp/chmod set regardless of the
# starting state, so it is safe on every deploy and after every restore.
set -euo pipefail

ROOT="${1:?usage: enforce_shared_state.sh <shared-state-root> [group]}"
GROUP="${2:-zhixue-app}"

if [ ! -d "$ROOT" ]; then
  echo "enforce_shared_state: missing shared state root: $ROOT" >&2
  exit 1
fi
if ! getent group "$GROUP" >/dev/null 2>&1; then
  echo "enforce_shared_state: missing group: $GROUP" >&2
  exit 1
fi

# chgrp, never chown: who owns a learner's upload or the live database is not this
# script's decision to make.
chgrp -R "$GROUP" "$ROOT"
find "$ROOT" -type d -exec chmod g+rwxs,o-rwx {} +
find "$ROOT" -type f -exec chmod g+rw,o-rwx {} +
# setgid on the root itself so every newly created entry inherits the shared group.
chmod 2770 "$ROOT"

echo "enforce_shared_state: $ROOT — owner preserved, group=$GROUP, dirs 2770, files g+rw, world removed"
