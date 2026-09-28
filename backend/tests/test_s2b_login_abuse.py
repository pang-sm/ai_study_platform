"""SECURITY_S2B — password login must resist online guessing, without becoming the weapon.

``POST /login`` counted nothing: one client could guess a password, or walk a list of
accounts, as fast as the network allowed, and the only cost was the bcrypt work the server
did on the attacker's behalf.

The protection is two independent sliding-window budgets — the source address and the
identifier — and every test here exists to pin one of three properties:

* each dimension bites on its own (a per-IP cap alone loses to a botnet; a per-account cap
  alone loses to spraying);
* a refusal changes nothing except the answer — no session, no account disclosure, no
  credential or token in the log;
* pressure is always temporary, so the throttle cannot be turned into a way to lock a
  learner out of their own account.
"""
import logging
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
import models
from core import login_abuse
from conftest import register_and_login

AUDIT_LOGGER = "security.audit"
GENERIC_FAILURE = "账号、邮箱或密码错误"


@pytest.fixture(autouse=True)
def _capture_audit(caplog):
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
    yield caplog


def _audit_lines(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == AUDIT_LOGGER and record.getMessage().startswith("LOGIN")
    ]


def _client_from(ip: str) -> TestClient:
    """A client whose socket peer is ``ip`` — the only address a default deployment trusts."""
    return TestClient(main.app, client=(ip, 50000))


def _wrong_login(client: TestClient, username: str, password: str = "not-the-password"):
    return client.post("/login", json={"username": username, "password": password})


def _identifier_attempts(client: TestClient, username: str, times: int):
    """Spend ``times`` failed attempts on one account, returning the last response."""
    response = None
    for _ in range(times):
        response = _wrong_login(client, username)
    return response


# ── 1. the happy path is untouched ─────────────────────────────────────────────────

def test_normal_login_still_succeeds(client: TestClient):
    register_and_login(client, "s2b-normal")
    client.cookies.clear()

    response = client.post("/login", json={"username": "s2b-normal", "password": "secret123"})
    assert response.status_code == 200
    assert "ai_session" in client.cookies


def test_email_login_by_verified_email_still_works(client: TestClient):
    """The identifier dimension keys on the string typed, so the email route must still work."""
    register_and_login(client, "s2b-by-email")
    client.cookies.clear()

    response = client.post("/login", json={"username": "s2b-by-email@example.test", "password": "secret123"})
    assert response.status_code == 200


# ── 2. the generic failure is preserved ────────────────────────────────────────────

def test_one_wrong_password_returns_the_existing_generic_failure(client: TestClient):
    register_and_login(client, "s2b-one-wrong")
    client.cookies.clear()

    response = _wrong_login(client, "s2b-one-wrong")
    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_FAILURE


# ── 3. the identifier dimension ────────────────────────────────────────────────────

def test_repeated_guesses_on_one_account_are_refused(client: TestClient):
    register_and_login(client, "s2b-brute")
    client.cookies.clear()

    last = _identifier_attempts(client, "s2b-brute", login_abuse.IDENTIFIER_MAX_FAILURES)
    assert last.status_code == 400, "the budget must not bite early"

    refused = _wrong_login(client, "s2b-brute")
    assert refused.status_code == 429
    assert refused.json()["detail"]["code"] == login_abuse.RATE_LIMITED_CODE

    retry_after = refused.headers.get("Retry-After")
    assert retry_after is not None and int(retry_after) > 0


def test_an_unknown_identifier_is_budgeted_the_same_as_a_real_one(client: TestClient):
    """Spraying never-known names must cost the same as spraying real ones."""
    _identifier_attempts(client, "s2b-ghost-account", login_abuse.IDENTIFIER_MAX_FAILURES)
    refused = _wrong_login(client, "s2b-ghost-account")
    assert refused.status_code == 429


def test_the_identifier_budget_survives_a_changing_source(monkeypatch):
    """Many hosts converging on one account still trip the account budget."""
    with _client_from("10.1.0.1") as setup:
        register_and_login(setup, "s2b-distributed")

    statuses = []
    for index in range(login_abuse.IDENTIFIER_MAX_FAILURES + 1):
        with _client_from(f"10.9.{index}.{index}") as attacker:
            statuses.append(_wrong_login(attacker, "s2b-distributed").status_code)

    assert statuses[: login_abuse.IDENTIFIER_MAX_FAILURES] == [400] * login_abuse.IDENTIFIER_MAX_FAILURES
    assert statuses[-1] == 429, "the sixth source must be refused even though it is a new IP"


