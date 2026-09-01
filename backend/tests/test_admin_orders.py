"""Admin order management: read real MembershipOrder, cancel/refund state machine."""
import itertools

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models
import main


_counter = itertools.count(1)


def _make_super(client):
    username = f"order-admin-{next(_counter)}"
    register_and_login(client, username)
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username=username).one()
        u.is_admin = 1
        u.admin_role = "super_admin"
        db.commit()
    finally:
        db.close()
    return username


def _buy_order():
    """Register a user and buy a course_learning monthly order (paid). Returns (client, order_id)."""
    tc = TestClient(main.app)
    username = f"order-buyer-{next(_counter)}"
    register_and_login(tc, username)
    r = tc.post("/membership/orders", json={"service_key": "course_learning", "target_plan": "monthly"})
    assert r.status_code == 200, r.text
    order_id = r.json()["order"]["id"]
    pay = tc.post(f"/membership/orders/{order_id}/pay")
    assert pay.status_code == 200, pay.text
    return tc, order_id, username


def test_admin_orders_list_and_detail(client):
    _make_super(client)
    tc, order_id, username = _buy_order()

    listed = client.get("/admin/orders")
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] >= 1
    assert "total_pages" in listed.json()

    detail = client.get(f"/admin/orders/{order_id}")
    assert detail.status_code == 200, detail.text
    o = detail.json()["order"]
    assert o["id"] == order_id
    assert o["service_key"] == "course_learning"
    assert o["target_plan"] == "monthly"
    assert o["status"] == "paid"
    assert o["is_mock"] is True
    assert o["payment_provider"] == "mock"
    assert o["grant"]["granted"] is True  # paid order must have a MembershipGrant


def test_admin_order_refund_writes_refund_and_audit(client):
    _make_super(client)
    _, order_id, _ = _buy_order()

    r = client.post(f"/admin/orders/{order_id}/refund", json={"reason": "测试退款"})
    assert r.status_code == 200, r.text
    assert r.json()["refund"]["status"] == "refunded"

    db = SessionLocal()
    try:
        refund = db.query(models.Refund).filter(models.Refund.order_id == order_id).first()
        assert refund is not None
        assert refund.status == "refunded"
        order = db.query(models.MembershipOrder).filter(models.MembershipOrder.id == order_id).one()
        assert order.refund_status == "refunded"
        logs = db.query(models.AdminAuditLog).filter_by(target_type="order", target_id=str(order_id), action="admin_order_refund").count()
        assert logs >= 1
    finally:
        db.close()


def test_admin_order_cancel_pending(client):
    _make_super(client)
    tc = TestClient(main.app)
    username = f"order-cancel-{next(_counter)}"
    register_and_login(tc, username)
    r = tc.post("/membership/orders", json={"service_key": "programming", "target_plan": "monthly"})
    order_id = r.json()["order"]["id"]
    assert r.json()["order"]["status"] == "pending"

    c = client.post(f"/admin/orders/{order_id}/cancel")
    assert c.status_code == 200, c.text
    assert c.json()["order"]["status"] == "cancelled"


def test_admin_order_illegal_transitions(client):
    _make_super(client)
    tc, order_id, _ = _buy_order()  # paid order
    # cancel paid -> 409
    assert client.post(f"/admin/orders/{order_id}/cancel").status_code == 409
    # refund again -> idempotent 200 (not an illegal transition), but first refund then cancel refunded -> 409 handled separately
    # refund a cancelled/pending order -> 409
    tc2 = TestClient(main.app)
    register_and_login(tc2, f"order-illegal-{next(_counter)}")
    r2 = tc2.post("/membership/orders", json={"service_key": "course_learning", "target_plan": "monthly"})
    oid2 = r2.json()["order"]["id"]
    assert client.post(f"/admin/orders/{oid2}/refund", json={"reason": ""}).status_code == 409  # pending cannot refund


def test_non_admin_rejected(client):
    tc = TestClient(main.app)
    register_and_login(tc, f"order-normal-{next(_counter)}")
    assert tc.get("/admin/orders").status_code == 403
    assert tc.get("/admin/orders/1").status_code == 403
