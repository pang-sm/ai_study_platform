"""ACCEL_PRODUCT_S10 PART B — feature entitlement resolves from the UNIFIED tier.

The authority chain this file pins:

    subscriptions (ONE tier per user)
        ↓
    capability policy (which tier grants which capability)
        ↓
    feature entitlement (learning_plan / learning_report)

``user_service_memberships`` no longer appears in that chain. It remains a compatibility row
for the four legacy fixed-count quotas, and the tests below assert that writing a paid plan
into it does NOT open a product feature — because if it did, the membership surface could
hand out two kinds of activation that disagree, which is the state S10 removes.

The direction still matters, but for a different job: it decides which features EXIST.
`programming` gates neither feature and answers with an empty mapping.
"""
from datetime import timedelta

import pytest

from conftest import register_and_login
import models
from main import utc_now
from membership import get_feature_entitlement
from usage.models import Subscription


def _set_membership(db_session, user_id, service_key, plan, expires_at=None):
    """Write ONLY the per-direction compatibility row — deliberately not a grant."""
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


def _set_tier(db_session, user_id, tier, end_at=None):
    """Write the unified tier — the only thing that opens a product feature."""
    now = utc_now().replace(tzinfo=None)
    db_session.query(Subscription).filter(
        Subscription.user_id == user_id, Subscription.status == "active",
    ).update({"status": "cancelled", "updated_at": now})
    if tier != "free":
        db_session.add(Subscription(
            user_id=user_id, tier=tier, status="active", start_at=now,
            end_at=end_at.replace(tzinfo=None) if end_at else None,
            source="test", created_at=now, updated_at=now))
    db_session.commit()