# ── 4. the source dimension ────────────────────────────────────────────────────────

def test_one_source_spraying_many_accounts_is_refused(monkeypatch, caplog):
    """The account budget is blind to a spray, so the source budget has to catch it."""
    monkeypatch.setattr(login_abuse, "SOURCE_MAX_FAILURES", 4)

    with _client_from("10.2.0.1") as attacker:
        for index in range(4):
            assert _wrong_login(attacker, f"s2b-spray-{index}").status_code == 400
        refused = _wrong_login(attacker, "s2b-spray-99")
        assert refused.status_code == 429

    limited = [line for line in _audit_lines(caplog) if "event=LOGIN_RATE_LIMITED" in line]
    assert limited and "scope=source" in limited[-1], "the source dimension is what fired here"


def test_a_source_budget_is_shared_by_every_identifier_under_it(monkeypatch):
    """Hitting the source budget stops even a first guess at a brand-new account."""
    monkeypatch.setattr(login_abuse, "SOURCE_MAX_FAILURES", 3)

    with _client_from("10.2.0.2") as attacker:
        for index in range(3):
            _wrong_login(attacker, f"s2b-shared-{index}")
        assert _wrong_login(attacker, "s2b-shared-brand-new").status_code == 429


def test_a_new_source_can_still_use_the_service(monkeypatch):
    """One abusive host must not spend anyone else's budget."""
    monkeypatch.setattr(login_abuse, "SOURCE_MAX_FAILURES", 3)

    with _client_from("10.2.0.3") as attacker:
        for index in range(3):
            _wrong_login(attacker, f"s2b-scoped-{index}")

    with _client_from("10.2.0.4") as learner:
        assert _wrong_login(learner, "s2b-someone-else").status_code == 400


# ── 5. no permanent lock ───────────────────────────────────────────────────────────

def test_the_identifier_budget_expires_on_its_own(monkeypatch, client: TestClient):
    """The block must lift by itself — a throttle that never releases is an account lockout.

    The failures are seeded directly rather than by five real requests: each real request
    spends a bcrypt verification, so accumulating them would take longer than the test's own
    window and the budget would drain as fast as it filled.
    """
    register_and_login(client, "s2b-expiry")
    client.cookies.clear()

    monkeypatch.setattr(login_abuse, "IDENTIFIER_WINDOW_SECONDS", 1)
    for _ in range(login_abuse.IDENTIFIER_MAX_FAILURES):
        login_abuse.record_login_failure(ip="testclient", identifier="s2b-expiry")

    assert _wrong_login(client, "s2b-expiry").status_code == 429

    time.sleep(1.1)
    assert _wrong_login(client, "s2b-expiry").status_code == 400, "the lock must lift by itself"


def test_a_correct_password_clears_the_account_pressure(client: TestClient):
    register_and_login(client, "s2b-clears")
    client.cookies.clear()

    _identifier_attempts(client, "s2b-clears", login_abuse.IDENTIFIER_MAX_FAILURES - 1)
    assert client.post(
        "/login", json={"username": "s2b-clears", "password": "secret123"}
    ).status_code == 200

    # Budget reset by the success: a fresh run of mistakes must be tolerated again.
    assert _wrong_login(client, "s2b-clears").status_code == 400


def test_a_success_does_not_reset_the_source_history(monkeypatch):
    """Otherwise one valid account would buy an attacker unlimited spraying from that host."""
    monkeypatch.setattr(login_abuse, "SOURCE_MAX_FAILURES", 3)

    with _client_from("10.3.0.1") as attacker:
        register_and_login(attacker, "s2b-own-account")
        attacker.cookies.clear()

        for index in range(2):
            _wrong_login(attacker, f"s2b-burn-{index}")

        # Signing in with a password that is actually correct must succeed here (the source
        # budget is not yet spent) — and must not refund the two failures already charged.
        assert attacker.post(
            "/login", json={"username": "s2b-own-account", "password": "secret123"}
        ).status_code == 200

        assert _wrong_login(attacker, "s2b-after-success").status_code == 400
        # Third failure since the source was first charged. If the success had cleared the
        # history the count would be 1 here and this would still be admitted.
        assert _wrong_login(attacker, "s2b-after-success").status_code == 429


