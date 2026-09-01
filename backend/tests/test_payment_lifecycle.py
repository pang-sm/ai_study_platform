from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor
from conftest import register_and_login
from database import SessionLocal
import main
import models
from payments import get_payment_provider
from payments.service import apply_verified_payment


def _order(client, service="course_learning", plan="monthly"):
    response = client.post("/membership/orders", json={"service_key": service, "target_plan": plan, "amount": 1})
    assert response.status_code == 200, response.text
    return response.json()["order"]


def test_server_price_snapshot_and_local_event_ledger(client):
    register_and_login(client, "payment-snapshot")
    order = _order(client)
    assert order["amount"] == 2900  # ignored client amount
    assert order["list_price"] == 2900
    assert order["pricing_version"] == "market_trial_candidate_v1"
    paid = client.post(f"/membership/orders/{order['id']}/pay")
    assert paid.status_code == 200
    duplicate = client.post(f"/membership/orders/{order['id']}/pay")
    assert duplicate.json()["idempotent"] is True
    db = SessionLocal()
    try:
        assert db.query(models.PaymentEvent).filter_by(order_id=order["id"]).count() == 1
        assert db.query(models.MembershipGrant).filter_by(order_id=order["id"]).count() == 1
        assert db.query(models.RevenueLedgerEntry).filter_by(order_id=order["id"], entry_type="PAYMENT").count() == 1
    finally:
        db.close()


def test_mock_payment_is_refused_in_production(client, monkeypatch):
    register_and_login(client, "payment-production-deny")
    order = _order(client)
    monkeypatch.setattr(main, "is_mock_payment_allowed", lambda: False)
    assert client.post(f"/membership/orders/{order['id']}/pay").status_code == 403


def test_concurrent_duplicate_event_creates_one_grant_and_revenue_entry(client):
    register_and_login(client, "payment-concurrent")
    order = _order(client)
    event = get_payment_provider().verify_callback({"order_no": order["order_no"], "amount": order["amount"], "currency": "CNY"})

    def deliver():
        db = SessionLocal()
        try:
            apply_verified_payment(db, event)
            db.commit()
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: deliver(), range(2)))
    db = SessionLocal()
    try:
        assert db.query(models.PaymentEvent).filter_by(order_id=order["id"]).count() == 1
        assert db.query(models.MembershipGrant).filter_by(order_id=order["id"]).count() == 1
        assert db.query(models.RevenueLedgerEntry).filter_by(order_id=order["id"], entry_type="PAYMENT").count() == 1
    finally:
        db.close()


def test_service_isolation_renewal_and_refund_rebuild(client):
    register_and_login(client, "payment-refund")
    course_a = _order(client, "course_learning", "monthly")
    assert client.post(f"/membership/orders/{course_a['id']}/pay").status_code == 200
    course_b = _order(client, "course_learning", "monthly")
    assert client.post(f"/membership/orders/{course_b['id']}/pay").status_code == 200
    programming = _order(client, "programming", "monthly")
    assert client.post(f"/membership/orders/{programming['id']}/pay").status_code == 200
    refunded = client.post(f"/membership/orders/{course_a['id']}/refund", json={"reason": "local test"})
    assert refunded.status_code == 200, refunded.text
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(username="payment-refund").one()
        course = db.query(models.UserServiceMembership).filter_by(user_id=user.id, service_key="course_learning").one()
        code = db.query(models.UserServiceMembership).filter_by(user_id=user.id, service_key="programming").one()
        assert course.is_enabled is True  # later renewal B survives refund A
        assert code.is_enabled is True
        assert db.query(models.RevenueLedgerEntry).filter_by(order_id=course_a["id"], entry_type="REFUND").count() == 1
    finally:
        db.close()


def test_order_ownership_blocks_other_user_refund(client):
    register_and_login(client, "payment-owner-a")
    order = _order(client)
    other = TestClient(client.app)
    try:
        register_and_login(other, "payment-owner-b")
        assert other.post(f"/membership/orders/{order['id']}/refund", json={}).status_code == 404
    finally:
        other.close()
