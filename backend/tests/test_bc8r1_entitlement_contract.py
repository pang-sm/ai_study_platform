"""FRONTEND_BC8_R1 / ACCEL_PRODUCT_S10 — membership entitlement typed contract closure.

Gates this file exists to prove:

  * `GET /membership/entitlements` has a concrete 2xx response model that faithfully
    describes what the endpoint ACTUALLY returns, for every tier and every direction —
    including the empty mapping `programming` legitimately answers with;
  * `features.learning_plan.allowed`, `.required_tier` and `.required_capability` are typed,
    with their values preserved exactly;
  * the membership POLICY holds: Free denied, Standard and Advanced allowed, and the
    per-direction commercial catalog is untouched by the entitlement's move to the unified
    tier.

S10 changed WHAT the entry carries — a unified tier instead of a legacy plan code — because
the old value named nothing a learner could act on and forced every consumer to invent a
plan→tier translation the backend never made.

`backend/app.db` is never opened for write.
"""
from pathlib import Path

import pytest

from conftest import grant_unified_tier, register_and_login
import main

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"

ENTITLEMENTS = "/membership/entitlements"
PLAN = "/exam/11408/subjects/operating_system/study-plan"

# The unified tiers that grant learning_plan. Free is the denied case.
GRANTING_TIERS = ("standard", "advanced")


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
    assert model.current_tier == "free"
    assert model.policy_version
    assert model.features["learning_plan"].allowed is False
    assert model.features["learning_plan"].required_tier == "standard"
    assert model.features["learning_plan"].required_capability == "planning.generate"


@pytest.mark.parametrize("tier", GRANTING_TIERS)
def test_granting_tier_responses_validate_against_the_response_model(client, db_session, tier):
    username = f"bc8r1_{tier}"
    profile = register_and_login(client, username)
    grant_unified_tier(db_session, profile["username"], tier)
    body = entitlements(client)
    model = main.MembershipEntitlementsResponse.model_validate(body)

    assert model.current_tier == tier
    assert model.features["learning_plan"].allowed is True
    # required_tier is the CHEAPEST tier that grants it, not the tier you happen to hold
    assert model.features["learning_plan"].required_tier == "standard"


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


def test_the_requirement_is_a_tier_and_is_the_same_in_every_direction(client):
    """S10: the requirement is the UNIFIED tier, so it does NOT vary by direction.

    Before S10 this was direction-specific (`monthly_sprint` under exam_11408, `monthly`
    under course_learning), which is why it had to be a bare string. One membership means one
    answer, and the direction's remaining job is to decide which features EXIST.
    """
    register_and_login(client, "bc8r1_directions2")
    exam = main.MembershipEntitlementsResponse.model_validate(entitlements(client, "exam_11408"))
    course = main.MembershipEntitlementsResponse.model_validate(
        entitlements(client, "course_learning"))
    assert exam.features["learning_plan"].required_tier == "standard"
    assert course.features["learning_plan"].required_tier == "standard"
    assert (exam.features["learning_report"].required_capability
            == course.features["learning_report"].required_capability is None)


def test_legacy_alias_resolves_to_the_canonical_service_key(client):
    """BC8-R1 is a typing closure, not a namespace migration: aliases are preserved."""
    register_and_login(client, "bc8r1_alias")
    for alias in ("exam", "exam_408", "exam_11408"):
        assert entitlements(client, alias)["service_key"] == "exam_11408"
    assert client.get(ENTITLEMENTS, params={"service_key": "nope"}).status_code == 400


def test_entitlements_require_authentication(client):
    assert client.get(ENTITLEMENTS, params={"service_key": "exam_11408"}).status_code in (401, 403)


def test_one_user_never_sees_another_users_tier(client, db_session):
    profile = register_and_login(client, "bc8r1_owner")
    grant_unified_tier(db_session, profile["username"], "advanced")
    assert entitlements(client)["current_tier"] == "advanced"

    client.cookies.clear()
    register_and_login(client, "bc8r1_other")
    assert entitlements(client)["current_tier"] == "free"
    assert entitlements(client)["features"]["learning_plan"]["allowed"] is False


# ================================================================ B. policy


def test_membership_policy_is_free_denied_and_every_paid_tier_allowed(client, db_session):
    """The product decision S10 was required to preserve."""
    profile = register_and_login(client, "bc8r1_policy")

    free = entitlements(client)
    assert free["current_tier"] == "free"
    assert free["features"]["learning_plan"]["allowed"] is False
    assert free["features"]["learning_plan"]["required_tier"] == "standard"
    assert free["features"]["learning_report"] == {
        "allowed": True, "required_tier": "free", "required_capability": None}
    assert client.get(PLAN).status_code == 403

    grant_unified_tier(db_session, profile["username"], "standard")
    standard = entitlements(client)
    assert standard["current_tier"] == "standard"
    assert standard["features"]["learning_plan"]["allowed"] is True
    assert client.get(PLAN).status_code == 200

    grant_unified_tier(db_session, profile["username"], "advanced")
    advanced = entitlements(client)
    assert advanced["current_tier"] == "advanced"
    assert advanced["features"]["learning_plan"]["allowed"] is True
    assert client.get(PLAN).status_code == 200


