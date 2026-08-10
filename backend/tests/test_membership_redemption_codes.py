from datetime import timedelta

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import main
import models
from membership import hash_code


def _make_admin(client: TestClient, username: str = "redemption-admin"):
    register_and_login(client, username)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).one()
        user.is_admin = 1
        user.admin_role = "super_admin"
        db.commit()
    finally:
        db.close()


def _create_code(admin: TestClient, **overrides):
    payload = {
        "service_key": "course_learning",
        "target_plan": "monthly",
        "membership_duration_days": 30,
        "code_expires_at": (main.utc_now() + timedelta(days=3)).isoformat(),
        "max_redemptions": 1,
        "count": 1,
        "note": "automated test",
    }
    payload.update(overrides)
    response = admin.post("/admin/membership/redemption-codes", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["codes"][0]


def test_admin_creates_direction_bound_code_and_user_previews_then_redeems(client: TestClient):
    _make_admin(client)
    normal = TestClient(client.app)
    try:
        register_and_login(normal, "redemption-user-a")
        denied = normal.post("/admin/membership/redemption-codes", json={})
        assert denied.status_code == 403

        created = _create_code(client, service_key="programming", target_plan="quarterly", membership_duration_days=90)
        assert len(created["code"].split("-")) == 4
        assert "code" not in client.get("/admin/membership/redemption-codes").json()["items"][0]

        wrong_direction = normal.post("/membership/redeem/preview", json={"code": created["code"], "service_key": "course_learning"})
        assert wrong_direction.status_code == 400
        preview = normal.post("/membership/redeem/preview", json={"code": created["code"]})
        assert preview.status_code == 200, preview.text
        assert preview.json()["preview"]["service_key"] == "programming"
        assert preview.json()["preview"]["membership_duration_days"] == 90

        redeemed = normal.post("/membership/redeem", json={"code": created["code"]})
        assert redeemed.status_code == 200, redeemed.text
        assert redeemed.json()["redemption"]["target_plan"] == "quarterly"
        catalog = normal.get("/membership/catalog", params={"service_key": "programming"})
        assert catalog.json()["current"]["plan"] == "quarterly"
        assert catalog.json()["current"]["expires_at"]
        assert normal.post("/membership/redeem", json={"code": created["code"]}).status_code == 400

        detail = client.get(f"/admin/membership/redemption-codes/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["usage"][0]["username"] == "redemption-user-a"
    finally:
        normal.close()


def test_redemption_rules_expiry_revoke_exhaustion_and_user_isolation(client: TestClient):
    _make_admin(client, "redemption-admin-rules")
    user_a = TestClient(client.app)
    user_b = TestClient(client.app)
    try:
        register_and_login(user_a, "redemption-rule-a")
        register_and_login(user_b, "redemption-rule-b")

        single = _create_code(client, target_plan="monthly")
        assert user_a.post("/membership/redeem", json={"code": single["code"]}).status_code == 200
        assert user_b.post("/membership/redeem", json={"code": single["code"]}).status_code == 400

        multi = _create_code(client, target_plan="quarterly", max_redemptions=2)
        assert user_a.post("/membership/redeem", json={"code": multi["code"]}).status_code == 200
        assert user_b.post("/membership/redeem", json={"code": multi["code"]}).status_code == 200
        assert user_a.post("/membership/redeem", json={"code": multi["code"]}).status_code == 400

        revoked = _create_code(client)
        assert client.post(f"/admin/membership/redemption-codes/{revoked['id']}/revoke").status_code == 200
        assert user_b.post("/membership/redeem", json={"code": revoked["code"]}).status_code == 400

        expired_plaintext = "EXPR-EXPR-EXPR-EXPR"
        db = SessionLocal()
        try:
            db.add(models.RedemptionCode(
                code_hash=hash_code(expired_plaintext),
                service_key="course_learning",
                target_plan="monthly",
                membership_duration_days=30,
                code_expires_at=main.utc_now() - timedelta(minutes=1),
                plan_code="monthly",
                max_uses=1,
                status="active",
                created_by="test",
            ))
            db.commit()
        finally:
            db.close()
        assert user_b.post("/membership/redeem/preview", json={"code": expired_plaintext}).status_code == 400
    finally:
        user_a.close()
        user_b.close()


def test_same_plan_renewal_upgrade_preserves_time_quota_and_not_revenue(client: TestClient):
    _make_admin(client, "redemption-admin-time")
    user = TestClient(client.app)
    try:
        register_and_login(user, "redemption-time-user")
        db = SessionLocal()
        try:
            account = db.query(models.User).filter(models.User.username == "redemption-time-user").one()
            membership = models.UserServiceMembership(
                user_id=account.id,
                service_key="course_learning",
                is_enabled=True,
                plan="monthly",
                status="active",
                activated_at=main.utc_now() - timedelta(days=10),
                expires_at=main.utc_now() + timedelta(days=20),
            )
            db.add(membership)
            db.commit()
        finally:
            db.close()

        before_orders = user.get("/membership/orders").json()["orders"]
        renewal = _create_code(client, target_plan="monthly", membership_duration_days=30)
        preview = user.post("/membership/redeem/preview", json={"code": renewal["code"]}).json()["preview"]
        assert preview["current_plan"] == "monthly"
        assert preview["current_expires_at"] < preview["projected_expires_at"]
        assert user.post("/membership/redeem", json={"code": renewal["code"]}).status_code == 200

        upgrade = _create_code(client, target_plan="quarterly", membership_duration_days=90)
        assert user.post("/membership/redeem", json={"code": upgrade["code"]}).status_code == 200
        catalog = user.get("/membership/catalog", params={"service_key": "course_learning"}).json()
        assert catalog["current"]["plan"] == "quarterly"
        quarterly = next(item for item in catalog["plans"] if item["plan_code"] == "quarterly")
        assert quarterly["quota"]["ai_chat_daily_limit"] == 500
        assert user.get("/membership/orders").json()["orders"] == before_orders

        downgrade = _create_code(client, target_plan="monthly")
        assert user.post("/membership/redeem/preview", json={"code": downgrade["code"]}).status_code == 400
    finally:
        user.close()
