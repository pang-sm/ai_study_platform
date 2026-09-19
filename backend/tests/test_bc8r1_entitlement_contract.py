"""FRONTEND_BC8_R1 — membership entitlement typed contract closure.

Gates this file exists to prove:

  * `GET /membership/entitlements` has a concrete 2xx response model that faithfully
    describes what the endpoint ACTUALLY returns, for every tier and every direction —
    including the empty mapping `programming` legitimately answers with;
  * `features.learning_plan.allowed` and `.required_plan` are typed, with their values
    preserved exactly;
  * the membership POLICY is untouched: free denied, paid allowed, same catalog.

`backend/app.db` is never opened for write.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import register_and_login
import database
import main
from models import User, UserServiceMembership

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"

ENTITLEMENTS = "/membership/entitlements"
PLAN = "/exam/11408/subjects/operating_system/study-plan"

# exam_11408 catalog: free denies learning_plan, every paid tier grants it.
PAID_TIERS = ("monthly_sprint", "quarterly_boost", "full_exam")


def grant(username: str, plan: str, service_key: str = "exam_11408") -> None:
    db = database.SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).one()
        membership = (db.query(UserServiceMembership)
                      .filter(UserServiceMembership.user_id == user.id,
                              UserServiceMembership.service_key == service_key).first())
        if membership is None:
            membership = UserServiceMembership(user_id=user.id, service_key=service_key)
            db.add(membership)
        membership.is_enabled = True
        membership.plan = plan
        membership.status = "active"
        membership.activated_at = datetime.now(timezone.utc)
        membership.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        db.commit()
    finally:
        db.close()


def entitlements(client, service_key: str = "exam_11408") -> dict:
    r = client.get(ENTITLEMENTS, params={"service_key": service_key})
    assert r.status_code == 200, r.text
    return r.json()


# ================================================================ A. the model fits


def test_free_response_validates_against_the_response_model(client):
    register_and_login(client, "bc8r1_free")
    body = entitlements(client)
    model = main.MembershipEntitlementsResponse.model_validate(body)

    assert model.service_key == "exam_11408"
    assert model.current_plan == "free"
    assert model.features["learning_plan"].allowed is False
    assert model.features["learning_plan"].required_plan == "monthly_sprint"


@pytest.mark.parametrize("tier", PAID_TIERS)
def test_paid_responses_validate_against_the_response_model(client, tier):
    username = f"bc8r1_{tier}"
    register_and_login(client, username)
    grant(username, tier)
    body = entitlements(client)
    model = main.MembershipEntitlementsResponse.model_validate(body)

    assert model.current_plan == tier
    assert model.features["learning_plan"].allowed is True
    # required_plan is the CHEAPEST plan that grants it, not the tier you happen to hold
    assert model.features["learning_plan"].required_plan == "monthly_sprint"


def test_every_direction_validates_including_the_empty_mapping(client):
    """`features` is a mapping, not a closed record — `programming` really is `{}`."""
    register_and_login(client, "bc8r1_directions")
    for service_key, expected_keys in (
        ("exam_11408", {"learning_plan", "learning_report"}),
        ("course_learning", {"learning_plan", "learning_report"}),
        ("programming", set()),
    ):
        model = main.MembershipEntitlementsResponse.model_validate(
            entitlements(client, service_key))
        assert set(model.features) == expected_keys, service_key
        assert model.service_key == service_key


def test_required_plan_is_direction_specific(client):
    """The reason `required_plan` is a string and not a shared enum."""
    register_and_login(client, "bc8r1_directions2")
    exam = main.MembershipEntitlementsResponse.model_validate(entitlements(client, "exam_11408"))
    course = main.MembershipEntitlementsResponse.model_validate(
        entitlements(client, "course_learning"))
    assert exam.features["learning_plan"].required_plan == "monthly_sprint"
    assert course.features["learning_plan"].required_plan == "monthly"


def test_legacy_alias_resolves_to_the_canonical_service_key(client):
    """BC8-R1 is a typing closure, not a namespace migration: aliases are preserved."""
    register_and_login(client, "bc8r1_alias")
    for alias in ("exam", "exam_408", "exam_11408"):
        assert entitlements(client, alias)["service_key"] == "exam_11408"
    assert client.get(ENTITLEMENTS, params={"service_key": "nope"}).status_code == 400


def test_entitlements_require_authentication(client):
    assert client.get(ENTITLEMENTS, params={"service_key": "exam_11408"}).status_code in (401, 403)


def test_one_user_never_sees_another_users_plan(client):
    register_and_login(client, "bc8r1_owner")
    grant("bc8r1_owner", "full_exam")
    assert entitlements(client)["current_plan"] == "full_exam"

    client.cookies.clear()
    register_and_login(client, "bc8r1_other")
    assert entitlements(client)["current_plan"] == "free"
    assert entitlements(client)["features"]["learning_plan"]["allowed"] is False


# ================================================================ B. policy unchanged


def test_membership_policy_is_unchanged(client):
    """MEMBERSHIP_POLICY_CHANGED = NO — free denied, paid allowed, same catalog."""
    register_and_login(client, "bc8r1_policy")

    free = entitlements(client)
    assert free["current_plan"] == "free"
    assert free["features"]["learning_plan"]["allowed"] is False
    assert free["features"]["learning_plan"]["required_plan"] == "monthly_sprint"
    assert free["features"]["learning_report"] == {"allowed": True, "required_plan": "free"}
    assert client.get(PLAN).status_code == 403

    grant("bc8r1_policy", "monthly_sprint")
    paid = entitlements(client)
    assert paid["current_plan"] == "monthly_sprint"
    assert paid["features"]["learning_plan"]["allowed"] is True
    assert paid["features"]["learning_plan"]["required_plan"] == "monthly_sprint"
    assert paid["features"]["learning_report"] == {"allowed": True, "required_plan": "free"}
    assert client.get(PLAN).status_code == 200


def test_the_catalog_and_the_quota_map_are_untouched():
    """The config BC8-R1 typed but deliberately did not change."""
    from membership import SERVICE_FEATURE_QUOTAS, get_service_plan_catalog
    assert SERVICE_FEATURE_QUOTAS == {
        "exam_11408": {"learning_plan": "learning_plan", "learning_report": "learning_report"},
        "course_learning": {"learning_plan": "learning_plan",
                            "learning_report": "learning_report"},
    }
    catalog = get_service_plan_catalog("exam_11408")
    assert {tier: bool(d["quota"]["learning_plan"]) for tier, d in catalog.items()} == {
        "free": False, "monthly_sprint": True, "quarterly_boost": True, "full_exam": True}


# ================================================================ C. OpenAPI


def test_the_success_response_is_concrete_in_openapi(client):
    """MEMBERSHIP_ENTITLEMENT_SUCCESS_UNKNOWN = 0."""
    spec = client.get("/openapi.json").json()
    op = spec["paths"][ENTITLEMENTS]["get"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema.get("$ref") == "#/components/schemas/MembershipEntitlementsResponse"

    model = spec["components"]["schemas"]["MembershipEntitlementsResponse"]
    assert set(model["required"]) == {"service_key", "current_plan", "features"}
    assert model["additionalProperties"] is False
    features = model["properties"]["features"]
    assert features["type"] == "object"
    assert features["additionalProperties"] == {
        "$ref": "#/components/schemas/MembershipFeatureEntitlement"}

    entry = spec["components"]["schemas"]["MembershipFeatureEntitlement"]
    assert set(entry["required"]) == {"allowed", "required_plan"}
    assert entry["properties"]["allowed"]["type"] == "boolean"
    assert entry["properties"]["required_plan"]["type"] == "string"

    assert op["responses"]["200"]["content"]["application/json"]["schema"] != {}


def test_no_schema_or_migration_was_needed():
    """BC8R1 contributed no revision. Pinned as a chain property, not as "the head is
    0009" — a later sprint may legitimately advance the head."""
    versions = {p.name: p.read_text(encoding="utf-8")
                for p in (BACKEND_DIR.parent / "migrations" / "versions").glob("*.py")}
    assert any(n.startswith("20260919_0009") for n in versions), sorted(versions)
    bc7_head = next(t for n, t in versions.items() if n.startswith("20260919_0009"))
    assert 'down_revision: Union[str, None] = "20260917_0008"' in bc7_head


def test_real_app_db_is_never_mutated_by_this_suite():
    import sqlite3
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        tables = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        memberships = con.execute(
            "SELECT COUNT(*) FROM user_service_memberships").fetchone()[0]
    finally:
        con.close()
    assert integrity == "ok"
    assert tables == 72
    assert memberships == 0

