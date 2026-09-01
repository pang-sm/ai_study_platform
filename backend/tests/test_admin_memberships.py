from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models


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
