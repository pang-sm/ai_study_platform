from datetime import timedelta

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import main
import models


def test_membership_order_uses_server_catalog_and_is_idempotent(client: TestClient):
    register_and_login(client, "membership-owner")

    catalog = client.get("/membership/catalog", params={"service_key": "course_learning"})
    assert catalog.status_code == 200, catalog.text
    monthly = next(item for item in catalog.json()["plans"] if item["plan_code"] == "monthly")
    assert monthly["price_cents"] == 2900
    assert catalog.json()["payment_provider"] == "mock"

    first = client.post(
        "/membership/orders",
        json={"service_key": "course", "target_plan": "monthly", "amount": 1},
    )
    assert first.status_code == 200, first.text
    first_order = first.json()["order"]
    assert first_order["service_key"] == "course_learning"
    assert first_order["amount"] == 2900
    assert first_order["status"] == "pending"

    repeated = client.post(
        "/membership/orders",
        json={"service_key": "course_learning", "target_plan": "monthly"},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["order"]["id"] == first_order["id"]
    assert repeated.json()["reused"] is True

    paid = client.post(f"/membership/orders/{first_order['id']}/pay")
    assert paid.status_code == 200, paid.text
    assert paid.json()["order"]["status"] == "paid"
    assert paid.json()["order"]["membership_expires_at"]

    duplicate_pay = client.post(f"/membership/orders/{first_order['id']}/pay")
    assert duplicate_pay.status_code == 200, duplicate_pay.text
    assert duplicate_pay.json()["idempotent"] is True

    current = client.get("/membership/catalog", params={"service_key": "course_learning"})
    assert current.json()["current"]["plan"] == "monthly"

    downgrade = client.post(
        "/membership/orders",
        json={"service_key": "course_learning", "target_plan": "free"},
    )
    assert downgrade.status_code == 400

    same_or_lower = client.post(
        "/membership/orders",
        json={"service_key": "course_learning", "target_plan": "monthly"},
    )
    assert same_or_lower.status_code == 409


def test_membership_orders_are_isolated_between_users(client: TestClient):
    register_and_login(client, "membership-a")
    created = client.post(
        "/membership/orders",
        json={"service_key": "programming", "target_plan": "monthly"},
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["order"]["id"]

    other = TestClient(client.app)
    try:
        register_and_login(other, "membership-b")
        assert other.get("/membership/orders").json()["orders"] == []
        assert other.get(f"/membership/orders/{order_id}").status_code == 404
        assert other.post(f"/membership/orders/{order_id}/pay").status_code == 404
        assert other.post(f"/membership/orders/{order_id}/cancel").status_code == 404
    finally:
        other.close()


def test_membership_expiry_falls_back_to_free_and_reminder_is_scoped(client: TestClient):
    register_and_login(client, "membership-expiry")
    created = client.post(
        "/membership/orders",
        json={"service_key": "exam_11408", "target_plan": "monthly_sprint"},
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["order"]["id"]
    paid = client.post(f"/membership/orders/{order_id}/pay")
    assert paid.status_code == 200, paid.text

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "membership-expiry").one()
        membership = db.query(models.UserServiceMembership).filter(
            models.UserServiceMembership.user_id == user.id,
            models.UserServiceMembership.service_key == "exam_11408",
        ).one()
        membership.expires_at = main.utc_now() + timedelta(days=1)
        db.commit()
    finally:
        db.close()

    reminders = client.get("/membership/reminders")
    assert reminders.status_code == 200, reminders.text
    assert reminders.json()["reminders"][0]["service_key"] == "exam_11408"

    db = SessionLocal()
    try:
        membership = db.query(models.UserServiceMembership).filter(
            models.UserServiceMembership.service_key == "exam_11408",
        ).join(models.User).filter(models.User.username == "membership-expiry").one()
        membership.expires_at = main.utc_now() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    catalog = client.get("/membership/catalog", params={"service_key": "exam_11408"})
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["current"]["plan"] == "free"
