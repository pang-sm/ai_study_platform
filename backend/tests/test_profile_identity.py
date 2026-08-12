from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

from conftest import register_and_login
import models


def _png_bytes():
    image = Image.new("RGB", (2, 2), color="purple")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_profile_identity_fields_are_current_user_owned_and_persist(client):
    register_and_login(client, "profile-owner")
    response = client.put("/me/profile", json={
        "nickname": "资料测试",
        "major": "信息安全",
        "grade": "大三",
        "semester": "上学期",
    })
    assert response.status_code == 200, response.text
    profile = response.json()["profile"]
    assert {key: profile[key] for key in ("nickname", "major", "grade", "semester")} == {
        "nickname": "资料测试", "major": "信息安全", "grade": "大三", "semester": "上学期",
    }
    assert client.get("/me/profile").json()["profile"]["semester"] == "上学期"


def test_profile_rejects_sensitive_fields_and_cross_user_update(client):
    register_and_login(client, "profile-owner-a")
    assert client.put("/me/profile", json={"plan": "admin"}).status_code == 422
    other = TestClient(client.app)
    try:
        register_and_login(other, "profile-owner-b")
        denied = other.put("/me/profile?username=profile-owner-a", json={"major": "越权"})
        assert denied.status_code == 403
    finally:
        other.close()


def test_avatar_upload_validates_content_and_me_returns_canonical_url(client):
    register_and_login(client, "avatar-owner")
    uploaded = client.post(
        "/me/avatar",
        files={"file": ("avatar.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    avatar_url = uploaded.json()["profile"]["avatar_url"]
    assert avatar_url.startswith("/api/me/avatar/")
    assert "/api/api/" not in avatar_url
    # The application is mounted below Nginx's `/api` prefix in production;
    # TestClient calls the FastAPI application directly.
    assert client.get(avatar_url.removeprefix("/api")).status_code == 200

    rejected_type = client.post(
        "/me/avatar",
        files={"file": ("avatar.svg", b"<svg/>", "image/svg+xml")},
    )
    assert rejected_type.status_code == 400
    rejected_content = client.post(
        "/me/avatar",
        files={"file": ("avatar.png", b"not-a-png", "image/png")},
    )
    assert rejected_content.status_code == 400
    oversized = client.post(
        "/me/avatar",
        files={"file": ("avatar.png", b"x" * (3 * 1024 * 1024 + 1), "image/png")},
    )
    assert oversized.status_code == 400


def test_me_omits_stale_uploaded_avatar_link(client, db_session):
    user = register_and_login(client, "stale-avatar-owner")
    record = db_session.query(models.User).filter(models.User.username == user["username"]).one()
    record.avatar = "missing-avatar.png"
    db_session.commit()
    profile = client.post("/me", json={}).json()["user"]
    assert profile["avatar"] == "missing-avatar.png"
    assert profile["avatar_url"] is None