def test_the_direction_decides_which_features_exist(client, db_session):
    profile = register_and_login(client, "feature-entitlement-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()

    # learning_report is a BASE feature: open on every tier, Free included (SSOT §5.1 puts
    # 学习记录 inside the Free learning loop). It has no required capability.
    free = get_feature_entitlement(user, db_session, "course_learning", "learning_report")
    assert free["allowed"] is True
    assert free["feature"] == "learning_report"
    assert free["service_key"] == "course_learning"
    assert free["current_tier"] == "free"
    assert free["required_tier"] == "free"
    assert free["required_capability"] is None

    # learning_plan is NOT free, and the requirement is stated as a TIER.
    exam = get_feature_entitlement(user, db_session, "exam_11408", "learning_plan")
    assert exam["allowed"] is False
    assert exam["current_tier"] == "free"
    assert exam["required_tier"] == "standard"
    assert exam["required_capability"] == "planning.generate"

    # `programming` gates neither feature, so the feature does not exist there.
    with pytest.raises(ValueError, match="Unsupported membership feature"):
        get_feature_entitlement(user, db_session, "programming", "learning_plan")


def test_one_tier_opens_the_feature_in_every_direction(client, db_session):
    """The point of unification: one membership, so one answer per feature."""
    profile = register_and_login(client, "feature-unified-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()

    _set_tier(db_session, user.id, "standard")
    for service_key in ("exam_11408", "course_learning"):
        ent = get_feature_entitlement(user, db_session, service_key, "learning_plan")
        assert ent["allowed"] is True, service_key
        assert ent["current_tier"] == "standard"


def test_a_legacy_direction_row_alone_opens_nothing(client, db_session):
    """THE S10 INVARIANT. A paid per-direction row is a record, not an authority.

    Before S10 this row was what opened `learning_plan`, and the unified tier was a number
    that changed nothing — so the membership surface had to offer the legacy path to resolve
    a lock. Now the reverse holds: the row opens nothing, and the tier opens everything.
    """
    profile = register_and_login(client, "feature-legacy-row-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()

    _set_membership(db_session, user.id, "exam_11408", "full_exam")
    ent = get_feature_entitlement(user, db_session, "exam_11408", "learning_plan")
    assert ent["allowed"] is False
    assert ent["current_tier"] == "free"


def test_an_expired_tier_is_free_again(client, db_session):
    """Expiry is decided by the SUBSCRIPTION's end_at, not by a direction row's."""
    profile = register_and_login(client, "expired-feature-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    _set_tier(db_session, user.id, "standard", end_at=utc_now() - timedelta(minutes=1))
    # a still-"active" row that has already ended resolves to free
    _set_membership(db_session, user.id, "course_learning", "full")

    entitlement = get_feature_entitlement(user, db_session, "course_learning", "learning_plan")
    assert entitlement["allowed"] is False
    assert entitlement["current_tier"] == "free"
    assert entitlement["required_tier"] == "standard"


def test_advanced_also_opens_the_plan(client, db_session):
    profile = register_and_login(client, "feature-advanced-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    _set_tier(db_session, user.id, "advanced")
    ent = get_feature_entitlement(user, db_session, "exam_11408", "learning_plan")
    assert ent["allowed"] is True
    assert ent["current_tier"] == "advanced"
    # the requirement is still stated as the CHEAPEST tier that grants it, not the one held
    assert ent["required_tier"] == "standard"


def test_feature_entitlement_rejects_unknown_feature(client, db_session):
    profile = register_and_login(client, "invalid-feature-user")
    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    with pytest.raises(ValueError, match="Unsupported membership feature"):
        get_feature_entitlement(user, db_session, "course_learning", "advanced_ai")


def test_the_gate_refuses_in_tiers_and_the_upgrade_opens_it(client, db_session):
    profile = register_and_login(client, "feature-guard-user")
    username = profile["username"]

    listing = client.get("/membership/entitlements", params={"service_key": "course_learning"})
    assert listing.status_code == 200
    assert listing.json()["current_tier"] == "free"
    assert listing.json()["features"]["learning_plan"] == {
        "allowed": False, "required_tier": "standard",
        "required_capability": "planning.generate",
    }

    locked = client.get("/course-learning/study-plan",
                        params={"username": username, "course_id": "data_structure"})
    assert locked.status_code == 403
    assert locked.json()["detail"] == {
        "code": "FEATURE_REQUIRES_UPGRADE",
        "feature": "learning_plan",
        "service_key": "course_learning",
        "current_tier": "free",
        "required_tier": "standard",
        "required_capability": "planning.generate",
    }

    user = db_session.query(models.User).filter(models.User.id == profile["id"]).one()
    _set_tier(db_session, user.id, "standard")
    allowed = client.get("/course-learning/study-plan",
                         params={"username": username, "course_id": "data_structure"})
    assert allowed.status_code == 200, allowed.text


def test_free_users_can_access_report_review_but_not_learning_plan(client, db_session):
    profile = register_and_login(client, "feature-api-free-user")
    username = profile["username"]

    # 学习报告 / 练习复盘已免费
    course_review = client.get("/review/center",
                               params={"username": username, "course_id": "data_structure"})
    assert course_review.status_code == 200

    # 学习计划仍为付费权益
    exam_plan = client.get("/exam/11408/subjects/data_structure/study-plan",
                           params={"username": username})
    assert exam_plan.status_code == 403
    assert exam_plan.json()["detail"] == {
        "code": "FEATURE_REQUIRES_UPGRADE",
        "feature": "learning_plan",
        "service_key": "exam_11408",
        "current_tier": "free",
        "required_tier": "standard",
        "required_capability": "planning.generate",
    }


def test_a_tier_is_per_learner_and_does_not_leak(client, db_session):
    """Cross-user isolation of the tier itself."""
    payer = register_and_login(client, "feature-isolation-user")
    payer_user = db_session.query(models.User).filter(models.User.id == payer["id"]).one()
    _set_tier(db_session, payer_user.id, "standard")

    assert client.get("/exam/11408/subjects/data_structure/study-plan",
                      params={"username": payer["username"]}).status_code == 200

    other = register_and_login(client, "feature-isolation-other")
    other_user = db_session.query(models.User).filter(models.User.id == other["id"]).one()
    assert get_feature_entitlement(other_user, db_session, "exam_11408",
                                   "learning_plan")["allowed"] is False


def test_entitlement_errors_and_ordinary_http_errors_keep_json_contract(client):
    assert client.get("/membership/entitlements", params={"service_key": "invalid"}).status_code == 401

    profile = register_and_login(client, "feature-http-contract-user")
    invalid = client.get("/membership/entitlements", params={"service_key": "invalid"})
    assert invalid.status_code == 400
    assert isinstance(invalid.json()["detail"], str)

    missing = client.get("/learning/reports", params={"username": profile["username"]})
    assert missing.status_code == 400
    assert isinstance(missing.json()["detail"], str)
