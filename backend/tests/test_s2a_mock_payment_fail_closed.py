"""SECURITY_S2A — the mock payment provider must be explicitly enabled, never defaulted on.

The mock provider settles an order with no money changing hands, so its availability is a
security decision. It used to be opt-OUT: the check read ``os.getenv("APP_ENV", "local")`` and
accepted the empty string, so a deployment that omitted ``APP_ENV``, set it blank, or mistyped
it had the mock provider enabled — and any authenticated learner could pay an order and
activate a paid membership for free.

These tests are about the ORDER's fate, not just the status code: a refusal must leave the
order unpaid, write no payment event, grant no membership and post no revenue.
"""
import pytest

import database
import main
import models
from conftest import register_and_login
from payments import MOCK_PAYMENT_ENVIRONMENTS, get_payment_provider, is_mock_payment_allowed
from usage import service as usage_service


# ── the policy itself ──────────────────────────────────────────────────────────────

DENIED_ENV_VALUES = [
    "production", "prod", "PRODUCTION", " Production ",   # the live deployment value
    "prodction", "prodution", "production-us",             # typos must not fuzzy-match
    "staging", "stage", "qa", "preview", "random", "0", "false",
    "", "   ",                                             # blank is NOT "local"
]

ALLOWED_ENV_VALUES = ["local", "test", "acceptance", "LOCAL", " Acceptance "]


@pytest.mark.parametrize("value", DENIED_ENV_VALUES)
def test_mock_payment_is_denied_for_every_environment_that_is_not_explicitly_allowed(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    assert is_mock_payment_allowed() is False, value


@pytest.mark.parametrize("value", ALLOWED_ENV_VALUES)
def test_mock_payment_is_allowed_only_for_the_named_environments(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    assert is_mock_payment_allowed() is True, value


def test_missing_app_env_denies(monkeypatch):
    """The regression itself: unset used to fall back to "local" and allow."""
    monkeypatch.delenv("APP_ENV", raising=False)
    assert is_mock_payment_allowed() is False


def test_production_cannot_be_opened_by_widening_the_allowlist(monkeypatch):
    """Production is checked first, so a mistake in the allowlist cannot open it."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr("payments.registry.MOCK_PAYMENT_ENVIRONMENTS", ("production", "local"))
    assert is_mock_payment_allowed() is False


def test_provider_selection_is_independent_of_the_mock_permission(monkeypatch):
    """The real-provider path is untouched: this round changed WHO may use mock, not which
    adapter is selected (that remains the explicit PAYMENT_PROVIDER opt-in)."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("PAYMENT_PROVIDER", raising=False)
    assert is_mock_payment_allowed() is False
    assert get_payment_provider().name == "mock"


def test_the_allowlist_is_a_named_set_not_a_heuristic():
    assert set(MOCK_PAYMENT_ENVIRONMENTS) == {"local", "test", "acceptance"}


# ── end to end: what a refusal does to the order ───────────────────────────────────

def _order(client, plan: str = "monthly") -> dict:
    response = client.post("/membership/orders",
                           json={"service_key": "course_learning", "target_plan": plan, "amount": 1})
    assert response.status_code == 200, response.text
    return response.json()["order"]


def _order_fate(order_id: int) -> dict:
    db = database.SessionLocal()
    try:
        order = db.get(models.MembershipOrder, order_id)
        return {
            "status": order.status,
            "paid_at": order.paid_at,
            "payment_events": db.query(models.PaymentEvent).filter_by(order_id=order_id).count(),
            "membership_grants": db.query(models.MembershipGrant).filter_by(order_id=order_id).count(),
            "revenue_entries": db.query(models.RevenueLedgerEntry)
                                     .filter_by(order_id=order_id, entry_type="PAYMENT").count(),
            "paid_amount": order.paid_amount,
        }
    finally:
        db.close()


def _tier(username: str) -> str:
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        return usage_service.effective_subscription(db, user.id)
    finally:
        db.close()


def _fresh_user(client) -> str:
    """A uniquely named learner — the test database is shared, so a fixed name collides."""
    import secrets as _secrets
    username = f"s2a-{_secrets.token_hex(5)}"
    register_and_login(client, username)
    return username


def _assert_untouched(order_id: int) -> None:
    fate = _order_fate(order_id)
    assert fate == {"status": "pending", "paid_at": None, "payment_events": 0,
                    "membership_grants": 0, "revenue_entries": 0, "paid_amount": None}, fate


@pytest.mark.parametrize("app_env", ["production", "prodction", "staging", ""])
def test_mock_pay_is_refused_and_leaves_the_order_untouched(client, monkeypatch, app_env):
    monkeypatch.setenv("APP_ENV", app_env)
    username = _fresh_user(client)
    order = _order(client)
    tier_before = _tier(username)

    response = client.post(f"/membership/orders/{order['id']}/pay")

    assert response.status_code == 403, response.text
    _assert_untouched(order["id"])
    assert _tier(username) == tier_before, "a refused mock payment must not activate a membership"


def test_mock_pay_is_refused_when_app_env_is_absent(client, monkeypatch):
    """The original fail-open: no APP_ENV at all."""
    monkeypatch.delenv("APP_ENV", raising=False)
    _fresh_user(client)
    order = _order(client)

    response = client.post(f"/membership/orders/{order['id']}/pay")

    assert response.status_code == 403, response.text
    _assert_untouched(order["id"])


def test_mock_pay_still_works_in_a_named_development_environment(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "acceptance")
    _fresh_user(client)
    order = _order(client)

    response = client.post(f"/membership/orders/{order['id']}/pay")

    assert response.status_code == 200, response.text
    fate = _order_fate(order["id"])
    assert fate["status"] == "paid" and fate["payment_events"] == 1
    assert fate["membership_grants"] == 1 and fate["revenue_entries"] == 1


# ── the callback can never settle through mock, in any environment ─────────────────

@pytest.mark.parametrize("app_env", ["production", "local", "acceptance", ""])
def test_mock_callback_is_unavailable_in_every_environment(client, monkeypatch, app_env):
    """Even self-reporting `provider=mock` cannot settle — the route is closed by design."""
    monkeypatch.setenv("APP_ENV", app_env)

    response = client.post("/payments/callback/mock", json={"order_no": "MT0", "amount": 1})

    assert response.status_code == 404, response.text


def test_mock_refund_is_refused_in_production(client, monkeypatch):
    """The refund gate uses the same predicate, so it fails closed with it."""
    monkeypatch.setenv("APP_ENV", "acceptance")
    _fresh_user(client)
    order = _order(client)
    assert client.post(f"/membership/orders/{order['id']}/pay").status_code == 200

    monkeypatch.setenv("APP_ENV", "production")
    refund = client.post(f"/membership/orders/{order['id']}/refund", json={"reason": "x"})

    assert refund.status_code == 403, refund.text
    db = database.SessionLocal()
    try:
        assert db.query(models.Refund).filter_by(order_id=order["id"]).count() == 0
    finally:
        db.close()
