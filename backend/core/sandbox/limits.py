"""Hard limits for the code-execution sandbox — SECURITY_S0B.

Every value here is a HARD bound enforced by the container runtime, not a hint.
Nothing in this module may be loosened to make a slow program pass: the point of a
judge is to reject programs that exceed the budget, and a learner-visible "time
limit exceeded" is the correct answer, not a longer timeout.

Values were chosen from the actual production catalogue (240 standard-io exercises,
60 per language, all small stdin/stdout programs) rather than copied from a spec.
"""
from __future__ import annotations

# Pinned image tags. ``latest`` is forbidden: the judge's semantics depend on a
# fixed compiler/interpreter version, and an image drift must be a deliberate,
# reviewed change. These are the exact tags the deployment must pre-pull.
IMAGE_PYTHON = "python:3.11-slim"
IMAGE_C_FAMILY = "gcc:13"
IMAGE_JAVA = "eclipse-temurin:21-jdk"

IMAGES = {
    "Python": IMAGE_PYTHON,
    "C": IMAGE_C_FAMILY,
    "C++": IMAGE_C_FAMILY,
    "Java": IMAGE_JAVA,
}

# The program's OWN time limit, enforced INSIDE the container by coreutils ``timeout``
# (SIGTERM, then SIGKILL one second later). Measuring here rather than on the host is
# what makes the verdict honest: container start-up and host load cannot turn a fast
# program into a false "time limit exceeded", and a real infinite loop is still stopped
# at exactly this many seconds.
PROGRAM_TIME_SECONDS = 3
COMPILE_TIME_SECONDS = 10

# Transitional CPU-time backstop (SECURITY_S0B-P1, rootless Podman).
#
# Rootless Podman on this host CANNOT set a cgroup CPU quota: systemd delegates only the
# ``memory`` and ``pids`` controllers to user sessions, so ``cpu.max`` does not exist and
# ``--cpus`` fails. Instead the runner passes ``--ulimit cpu=<sec>:<sec>`` (RLIMIT_CPU).
#
# RLIMIT_CPU is a per-process CUMULATIVE CPU-second cap, NOT a rate limit, and it does NOT
# bound the aggregate CPU of a process tree. It is a defense-in-depth backstop on top of
# the in-container wall ``timeout`` (PROGRAM_TIME_SECONDS) — it is NOT a replacement for a
# cgroup quota, and a passing RLIMIT_CPU test must never be recorded as a cgroup-quota
# pass. The value covers compile (COMPILE_TIME_SECONDS) + run (PROGRAM_TIME_SECONDS) plus
# a small margin so a legitimate build is never killed by the backstop.
CPU_TIME_LIMIT_SECONDS = COMPILE_TIME_SECONDS + PROGRAM_TIME_SECONDS + 2

# Outer safety net only (container start + compile + run + teardown). The real limits
# are PROGRAM_TIME_SECONDS / COMPILE_TIME_SECONDS above; this catches a wedged daemon
# or a hung container start so a worker is never blocked indefinitely.
WALL_TIME_MS = {
    "Python": 20000,
    "C": 30000,
    "C++": 30000,
    "Java": 45000,
}

# ``timeout``'s exit status when it had to stop the command.
TIMEOUT_EXIT_CODE = 124

# Physical memory (RAM) cap. ``--memory-swap`` is set equal to ``--memory`` so the
# container cannot page to swap and silently exceed the RAM bound.
MEMORY_LIMIT = {
    "Python": "256m",
    "C": "256m",
    "C++": "256m",
    "Java": "512m",  # a JVM needs headroom beyond the program's own heap
}

# CPU quota. 1.0 == one full core; the container cannot starve the host backend.
CPU_LIMIT = "1"

# Maximum number of processes/threads. Bounds fork bombs: the cgroup pids controller
# kills the container once the limit is hit rather than letting it exhaust the host.
PIDS_LIMIT = 64

# Per-stream output cap, enforced on the host side. Once a stream exceeds this the
# container is killed — draining an unbounded stream would move the DoS onto the host.
OUTPUT_CAP_BYTES = 1024 * 1024

# Output capture (SECURITY_S0B-P1). The program's stdout/stderr are redirected INSIDE the
# container to two host-created FIFOs. The HOST holds the only read end and counts bytes
# itself, so capture never depends on the container CLI's attached-output relay — which
# rootless Podman 3.4.4 truncates (a 3 MiB write arrived as ~900 KiB) — and, unlike a plain
# file, a FIFO cannot be truncated by the learner to hide an over-limit run.
#
# Read exclusivity: the FIFO is mode 0602 (owner read+write, everyone else WRITE ONLY), and
# the container must NOT be the FIFO's owner. Rootful Docker's container root qualifies once
# capabilities are dropped; rootless Podman maps the container's root onto the runner's own
# uid, so it must run as a non-owner uid (PODMAN_CONTAINER_USER). The learner may therefore
# write the stream but never read it or become a second reader of the trusted channel.
#
# The bound is the host's own byte count + kill; RLIMIT_FSIZE is NOT used — it does not
# bound a FIFO's total output.
OUTPUT_FIFO_MODE = 0o602
OUTPUT_MOUNT_DIR = "/out"
PODMAN_CONTAINER_USER = "1000:1000"

# Size of the writable /tmp tmpfs inside the container. Compilation artefacts live
# here (never on the host), so this bounds how much a build can stage.
TMPFS_SIZE = {
    "Python": "64m",
    "C": "128m",
    "C++": "128m",
    "Java": "256m",
}

# Source-size bounds (bytes). Applied before anything is written to disk.
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_SOURCE_BYTES = 1024 * 1024
MAX_STDIN_BYTES = 64 * 1024

# Exit code the in-container shell uses to signal "compilation failed" so a build
# failure is never mistaken for a program that ran and crashed.
COMPILE_FAILED_EXIT = 101

# ``docker rm -f`` grace period after a timeout or output-cap kill.
KILL_GRACE_SECONDS = 10

# How long the ``docker`` CLI itself may take before we give up on it.
CLI_TIMEOUT_SLACK_SECONDS = 15

# How many containers may run at once. The judge runs one container per case and had no
# concurrency bound of its own, so this is the global ceiling that keeps a burst of
# submissions from exhausting the host. A request that cannot get a slot in time is
# refused with a structured "busy" result rather than queueing forever.
MAX_CONCURRENT_CONTAINERS = 2
CONTAINER_ACQUIRE_TIMEOUT_SECONDS = 20
