"""SECURITY_S0B / S0B-P1 — backend selection, fail-closed behaviour and response shapes.

These tests never need Docker. They pin the contract that decides *whether* isolation is
possible (now: an explicit opt-in AND the runner's Unix socket) and how its outcome is
projected into the existing API shapes. The isolation properties are proven separately in
``test_s0b_sandbox_security.py`` (runner-side, real containers).

The central invariant is unchanged: when the sandbox is enabled, no path may fall back to a
host subprocess. The legacy Exercism/JUnit/adapter runners therefore still have to refuse.
"""
from __future__ import annotations

import pytest

import main
import programming_execution
import programming_io_adapter
from core import code_execution, sandbox
from core.sandbox import ExecutionRequest, SourceFile, Verdict
from core.sandbox.docker_backend import DockerExecutionBackend
from core.sandbox.types import CompileResult, ExecutionResult


@pytest.fixture(autouse=True)
def _reset_backend_cache(monkeypatch):
    """Never let one test's cached client leak into the next."""
    monkeypatch.setattr(sandbox, "_client", None, raising=False)


def _present_socket(monkeypatch, tmp_path) -> str:
    """Point the sandbox at a socket path that EXISTS (no runner is actually dialled here)."""
    sock = tmp_path / "runner.sock"
    sock.write_text("", encoding="utf-8")
    monkeypatch.setenv("SANDBOX_RUNNER_SOCKET", str(sock))
    return str(sock)


# ── backend selection ──────────────────────────────────────────────────────────────

def test_no_opt_in_means_no_backend(monkeypatch, tmp_path):
    monkeypatch.delenv(code_execution.CODE_EXECUTION_BACKEND_ENV, raising=False)
    _present_socket(monkeypatch, tmp_path)
    assert sandbox.get_execution_backend() is None


@pytest.mark.parametrize("value", ["", "none", "host", "subprocess", "true", "dockerized"])
def test_unknown_backend_value_means_no_backend(monkeypatch, tmp_path, value):
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, value)
    _present_socket(monkeypatch, tmp_path)
    assert sandbox.get_execution_backend() is None


def test_docker_opt_in_yields_the_runner_client(monkeypatch, tmp_path):
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, "docker")
    _present_socket(monkeypatch, tmp_path)
    backend = sandbox.get_execution_backend()
    assert isinstance(backend, sandbox.SandboxRunnerClient)


def test_preflight_reports_not_configured_without_opt_in(monkeypatch):
    monkeypatch.delenv(code_execution.CODE_EXECUTION_BACKEND_ENV, raising=False)
    report = sandbox.sandbox_preflight()
    assert report["ready"] is False
    assert report["reason"] == "backend_not_configured"


def test_preflight_reports_missing_socket(monkeypatch, tmp_path):
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, "docker")
    monkeypatch.setenv("SANDBOX_RUNNER_SOCKET", str(tmp_path / "absent.sock"))
    report = sandbox.sandbox_preflight()
    assert report["ready"] is False
    assert report["reason"] == "runner_socket_missing"


# ── the backend never spawns docker for input it can reject itself ──────────────────

def test_unsupported_language_is_rejected_without_running_anything(monkeypatch):
    backend = DockerExecutionBackend()
    spawned = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: spawned.append(a))
    result = backend.run(ExecutionRequest(language="Ruby", files=()))
    assert result.verdict is Verdict.INTERNAL_ERROR
    assert spawned == []


def test_oversize_source_is_rejected_before_any_container(monkeypatch):
    backend = DockerExecutionBackend()
    spawned = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: spawned.append(a))
    result = backend.run(ExecutionRequest(
        language="Python",
        files=(SourceFile("main.py", "x = 1\n" * 200_000),),
        entry_file="main.py",
    ))
    assert result.verdict is Verdict.OUTPUT_LIMIT
    assert spawned == []


def test_path_traversal_is_rejected_before_any_container(monkeypatch):
    backend = DockerExecutionBackend()
    spawned = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: spawned.append(a))
    result = backend.run(ExecutionRequest(
        language="Python",
        files=(SourceFile("../../etc/passwd", "x"),),
        entry_file="main.py",
    ))
    assert result.verdict is Verdict.INTERNAL_ERROR
    assert spawned == []


# ── projecting a result onto the existing API shapes ───────────────────────────────

def _result(verdict, **kw):
    return ExecutionResult(language="C", verdict=verdict, **kw)


def test_exec_dict_shape_and_timeout_flag():
    payload = main._sandbox_exec_dict(_result(Verdict.ACCEPTED, stdout="ok\n", exit_code=0, duration_ms=12))
    for key in ("success", "stdout", "stderr", "exit_code", "duration_ms", "timed_out",
                "error_message", "compile_error", "compiled", "stdout_truncated", "stderr_truncated"):
        assert key in payload
    assert payload["success"] is True and payload["compiled"] is True and payload["timed_out"] is False


def test_exec_dict_marks_timeout_and_compile_error():
    timed = main._sandbox_exec_dict(_result(Verdict.TIMEOUT, duration_ms=4000, exit_code=137))
    assert timed["timed_out"] is True
    assert timed["error_message"]

    failed = main._sandbox_exec_dict(_result(
        Verdict.COMPILE_ERROR, compile=CompileResult(ok=False, diagnostic="syntax error"), exit_code=101))
    assert failed["compiled"] is False
    assert failed["compile_error"] == "syntax error"


def test_internal_error_never_leaks_detail_to_the_learner():
    payload = main._sandbox_exec_dict(_result(
        Verdict.INTERNAL_ERROR, internal_error="/var/run/docker.sock: permission denied"))
    assert payload["error_message"] == code_execution.UNAVAILABLE_MESSAGE
    assert "docker.sock" not in payload["error_message"]


# ── the legacy host runners refuse once the sandbox is enabled ──────────────────────

@pytest.fixture
def sandbox_enabled(monkeypatch, tmp_path):
    """Opt in AND make the runner socket present, so the gate opens."""
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, "docker")
    _present_socket(monkeypatch, tmp_path)


def test_java_gradle_runner_refuses_under_the_sandbox(sandbox_enabled):
    result = programming_execution.run_java_tests([], [])
    assert result["success"] is False
    assert result["failed_categories"] == ["unsupported"]


def test_io_adapter_refuses_under_the_sandbox(sandbox_enabled):
    result = programming_io_adapter.run_sample(
        "Python", None,
        [{"relative_path": "solution.py", "content": "def add(a, b):\n    return a + b\n"}],
        {"stdin_text": "", "adapter_config": {"protocol": "stdin_stdout_v1", "callable": "add"}},
    )
    assert result is None


def test_official_runner_refuses_the_legacy_path_under_the_sandbox(sandbox_enabled, monkeypatch):
    """A non-standard-io exercise must not reach the host runner when the sandbox is on."""
    called = []
    monkeypatch.setattr(main, "run_java_tests", lambda *a, **k: called.append(a))
    monkeypatch.setattr(main, "run_programming_io_adapter", lambda *a, **k: called.append(a))

    exercise = type("E", (), {
        "language": "Java", "public_tests_json": "[]", "official_test_files_json": "[]",
        "audit_report_json": "{}", "slug": "x",
    })()
    monkeypatch.setattr(main, "_exercise_manifest", lambda ex: {"runner": "junit"})
    result = main._run_official_exercise_tests(None, exercise, [], submission=True)
    assert result["failed_categories"] == ["unsupported"]
    assert called == [], "the host runner must never be reached under the sandbox"
