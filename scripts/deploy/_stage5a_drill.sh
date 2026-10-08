#!/usr/bin/env bash
# SECURITY_S0B Stage 5A — cutover / rollback / data-consistency drill.
#
# Runs ENTIRELY inside /var/tmp/stage5a-drill. It never touches /home/ubuntu,
# /opt/ai_study_platform or /var/lib/ai_study_platform, and it never restarts anything.
#
# What it proves, in the order the real cutover would meet it:
#   1. the old layout (real directories) and the new layout (symlinks into shared state)
#      can both serve the same data;
#   2. the deploy's OLD rsync excludes destroy the symlinks and the NEW ones do not;
#   3. SQLite's WAL/SHM survive an identity change ONLY because of umask 0007 + setgid —
#      with the default umask the rollback path cannot write its own WAL;
#   4. after the switch, writes made by the NEW identity are visible to the OLD code
#      path, so a rollback never reads a stale copy;
#   5. enforce_shared_state.sh repairs exactly the regression the old deploy caused, and
#      is idempotent across repeated deploys.
set -uo pipefail

DRILL=/var/tmp/stage5a-drill
SHARED=$DRILL/shared
OLD=$DRILL/old_tree
NEW=$DRILL/new_tree
PASS=0
FAIL=0

ok()   { echo "  PASS  $*"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }
chk()  { if [ "$2" = "$3" ]; then ok "$1 ($2)"; else bad "$1 — got '$2', expected '$3'"; fi; }
head2() { echo; echo "── $* ──"; }

# ── 0. build the drill layout ───────────────────────────────────────────────────
head2 "0. setup"
sudo rm -rf "$DRILL"
mkdir -p "$SHARED/uploads" "$SHARED/backups" "$OLD/backend/uploads" "$OLD/backend/backups"
mkdir -p "$NEW/backend"
ln -sfn "$SHARED/uploads" "$NEW/backend/uploads"
ln -sfn "$SHARED/backups" "$NEW/backend/backups"
# The shared tree gets the production model; the old tree gets today's permissive one.
sudo chgrp -R zhixue-app "$SHARED"
sudo find "$SHARED" -type d -exec chmod 2770 {} +
chmod 755 "$DRILL" "$OLD" "$OLD/backend" "$NEW" "$NEW/backend"
# A sentinel already in shared state, so the --delete test can prove that replacing the
# release tree cannot reach the authoritative copy.
echo "already-authoritative" > "$SHARED/uploads/sentinel.md"
echo "  layout built under $DRILL"

# ── 1. the OLD release serves and writes ────────────────────────────────────────
head2 "1. old release writes (real directories, ubuntu, umask 022)"
sudo -u ubuntu -H bash -c "umask 022; echo old-material-1 > '$OLD/backend/uploads/material-1.md'"
sudo -u ubuntu -H bash -c "umask 022; echo old-backup-1 > '$OLD/backend/backups/snapshot-1.db'"
chk "old upload written"  "$(cat "$OLD/backend/uploads/material-1.md")" "old-material-1"

# ── 2. rsync --delete: the exclude patterns decide whether the symlink survives ──
head2 "2. rsync --delete vs the uploads/backups symlinks"
STAGE=$DRILL/stage
mkdir -p "$STAGE/backend/core"
echo "print(1)" > "$STAGE/backend/core/app.py"
# a) the PRE-Stage-5A patterns (trailing slash = "directory contents only")
rsync -a --delete --exclude='.git/' --exclude='backend/app.db' --exclude='backend/.env' \
  --exclude='backend/.venv/' --exclude='backend/backups/' --exclude='backend/uploads/' \
  "$STAGE/" "$NEW/" >/dev/null 2>&1
if [ -L "$NEW/backend/uploads" ]; then
  bad "OLD excludes PROTECTED the symlink — the reported bug does not reproduce"
else
  ok "OLD excludes DELETED the symlink (reproduces the bug the fix addresses)"