def test_a_rate_limited_attempt_creates_no_session(client: TestClient):
    register_and_login(client, "s2b-no-session")
    user_id = (
        main.SessionLocal()
        .query(models.User)
        .filter(models.User.username == "s2b-no-session")
        .one()
        .id
    )
    client.cookies.clear()

    def sessions_for_user() -> int:
        db = main.SessionLocal()
        try:
            return db.query(models.AuthSession).filter(models.AuthSession.user_id == user_id).count()
        finally:
            db.close()

    # Registration and the harness login already opened sessions; what matters is that a
    # refused attempt adds none.
    before = sessions_for_user()

    _identifier_attempts(client, "s2b-no-session", login_abuse.IDENTIFIER_MAX_FAILURES)
    refused = client.post("/login", json={"username": "s2b-no-session", "password": "secret123"})
    assert refused.status_code == 429, "even the CORRECT password is refused while throttled"
    assert "ai_session" not in client.cookies
    assert sessions_for_user() == before, "a refused attempt must not open a session"


# ── 6. enumeration resistance ──────────────────────────────────────────────────────

def test_unknown_account_and_wrong_password_are_indistinguishable(client: TestClient):
    register_and_login(client, "s2b-exists")
    client.cookies.clear()

    unknown = _wrong_login(client, "s2b-does-not-exist-at-all", "some-password")
    wrong = _wrong_login(client, "s2b-exists", "some-password")

    assert unknown.status_code == wrong.status_code == 400
    assert unknown.json() == wrong.json() == {"detail": GENERIC_FAILURE}


def test_the_unknown_account_path_still_spends_a_password_verification(client: TestClient, monkeypatch):
    """Equal wording is not enough if equal *timing* is missing: skipping bcrypt for an
    unknown account answers "does this name exist?" in the response time."""
    seen: list[str] = []
    real_verify = main.verify_password

    def spy(password: str, hashed: str) -> bool:
        seen.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(main, "verify_password", spy)

    response = _wrong_login(client, "s2b-timing-ghost", "some-password")
    assert response.status_code == 400
    assert len(seen) == 1, "the unknown-account path must verify against the dummy hash"
    assert seen[0] == main._LOGIN_TIMING_PARITY_HASH


def test_a_real_wrong_password_verifies_against_the_stored_hash(client: TestClient, monkeypatch):
    register_and_login(client, "s2b-timing-real")
    client.cookies.clear()

    seen: list[str] = []
    real_verify = main.verify_password

    def spy(password: str, hashed: str) -> bool:
        seen.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(main, "verify_password", spy)
    _wrong_login(client, "s2b-timing-real", "some-password")

    assert seen and seen[0] != main._LOGIN_TIMING_PARITY_HASH


def test_an_over_long_password_on_an_unknown_account_is_still_a_clean_400(client: TestClient):
    """bcrypt 5 refuses input over 72 bytes by raising. The timing-parity verification must not
    turn the answer an unknown account used to give (a plain 400) into a 500."""
    response = _wrong_login(client, "s2b-long-password-ghost", "p" * 200)
    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_FAILURE


def test_a_refusal_never_says_which_bucket_was_hit(client: TestClient):
    register_and_login(client, "s2b-opaque")
    client.cookies.clear()
    _identifier_attempts(client, "s2b-opaque", login_abuse.IDENTIFIER_MAX_FAILURES)

    refused = _wrong_login(client, "s2b-opaque")
    assert refused.status_code == 429
    body = refused.text
    assert GENERIC_FAILURE not in body
    for leak in ("s2b-opaque", "identifier", "source", "5", "attempt"):
        assert leak not in refused.json()["detail"]["message"]


# ── 7. the log is part of the containment boundary ─────────────────────────────────

def test_a_failed_login_is_recorded_without_the_password(client: TestClient, caplog):
    register_and_login(client, "s2b-log-fail")
    client.cookies.clear()

    _wrong_login(client, "s2b-log-fail", "hunter2-should-never-appear")

    lines = _audit_lines(caplog)
    assert any("event=LOGIN_FAILED" in line for line in lines)
    assert "hunter2-should-never-appear" not in caplog.text


