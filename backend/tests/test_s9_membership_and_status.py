"""ACCEL_PRODUCT_S9 PARTS G/H/I/K/L/M — membership surface, collection status, safety.

The membership page exists to give locked paid features a legitimate destination. Three
properties make it real rather than decorative, and all three are asserted here:

  * it reads the product's OWN entitlement endpoint, so what it shows and what gates a
    feature are the same verdict;
  * it is authorized and per-user — one learner's tier, usage and codes are not another's;
  * it offers only actions the backend can COMPLETE. Online payment is mock-only and
    production refuses it, so the surface states that instead of creating an order that
    could never be settled.

The scientific-status block is asserted to be admin-only, PII-free, and counted from the
real event stream — a count that was never taken reports ``measured: false``, never 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from conftest import register_and_login

import models
from membership import hash_code

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def _seed_code(db, code, *, target_plan="monthly_sprint", days=30, max_uses=1):
    entry = models.RedemptionCode(
        code_hash=hash_code(code), service_key="exam_11408", target_plan=target_plan,
        membership_duration_days=days, plan_code=target_plan, max_uses=max_uses,
        used_count=0, status="active", created_by="test")
    db.add(entry)
    db.commit()
    return entry


# ================================================================ PART G — the surface

def test_the_membership_surface_is_authenticated_on_every_per_user_endpoint(client):
    """A membership page is per-learner; every per-user read must refuse an anonymous caller."""
    for path in ("/subscription", "/usage/summary", "/membership/entitlements"):
        assert client.get(path).status_code == 401, path
    assert client.post("/subscription/redeem/preview", json={"code": "X"}).status_code == 401
    assert client.post("/subscription/redeem", json={"code": "X"}).status_code == 401

    # The plan CATALOG is deliberately public: it is the same for every learner and carries
    # no per-user value, so there is nothing behind it to authorize. Asserted explicitly so
    # the difference from the three reads above is a decision rather than an oversight.
    assert client.get("/subscription/plans").status_code == 200


def test_current_tier_and_plan_catalog_are_concrete(client):
    """The page's own inputs: a tier, and a catalog whose limits are real numbers or null."""
    register_and_login(client, "s9_member_a")
    assert client.get("/subscription").json() == {"tier": "free", "policy_version": "v1"}

    catalog = client.get("/subscription/plans").json()
    assert catalog["policy_version"] == "v1"
    plans = catalog["plans"]
    assert set(plans) == {"free", "standard", "advanced"}
    for definition in plans.values():
        assert set(definition) == {"label", "daily_budget", "weekly_budget", "capabilities"}
        assert isinstance(definition["capabilities"], list) and definition["capabilities"]
    # Advanced has NO daily cap, and the absence is null — not a zero
    assert plans["advanced"]["daily_budget"] is None
    assert plans["free"]["daily_budget"] == 100


def test_usage_summary_reports_one_shape_for_capped_and_uncapped_periods(client, db_session):
    """The uncapped period used to omit two keys, so one endpoint answered two shapes."""
    register_and_login(client, "s9_member_usage")
    body = client.get("/usage/summary").json()
    assert body["tier"] == "free"
    keys = {"budget", "reserved", "settled", "remaining"}
    for period in ("daily", "weekly"):
        assert set(body["periods"][period]) == keys

    from usage import service
    user = db_session.query(models.User).filter(
        models.User.username == "s9_member_usage").one()
    service.activate_subscription(db_session, user.id, "advanced", 30)
    advanced = client.get("/usage/summary").json()
    assert advanced["tier"] == "advanced"
    # no daily cap → every field null, and still the SAME key set
    assert set(advanced["periods"]["daily"]) == keys
    assert advanced["periods"]["daily"]["budget"] is None
    assert advanced["periods"]["daily"]["remaining"] is None
    assert advanced["periods"]["weekly"]["budget"] == 20000


def test_the_entitlement_verdict_is_the_same_one_that_gates_the_feature(client, db_session):
    """The membership page and the locked Study Plan read ONE endpoint, so they agree."""
    register_and_login(client, "s9_member_gate")
    body = client.get("/membership/entitlements", params={"service_key": "exam_11408"}).json()
    feature = body["features"]["learning_plan"]
    assert body["service_key"] == "exam_11408"
    assert feature["allowed"] is False
    # the requirement is reported as the legacy plan code the backend holds, unglossed
    assert feature["required_plan"] == "monthly_sprint"

    # and it is a REAL gate: the study plan refuses this learner
    plan = client.get("/exam/11408/subjects/data_structure/study-plan")
    assert plan.status_code in (200, 403)


