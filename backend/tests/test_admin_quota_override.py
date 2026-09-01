"""Admin quota override: unified resolver, per-direction isolation, enforcement sync."""
import itertools

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models
import main


_admin_counter = itertools.count(1)


def _make_admin(client):
    username = f"qo-admin-{next(_admin_counter)}"
    register_and_login(client, username)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        user.is_admin, user.admin_role = 1, "super_admin"
        db.commit()
    finally:
        db.close()


def _new_target(username):
    register_and_login(TestClient(main.app), username)
    db = SessionLocal()
    try:
        return db.query(models.User).filter_by(username=username).one().id
    finally:
        db.close()


def _quota(client, user_id, service_key, quota_key):
    detail = client.get(f"/admin/quota/{user_id}")
    assert detail.status_code == 200, detail.text
    svc = next(s for s in detail.json()["services"] if s["service_key"] == service_key)
    return next(q for q in svc["quotas"] if q["quota_key"] == quota_key)


def _set_override(client, user_id, service_key, quota_key, limit):
    return client.put(
        f"/admin/quota/{user_id}/override",
        json={"service_key": service_key, "quota_key": quota_key, "limit": limit},
    )


def test_free_user_three_direction_defaults(client):
    _make_admin(client)
    uid = _new_target("qo-defaults")
    d = client.get(f"/admin/quota/{uid}").json()
    by_service = {s["service_key"]: {q["quota_key"]: q for q in s["quotas"]} for s in d["services"]}
    assert set(by_service) == {"exam_11408", "course_learning", "programming"}

    exam = by_service["exam_11408"]
    assert exam["ai_chat_daily_limit"]["effective_limit"] == 50
    assert exam["ai_question_daily_limit"]["effective_limit"] == 5
    assert exam["single_file_limit_mb"]["effective_limit"] == 20
    assert exam["material_upload_limit_mb"]["effective_limit"] == 100

    course = by_service["course_learning"]
    assert course["ai_chat_daily_limit"]["effective_limit"] == 5
    assert course["ai_question_daily_limit"]["effective_limit"] == 10
    assert course["single_file_limit_mb"]["effective_limit"] == 20
    assert course["material_upload_limit_mb"]["effective_limit"] == 100

    prog = by_service["programming"]
    assert prog["ai_chat_daily_limit"]["effective_limit"] == 5
    assert prog["ai_question_daily_limit"]["effective_limit"] == 3
    assert prog["single_file_limit_mb"]["effective_limit"] == 20
    assert prog["material_upload_limit_mb"]["effective_limit"] == 0


def test_override_set_persist_resolver_enforcement(client):
    _make_admin(client)
    uid = _new_target("qo-override")
    r = _set_override(client, uid, "course_learning", "ai_question_daily_limit", 50)
    assert r.status_code == 200, r.text
    assert r.json()["default_limit"] == 10
    assert r.json()["override_limit"] == 50
    assert r.json()["effective_limit"] == 50

    # B — DB correct
    db = SessionLocal()
    try:
        row = db.query(models.UserQuotaOverride).filter_by(
            user_id=uid, service_key="course_learning", quota_key="ai_question_daily_limit"
        ).one()
        assert row.override_limit == 50
        assert row.enabled is True
    finally:
        db.close()

    # C — persists after re-fetch
    q = _quota(client, uid, "course_learning", "ai_question_daily_limit")
    assert q["has_override"] is True
    assert q["override_limit"] == 50
    assert q["effective_limit"] == 50

    # D + E — resolver and runtime enforcement read the override
    db = SessionLocal()
    try:
        resolved = main.resolve_effective_quota(db, uid, "course_learning", "ai_question_daily_limit")
        assert resolved["effective_limit"] == 50
        user = db.query(models.User).filter_by(id=uid).one()
        enforced = main.check_usage_limit(user.username, "question_generate", db, "course_learning")
        assert enforced["limit"] == 50
    finally:
        db.close()


def test_override_delete_restores_default(client):
    _make_admin(client)
    uid = _new_target("qo-delete")
    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", 50).status_code == 200

    d = client.delete(f"/admin/quota/{uid}/override?service_key=course_learning&quota_key=ai_question_daily_limit")
    assert d.status_code == 200, d.text
    assert d.json()["has_override"] is False
    assert d.json()["effective_limit"] == 10

    db = SessionLocal()
    try:
        assert db.query(models.UserQuotaOverride).filter_by(
            user_id=uid, service_key="course_learning", quota_key="ai_question_daily_limit"
        ).count() == 0
    finally:
        db.close()

    assert _quota(client, uid, "course_learning", "ai_question_daily_limit")["effective_limit"] == 10