def test_the_log_does_not_say_whether_the_account_exists(client: TestClient, caplog):
    register_and_login(client, "s2b-log-exists")
    client.cookies.clear()

    _wrong_login(client, "s2b-log-exists", "wrong-password")
    _wrong_login(client, "s2b-log-ghost", "wrong-password")

    failures = "\n".join(line for line in _audit_lines(caplog) if "event=LOGIN_FAILED" in line)
    assert failures.count("event=LOGIN_FAILED") == 2
    # One reason for both, so the log cannot answer "does this account exist?".
    assert failures.count("reason=invalid_credentials") == 2
    # A real account and a made-up one are written the same way: as a digest, never a name.
    assert "s2b-log-exists" not in failures
    assert "s2b-log-ghost" not in failures
    assert login_abuse.identifier_digest("s2b-log-exists") in failures
    assert login_abuse.identifier_digest("s2b-log-ghost") in failures


def test_a_successful_login_is_recorded_without_the_session_token(client: TestClient, caplog):
    register_and_login(client, "s2b-log-ok")
    token = client.cookies.get("ai_session")
    assert token

    assert any("event=LOGIN_SUCCEEDED" in line for line in _audit_lines(caplog))
    assert token not in caplog.text
    assert token[:12] not in caplog.text


def test_a_refusal_is_recorded_with_its_scope_and_hint(client: TestClient, caplog):
    register_and_login(client, "s2b-log-limited")
    client.cookies.clear()
    _identifier_attempts(client, "s2b-log-limited", login_abuse.IDENTIFIER_MAX_FAILURES)
    _wrong_login(client, "s2b-log-limited")

    limited = [line for line in _audit_lines(caplog) if "event=LOGIN_RATE_LIMITED" in line]
    assert limited, "a refusal must leave a trace"
    assert "scope=identifier" in limited[-1]
    assert "retry_after=" in limited[-1]


# ── 8. the audit trail must actually reach a handler ───────────────────────────────

def test_the_audit_logger_is_emitting_at_info():
    """The events are emitted at INFO; an unconfigured root logger would discard them and the
    audit trail would exist only in the tests that attach their own handler."""
    audit = logging.getLogger(AUDIT_LOGGER)
    assert audit.isEnabledFor(logging.INFO)
    assert audit.handlers or logging.getLogger().handlers


# ── 9. proxy trust is fail-closed ──────────────────────────────────────────────────