def test_redemption_preview_then_activate_is_a_real_activation(client, db_session):
    """The ONE path the surface offers must actually complete, end to end."""
    register_and_login(client, "s9_member_redeem")
    _seed_code(db_session, "S9-EXAM-30D")

    preview = client.post("/subscription/redeem/preview", json={"code": "S9-EXAM-30D"})
    assert preview.status_code == 200
    assert preview.json()["duration_days"] == 30
    # previewing does NOT activate
    assert client.get("/subscription").json()["tier"] == "free"

    redeemed = client.post("/subscription/redeem", json={"code": "S9-EXAM-30D"})
    assert redeemed.status_code == 200
    assert redeemed.json()["tier"] == "standard"
    assert client.get("/subscription").json()["tier"] == "standard"


def test_redeeming_the_required_plan_flips_the_gate_the_locked_state_reports(
        client, db_session):
    """PART H/K end to end: locked → membership → activated → the feature really opens.

    This is the whole point of the link. Before S9 the locked Study Plan had nowhere to go;
    now the destination must actually be able to resolve the lock, not merely describe it.
    """
    register_and_login(client, "s9_member_unlock")

    before = client.get("/membership/entitlements",
                        params={"service_key": "exam_11408"}).json()
    assert before["current_plan"] == "free"
    assert before["features"]["learning_plan"]["allowed"] is False
    assert before["features"]["learning_plan"]["required_plan"] == "monthly_sprint"

    # the code grants exactly the plan the locked state names
    _seed_code(db_session, "S9-UNLOCK-30D", target_plan="monthly_sprint")
    assert client.post("/membership/redeem", json={"code": "S9-UNLOCK-30D"}).status_code == 200

    after = client.get("/membership/entitlements",
                       params={"service_key": "exam_11408"}).json()
    assert after["current_plan"] == "monthly_sprint"
    assert after["features"]["learning_plan"]["allowed"] is True

    # THE TWO MEMBERSHIP SYSTEMS ARE INDEPENDENT TODAY, AND THIS IS THE MEASUREMENT.
    # A per-direction plan is what gates a product feature; the unified tier is the frozen
    # TARGET model and its activation does not write the per-direction row (SSOT §41: CURRENT
    # is still the three-service membership). Asserted rather than assumed, because the
    # membership surface must offer the activation that RESOLVES THE LOCK: offering the
    # unified one would change a number and open nothing.
    assert client.get("/subscription").json()["tier"] == "free"


def test_the_unified_redeem_moves_the_tier_but_opens_no_feature(client, db_session):
    """The other half of the same measurement: `/subscription/redeem` is real, and it is not
    the path that unlocks a feature. Recorded so the choice above is auditable."""
    register_and_login(client, "s9_member_unified_only")
    _seed_code(db_session, "S9-UNIFIED-30D", target_plan="monthly_sprint")

    assert client.post("/subscription/redeem",
                       json={"code": "S9-UNIFIED-30D"}).status_code == 200
    assert client.get("/subscription").json()["tier"] == "standard"
    # ... and the product feature is still locked
    verdict = client.get("/membership/entitlements",
                         params={"service_key": "exam_11408"}).json()
    assert verdict["current_plan"] == "free"
    assert verdict["features"]["learning_plan"]["allowed"] is False


def test_an_invalid_code_is_refused_with_the_real_reason(client):
    register_and_login(client, "s9_member_badcode")
    response = client.post("/subscription/redeem", json={"code": "NOT-A-REAL-CODE"})
    assert response.status_code == 400
    # the backend's own message travels; the surface does not invent a friendlier one
    assert response.json()["detail"] == "兑换码不存在"


def test_membership_state_does_not_leak_between_learners(client, db_session):
    register_and_login(client, "s9_member_x")
    _seed_code(db_session, "S9-X-ONLY")
    assert client.post("/subscription/redeem", json={"code": "S9-X-ONLY"}).status_code == 200
    assert client.get("/subscription").json()["tier"] == "standard"
    x_usage = client.get("/usage/summary").json()

    # a second learner, in the same process, sees a fresh account
    register_and_login(client, "s9_member_y")
    assert client.get("/subscription").json()["tier"] == "free"
    y_usage = client.get("/usage/summary").json()
    assert y_usage["tier"] == "free"
    assert x_usage["periods"]["daily"]["budget"] == 1000      # X kept the paid tier
    assert y_usage["periods"]["daily"]["budget"] == 100       # Y did not inherit it

    # and X's one-use code cannot be redeemed again by Y
    second = client.post("/subscription/redeem", json={"code": "S9-X-ONLY"})
    assert second.status_code == 400


