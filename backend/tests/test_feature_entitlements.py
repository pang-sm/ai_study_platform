from datetime import timedelta

import pytest

from conftest import register_and_login
import models
from main import utc_now
from membership import get_feature_entitlement


def _set_membership(db_session, user_id, service_key, plan, expires_at=None):
    record = db_session.query(models.UserServiceMembership).filter(
        models.UserServiceMembership.user_id == user_id,
        models.UserServiceMembership.service_key == service_key,
    ).first()
    if not record:
        record = models.UserServiceMembership(user_id=user_id, service_key=service_key)
        db_session.add(record)
    record.is_enabled = True
    record.status = "active"
    record.plan = plan
    record.expires_at = expires_at
    db_session.commit()


def test_feature_entitlement_uses_catalog_and_keeps_services_isolated(client, db_session):
    profile = register_and_login(client, "feature-entitlement-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()

    # learning_report 免费（练习复盘已合并进学习报告，学习报告免费）。
    free = get_feature_entitlement(user, db_session, "course_learning", "learning_report")
    assert free["allowed"] is True
    assert free["feature"] == "learning_report"
    assert free["service_key"] == "course_learning"
    assert free["current_plan"] == "free"
    assert free["required_plan"] == "free"

    _set_membership(db_session, user.id, "course_learning", "monthly")
    course_paid = get_feature_entitlement(user, db_session, "course_learning", "learning_report")
    assert course_paid["allowed"] is True
    assert course_paid["current_plan"] == "monthly"

    exam = get_feature_entitlement(user, db_session, "exam_11408", "learning_plan")
    assert exam["allowed"] is False
    assert exam["current_plan"] == "free"
    assert exam["required_plan"] == "monthly_sprint"


def test_feature_entitlement_treats_expired_membership_as_free(client, db_session):
    profile = register_and_login(client, "expired-feature-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    _set_membership(db_session, user.id, "course_learning", "full", utc_now() - timedelta(minutes=1))

    entitlement = get_feature_entitlement(user, db_session, "course_learning", "learning_plan")
    assert entitlement["allowed"] is False
    assert entitlement["current_plan"] == "free"
    assert entitlement["required_plan"] == "monthly"


def test_feature_entitlement_rejects_unknown_feature(client, db_session):
    profile = register_and_login(client, "invalid-feature-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    with pytest.raises(ValueError, match="Unsupported membership feature"):
        get_feature_entitlement(user, db_session, "course_learning", "advanced_ai")


def test_entitlement_api_and_course_plan_guard_use_current_user(client, db_session):
    profile = register_and_login(client, "feature-guard-user")
    username = profile["username"]

    listing = client.get("/membership/entitlements", params={"service_key": "course_learning"})
    assert listing.status_code == 200
    assert listing.json()["features"]["learning_plan"] == {"allowed": False, "required_plan": "monthly"}

    locked = client.get("/course-learning/study-plan", params={"username": username, "course_id": "data_structure"})
    assert locked.status_code == 403
    assert locked.json()["detail"] == {
        "code": "FEATURE_REQUIRES_UPGRADE",
        "feature": "learning_plan",
        "service_key": "course_learning",
        "current_plan": "free",
        "required_plan": "monthly",
    }

    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    _set_membership(db_session, user.id, "course_learning", "monthly")
    allowed = client.get("/course-learning/study-plan", params={"username": username, "course_id": "data_structure"})
    assert allowed.status_code == 200, allowed.text


def test_free_users_can_access_report_review_but_not_learning_plan(client, db_session):
    profile = register_and_login(client, "feature-api-free-user")
    username = profile["username"]

    # 学习报告 / 练习复盘已免费
    course_review = client.get("/review/center", params={"username": username, "course_id": "data_structure"})
    assert course_review.status_code == 200

    # 学习计划仍为付费权益
    exam_plan = client.get("/exam/11408/subjects/data_structure/study-plan", params={"username": username})
    assert exam_plan.status_code == 403
    assert exam_plan.json()["detail"] == {
        "code": "FEATURE_REQUIRES_UPGRADE",
        "feature": "learning_plan",
        "service_key": "exam_11408",
        "current_plan": "free",
        "required_plan": "monthly_sprint",
    }


def test_paid_direction_does_not_unlock_another_direction_or_expired_access(client, db_session):
    profile = register_and_login(client, "feature-isolation-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    _set_membership(db_session, user.id, "course_learning", "monthly")

    # 学习报告/练习复盘免费，course_learning 付费不解锁 exam_11408 的学习计划
    allowed_review = client.get("/review/center", params={"username": profile["username"], "course_id": "data_structure"})
    assert allowed_review.status_code == 200

    exam_plan = client.get("/exam/11408/subjects/data_structure/study-plan", params={"username": profile["username"]})
    assert exam_plan.status_code == 403
    assert exam_plan.json()["detail"]["service_key"] == "exam_11408"

    _set_membership(db_session, user.id, "exam_11408", "monthly_sprint")
    paid_exam_plan = client.get("/exam/11408/subjects/data_structure/study-plan", params={"username": profile["username"]})
    assert paid_exam_plan.status_code == 200, paid_exam_plan.text

    _set_membership(db_session, user.id, "exam_11408", "monthly_sprint", utc_now() - timedelta(minutes=1))
    expired_plan = client.get("/exam/11408/subjects/data_structure/study-plan", params={"username": profile["username"]})
    assert expired_plan.status_code == 403
    assert expired_plan.json()["detail"]["current_plan"] == "free"


def test_entitlement_errors_and_ordinary_http_errors_keep_json_contract(client):
    assert client.get("/membership/entitlements", params={"service_key": "invalid"}).status_code == 401

    profile = register_and_login(client, "feature-http-contract-user")
    invalid = client.get("/membership/entitlements", params={"service_key": "invalid"})
    assert invalid.status_code == 400
    assert isinstance(invalid.json()["detail"], str)

    missing = client.get("/learning/reports", params={"username": profile["username"]})
    assert missing.status_code == 400
    assert isinstance(missing.json()["detail"], str)
