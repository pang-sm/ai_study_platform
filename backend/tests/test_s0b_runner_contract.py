"""SECURITY_S0B-P1 — the web→runner boundary fails closed.

The web process holds no docker. Its only path to execution is ``SandboxRunnerClient`` over
a Unix socket, and every failure — missing socket, refused connection, timeout, HTTP error,
oversize body, non-JSON, schema mismatch — must collapse to an ``INTERNAL_ERROR`` result.
It must NEVER spawn a host process and must NEVER fall back to rootful docker.
"""
from __future__ import annotations

import pytest

import httpx

from core.sandbox import ExecutionRequest, SourceFile, Verdict
from core.sandbox.runner_client import MAX_RESPONSE_BYTES, SandboxRunnerClient

REQUEST = ExecutionRequest(
    language="Python",
    files=(SourceFile("main.py", "print(1)\n"),),
    entry_file="main.py",
)


class _HostProcessSpy:
    def __init__(self):
        self.calls = []

    @property
    def called(self) -> bool:
        return bool(self.calls)

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        raise AssertionError(f"host process spawn attempted: {args!r}")


@pytest.fixture
def host_spy(monkeypatch):
    spy = _HostProcessSpy()
    import subprocess
    monkeypatch.setattr(subprocess, "run", spy)
    monkeypatch.setattr(subprocess, "Popen", spy)
    monkeypatch.setattr(subprocess, "check_output", spy)
    monkeypatch.setattr(subprocess, "call", spy)
    return spy


def test_missing_socket_fails_closed(tmp_path):
    result = SandboxRunnerClient(socket_path=str(tmp_path / "absent.sock")).run(REQUEST)
    assert result.verdict is Verdict.INTERNAL_ERROR
    assert result.stdout == "" and result.exit_code is None


def test_http_error_fails_closed():
    transport = httpx.MockTransport(lambda req: httpx.Response(500, json={"detail": "boom"}))
    result = SandboxRunnerClient(transport=transport).run(REQUEST)
    assert result.verdict is Verdict.INTERNAL_ERROR
    assert "docker" not in result.internal_error.lower()


def test_non_json_fails_closed():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="not json"))
    assert SandboxRunnerClient(transport=transport).run(REQUEST).verdict is Verdict.INTERNAL_ERROR


def test_oversize_body_fails_closed():
    big = b"x" * (MAX_RESPONSE_BYTES + 10)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=big))
    assert SandboxRunnerClient(transport=transport).run(REQUEST).verdict is Verdict.INTERNAL_ERROR


def test_unknown_verdict_fails_closed():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"verdict": "not_a_verdict"}))
    result = SandboxRunnerClient(transport=transport).run(REQUEST)
    assert result.verdict is Verdict.INTERNAL_ERROR


def test_valid_response_is_projected():
    def handler(req):
        # The web side must never send argv/image/mounts — only the bounded shape.
        import json
        body = json.loads(req.content)
        assert set(body) <= {
            "language", "files", "entry_file", "main_class", "stdin",
            "compile_files", "wall_time_ms", "compile_only",
        }
        return httpx.Response(200, json={
            "language": "Python", "verdict": "accepted", "stdout": "1\n", "stderr": "",
            "exit_code": 0, "duration_ms": 5, "timed_out": False, "output_truncated": False,
            "compile": None, "internal_error": "",
        })

    result = SandboxRunnerClient(transport=httpx.MockTransport(handler)).run(REQUEST)
    assert result.verdict is Verdict.ACCEPTED
    assert result.stdout == "1\n"


def test_preflight_degrades_on_failure(tmp_path):
    report = SandboxRunnerClient(socket_path=str(tmp_path / "absent.sock")).preflight()
    assert report["ready"] is False


def test_client_never_spawns_a_host_process(host_spy, tmp_path):
    SandboxRunnerClient(socket_path=str(tmp_path / "absent.sock")).run(REQUEST)
    assert host_spy.called is False, host_spy.calls


def test_client_module_imports_no_process_or_docker_machinery():
    """The client must not be able to reach docker even by accident."""
    import core.sandbox.runner_client as rc
    source = open(rc.__file__, encoding="utf-8").read()
    for forbidden in ("import subprocess", "shutil.which", "docker_backend", "DockerExecutionBackend"):
        assert forbidden not in source, f"runner_client must not reference {forbidden!r}"
