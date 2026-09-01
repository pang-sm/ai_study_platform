"""Admin system settings: registry, validation, runtime effect, audit."""
import itertools

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models
import main


_counter = itertools.count(1)


def _make_admin(client, role):
    username = f"settings-{role}-{next(_counter)}"
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


def _make_super(client):
    return _make_admin(client, "super_admin")


def _make_operator(client):
    return _make_admin(client, "operator")


def test_settings_list_only_registry_keys(client):
    _make_super(client)
    r = client.get("/admin/settings")
    assert r.status_code == 200
    keys = {i["key"] for i in r.json()["items"]}
    assert "feature_ai_chat_enabled" in keys
    assert "feature_material_upload_enabled" in keys
    assert "feature_report_share_enabled" in keys
    assert "feature_practice_center_enabled" in keys
    # dead + legacy keys must NOT be exposed
    assert "feature_code_studio_enabled" not in keys
    assert "limit_free_daily_ai_calls" not in keys
    # every item has schema
    assert all(i["type"] == "bool" and i["editable"] is True for i in r.json()["items"])


def test_settings_put_bool_writes_audit(client):
    admin = _make_super(client)
    r = client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": False}})
    assert r.status_code == 200, r.text
    # DB updated
    db = SessionLocal()
    try:
        s = db.query(models.SystemSetting).filter(models.SystemSetting.key == "feature_ai_chat_enabled").first()
        assert s.value in ("false", "False")
        assert s.updated_by == admin
        logs = db.query(models.AdminAuditLog).filter_by(target_type="settings").order_by(models.AdminAuditLog.id.desc()).first()
        assert logs is not None
        assert "feature_ai_chat_enabled" in logs.detail
    finally:
        db.close()
    # restore
    client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": True}})


def test_settings_put_unknown_key_400(client):
    _make_super(client)
    assert client.put("/admin/settings", json={"updates": {"not_a_real_key": "x"}}).status_code == 400


def test_settings_put_legacy_quota_rejected(client):
    _make_super(client)
    assert client.put("/admin/settings", json={"updates": {"limit_free_daily_ai_calls": "99"}}).status_code == 400


def test_settings_put_invalid_bool_400(client):
    _make_super(client)
    assert client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": "abc"}}).status_code == 400


def test_setting_runtime_effect(client):
    _make_super(client)
    # read current
    cur = client.get("/admin/settings").json()["items"]
    ai = next(i for i in cur if i["key"] == "feature_ai_chat_enabled")
    original = ai["value"]
    new_val = "false" if original == "true" else "true"
    assert client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": new_val}}).status_code == 200
    # runtime reader (public settings) reflects the change
    pub = client.get("/settings/public")
    assert pub.json()["feature_ai_chat_enabled"] == (new_val == "true")
    # restore
    assert client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": original}}).status_code == 200
    assert client.get("/settings/public").json()["feature_ai_chat_enabled"] == (original == "true")


def test_non_admin_rejected(client):
    tc = TestClient(main.app)
    register_and_login(tc, f"settings-normal-{next(_counter)}")
    assert tc.get("/admin/settings").status_code == 403
    assert tc.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": False}}).status_code == 403


def test_operator_can_view_and_edit_settings(client):
    op = _make_operator(client)
    # GET allowed
    assert client.get("/admin/settings").status_code == 200
    # PUT a safe setting allowed
    cur = client.get("/admin/settings").json()["items"]
    ai = next(i for i in cur if i["key"] == "feature_ai_chat_enabled")
    original = ai["value"]
    new_val = "false" if original == "true" else "true"
    assert client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": new_val}}).status_code == 200
    # runtime effect
    assert client.get("/settings/public").json()["feature_ai_chat_enabled"] == (new_val == "true")
    # audit log records operator
    db = SessionLocal()
    try:
        logs = db.query(models.AdminAuditLog).filter_by(target_type="settings").order_by(models.AdminAuditLog.id.desc()).first()
        assert logs is not None and logs.admin_username == op
    finally:
        db.close()
    # restore
    assert client.put("/admin/settings", json={"updates": {"feature_ai_chat_enabled": original}}).status_code == 200


def test_operator_still_cannot_use_super_only(client):
    _make_operator(client)
    # super-only capabilities remain forbidden for operator
    assert client.get("/admin/admins").status_code == 403
    assert client.post("/admin/admins", json={"username": "x", "password": "secret123", "confirm_password": "secret123"}).status_code == 403
    assert client.put("/admin/settings", json={"updates": {"limit_free_daily_ai_calls": "99"}}).status_code == 400  # still not editable