fi
# b) the Stage-5A patterns (anchored, no trailing slash)
ln -sfn "$SHARED/uploads" "$NEW/backend/uploads"
ln -sfn "$SHARED/backups" "$NEW/backend/backups"
rsync -a --delete --exclude='.git/' --exclude='backend/app.db' --exclude='backend/.env' \
  --exclude='backend/.venv/' --exclude='/backend/backups' --exclude='/backend/uploads' \
  "$STAGE/" "$NEW/" >/dev/null 2>&1
[ -L "$NEW/backend/uploads" ] && ok "NEW excludes KEPT the uploads symlink" || bad "NEW excludes deleted the symlink"
[ -L "$NEW/backend/backups" ] && ok "NEW excludes KEPT the backups symlink" || bad "NEW excludes deleted the backups symlink"
chk "shared data intact after --delete" "$(cat "$SHARED/uploads/sentinel.md")" "already-authoritative"

# ── 3. the cutover: final sync, preserve the originals, redirect the old tree ────
head2 "3. cutover"
rsync -a "$OLD/backend/uploads/" "$SHARED/uploads/"     # final delta sync
rsync -a "$OLD/backend/backups/" "$SHARED/backups/"
# `rsync -a src/ dst/` applies the SOURCE directory's own mode and ownership to `dst`.
# The release-side source is a plain 0755 ubuntu:ubuntu directory, so the final sync —
# the very step that hands the data over — strips the shared-state model and leaves the
# authoritative uploads directory unwritable by the web identity. It has to be repaired
# afterwards, and this is the drill that caught it.
AFTER_SYNC="$(stat -c '%a %G' "$SHARED/uploads")"
if [ "$AFTER_SYNC" = "2770 zhixue-app" ]; then
  echo "  note  final sync left the shared model intact ($AFTER_SYNC)"
else
  ok "final sync STRIPPED the shared model ($AFTER_SYNC) — enforcement must follow every sync"
fi
sudo bash /tmp/check5a/enforce_shared_state.sh "$SHARED" zhixue-app >/dev/null
chk "shared model restored after the final sync" "$(stat -c '%a %G' "$SHARED/uploads")" "2770 zhixue-app"
sudo mv "$OLD/backend/uploads" "$OLD/backend/uploads.pre-cutover"
sudo mv "$OLD/backend/backups" "$OLD/backend/backups.pre-cutover"
ln -sfn "$SHARED/uploads" "$OLD/backend/uploads"
ln -sfn "$SHARED/backups" "$OLD/backend/backups"
[ -L "$OLD/backend/uploads" ] && ok "old tree now points at the shared uploads" || bad "old tree uploads not redirected"
[ -d "$OLD/backend/uploads.pre-cutover" ] && ok "original directory preserved as rollback material" || bad "original not preserved"
chk "old data visible through the redirect" "$(cat "$OLD/backend/uploads/material-1.md")" "old-material-1"

# ── 4. the NEW release writes ───────────────────────────────────────────────────
head2 "4. new release writes (zhixue-web through the symlink)"
sudo -u zhixue-web -H bash -c "umask 007; echo new-material-2 > '$NEW/backend/uploads/material-2.md'" \
  && ok "zhixue-web wrote through the symlink" || bad "zhixue-web could not write through the symlink"
chk "new write landed in shared state" "$(cat "$SHARED/uploads/material-2.md")" "new-material-2"

# ── 5. rollback: the OLD code path must see everything ──────────────────────────
head2 "5. rollback to the old release"
OLDFILES=$(cat "$OLD/backend/uploads/material-1.md" "$OLD/backend/uploads/material-2.md" 2>/dev/null | tr '\n' ',')
chk "old code path sees old AND new data" "$OLDFILES" "old-material-1,new-material-2,"
chk "exactly one writable copy exists" "$(find "$DRILL" -name 'material-2.md' | wc -l)" "1"
chk "pre-cutover copy was not written to" \
    "$(find "$OLD/backend/uploads.pre-cutover" -type f | wc -l)" "1"