def test_override_direction_isolation(client):
    _make_admin(client)
    uid = _new_target("qo-direction")
    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", 50).status_code == 200

    assert _quota(client, uid, "course_learning", "ai_question_daily_limit")["effective_limit"] == 50
    assert _quota(client, uid, "exam_11408", "ai_question_daily_limit")["effective_limit"] == 5
    assert _quota(client, uid, "programming", "ai_question_daily_limit")["effective_limit"] == 3


def test_override_quota_isolation(client):
    _make_admin(client)
    uid = _new_target("qo-quota")
    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", 50).status_code == 200

    # same direction, different quota key unchanged
    assert _quota(client, uid, "course_learning", "ai_chat_daily_limit")["effective_limit"] == 5


def test_plan_change_updates_default_keeps_override(client):
    _make_admin(client)
    uid = _new_target("qo-plan")
    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", 50).status_code == 200

    # upgrade course_learning to monthly (catalog default question_generate = 30)
    up = client.patch(f"/admin/users/{uid}/memberships", json={
        "memberships": {"course_learning": {"plan": "monthly", "is_enabled": True}},
    })
    assert up.status_code == 200, up.text

    q = _quota(client, uid, "course_learning", "ai_question_daily_limit")
    assert q["default_limit"] == 30
    assert q["override_limit"] == 50
    assert q["effective_limit"] == 50  # override wins over upgraded default

    # delete → effective returns to the NEW plan default (30)
    assert client.delete(f"/admin/quota/{uid}/override?service_key=course_learning&quota_key=ai_question_daily_limit").status_code == 200
    q2 = _quota(client, uid, "course_learning", "ai_question_daily_limit")
    assert q2["default_limit"] == 30
    assert q2["effective_limit"] == 30


def test_material_override_resolves(client):
    _make_admin(client)
    uid = _new_target("qo-material")
    assert _set_override(client, uid, "course_learning", "material_upload_limit_mb", 999).status_code == 200
    assert _set_override(client, uid, "course_learning", "single_file_limit_mb", 88).status_code == 200

    db = SessionLocal()
    try:
        limits = main.resolve_effective_material_limits(db, uid, "course_learning")
        assert limits["material_storage_limit_mb"] == 999
        assert limits["single_file_limit_mb"] == 88
    finally:
        db.close()


def test_quota_used_reads_real_usage(client):
    _make_admin(client)
    uid = _new_target("qo-used")
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(id=uid).one()
        db.add(models.AiUsageLog(
            username=user.username, feature="question_generate", service_key="course_learning",
            status="success", action_id="qo-used-action-1",
        ))
        db.commit()
    finally:
        db.close()

    q = _quota(client, uid, "course_learning", "ai_question_daily_limit")
    assert q["used"] == 1
    assert q["remaining"] == 9  # default 10 - 1


def test_override_invalid_inputs_4xx(client):
    _make_admin(client)
    uid = _new_target("qo-invalid")

    assert _set_override(client, uid, "bad-service", "ai_question_daily_limit", 10).status_code == 400
    assert _set_override(client, uid, "course_learning", "bad-quota", 10).status_code == 400
    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", -1).status_code == 400
    wrong_type = _set_override(client, uid, "course_learning", "ai_question_daily_limit", "abc")
    assert 400 <= wrong_type.status_code < 500


def test_non_admin_rejected(client):
    caller = TestClient(main.app)
    register_and_login(caller, "qo-normal-user")

    assert caller.get("/admin/quota").status_code == 403
    assert caller.get("/admin/quota/1").status_code == 403
    assert caller.put("/admin/quota/1/override", json={
        "service_key": "course_learning", "quota_key": "ai_question_daily_limit", "limit": 10,
    }).status_code == 403


