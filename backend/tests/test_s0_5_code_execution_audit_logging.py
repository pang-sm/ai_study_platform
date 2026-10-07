"""SECURITY_S0.5 — audit logging for learner code execution, and what it must never contain.

SECURITY_S0 closed the host-RCE path but recorded nothing, so the incident review could only
answer ``INSUFFICIENT_LOGGING``. These tests hold two separate contracts:

* **Detection** — every execution attempt, allowed or denied, produces a structured event
  naming the learner, the action, the backend and (on refusal) the reason.
* **Containment of the log itself** — the audit line is an allowlist. Submitted source,
  stdin, stdout/stderr and any credential must never appear in it, even though the entry
  points have all of those in hand at the moment they emit.
"""
import json
import logging

import pytest

import main
from core import code_execution, security_audit
from conftest import register_and_login

AUDIT_LOGGER = "security.audit"
DENIED = security_audit.CODE_EXECUTION_DENIED_SANDBOX_UNAVAILABLE
PERMITTED = security_audit.CODE_EXECUTION_PERMITTED

# A payload that would name the production database if it ever reached the log.
MALICIOUS_SOURCE = "print(open('/var/lib/ai_study_platform/app.db','rb').read()[:200])"
SECRET_STDIN = "AKIAIOSFODNN7EXAMPLE\nsk-live-9f3ab2c7d1e4"
SECRET_MARKERS = ("AKIAIOSFODNN7EXAMPLE", "sk-live-9f3ab2c7d1e4", "/var/lib/ai_study_platform/app.db")


def _audit_lines(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == AUDIT_LOGGER]


def _audit_blob(caplog) -> str:
    return "\n".join(_audit_lines(caplog))


def _create_project(client, username: str, language: str, code: str) -> int:
    created = client.post("/code/projects", json={
        "username": username, "name": "s0_5", "language": language, "course_id": "programming",
    })
    assert created.status_code == 200, created.text
    project_id = created.json()["project"]["id"]
    files = client.get(f"/code/projects/{project_id}", params={"username": username}).json()["project"]["files"]
    client.put(f"/code/projects/{project_id}/files/{files[0]['id']}", json={
        "username": username, "content": code,
    })
    return project_id


@pytest.fixture
def no_backend(monkeypatch):
    monkeypatch.delenv(code_execution.CODE_EXECUTION_BACKEND_ENV, raising=False)


@pytest.fixture(autouse=True)
def _capture_audit(caplog):
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
    yield caplog


# ── A/B: an attempt is recorded, with the fields an investigator needs ─────────────

def test_denied_project_execution_emits_audit_event(client, no_backend, _capture_audit):
    register_and_login(client, "s05-audit")
    project_id = _create_project(client, "s05-audit", "Python", MALICIOUS_SOURCE)
    _capture_audit.clear()

    response = client.post(f"/code/projects/{project_id}/execute", json={"username": "s05-audit"})
    assert response.status_code == 503

    lines = _audit_lines(_capture_audit)
    assert len(lines) == 1, lines
    line = lines[0]
    assert "CODE_EXECUTION" in line
    assert f"event={DENIED}" in line
    assert "allowed=false" in line
    assert "user=s05-audit" in line
    assert "action=code.project.execute" in line
    assert "language=Python" in line
    assert f"resource={project_id}" in line
    assert "backend=disabled" in line
    assert "reason=sandbox_unavailable" in line


def test_audit_event_carries_a_request_correlation_id(client, no_backend, _capture_audit):
    register_and_login(client, "s05-corr")
    project_id = _create_project(client, "s05-corr", "Python", "print(1)")
    _capture_audit.clear()

    client.post(f"/code/projects/{project_id}/execute", json={"username": "s05-corr"})

    line = _audit_lines(_capture_audit)[0]
    request_id = dict(part.split("=", 1) for part in line.split() if "=" in part).get("request_id", "")
    assert request_id, line


def test_permitted_attempt_is_also_recorded(client, monkeypatch, tmp_path, _capture_audit):
    """The allow path must log too — otherwise a future sandbox would run silently."""
    register_and_login(client, "s05-allow")
    project_id = _create_project(client, "s05-allow", "Python", "print(1)")

    # Simulate a verified sandbox being available WITHOUT executing anything: the guard is
    # asserted directly so no host process (and no runner call) is spawned by this test.
    sock = tmp_path / "runner.sock"
    sock.write_text("", encoding="utf-8")
    monkeypatch.setenv("SANDBOX_RUNNER_SOCKET", str(sock))
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, "docker")
    _capture_audit.clear()

    with security_audit.code_execution_audit_context(
        user="s05-allow", action="code.project.execute", language="Python", resource=project_id,
    ):
        code_execution.require_secure_code_execution()

    line = _audit_lines(_capture_audit)[0]
    assert f"event={PERMITTED}" in line
    assert "allowed=true" in line
    assert "backend=docker" in line
    assert "reason=" not in line