def test_the_direction_catalog_is_untouched():
    """S10 changed the ENTITLEMENT's authority, not the per-direction commercial catalog.

    The catalog still supplies the four legacy fixed-count quotas, and its Free-vs-paid shape
    is what `plan_code_for_tier` maps a unified tier onto. It is no longer a second authority
    over any product FEATURE.
    """
    from membership import SERVICE_FEATURES, get_service_plan_catalog
    assert SERVICE_FEATURES == {
        "exam_11408": ("learning_plan", "learning_report"),
        "course_learning": ("learning_plan", "learning_report"),
    }
    catalog = get_service_plan_catalog("exam_11408")
    assert {tier: bool(d["quota"]["learning_plan"]) for tier, d in catalog.items()} == {
        "free": False, "monthly_sprint": True, "quarterly_boost": True, "full_exam": True}


def test_the_tier_alone_decides_the_feature(client, db_session, monkeypatch):
    """The structural claim, proved rather than asserted in prose.

    The verdict must be a pure function of the UNIFIED TIER: changing the tier changes the
    verdict with NO membership row written anywhere, and writing a membership row changes
    nothing. If any code path re-introduced a second authority, one of these two would fail.
    """
    from membership import get_feature_entitlement
    from models import User, UserServiceMembership
    from usage import capabilities

    assert capabilities.FEATURE_CAPABILITY == {
        "learning_plan": "planning.generate",
        "learning_report": None,
    }

    profile = register_and_login(client, "bc8r1_single_authority")
    user = db_session.query(User).filter(User.id == profile["id"]).one()

    assert get_feature_entitlement(user, db_session, "exam_11408",
                                   "learning_plan")["allowed"] is False

    # 1. the tier alone flips it — no row of any kind is written.
    #    `membership` imported the resolver by name, so that is the name to replace.
    monkeypatch.setattr("membership.effective_subscription", lambda *a, **k: "standard")
    assert get_feature_entitlement(user, db_session, "exam_11408",
                                   "learning_plan")["allowed"] is True

    # 2. a paid per-direction row alone does NOT — the tier is still what decides
    monkeypatch.undo()
    db_session.add(UserServiceMembership(user_id=user.id, service_key="exam_11408",
                                         is_enabled=True, plan="full_exam", status="active"))
    db_session.commit()
    assert get_feature_entitlement(user, db_session, "exam_11408",
                                   "learning_plan")["allowed"] is False


# ================================================================ C. OpenAPI


def test_the_success_response_is_concrete_in_openapi(client):
    """MEMBERSHIP_ENTITLEMENT_SUCCESS_UNKNOWN = 0."""
    spec = client.get("/openapi.json").json()
    op = spec["paths"][ENTITLEMENTS]["get"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema.get("$ref") == "#/components/schemas/MembershipEntitlementsResponse"

    model = spec["components"]["schemas"]["MembershipEntitlementsResponse"]
    assert set(model["required"]) == {"service_key", "current_tier", "policy_version", "features"}
    assert model["additionalProperties"] is False
    features = model["properties"]["features"]
    assert features["type"] == "object"
    assert features["additionalProperties"] == {
        "$ref": "#/components/schemas/MembershipFeatureEntitlement"}

    entry = spec["components"]["schemas"]["MembershipFeatureEntitlement"]
    assert set(entry["required"]) == {"allowed", "required_tier", "required_capability"}
    assert entry["properties"]["allowed"]["type"] == "boolean"
    assert entry["properties"]["required_tier"]["type"] == "string"
    # nullable, because `learning_report` is a base feature with no capability gate
    assert "anyOf" in entry["properties"]["required_capability"]

    # The legacy plan-code field is GONE from the schema, not merely unused.
    assert "required_plan" not in entry["properties"]
    assert "current_plan" not in model["properties"]


def test_the_redeem_endpoints_declare_concrete_models(client):
    """Both halves of the ONE redeem flow answer with a typed body."""
    spec = client.get("/openapi.json").json()
    for path, model_name in (
        ("/subscription/redeem/preview", "RedeemPreviewResponse"),
        ("/subscription/redeem", "RedeemResultResponse"),
    ):
        schema = spec["paths"][path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema.get("$ref") == f"#/components/schemas/{model_name}", path


def test_no_schema_or_migration_was_needed_for_bc8r1():
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
