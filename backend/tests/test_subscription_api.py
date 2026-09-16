"""STEP 7B final: Unified Subscription / Usage API contract tests.

Order flow is now: create PENDING order → (mock) payment → activation.
Redemption resolves the REAL redemption_codes table (no demo codes).
"""
import models
from membership import hash_code
from conftest import register_and_login


def _seed_redemption_code(db, code, service_key="course_learning",
                          target_plan="monthly", days=30, max_uses=1):
    entry = models.RedemptionCode(
        code_hash=hash_code(code),
        service_key=service_key,
        target_plan=target_plan,
        membership_duration_days=days,
        plan_code=target_plan,
        max_uses=max_uses,
        used_count=0,
        status="active",
        created_by="test",
    )
    db.add(entry)
    db.commit()
    return entry


def test_subscription_default_free(client):
    register_and_login(client, "api_alice")
    r = client.get("/subscription")
    assert r.status_code == 200
    assert r.json()["tier"] == "free"


def test_subscription_plans(client):
    register_and_login(client, "api_bob")
    r = client.get("/subscription/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert set(plans.keys()) == {"free", "standard", "advanced"}


def test_order_is_pending_not_activated(client):
    register_and_login(client, "api_carol")
    r = client.post("/subscription/orders", json={"tier": "standard", "duration_days": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["activated"] is False
    assert body["order"]["status"] == "pending"
    # Creating an order must NOT activate the subscription.
    assert client.get("/subscription").json()["tier"] == "free"


def test_order_pay_activates_tier(client):
    register_and_login(client, "api_dave")
    order = client.post("/subscription/orders", json={"tier": "standard", "duration_days": 30}).json()["order"]
    r = client.post(f"/subscription/orders/{order['id']}/pay")
    assert r.status_code == 200
    assert r.json()["order"]["status"] == "paid"
    assert r.json()["subscription"]["tier"] == "standard"
    assert client.get("/subscription").json()["tier"] == "standard"


def test_order_pay_idempotent(client):
    register_and_login(client, "api_erin")
    order = client.post("/subscription/orders", json={"tier": "advanced", "duration_days": 30}).json()["order"]
    assert client.post(f"/subscription/orders/{order['id']}/pay").status_code == 200
    r2 = client.post(f"/subscription/orders/{order['id']}/pay")
    assert r2.status_code == 200
    assert r2.json()["idempotent"] is True
    assert client.get("/subscription").json()["tier"] == "advanced"


def test_redeem_preview_real_code(client, db_session):
    register_and_login(client, "api_frank")
    _seed_redemption_code(db_session, "REAL-STD-30", target_plan="monthly", days=30)
    p = client.post("/subscription/redeem/preview", json={"code": "REAL-STD-30"})
    assert p.status_code == 200
    body = p.json()
    assert body["tier"] == "standard"
    assert body["duration_days"] == 30


def test_redeem_real_code_activates(client, db_session):
    register_and_login(client, "api_grace")
    _seed_redemption_code(db_session, "REAL-ADV-30", target_plan="full", days=30)
    r = client.post("/subscription/redeem", json={"code": "REAL-ADV-30"})
    assert r.status_code == 200
    assert r.json()["tier"] == "advanced"
    assert client.get("/subscription").json()["tier"] == "advanced"


def test_redeem_code_single_use(client, db_session):
    register_and_login(client, "api_heidi")
    _seed_redemption_code(db_session, "ONE-USE-CODE", target_plan="monthly", days=30, max_uses=1)
    assert client.post("/subscription/redeem", json={"code": "ONE-USE-CODE"}).status_code == 200
    # Same code redeemed by another user must fail (exhausted).
    register_and_login(client, "api_ivan")
    r = client.post("/subscription/redeem", json={"code": "ONE-USE-CODE"})
    assert r.status_code == 400


def test_unknown_redeem_code(client):
    register_and_login(client, "api_jack")
    r = client.post("/subscription/redeem/preview", json={"code": "NOPE"})
    assert r.status_code == 400


def test_usage_summary_shape(client):
    register_and_login(client, "api_kate")
    r = client.get("/usage/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert "daily" in body["periods"] and "weekly" in body["periods"]
    assert body["periods"]["daily"]["budget"] == 100


def test_cross_user_isolation(client):
    # user 1: leo → advanced (order + pay)
    register_and_login(client, "api_leo")
    order = client.post("/subscription/orders", json={"tier": "advanced", "duration_days": 30}).json()["order"]
    client.post(f"/subscription/orders/{order['id']}/pay")
    assert client.get("/subscription").json()["tier"] == "advanced"
    # user 2: mia → still free
    register_and_login(client, "api_mia")
    assert client.get("/subscription").json()["tier"] == "free"