def test_override_writes_audit_log(client):
    _make_admin(client)
    uid = _new_target("qo-audit")

    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", 50).status_code == 200
    assert _set_override(client, uid, "course_learning", "ai_question_daily_limit", 60).status_code == 200
    assert client.delete(f"/admin/quota/{uid}/override?service_key=course_learning&quota_key=ai_question_daily_limit").status_code == 200

    db = SessionLocal()
    try:
        actions = [l.action for l in db.query(models.AdminAuditLog).filter_by(target_id=str(uid)).all()]
        assert "quota_override_create" in actions
        assert "quota_override_update" in actions
        assert "quota_override_delete" in actions
    finally:
        db.close()


def test_free_quota_regression_locks_catalog_values(client):
    """Lock the three-direction Free core AI quota so catalog refactors can't
    re-introduce the cross-direction copy (course_learning must be 5/10, not 50/5)."""
    _make_admin(client)
    tc = TestClient(main.app)
    register_and_login(tc, "qo-regression-user")
    db = SessionLocal()
    try:
        uid = db.query(models.User).filter_by(username="qo-regression-user").one().id
        user = db.query(models.User).filter_by(id=uid).one()
    finally:
        db.close()

    expected = {
        "exam_11408": (50, 5),
        "course_learning": (5, 10),
        "programming": (5, 3),
    }

    for sk, (chat, question) in expected.items():
        # 1) unified resolver default
        db = SessionLocal()
        try:
            assert main.resolve_effective_quota(db, uid, sk, "ai_chat_daily_limit")["default_limit"] == chat
            assert main.resolve_effective_quota(db, uid, sk, "ai_question_daily_limit")["default_limit"] == question
        finally:
            db.close()

        # 2) /me/quota (service-aware user-facing numbers)
        r = tc.get(f"/me/quota?service_key={sk}")
        assert r.status_code == 200, r.text
        fl = r.json()["feature_limits"]
        assert fl["chat"]["limit"] == chat, (sk, fl["chat"])
        assert fl["question_generate"]["limit"] == question, (sk, fl["question_generate"])

        # 3) /admin quota detail (admin-facing numbers)
        admin_q = _quota(client, uid, sk, "ai_chat_daily_limit")
        assert admin_q["effective_limit"] == chat, (sk, "chat")
        admin_qq = _quota(client, uid, sk, "ai_question_daily_limit")
        assert admin_qq["effective_limit"] == question, (sk, "question")

    # 4) runtime enforcement reads the same numbers
    db = SessionLocal()
    try:
        assert main.check_usage_limit(user.username, "chat", db, "course_learning")["limit"] == 5
        assert main.check_usage_limit(user.username, "question_generate", db, "course_learning")["limit"] == 10
        assert main.check_exam_408_usage_limit(user, "chat", db)["limit"] == 50
        assert main.check_exam_408_usage_limit(user, "question_generate", db)["limit"] == 5
        assert main.check_programming_usage_limit(user, "code_analyze", db)["limit"] == 5
        assert main.check_programming_usage_limit(user, "challenge_generate", db)["limit"] == 3
    finally:
        db.close()


def test_package_quota_dicts_derive_from_catalog():
    """The three package-quota dicts must mirror SERVICE_PLAN_CATALOG, never drift."""
    from membership import SERVICE_PLAN_CATALOG
    for plan_code, definition in SERVICE_PLAN_CATALOG["course_learning"].items():
        q = definition.get("quota") or {}
        assert main.COURSE_PACKAGE_QUOTA[plan_code]["ai_chat_daily_limit"] == q["ai_chat_daily_limit"]
        assert main.COURSE_PACKAGE_QUOTA[plan_code]["ai_question_daily_limit"] == q["ai_question_daily_limit"]
    for plan_code, definition in SERVICE_PLAN_CATALOG["exam_11408"].items():
        q = definition.get("quota") or {}
        assert main.EXAM_PACKAGE_QUOTA[plan_code]["ai_chat_daily_limit"] == q["ai_chat_daily_limit"]
        assert main.EXAM_PACKAGE_QUOTA[plan_code]["ai_question_daily_limit"] == q["ai_question_daily_limit"]
    for plan_code, definition in SERVICE_PLAN_CATALOG["programming"].items():
        q = definition.get("quota") or {}
        assert main.PROGRAMMING_PACKAGE_QUOTA[plan_code]["ai_chat_daily_limit"] == q["ai_chat_daily_limit"]
        assert main.PROGRAMMING_PACKAGE_QUOTA[plan_code]["ai_question_daily_limit"] == q["ai_question_daily_limit"]
