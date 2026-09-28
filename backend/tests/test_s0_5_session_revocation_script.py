"""SECURITY_S0.5 — the session-revocation operation and what it must achieve.

SECURITY_S0's read primitive reached ``app.db``, which stores session-token hashes. The
conservative response is to invalidate every live session rather than argue about whether a
hash is replayable. This exercises the operator script that does it, end to end, on a real
database — including the two properties that make it safe to run against production:

* it invalidates an already-issued cookie, and
* it leaves login working afterwards (a revoke that breaks authentication would be worse
  than the exposure it was responding to).
"""
import os
import subprocess
import sys
from pathlib import Path

from conftest import register_and_login

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deploy" / "revoke_all_sessions.py"

AUTH_REQUIRED_PATH = "/me/quota"


def _run_script(**overrides) -> subprocess.CompletedProcess:
    env = {**os.environ, **overrides}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env, capture_output=True, text=True, cwd=str(REPO_ROOT),
    )


def test_script_reports_counts_and_revokes_every_live_session(client):
    register_and_login(client, "s05-revoke")
    assert client.get(AUTH_REQUIRED_PATH).status_code == 200, "session should work before revoke"

    result = _run_script()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ACTIVE_SESSION_COUNT_BEFORE=" in result.stdout
    assert "ACTIVE_SESSION_COUNT_AFTER=0" in result.stdout


def test_an_already_issued_cookie_is_rejected_after_revocation(client):
    register_and_login(client, "s05-revoke-old")
    assert client.get(AUTH_REQUIRED_PATH).status_code == 200

    _run_script()

    response = client.get(AUTH_REQUIRED_PATH)
    assert response.status_code == 401, response.text


def test_login_still_works_after_revocation(client):
    """Revocation must not break authentication — that would be a self-inflicted outage."""
    register_and_login(client, "s05-revoke-next")

    _run_script()

    fresh = client.post("/login", json={"username": "s05-revoke-next", "password": "secret123"})
    assert fresh.status_code == 200, fresh.text
    assert "ai_session" in client.cookies
    assert client.get(AUTH_REQUIRED_PATH).status_code == 200


def test_script_is_idempotent(client):
    register_and_login(client, "s05-revoke-idem")

    first = _run_script()
    second = _run_script()

    assert first.returncode == 0
    assert second.returncode == 0
    assert "ACTIVE_SESSION_COUNT_BEFORE=0" in second.stdout
    assert "ACTIVE_SESSION_COUNT_AFTER=0" in second.stdout


def test_script_refuses_to_run_without_an_explicit_database_target():
    """Never fall back to a default database: the whole point is to hit a named one."""
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env, capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "DATABASE_URL" in result.stdout
