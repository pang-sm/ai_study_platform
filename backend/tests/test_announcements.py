from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models


def _make_admin(client: TestClient, username: str = "announcement-admin"):
    register_and_login(client, username)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).one()
        user.is_admin = 1
        user.admin_role = "super_admin"
        db.commit()
    finally:
        db.close()


def test_announcement_rejects_blank_and_single_character_content(client: TestClient):
    _make_admin(client)
    for title, content in (("", "valid content"), ("1", "1"), ("valid title", " ")):
        response = client.post(
            "/admin/announcements",
            json={"admin_username": "announcement-admin", "title": title, "content": content},
        )
        assert response.status_code == 400, response.text


def test_announcement_publish_and_withdraw_controls_public_feed(client: TestClient):
    _make_admin(client, "announcement-admin-publish")
    created = client.post(
        "/admin/announcements",
        json={
            "admin_username": "announcement-admin-publish",
            "title": "系统维护通知",
            "content": "今晚 23:00 进行例行维护。",
            "status": "published",
        },
    )
    assert created.status_code == 200, created.text
    announcement_id = created.json()["announcement"]["id"]

    public_client = TestClient(client.app)
    active = public_client.get("/announcements/active")
    assert active.status_code == 200
    assert any(item["id"] == announcement_id for item in active.json()["items"])

    withdrawn = client.post(
        f"/admin/announcements/{announcement_id}/withdraw",
        json={"admin_username": "announcement-admin-publish"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    active_after = public_client.get("/announcements/active")
    assert active_after.status_code == 200
    assert all(item["id"] != announcement_id for item in active_after.json()["items"])
