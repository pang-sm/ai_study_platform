"""Auth V2 product-contract tests.

Covers the formal register / password-login / email-code-login / session
contract with no legacy-user compatibility:
  - register requires verified email, sets email_verified=True
  - password login accepts username OR verified email
  - email-code login never auto-registers an unknown email
  - server-side session, HttpOnly ai_session, SameSite=Lax
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import models


def _capture_send(client: TestClient, email: str, path: str = "/auth/register/send-code"):
    captured: list[str] = []

    def capture(_recipient: str, code: str) -> bool:
        captured.append(code)
        return True

    with patch.object(main, "_send_email_code", side_effect=capture):
        resp = client.post(path, json={"email": email})
    return resp, captured


def _register(client: TestClient, username: str, email: str, password: str = "secret123"):
    resp, codes = _capture_send(client, email)
    assert resp.status_code == 200, resp.text
    assert len(codes) == 1
    verified = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert verified.status_code == 200, verified.text
    reg = client.post("/register", json={"username": username, "password": password, "email": email})
    assert reg.status_code == 200, reg.text
    return reg


# ── REGISTER ──────────────────────────────────────────────


def test_register_send_code_and_verify(client):
    email = "v2-send-ok@example.test"
    resp, codes = _capture_send(client, email)
    assert resp.status_code == 200
    assert len(codes) == 1 and len(codes[0]) == 6 and codes[0].isdigit()
    verified = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert verified.status_code == 200


def test_register_invalid_email(client):
    resp = client.post("/auth/register/send-code", json={"email": "not-an-email"})
    assert resp.status_code == 400


def test_register_duplicate_email_rejected(client):
    _register(client, "v2-dup-email", "v2-dup-email@example.test")
    resp, _ = _capture_send(client, "V2-DUP-EMAIL@example.test")
    assert resp.status_code == 400


def test_register_wrong_code_increments_attempts(client, db_session):
    email = "v2-wrong-code@example.test"
    resp, codes = _capture_send(client, email)
    assert resp.status_code == 200
    wrong = "111111" if codes[0] != "111111" else "000000"
    bad = client.post("/auth/register/verify-code", json={"email": email, "code": wrong})
    assert bad.status_code == 400
    rec = (
        db_session.query(models.VerificationCode)
        .filter_by(target=email, purpose="register_email", used=False)
        .first()
    )
    assert rec is not None and rec.attempts == 1
    # correct code still accepted below the attempts cap
    ok = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert ok.status_code == 200


def test_register_expired_code(client, db_session):
    email = "v2-expired@example.test"
    resp, codes = _capture_send(client, email)
    assert resp.status_code == 200
    rec = (
        db_session.query(models.VerificationCode)
        .filter_by(target=email, purpose="register_email", used=False)
        .first()
    )
    rec.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    verified = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert verified.status_code == 400


def test_register_create_account_and_me(client):
    reg = _register(client, "v2-created", "v2-created@example.test")
    assert "ai_session" in client.cookies
    me = client.post("/me", json={})
    assert me.status_code == 200
    profile = me.json()["user"]
    assert profile["username"] == "v2-created"
    assert profile["email"] == "v2-created@example.test"
    assert profile["email_verified"] is True


def test_register_duplicate_username(client):
    _register(client, "v2-dup-user", "v2-dup-user-a@example.test")
    resp, codes = _capture_send(client, "v2-dup-user-b@example.test")
    assert resp.status_code == 200
    client.post("/auth/register/verify-code", json={"email": "v2-dup-user-b@example.test", "code": codes[0]})
    reg = client.post("/register", json={"username": "v2-dup-user", "password": "secret123", "email": "v2-dup-user-b@example.test"})
    assert reg.status_code == 400


def test_register_requires_verification_proof(client):
    # Registering without going through send-code -> verify-code must fail.
    reg = client.post("/register", json={"username": "v2-no-proof", "password": "secret123", "email": "v2-no-proof@example.test"})
    assert reg.status_code == 400


# ── PASSWORD LOGIN ────────────────────────────────────────


def test_password_login_by_username(client):
    _register(client, "v2-pw-user", "v2-pw-user@example.test")
    client.cookies.clear()
    login = client.post("/login", json={"username": "v2-pw-user", "password": "secret123"})
    assert login.status_code == 200
    assert client.post("/me", json={}).status_code == 200


def test_password_login_by_verified_email(client):
    _register(client, "v2-pw-email", "v2-pw-email@example.test")
    client.cookies.clear()
    login = client.post("/login", json={"username": "v2-pw-email@example.test", "password": "secret123"})
    assert login.status_code == 200
    assert client.post("/me", json={}).status_code == 200


def test_password_login_wrong_password(client):
    _register(client, "v2-wrong-pw", "v2-wrong-pw@example.test")
    client.cookies.clear()
    login = client.post("/login", json={"username": "v2-wrong-pw", "password": "bad-password"})
    assert login.status_code == 400


def test_password_login_unknown_account(client):
    login = client.post("/login", json={"username": "v2-ghost", "password": "whatever"})
    assert login.status_code == 400


# ── EMAIL CODE LOGIN ──────────────────────────────────────


def test_email_code_login_flow(client):
    _register(client, "v2-email-login", "v2-email-login@example.test")
    client.cookies.clear()
    resp, codes = _capture_send(client, "v2-email-login@example.test", path="/auth/email-login/send-code")
    assert resp.status_code == 200
    login = client.post("/auth/email-login", json={"email": "v2-email-login@example.test", "code": codes[0]})
    assert login.status_code == 200
    me = client.post("/me", json={})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "v2-email-login"


def test_email_code_login_unregistered_not_autoregistered(client):
    resp, _ = _capture_send(client, "v2-nobody@example.test", path="/auth/email-login/send-code")
    assert resp.status_code == 400


def test_email_code_login_wrong_code(client):
    _register(client, "v2-email-wrong", "v2-email-wrong@example.test")
    client.cookies.clear()
    resp, codes = _capture_send(client, "v2-email-wrong@example.test", path="/auth/email-login/send-code")
    assert resp.status_code == 200
    wrong = "111111" if codes[0] != "111111" else "000000"
    login = client.post("/auth/email-login", json={"email": "v2-email-wrong@example.test", "code": wrong})
    assert login.status_code == 400


# ── SESSION / SECURITY ────────────────────────────────────


def test_logout_revokes_session(client):
    _register(client, "v2-logout", "v2-logout@example.test")
    assert client.post("/me", json={}).status_code == 200
    out = client.post("/logout")
    assert out.status_code == 200
    assert client.post("/me", json={}).status_code == 401


def test_protected_endpoint_requires_session(client):
    assert client.get("/membership/summary", params={"username": "v2-anon"}).status_code == 401


def test_register_code_cannot_replay(client):
    email = "v2-replay@example.test"
    resp, codes = _capture_send(client, email)
    first = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert first.status_code == 200
    second = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert second.status_code == 400


def test_register_code_not_leaked_in_response(client):
    email = "v2-no-leak@example.test"
    resp, codes = _capture_send(client, email)
    assert codes[0] not in resp.text


def test_session_cookie_httponly(client):
    reg = _register(client, "v2-httponly", "v2-httponly@example.test")
    assert "ai_session=" in reg.headers["set-cookie"]
    assert "HttpOnly" in reg.headers["set-cookie"]


def test_register_proof_cookie_httponly(client):
    email = "v2-proof-httponly@example.test"
    resp, codes = _capture_send(client, email)
    verified = client.post("/auth/register/verify-code", json={"email": email, "code": codes[0]})
    assert verified.status_code == 200
    assert "zhixue_register_email_proof=" in verified.headers["set-cookie"]
    assert "HttpOnly" in verified.headers["set-cookie"]


def test_register_normalized_unique_email(client):
    _register(client, "v2-norm-1", "V2-Normalized@Example.com")
    resp, _ = _capture_send(client, "v2-normalized@example.com")
    assert resp.status_code == 400


def test_register_resend_rate_limit(client):
    email = "v2-ratelimit@example.test"
    first, _ = _capture_send(client, email)
    assert first.status_code == 200
    second, _ = _capture_send(client, email)
    assert second.status_code == 429
