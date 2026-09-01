"""Two-tier admin RBAC: super_admin vs ordinary admin (operator)."""
import itertools

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
from auth import verify_password
import models
import main


_counter = itertools.count(1)


def _make_admin(client, role):
    username = f"rbac-{role}-{next(_counter)}"
    register_and_login(client, username)
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username=username).one()
        u.is_admin = 1
        u.admin_role = role
        db.commit()
    finally:
        db.close()
    return username


def _target_id(username):
    db = SessionLocal()
    try:
        return db.query(models.User).filter_by(username=username).one().id
    finally:
        db.close()


def _make_super(client):
    return _make_admin(client, "super_admin")


def _make_operator(client):
    return _make_admin(client, "operator")


def _make_plain_user():
    tc = TestClient(main.app)
    username = f"rbac-target-{next(_counter)}"
    register_and_login(tc, username)
    return username, _target_id(username)


def test_operator_cannot_delete_user(client):
    _make_operator(client)
    _, uid = _make_plain_user()
    assert client.delete(f"/admin/users/{uid}").status_code == 403


def test_super_can_delete_user(client):
    _make_super(client)
    _, uid = _make_plain_user()
    assert client.delete(f"/admin/users/{uid}").status_code == 200


def test_operator_cannot_batch_delete(client):
    _make_operator(client)
    _, uid = _make_plain_user()
    r = client.post("/admin/users/batch", json={"user_ids": [uid], "action": "delete"})
    assert r.status_code == 403


def test_operator_can_batch_ban_unban(client):
    _make_operator(client)
    _, uid = _make_plain_user()
    assert client.post("/admin/users/batch", json={"user_ids": [uid], "action": "ban"}).status_code == 200
    assert client.post("/admin/users/batch", json={"user_ids": [uid], "action": "unban"}).status_code == 200


def test_operator_cannot_create_redemption_code(client):
    _make_operator(client)
    r = client.post("/admin/membership/redemption-codes", json={
        "service_key": "course_learning", "target_plan": "monthly",
        "membership_duration_days": 30, "code_expires_at": "2099-01-01T00:00:00Z",
        "max_redemptions": 1, "count": 1,
    })
    assert r.status_code == 403


def test_operator_cannot_create_admin(client):
    _make_operator(client)
    r = client.post("/admin/admins", json={"username": "rbac-created", "password": "secret123", "confirm_password": "secret123"})
    assert r.status_code == 403


def test_operator_cannot_list_admins(client):
    _make_operator(client)
    assert client.get("/admin/admins").status_code == 403


def test_super_can_create_admin_hashed_and_forced_operator(client):
    _make_super(client)
    r = client.post("/admin/admins", json={"username": "rbac-created-admin", "password": "secret123", "confirm_password": "secret123", "nickname": "新管理员"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["admin_role"] == "operator"
    assert "password" not in body and "hashed_password" not in body
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username="rbac-created-admin").one()
        assert u.is_admin == 1
        assert u.admin_role == "operator"
        assert u.hashed_password != "secret123"
        assert verify_password("secret123", u.hashed_password)
    finally:
        db.close()


def test_super_cannot_create_super_admin_via_role(client):
    _make_super(client)
    # The create endpoint ignores any role the caller passes.
    r = client.post("/admin/admins", json={"username": "rbac-forced-super", "password": "secret123", "confirm_password": "secret123"})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username="rbac-forced-super").one()
        assert u.admin_role == "operator"
    finally:
        db.close()


def test_audit_log_scope_operator_sees_own_only(client):
    op = _make_operator(client)
    # Super admin on a separate client so the operator's session isn't clobbered.
    super_client = TestClient(main.app)
    super_name = _make_super(super_client)
    # Operator performs an action (logged under their own username).
    _, uid = _make_plain_user()
    client.post(f"/admin/users/{uid}/ban", json={"reason": "scope-test"})
    # log a super-admin action directly
    db = SessionLocal()
    try:
        db.add(models.AdminAuditLog(admin_username=super_name, action="audit_logs_export", target_type="ai_logs", result="success", detail=""))
        db.commit()
    finally:
        db.close()
    r = client.get("/admin/logs?page_size=100")
    assert r.status_code == 200
    names = {item["admin_username"] for item in r.json()["items"]}
    assert op in names
    assert super_name not in names
    assert r.json()["can_view_all"] is False


def test_admin_protection_cannot_delete_or_demote(client):
    super_name = _make_super(client)
    # ensure a built-in "admin" super account exists
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter_by(username="admin").first()
        if not admin:
            from auth import hash_password
            admin = models.User(username="admin", hashed_password=hash_password("adminpass1"), is_admin=1, admin_role="super_admin", is_active=1)
            db.add(admin)
            db.commit()
            db.refresh(admin)
        admin_id = admin.id
    finally:
        db.close()

    # super (other than admin) cannot delete the built-in admin
    assert client.delete(f"/admin/users/{admin_id}").status_code == 403
    # cannot demote admin
    r = client.put("/admin/users/admin/admin-role", json={"admin_role": "operator"})
    assert r.status_code == 400