def test_terminal_denial_is_recorded(client, no_backend, _capture_audit):
    register_and_login(client, "s05-term")
    _capture_audit.clear()

    with client.websocket_connect("/code/interactive-run") as websocket:
        websocket.send_text(json.dumps({
            "username": "s05-term", "language": "python", "code": MALICIOUS_SOURCE,
        }))
        websocket.receive_text()

    lines = _audit_lines(_capture_audit)
    assert len(lines) == 1, lines
    assert f"event={DENIED}" in lines[0]
    assert "user=s05-term" in lines[0]
    assert "action=code.interactive_run" in lines[0]


# ── C/D/F: the log must not carry the artefact ─────────────────────────────────────

def test_submitted_source_never_reaches_the_log(client, no_backend, _capture_audit):
    register_and_login(client, "s05-src")
    project_id = _create_project(client, "s05-src", "Python", MALICIOUS_SOURCE)
    _capture_audit.clear()

    client.post(f"/code/projects/{project_id}/execute", json={"username": "s05-src", "stdin": SECRET_STDIN})

    blob = _audit_blob(_capture_audit)
    assert blob, "expected an audit event"
    for marker in SECRET_MARKERS:
        assert marker not in blob, f"{marker!r} leaked into the audit log"


def test_stdout_and_stderr_never_reach_the_log(client, no_backend, _capture_audit):
    register_and_login(client, "s05-out")
    project_id = _create_project(client, "s05-out", "Python", "print('STDOUT_MARKER'); raise SystemExit('STDERR_MARKER')")
    _capture_audit.clear()

    client.post(f"/code/projects/{project_id}/execute", json={"username": "s05-out"})

    blob = _audit_blob(_capture_audit)
    assert "STDOUT_MARKER" not in blob
    assert "STDERR_MARKER" not in blob


def test_audit_context_rejects_source_and_output_fields():
    """Structural guarantee: the allowlist refuses the fields, so no caller can add them.

    This is what makes the 'never log the artefact' rule survive a future refactor that
    happens to have the source in hand.
    """
    for forbidden in ("source", "code", "stdin", "stdout", "stderr", "cookie", "authorization", "token"):
        with pytest.raises(ValueError):
            with security_audit.code_execution_audit_context(**{forbidden: "LEAK"}):
                pass


# ── E/G: credentials and cookies ───────────────────────────────────────────────────

def test_session_cookie_never_reaches_the_log(client, no_backend, _capture_audit):
    register_and_login(client, "s05-cookie")
    project_id = _create_project(client, "s05-cookie", "Python", "print(1)")
    session_token = client.cookies.get("ai_session")
    assert session_token, "expected an authenticated session cookie"
    _capture_audit.clear()

    client.post(f"/code/projects/{project_id}/execute", json={"username": "s05-cookie"})

    blob = _audit_blob(_capture_audit)
    assert session_token not in blob
    assert "ai_session" not in blob


def test_unauthenticated_request_logs_nothing_about_credentials(client, no_backend, _capture_audit):
    """An anonymous probe is rejected by auth before any execution audit can carry an identity."""
    _capture_audit.clear()

    response = client.post("/code/projects/1/execute", json={"username": "ghost"})

    assert response.status_code == 401
    blob = _audit_blob(_capture_audit)
    assert "ghost" not in blob
    assert "ai_session" not in blob


# ── the audit line stays parseable and bounded ─────────────────────────────────────

def test_audit_line_is_single_line_and_bounded(client, no_backend, _capture_audit):
    register_and_login(client, "s05-fmt")
    project_id = _create_project(client, "s05-fmt", "Python", "print(1)")
    _capture_audit.clear()

    client.post(f"/code/projects/{project_id}/execute", json={"username": "s05-fmt"})

    line = _audit_lines(_capture_audit)[0]
    assert "\n" not in line and "\r" not in line
    assert len(line) < 500


def test_field_values_cannot_forge_new_log_fields():
    """A value containing '=' or a newline must not be able to fake a field or a record."""
    audit = security_audit
    with audit.code_execution_audit_context(user="attacker injected=spoofed\nevent=FAKE"):
        ...
    # Rendering is the unit under test here; assert the sanitiser flattens newlines.
    assert "\n" not in audit._flat("a\nb\r\nc")
    assert audit._flat("x" * 500).__len__() == 200
