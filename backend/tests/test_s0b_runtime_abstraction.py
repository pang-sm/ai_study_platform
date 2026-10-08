"""SECURITY_S0B-P1 — the container-runtime abstraction (Docker / rootless Podman).

ONE sandbox implementation, two selectable CLIs. These tests pin the invariants: both
runtimes carry the SAME isolation flags, only the CPU-limit mechanism differs, and a
runtime that fails to start the container fails CLOSED — never reported as the learner's
own error and never as a wrong answer.
"""
from __future__ import annotations

import os

import pytest

from core.sandbox import docker_backend as db
from core.sandbox.limits import CPU_TIME_LIMIT_SECONDS, MEMORY_LIMIT
from core.sandbox.types import ExecutionRequest, SourceFile


# ── the run directory must be readable by a capability-stripped container ───────────

_posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits only")


@_posix_only
def test_run_directory_is_made_readable_for_a_capability_stripped_container(tmp_path):
    """``--cap-drop ALL`` removes CAP_DAC_OVERRIDE, so a 0700 mkdtemp dir is unreadable."""
    root = tmp_path / "run"
    (root / "sub").mkdir(parents=True)
    (root / "main.py").write_text("print(1)\n", encoding="utf-8")
    (root / "sub" / "a.txt").write_text("x", encoding="utf-8")
    db._make_container_readable(str(root))
    assert (root.stat().st_mode & 0o777) == 0o755
    assert ((root / "sub").stat().st_mode & 0o777) == 0o755
    assert ((root / "main.py").stat().st_mode & 0o777) == 0o644
    assert ((root / "sub" / "a.txt").stat().st_mode & 0o777) == 0o644


@_posix_only
def test_interactive_run_directory_is_writable_for_the_compile_step(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "a").write_text("x", encoding="utf-8")
    db._make_container_readable(str(root), writable=True)
    assert (root.stat().st_mode & 0o777) == 0o777
    assert ((root / "a").stat().st_mode & 0o777) == 0o666


@_posix_only
def test_output_channel_is_two_write_only_fifos(tmp_path):
    """A FIFO cannot be truncated, and 0602 leaves the container write-only."""
    import stat as _stat
    db._prepare_output_files(str(tmp_path))
    for name in ("out.stdout", "out.stderr"):
        st = (tmp_path / name).stat()
        assert _stat.S_ISFIFO(st.st_mode), f"{name} must be a FIFO"
        assert (st.st_mode & 0o777) == 0o602, f"{name} must be 0602 (owner rw, other w only)"


def test_podman_runs_the_container_as_a_non_owner_user():
    """Rootless Podman maps container root onto the runner's own uid, which would make the
    container the FIFO's OWNER and so able to READ the trusted channel. A non-owner uid
    keeps it write-only; rootful Docker needs no flag (its root is not the owner)."""
    assert "--user" in db.isolation_flags(MEMORY_LIMIT["Python"], runtime="podman")
    assert "--user" not in db.isolation_flags(MEMORY_LIMIT["Python"], runtime="docker")


def test_java_copy_does_not_need_cap_chown():
    """``cp -a`` needs CAP_CHOWN (dropped with ALL); the inner command must use ``cp -r``."""
    backend = db.DockerExecutionBackend(runtime="docker")
    request = ExecutionRequest(
        language="Java", files=(SourceFile("Main.java", "class Main{}"),),
        entry_file="Main.java", main_class="Main",
    )
    joined = " ".join(backend._inner_script("Java", request, list(request.files)))
    assert "cp -r " in joined
    assert "cp -a " not in joined


# ── runtime selection ──────────────────────────────────────────────────────────────

def test_default_runtime_is_docker(monkeypatch):
    monkeypatch.delenv(db.CONTAINER_RUNTIME_ENV, raising=False)
    assert db.configured_runtime() == "docker"


@pytest.mark.parametrize("value,expected", [
    ("podman", "podman"), ("PODMAN", "podman"), ("docker", "docker"),
    ("nonsense", "docker"), ("", "docker"), ("  podman ", "podman"),
])
def test_configured_runtime(monkeypatch, value, expected):
    monkeypatch.setenv(db.CONTAINER_RUNTIME_ENV, value)
    assert db.configured_runtime() == expected