def test_a_forwarded_header_from_an_untrusted_peer_is_ignored(monkeypatch):
    monkeypatch.delenv(login_abuse.CLIENT_IP_HEADER_ENV, raising=False)
    resolved = login_abuse.resolve_client_ip("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})
    assert resolved == "203.0.113.9", "the socket peer is the only evidence without an opt-in"


def test_forging_a_forwarded_header_cannot_buy_a_fresh_budget(client: TestClient):
    """With trust off, rotating the header must not rotate the bucket."""
    register_and_login(client, "s2b-forge")
    client.cookies.clear()

    for index in range(login_abuse.IDENTIFIER_MAX_FAILURES):
        client.post(
            "/login",
            json={"username": "s2b-forge", "password": "wrong"},
            headers={"x-forwarded-for": f"198.51.100.{index}"},
        )
    assert _wrong_login(client, "s2b-forge").status_code == 429


def test_a_proxied_request_is_unresolvable_by_default(monkeypatch):
    """Behind the deployment's own nginx every peer is loopback. Keying on that would put the
    whole internet in one bucket, so the source dimension stands down instead."""
    monkeypatch.delenv(login_abuse.CLIENT_IP_HEADER_ENV, raising=False)
    assert login_abuse.resolve_client_ip("127.0.0.1", {}) is None
    assert login_abuse.resolve_client_ip("::1", {}) is None


def test_an_explicitly_trusted_header_is_used_and_its_forged_prefix_ignored(monkeypatch):
    monkeypatch.setenv(login_abuse.CLIENT_IP_HEADER_ENV, "x-forwarded-for")
    # nginx appends the address it actually saw, so the RIGHTMOST entry is the trustworthy
    # one; everything the client prepended is attacker-supplied noise.
    resolved = login_abuse.resolve_client_ip(
        "127.0.0.1", {"x-forwarded-for": "9.9.9.9, 203.0.113.7"}
    )
    assert resolved == "203.0.113.7"


def test_a_trusted_header_from_an_untrusted_peer_is_still_ignored(monkeypatch):
    monkeypatch.setenv(login_abuse.CLIENT_IP_HEADER_ENV, "x-forwarded-for")
    resolved = login_abuse.resolve_client_ip("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})
    assert resolved == "203.0.113.9"


def test_x_real_ip_is_supported_when_named(monkeypatch):
    monkeypatch.setenv(login_abuse.CLIENT_IP_HEADER_ENV, "x-real-ip")
    assert login_abuse.resolve_client_ip("127.0.0.1", {"x-real-ip": "203.0.113.7"}) == "203.0.113.7"
    assert login_abuse.resolve_client_ip("127.0.0.1", {"x-real-ip": "not-an-ip"}) is None


def test_an_unknown_client_address_disables_only_the_source_dimension():
    """With no address to charge, the account budget must still apply."""
    decision = login_abuse.check_login_attempt(ip=None, identifier="someone")
    assert decision.allowed
    for _ in range(login_abuse.IDENTIFIER_MAX_FAILURES):
        login_abuse.record_login_failure(ip=None, identifier="someone")
    assert login_abuse.check_login_attempt(ip=None, identifier="someone").allowed is False


# ── 10. the limiter's own arithmetic ───────────────────────────────────────────────

def test_case_variants_share_one_identifier_budget():
    for variant in ("Alice", "ALICE", "alice", "  alice  "):
        login_abuse.record_login_failure(ip=None, identifier=login_abuse.normalize_login_identifier(variant))
    assert len(login_abuse._failures[(login_abuse.SCOPE_IDENTIFIER, "alice")]) == 4


def test_escape_by_case_padding_is_closed():
    for variant in ("Bob", "bOb", "BOB", "bob", "  BOB "):
        login_abuse.record_login_failure(ip=None, identifier=login_abuse.normalize_login_identifier(variant))
    assert login_abuse.check_login_attempt(ip=None, identifier="bob").allowed is False


def test_the_backoff_grows_with_abuse_and_is_capped_at_the_window():
    identifier = "escalating"
    waits = []
    for _ in range(login_abuse.IDENTIFIER_MAX_FAILURES + 4):
        login_abuse.record_login_failure(ip=None, identifier=identifier)
        decision = login_abuse.check_login_attempt(ip=None, identifier=identifier)
        if not decision.allowed:
            waits.append(decision.retry_after)

    assert waits, "abuse must eventually be refused"
    assert waits == sorted(waits), "more abuse must never shorten the wait"
    assert max(waits) <= login_abuse.IDENTIFIER_WINDOW_SECONDS


def test_the_backoff_floor_doubles_per_episode_and_stops_at_the_window():
    window = login_abuse.IDENTIFIER_WINDOW_SECONDS
    base = login_abuse.BACKOFF_BASE_SECONDS

    assert login_abuse.backoff_floor_seconds(0, window) == base
    assert login_abuse.backoff_floor_seconds(1, window) == base
    assert login_abuse.backoff_floor_seconds(2, window) == base * 2
    assert login_abuse.backoff_floor_seconds(3, window) == base * 4
    assert login_abuse.backoff_floor_seconds(4, window) == base * 8
    # However long the abuse continues, the floor never outlives the window.
    assert login_abuse.backoff_floor_seconds(5, window) == window
    assert login_abuse.backoff_floor_seconds(99, window) == window


def test_a_capped_floor_never_exceeds_a_shorter_window():
    """The floor is capped by the dimension's own window, not by a shared constant."""
    assert login_abuse.backoff_floor_seconds(99, 5) == 5


def test_a_refused_attempt_does_not_extend_its_own_lockout(monkeypatch, client: TestClient):
    """The property that keeps this a throttle: knocking on a closed door does not wedge it.

    If a refused request were charged as a failure, an attacker could hold a learner's account
    shut indefinitely by never stopping — each attempt pushing the window further out. Refusals
    are therefore not recorded, and only the failure that exhausts the budget counts.
    """
    register_and_login(client, "s2b-no-extend")
    client.cookies.clear()

    for _ in range(login_abuse.IDENTIFIER_MAX_FAILURES):
        login_abuse.record_login_failure(ip="testclient", identifier="s2b-no-extend")

    first = _wrong_login(client, "s2b-no-extend")
    assert first.status_code == 429
    retry_first = int(first.headers["Retry-After"])

    last = first
    for _ in range(20):
        last = _wrong_login(client, "s2b-no-extend")
        assert last.status_code == 429

    assert int(last.headers["Retry-After"]) <= retry_first
    # Twenty-one refusals produced exactly one episode: the one that emptied the budget.
    assert len(login_abuse._exhaustions[(login_abuse.SCOPE_IDENTIFIER, "s2b-no-extend")]) == 1
    assert len(login_abuse._failures[(login_abuse.SCOPE_IDENTIFIER, "s2b-no-extend")]) == (
        login_abuse.IDENTIFIER_MAX_FAILURES
    )


def test_the_tracked_key_map_is_bounded(monkeypatch):
    monkeypatch.setattr(login_abuse, "MAX_TRACKED_KEYS", 50)
    for index in range(500):
        login_abuse.record_login_failure(ip=None, identifier=f"flood-{index}")
    assert len(login_abuse._failures) <= 50


def test_the_password_is_never_part_of_a_key():
    """A key built from the password would let one account hold many budgets."""
    before = set(login_abuse._failures)
    login_abuse.record_login_failure(ip="203.0.113.7", identifier="whose")
    added = set(login_abuse._failures) - before
    assert added == {
        (login_abuse.SCOPE_IDENTIFIER, "whose"),
        (login_abuse.SCOPE_SOURCE, "203.0.113.7"),
    }
    assert not any("password" in str(key) for key in added)


def test_the_production_defaults_are_the_documented_ones():
    """Guards against a test-only constant quietly becoming the shipped policy."""
    assert login_abuse.IDENTIFIER_MAX_FAILURES == 5
    assert login_abuse.IDENTIFIER_WINDOW_SECONDS == 300
    assert login_abuse.SOURCE_MAX_FAILURES >= login_abuse.IDENTIFIER_MAX_FAILURES


# ── 11. the code-based flows are untouched ────────────────────────────────────────

def test_email_code_login_is_unaffected(client: TestClient):
    register_and_login(client, "s2b-code-login")
    client.cookies.clear()

    sent: list[str] = []

    def capture(_recipient: str, code: str) -> bool:
        sent.append(code)
        return True

    with patch.object(main, "_send_email_code", side_effect=capture):
        assert client.post(
            "/auth/email-login/send-code", json={"email": "s2b-code-login@example.test"}
        ).status_code == 200
        response = client.post(
            "/auth/email-login",
            json={"email": "s2b-code-login@example.test", "code": sent[-1]},
        )
    assert response.status_code == 200
    assert "ai_session" in client.cookies


def test_the_code_resend_cooldown_still_applies(client: TestClient):
    register_and_login(client, "s2b-code-cooldown")

    with patch.object(main, "_send_email_code", return_value=True):
        first = client.post("/auth/email-login/send-code", json={"email": "s2b-code-cooldown@example.test"})
        second = client.post("/auth/email-login/send-code", json={"email": "s2b-code-cooldown@example.test"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_registration_code_flow_is_unaffected(client: TestClient):
    """The whole registration path goes through the same email primitives."""
    user = register_and_login(client, "s2b-register")
    assert user["username"] == "s2b-register"


def test_the_code_flow_does_not_clear_login_pressure(client: TestClient):
    """Different mechanisms must not hand each other a clean slate."""
    register_and_login(client, "s2b-cross")
    client.cookies.clear()

    _identifier_attempts(client, "s2b-cross", login_abuse.IDENTIFIER_MAX_FAILURES)
    assert _wrong_login(client, "s2b-cross").status_code == 429

    # A code login for the same account must not wipe the password budget.
    sent: list[str] = []

    def capture(_recipient: str, code: str) -> bool:
        sent.append(code)
        return True

    with patch.object(main, "_send_email_code", side_effect=capture):
        client.post("/auth/email-login/send-code", json={"email": "s2b-cross@example.test"})
        client.post("/auth/email-login", json={"email": "s2b-cross@example.test", "code": sent[-1]})

    assert _wrong_login(client, "s2b-cross").status_code == 429


def test_an_authenticated_session_is_unaffected(client: TestClient):
    register_and_login(client, "s2b-session")
    assert client.get("/me/profile").status_code == 200

    for index in range(login_abuse.IDENTIFIER_MAX_FAILURES + 1):
        _wrong_login(client, "someone-else-entirely", f"guess-{index}")

    # Abuse aimed at other accounts must not disturb the live session.
    assert client.get("/me/profile").status_code == 200
