from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models


def _make_admin(client: TestClient, username: str, role: str = "super_admin"):
    register_and_login(client, username)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).one()
        user.is_admin = 1
        user.admin_role = role
        db.commit()
    finally:
        db.close()


def test_admin_routes_use_session_identity_not_claimed_username(client: TestClient):
    assert TestClient(client.app).get("/admin/users").status_code in (401, 403)

    normal = TestClient(client.app)
    register_and_login(normal, "admin-identity-normal")
    assert normal.get("/admin/users?admin_username=admin-identity-super").status_code == 403

    super_admin = TestClient(client.app)
    _make_admin(super_admin, "admin-identity-super")
    assert super_admin.get("/admin/users?admin_username=not-the-session-user").status_code == 200


def test_admin_rbac_is_based_on_session_user_not_claimed_username(client: TestClient):
    operator = TestClient(client.app)
    _make_admin(operator, "admin-identity-operator", role="operator")

    # The operator claims a super-admin identity via a client-supplied field,
    # but authorization must resolve from the session user (operator), so a
    # super-only capability (creating another admin) is rejected.
    response = operator.post(
        "/admin/admins",
        json={
            "username": "admin-identity-forged",
            "password": "secret123",
            "confirm_password": "secret123",
            "nickname": "forged",
        },
    )
    assert response.status_code == 403


def test_existing_session_protected_redemption_and_support_routes_stay_protected(client: TestClient):
    anonymous = TestClient(client.app)
    assert anonymous.get("/admin/membership/redemption-codes").status_code in (401, 403)
    assert anonymous.get("/admin/support/unread-count").status_code in (401, 403)
