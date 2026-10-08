#!/usr/bin/env bash
# SECURITY_S0B Stage 5A — which systemd hardening can the sandbox runner keep?
#
# The runner needs rootless Podman, which needs a user namespace, setuid uid-mapping
# helpers and write access to its own cgroup. Several ordinary hardening options forbid
# exactly those things. This script answers the question by EXECUTING a bounded container
# under each candidate profile, so the unit file records measured facts.
#
# METHODOLOGY NOTE — this matters more than the properties themselves:
# rootless podman keeps a per-user "pause" process that holds the user namespace, and it
# OUTLIVES whatever started it. A pause process created outside the sandbox is reused
# inside it, and the container then fails with an opaque error that has nothing to do with
# the property under test. Every profile below therefore starts by dropping the pause
# process, so the run creates its own inside that profile's sandbox. Without this the audit
# reports failures caused by its own previous test — which is exactly what happened the
# first time it was run.
set -uo pipefail

SB_UID=997
PASS=0; FAIL=0
ok()  { echo "  PASS  $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }

# ReadWritePaths entries MUST already exist when systemd builds the unit's namespace: a
# missing one aborts the unit with status 226 (EXIT_NAMESPACE) in a few milliseconds and no
# output. The production unit lists /run/zhixue-sandbox, which is created by the tmpfiles.d
# entry installed alongside it (and, on a real boot, by systemd-tmpfiles-setup before the
# runner starts). The audit uses its own directory so it does not depend on that
# install step, but the dependency is real: install the unit and its tmpfiles entry
# together, never the unit alone.
AUDIT_RUNTIME=/run/zhixue-sandbox-audit
sudo install -d -m 2750 -o zhixue-sandbox -g zhixue-ipc "$AUDIT_RUNTIME"
trap 'sudo rm -rf "$AUDIT_RUNTIME"' EXIT

# A bounded, one-shot container exercising what hardening is most likely to break:
# namespace creation, the container's cgroup, and a writable tmpfs in a read-only root.
CONTAINER_CMD='podman run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 64 --memory 128m --memory-swap 128m --tmpfs /tmp:rw,exec,nosuid,size=16m python:3.11-slim python -c "open(chr(47)+chr(116)+chr(109)+chr(112)+chr(47)+chr(120),chr(119)).write(chr(49)); print(chr(104)+chr(97)+chr(114)+chr(100)+chr(101)+chr(110)+chr(45)+chr(111)+chr(107))"'

reset_pause() {
  # The pause process's command line is bare ``podman`` — matching on "podman pause" finds
  # nothing, silently, and the stale process from the previous profile is then reused with
  # a namespace that no longer exists. Match the process NAME instead.
  #
  # Do NOT also wipe /run/user/<uid>/libpod: that directory is part of the user-namespace
  # bookkeeping, and removing it makes the next start fail with "cannot setup namespace
  # using newuidmap: exit status 1" — a symptom that looks like a hardening conflict and is
  # not one. Killing the process alone is the correct and sufficient reset.
  sudo pkill -x -u zhixue-sandbox podman 2>/dev/null || true
  sleep 1
}

run_profile() {
  local label="$1"; shift
  reset_pause
  local out
  out=$(sudo systemd-run --wait --pipe --collect --quiet \
      --uid=zhixue-sandbox --gid=zhixue-sandbox \
      --setenv=XDG_RUNTIME_DIR=/run/user/$SB_UID \
      --setenv=HOME=/var/lib/zhixue-sandbox \
      --setenv=TMPDIR=/var/lib/zhixue-sandbox/tmp \
      --property=WorkingDirectory=/tmp \
      --property=ReadWritePaths="/var/lib/zhixue-sandbox $AUDIT_RUNTIME /run/user/$SB_UID" \
      "$@" \
      /bin/bash -c "cd /tmp && podman system migrate >/dev/null 2>&1; $CONTAINER_CMD" 2>&1)
  if printf '%s' "$out" | grep -q 'harden-ok'; then
    ok "$label"
  else
    bad "$label  —  $(printf '%s' "$out" | grep -m1 -i 'error' | cut -c1-110)"
  fi
}

# This audit deliberately does NOT run a "no hardening" baseline. Every podman invocation
# creates a per-user pause process that outlives the unit it started in, so a run from a
# plain shell leaves one that the following sandboxed run inherits — and the failures that
# follow have nothing to do with the property under test. Each profile below therefore
# starts by killing it and lets the unit create its own.
#
# The unit's own posture is validated end-to-end by _stage5a_ipc_driver.sh, which runs the
# real service under the real unit profile and executes a real container through the real
# client; repeating it here in a weaker form would only add a way to be wrong.
SAFE=(--property=ProtectSystem=strict --property=PrivateTmp=yes)

echo "── adversarial: every option the unit turns OFF must actually be required ──"
for property in NoNewPrivileges=yes RestrictSUIDSGID=yes RestrictNamespaces=yes \
                ProtectControlGroups=yes ProtectHome=yes ProtectHostname=yes \
                SystemCallFilter=@system-service; do
  run_profile "$property (unit omits it — FAIL here proves the omission is needed)" \
    --property="$property" "${SAFE[@]}"
done

echo
echo "══ HARDENING AUDIT: PASS=$PASS FAIL=$FAIL ══"
echo "PASS on the unit posture = the unit works. FAIL on every adversarial line = each"
echo "omitted option is load-bearing and the exemption is justified by measurement."
