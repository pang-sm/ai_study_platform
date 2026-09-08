from datetime import timedelta

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models
from main import utc_now


def _admin(client, username="membership-admin"):
    register_and_login(client, username)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        user.is_admin, user.admin_role = 1, "super_admin"
        db.commit()
    finally:
        db.close()


def test_admin_membership_uses_direction_records_and_runtime_entitlement(client: TestClient):
    _admin(client)
    target = register_and_login(TestClient(client.app), "membership-target")
    db = SessionLocal()
    try:
        target_user = db.query(models.User).filter_by(username=target["username"]).one()
        user_id = target_user.id
    finally:
        db.close()
    listed = client.get(f"/admin/memberships?keyword={target['username']}")
    assert listed.status_code == 200
    assert {row["service_key"] for row in listed.json()["items"]} == {"exam_11408", "course_learning", "programming"}
    updated = client.patch(f"/admin/users/{user_id}/memberships", json={"memberships": {"course_learning": {"plan": "monthly", "is_enabled": True}}})
    assert updated.status_code == 200
    assert updated.json()["memberships"]["course_learning"]["current_is_effective"] is True
    assert client.patch(f"/admin/users/{user_id}/memberships", json={"memberships": {"course": {"plan": "monthly"}}}).status_code == 400
    assert client.patch(f"/admin/users/{user_id}/memberships", json={"memberships": {"course_learning": {"plan": "not-a-plan"}}}).status_code == 400
    db = SessionLocal()
    try:
        rows = {m.service_key: m for m in db.query(models.UserServiceMembership).filter_by(user_id=user_id).all()}
        assert rows["course_learning"].plan == "monthly"
        assert "exam_11408" not in rows and "programming" not in rows
    finally:
        db.close()


def test_admin_reopens_expired_memberships_and_keeps_directions_isolated(client: TestClient):
    _admin(client, "membership-reopen-admin")
    target_client = TestClient(client.app)
    target = register_and_login(target_client, "membership-reopen-target")
    db = SessionLocal()
    try:
        target_user = db.query(models.User).filter_by(username=target["username"]).one()
        user_id = target_user.id
        db.add(models.UserServiceMembership(
            user_id=user_id, service_key="exam_11408", is_enabled=True,
            plan="monthly_sprint", status="expired", activated_at=utc_now() - timedelta(days=31),
            expires_at=utc_now() - timedelta(days=1),
        ))
        db.add(models.UserServiceMembership(
            user_id=user_id, service_key="course_learning", is_enabled=False,
            plan="free", status="disabled", expires_at=None,
        ))
        db.commit()
    finally:
        db.close()

    # expired -> same paid plan: stale status/date cannot be inherited.
    reopened = client.patch(f"/admin/users/{user_id}/memberships", json={"memberships": {
        "exam_11408": {"plan": "monthly_sprint", "is_enabled": True, "status": "expired", "expires_at": None},
    }})
    assert reopened.status_code == 200, reopened.text
    exam = reopened.json()["memberships"]["exam_11408"]
    assert exam["status"] == "active" and exam["current_is_effective"] is True
    assert exam["expires_at"]

    # The public catalog, entitlement, and quota all resolve that exact grant.
    catalog = target_client.get("/membership/catalog", params={"service_key": "exam_11408"}).json()
    entitlement = target_client.get("/membership/entitlements", params={"service_key": "exam_11408"}).json()
    quota = target_client.get("/me/quota", params={"service_key": "exam_11408"}).json()
    assert catalog["current"]["plan"] == entitlement["current_plan"] == "monthly_sprint"
    assert entitlement["features"]["learning_plan"]["allowed"] is True
    assert quota["feature_limits"]["chat"]["limit"] == 300

    # Reopen to a higher plan and independently update the other directions.
    upgraded = client.patch(f"/admin/users/{user_id}/memberships", json={"memberships": {
        "exam_11408": {"plan": "full_exam", "is_enabled": True, "status": "expired", "expires_at": None},
        "course_learning": {"plan": "monthly", "is_enabled": True},
        "programming": {"plan": "quarterly", "is_enabled": True},
    }})
    assert upgraded.status_code == 200, upgraded.text
    result = upgraded.json()["memberships"]
    assert all(item["status"] == "active" and item["current_is_effective"] for item in result.values())
    assert result["exam_11408"]["plan"] == "full_exam"
    assert result["course_learning"]["plan"] == "monthly"
    assert result["programming"]["plan"] == "quarterly"


def test_catalog_prices_match_admin_and_order_snapshots(client: TestClient):
    _admin(client, "membership-price-admin")
    user_client = TestClient(client.app)
    register_and_login(user_client, "membership-price-user")
    admin_catalog = client.get("/admin/memberships/catalog")
    assert admin_catalog.status_code == 200
    admin_services = {item["service_key"]: item["plans"] for item in admin_catalog.json()["services"]}
    expected_programming = {"monthly": 4900, "quarterly": 12900, "full": 39900}
    for service_key, admin_plans in admin_services.items():
        public = user_client.get("/membership/catalog", params={"service_key": service_key})
        assert public.status_code == 200
        public_prices = {item["plan_code"]: item["price_cents"] for item in public.json()["plans"]}
        assert public_prices == {item["plan_code"]: item["price_cents"] for item in admin_plans}
        if service_key == "programming":
            assert {key: public_prices[key] for key in expected_programming} == expected_programming
        paid_plan = next(item for item in public.json()["plans"] if item["plan_code"] != "free")
        order = user_client.post("/membership/orders", json={"service_key": service_key, "target_plan": paid_plan["plan_code"], "amount": 1}).json()["order"]
        assert order["amount"] == order["list_price"] == paid_plan["price_cents"]