# ── 6. SQLite across an identity change: umask is the whole ballgame ────────────
head2 "6. SQLite WAL/SHM across the identity switch"
cat > "$DRILL/wal_probe.py" <<'PYEOF'
import os, sqlite3, sys
db, tag = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db)
con.execute("PRAGMA journal_mode=WAL")
con.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")
con.execute("INSERT INTO t VALUES (?)", (tag,))
con.commit()
print("%o" % (os.stat(db + "-wal").st_mode & 0o777))
con.close()
PYEOF
chmod 644 "$DRILL/wal_probe.py"
DRILLDB=$SHARED/app.db
sudo rm -f "$DRILLDB" "$DRILLDB-wal" "$DRILLDB-shm"

# 6a — the production of today: umask 022, no group write anywhere.
sudo rm -f "$DRILLDB" "$DRILLDB-wal" "$DRILLDB-shm"
M1=$(sudo -u ubuntu -H bash -c "umask 022; python3 $DRILL/wal_probe.py $DRILLDB old" 2>/dev/null)
chk "old identity (umask 022) creates WAL mode" "$M1" "644"
chk "database file is not group-writable" "$(stat -c '%a' "$DRILLDB")" "644"
if sudo -u zhixue-web -H bash -c "umask 022; python3 $DRILL/wal_probe.py $DRILLDB handoff-umask022" >/dev/null 2>&1; then
  bad "handoff succeeded under umask 022 — the drill is not reproducing the hazard"
else
  ok "handoff DENIED under umask 022 (the hazard UMask=0007 exists to remove)"
fi

# 6b — the Stage 5A model: shared group, group write, and umask 0007 for the service.
sudo bash /tmp/check5a/enforce_shared_state.sh "$SHARED" zhixue-app >/dev/null
chk "database is group-writable after enforcement" "$(stat -c '%a' "$DRILLDB")" "660"
M2=$(sudo -u zhixue-web -H bash -c "umask 007; python3 $DRILL/wal_probe.py $DRILLDB new-umask007" 2>/dev/null)
chk "new identity (umask 007) creates WAL mode" "$M2" "660"
if sudo -u ubuntu -H bash -c "umask 007; python3 $DRILL/wal_probe.py $DRILLDB rollback-umask007" >/dev/null 2>&1; then
  ok "rollback identity writes the SAME database (shared group + UMask=0007)"
else
  bad "rollback identity still denied under the Stage 5A model"
fi
ROWS=$(sqlite3 "$DRILLDB" 'select count(*) from t' 2>/dev/null)
chk "no row lost across every identity switch" "${ROWS:-0}" "3"

# ── 7. the permission model heals the old deploy's regression, and is idempotent ─
head2 "7. enforce_shared_state.sh — repair and idempotency"
sudo chown -R ubuntu:ubuntu "$SHARED"          # what the OLD deploy did
sudo chmod 755 "$SHARED"                        # and this
chk "regression reproduced (group)"  "$(stat -c '%G' "$SHARED")" "ubuntu"
# GNU chmod keeps a directory's setgid bit when the mode is numeric, so 2755 here is the
# tool's documented behaviour, not a leftover: the observable damage is the group and the
# loss of the 2770 restriction, both of which enforce_shared_state.sh repairs.
chk "regression reproduced (mode)"   "$(stat -c '%a' "$SHARED")" "2755"
sudo bash /tmp/check5a/enforce_shared_state.sh "$SHARED" zhixue-app >/dev/null
chk "group repaired"  "$(stat -c '%G' "$SHARED")" "zhixue-app"
chk "mode repaired"   "$(stat -c '%a' "$SHARED")" "2770"
chk "owner preserved" "$(stat -c '%U' "$SHARED")" "ubuntu"
# second deploy: run it again and prove nothing drifts
BEFORE=$(sudo find "$SHARED" -printf '%M %u:%g %p\n' | sort | md5sum)
sudo bash /tmp/check5a/enforce_shared_state.sh "$SHARED" zhixue-app >/dev/null
AFTER=$(sudo find "$SHARED" -printf '%M %u:%g %p\n' | sort | md5sum)
chk "second run is a no-op (idempotent)" "$AFTER" "$BEFORE"
# and the drill's own data survived every one of those passes
chk "uploads intact after 4 permission passes" "$(find "$SHARED/uploads" -type f | wc -l)" "3"

echo
echo "══ DRILL RESULT: PASS=$PASS FAIL=$FAIL ══"
[ "$FAIL" -eq 0 ] || exit 1