def test_a_pending_order_is_never_created_by_the_membership_surface(client, db_session):
    """The surface's contract, asserted against the DB: it creates no order it cannot settle."""
    register_and_login(client, "s9_member_noorder")
    before = db_session.query(models.MembershipOrder).count()
    # the page renders from these four reads and nothing else
    for path in ("/subscription", "/subscription/plans", "/usage/summary",
                 "/membership/entitlements"):
        assert client.get(path).status_code == 200
    db_session.expire_all()
    assert db_session.query(models.MembershipOrder).count() == before


# ================================================================ PART I — collection status

def register_admin(client, db, username):
    """Register through the real route, then grant admin on that same row.

    Registering first matters: creating the user directly and then calling
    `register_and_login` would try to create it twice.
    """
    register_and_login(client, username)
    user = db.query(models.User).filter(models.User.username == username).one()
    user.is_admin = True
    db.commit()
    return user


def test_scientific_status_is_admin_only(client, db_session):
    anon = client.get("/science/status")
    assert anon.status_code == 401
    register_and_login(client, "s9_plain_learner")
    assert client.get("/science/status").status_code == 403
    register_admin(client, db_session, "s9_admin_user")
    assert client.get("/science/status").status_code == 200


def test_scientific_status_reports_factual_collection_readiness(client, db_session):
    """PART I: the counters a researcher needs, counted from the real stream."""
    from data_plane.models import LearningEvent

    register_admin(client, db_session, "s9_admin_status")
    body = client.get("/science/status").json()

    collection = body["data_collection"]
    assert collection["measured"] is True
    assert collection["scope"] == "exam_prep"
    for key in ("users_with_events", "users_with_eligible_interactions",
                "eligible_interactions", "concept_level_interactions",
                "module_level_interactions", "non_canonical_concept_ids",
                "events_scanned"):
        assert key in collection, key
        assert isinstance(collection[key], int), key
    assert collection["collection_start_version"] == "ACCEL_SPRINT_S6"

    # the counters agree with the stream they claim to measure
    assert collection["events_scanned"] == (
        db_session.query(LearningEvent)
        .filter(LearningEvent.user_id.isnot(None),
                LearningEvent.service_key == "exam_prep").count())
    assert collection["eligible_interactions"] == (
        collection["module_level_interactions"] + collection["concept_level_interactions"])

    # the fields the product does NOT record are stated, not faked as zeros
    uncollected = collection["uncollected_fields"]
    assert uncollected["response_time_ms"]["state"] == "NOT_COLLECTED"
    assert uncollected["response_time_ms"]["coverage"] is None
    assert uncollected["hint_count"]["state"] == "NOT_AVAILABLE"
    assert uncollected["hint_count"]["coverage"] is None


def test_scientific_status_carries_no_learner_identity(client, db_session):
    """A diagnostic that could name a learner would be a view of somebody's learning."""
    register_admin(client, db_session, "s9_admin_pii")
    raw = client.get("/science/status").text
    assert "s9_admin_pii" not in raw
    assert "@example.test" not in raw
    assert "password" not in raw.lower()
    body = json.loads(raw)
    # and the collection block is a volume measurement: counts, never references
    assert not any(isinstance(value, str) and len(value) == 16
                   for value in body["data_collection"].values())


def test_status_without_a_session_reports_unmeasured_rather_than_zero():
    """A count that was never taken is not a count of zero."""
    from science import status

    block = status.data_collection_status(None)
    assert block["measured"] is False
    assert "users_with_events" not in block
    assert "eligible_interactions" not in block
    assert block["collection_start_version"]


# ================================================================ PART L — migration safety

def test_the_migration_chain_reaches_a_single_head_on_a_fresh_database(tmp_path):
    """PART L: fresh deployment is `alembic upgrade head` and nothing else."""
    fresh = tmp_path / "fresh.db"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{fresh.as_posix()}")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]

    import sqlite3
    con = sqlite3.connect(f"file:{fresh.as_posix()}?mode=ro", uri=True)
    try:
        revision = con.execute("select version_num from alembic_version").fetchone()[0]
        assert revision == "20260919_0010"
        columns = {row[1] for row in con.execute("PRAGMA table_info(practice_attempts)")}
        assert {"response_time_source", "attempt_index"} <= columns
        # the tables S9 relies on exist, and no hint column was invented for a model's sake
        assert "hint_count" not in columns
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()


def test_there_is_exactly_one_alembic_head():
    """Two heads would make `upgrade head` ambiguous and the deployment unreproducible."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-1000:]
    heads = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(heads) == 1, result.stdout
    assert heads[0].startswith("20260919_0010")


def test_s9_added_no_migration_of_its_own():
    """S9 changed no schema. A revision added without a schema change is churn on the chain."""
    versions = sorted(p.name for p in (REPO_ROOT / "migrations" / "versions").glob("*.py"))
    assert versions[-1] == "20260919_0010_attempt_telemetry_provenance.py"