def test_backend_selects_the_runtime_binary(monkeypatch):
    monkeypatch.delenv(db.CONTAINER_RUNTIME_ENV, raising=False)
    backend = db.DockerExecutionBackend(runtime="podman")
    assert backend.runtime == "podman"
    assert backend._docker.endswith("podman")


# ── the isolation flags are shared; only the CPU mechanism differs ─────────────────

_COMMON = (
    "--network", "none", "--read-only", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges", "--pids-limit",
    "--memory", "--memory-swap", "nofile=256:256", "core=0:0",
)


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_both_runtimes_carry_every_shared_isolation_flag(runtime):
    joined = " ".join(db.isolation_flags(MEMORY_LIMIT["Python"], runtime=runtime))
    for flag in _COMMON:
        assert flag in joined, f"{runtime} missing {flag!r}"


def test_docker_uses_a_cgroup_cpu_quota():
    flags = db.isolation_flags(MEMORY_LIMIT["Python"], runtime="docker")
    assert "--cpus" in flags


def test_podman_uses_a_cpu_time_backstop_not_a_quota():
    flags = db.isolation_flags(MEMORY_LIMIT["Python"], runtime="podman")
    assert "--cpus" not in flags, "rootless podman cannot set a cgroup CPU quota here"
    assert f"cpu={CPU_TIME_LIMIT_SECONDS}:{CPU_TIME_LIMIT_SECONDS}" in flags


def test_podman_does_not_duplicate_output_to_the_journal_or_a_log_file():
    """An unbounded print loop must not be able to fill the host disk via podman's log driver."""
    podman = db.isolation_flags(MEMORY_LIMIT["Python"], runtime="podman")
    assert "--log-driver=none" in podman
    # Docker's default json-file driver is per-container and removed with the container.
    assert "--log-driver=none" not in db.isolation_flags(MEMORY_LIMIT["Python"], runtime="docker")


def test_podman_never_forwards_host_proxy_variables():
    """Podman forwards host proxy vars by default; the runner must disable it in argv."""
    assert "--http-proxy=false" in db.isolation_flags(MEMORY_LIMIT["Python"], runtime="podman")
    # Docker does not forward host env at all, so the flag is unnecessary there.
    assert "--http-proxy=false" not in db.isolation_flags(MEMORY_LIMIT["Python"], runtime="docker")


def test_no_runtime_ever_mounts_a_socket_or_goes_privileged():
    for runtime in ("docker", "podman"):
        joined = " ".join(db.isolation_flags(MEMORY_LIMIT["C"], runtime=runtime))
        for forbidden in ("docker.sock", "podman.sock", "--privileged", "--network host", "--cap-add"):
            assert forbidden not in joined


def test_run_command_never_pulls_and_carries_the_runtime_cpu_flag(monkeypatch):
    for runtime, cpu_flag in (("docker", "--cpus"), ("podman", "cpu=")):
        backend = db.DockerExecutionBackend(runtime=runtime)
        cmd = backend._docker_command("Python", ["python", "-u", "main.py"], "/tmp/x", "zhixue-sbx-t")
        joined = " ".join(cmd)
        assert "--pull=never" in cmd
        assert cpu_flag in joined
        assert "--network none" in joined


# ── exit-code mapping: a runtime failure must fail CLOSED ──────────────────────────

def test_container_start_failure_is_decided_by_the_runtimes_record_not_by_output():
    # No container at all (e.g. a missing image) -> the runtime never started it.
    assert db._is_container_start_failure(None) is True
    # A container created but never started -> start failure.
    assert db._is_container_start_failure(("created", 0)) is True
    assert db._is_container_start_failure(("configured", 0)) is True
    # The container RAN: the exit code is the learner's own, whatever it chose.
    assert db._is_container_start_failure(("exited", 125)) is False
    assert db._is_container_start_failure(("exited", 126)) is False
    assert db._is_container_start_failure(("exited", 127)) is False


def test_the_start_failure_decision_never_reads_learner_output():
    """Anti-spoofing guard: the decision must not be computed from the program's output."""
    import inspect as _inspect
    src = _inspect.getsource(db._is_container_start_failure).lower()
    assert "stderr" not in src
    assert "marker" not in src


def test_no_forgeable_stderr_marker_list_survives():
    """A learner can print anything to stderr; no marker list may decide a runtime failure."""
    import inspect as _inspect
    src = _inspect.getsource(db)
    assert "_RUNTIME_FAILURE_MARKERS" not in src
    assert "runc create failed" not in src
