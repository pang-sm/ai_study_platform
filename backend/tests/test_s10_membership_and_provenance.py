"""ACCEL_PRODUCT_S10 — the two claims this sprint makes, and how they are checked.

  PART B  ONE membership authority. `subscriptions` decides the tier; the tier decides every
          product feature through the capability policy. `user_service_memberships` is a
          COMPATIBILITY row for the four legacy fixed-count quotas and decides no feature.
  PART F/G/H  demo, acceptance and test facts are stamped with their origin, excluded from
          every model dataset, and reported SEPARATELY from real learner facts — never summed.

The migration tests run the real revision against a crafted legacy database, because the one
thing that must be provable about a data migration is what it does to the rows it was written
for.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from conftest import grant_unified_tier, register_and_login
import models
from data_plane import origin
from science import capabilities as science_capabilities, kt_dataset, status
from usage import service as usage_service

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
MIG_0011 = REPO_ROOT / "migrations" / "versions" / "20260919_0011_unified_membership_backfill.py"
MIG_0012 = REPO_ROOT / "migrations" / "versions" / "20260919_0012_data_origin_provenance.py"


def _load_migration(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================ PART B — one authority


def test_the_tier_is_the_only_thing_that_decides_a_feature(client, db_session):
    """Standard and Advanced grant learning_plan; Free denies it. No row is written for this."""
    from membership import get_feature_entitlement
    from models import User

    profile = register_and_login(client, "s10_authority")
    user = db_session.query(User).filter(User.id == profile["id"]).one()

    assert get_feature_entitlement(user, db_session, "exam_11408",
                                   "learning_plan")["allowed"] is False
    for tier in ("standard", "advanced"):
        grant_unified_tier(db_session, profile["username"], tier)
        ent = get_feature_entitlement(user, db_session, "exam_11408", "learning_plan")
        assert ent["allowed"] is True, tier
        assert ent["current_tier"] == tier


def test_budget_semantics_are_unchanged_by_the_membership_migration():
    """S10 moved the AUTHORITY, not the numbers. The tier→credits table is frozen."""
    assert usage_service.DAILY_BUDGET == {"free": 100, "standard": 1000, "advanced": None}
    assert usage_service.WEEKLY_BUDGET == {"free": 500, "standard": 5000, "advanced": 20000}
    # Advanced's daily cap is an ABSENCE, not a zero — and the resolver says which.
    assert usage_service.budget_amount_for("advanced", "daily") is None
    assert usage_service.budget_amount_for("advanced", "weekly") == 20000
    assert usage_service.budget_amount_for("free", "daily") == 100


def test_the_tier_to_plan_mapping_is_its_own_inverse():
    """A round trip must be a fixed point.

    `_membership_plan` compares the compatibility row against the plan a tier represents. If
    tier→plan were not the inverse of plan→tier, every resolution would walk the reported
    plan code one step up, and a rank-1 grant would silently read as rank 2.
    """
    from membership import plan_code_for_tier, tier_from_service_plan

    for service_key in ("exam_11408", "course_learning", "programming"):
        for tier in ("free", "standard", "advanced"):
            code = plan_code_for_tier(service_key, tier)
            assert tier_from_service_plan(service_key, code) == tier, (service_key, tier, code)


def test_a_unified_upgrade_raises_the_legacy_quotas_but_never_lowers_them(client, db_session):
    """The four legacy numeric quotas follow the tier UP and never down.

    Moving the authority without this would leave a Standard subscriber on Free's AI
    allowance — the tier changed and the quota did not.
    """
    from membership import resolve_effective_quota

    profile = register_and_login(client, "s10_quota_follows_tier")
    user_id = profile["id"]
    free_chat = resolve_effective_quota(db_session, user_id, "exam_11408",
                                        "ai_chat_daily_limit")["effective_limit"]

    grant_unified_tier(db_session, profile["username"], "standard")
    standard_chat = resolve_effective_quota(db_session, user_id, "exam_11408",
                                            "ai_chat_daily_limit")["effective_limit"]
    assert standard_chat > free_chat

    # a per-direction purchase that is HIGHER than the tier keeps its own limit
    row = db_session.query(models.UserServiceMembership).filter(
        models.UserServiceMembership.user_id == user_id,
        models.UserServiceMembership.service_key == "exam_11408").first()
    if row is None:
        row = models.UserServiceMembership(user_id=user_id, service_key="exam_11408")
        db_session.add(row)
    row.is_enabled, row.plan, row.status = True, "full_exam", "active"
    db_session.commit()
    assert resolve_effective_quota(db_session, user_id, "exam_11408",
                                   "ai_chat_daily_limit")["effective_limit"] == 1000


# ============================================================ PART B4 — the migration


def _legacy_database(path: Path) -> None:
    """The three tables the back-fill reads and writes, in their legacy shape."""
    con = sqlite3.connect(path)
    try:
        con.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50),
                                plan VARCHAR(20), plan_expire_at DATETIME);
            CREATE TABLE user_service_memberships (
                id INTEGER PRIMARY KEY, user_id INTEGER, service_key VARCHAR(50),
                is_enabled BOOLEAN, plan VARCHAR(30), status VARCHAR(20),
                expires_at DATETIME);
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY, user_id INTEGER, tier VARCHAR(20),
                status VARCHAR(20), start_at DATETIME, end_at DATETIME,
                source VARCHAR(30), created_at DATETIME, updated_at DATETIME);
        """)
        con.executescript("""
            INSERT INTO users (id, username, plan) VALUES
                (1, 'u_free',      'free'),
                (2, 'u_monthly',   'free'),
                (3, 'u_full',      'free'),
                (4, 'u_paid_plan', 'cs_pro'),
                (5, 'u_already',   'free');
            INSERT INTO user_service_memberships
                (user_id, service_key, is_enabled, plan, status, expires_at) VALUES
                (2, 'exam_11408',      1, 'monthly_sprint',  'active', '2099-01-01'),
                (3, 'exam_11408',      1, 'full_exam',       'active', '2099-01-01'),
                (4, 'course_learning', 1, 'monthly',         'active', '2099-01-01'),
                (5, 'exam_11408',      1, 'monthly_sprint',  'active', '2099-01-01');
            INSERT INTO subscriptions (user_id, tier, status, start_at, source) VALUES
                (5, 'advanced', 'active', '2026-01-01', 'redemption');
        """)
        con.commit()
    finally:
        con.close()


def _run_upgrade(module, engine) -> None:
    from alembic import op as alembic_op
    original = alembic_op.get_bind
    try:
        with engine.begin() as connection:
            alembic_op.get_bind = lambda: connection
            module.upgrade()
    finally:
        alembic_op.get_bind = original


def test_the_backfill_translates_history_and_loses_nobody(tmp_path):
    """PART B4: deterministic mapping, and no user loses an already-paid entitlement."""
    db_path = tmp_path / "legacy.db"
    _legacy_database(db_path)
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    _run_upgrade(_load_migration(MIG_0011, "s10_mig_0011"), engine)

    with engine.connect() as connection:
        tiers = dict(connection.execute(text(
            "SELECT user_id, tier FROM subscriptions WHERE status = 'active'")).fetchall())

    assert tiers == {
        2: "standard",   # rank-1 plan
        3: "advanced",   # rank-3 plan
        4: "standard",   # legacy users.plan = cs_pro
        5: "advanced",   # already had a higher tier; NOT downgraded
    }
    assert 1 not in tiers, "a free user must not gain a paid tier"


def test_the_backfill_is_idempotent(tmp_path):
    db_path = tmp_path / "legacy.db"
    _legacy_database(db_path)
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    module = _load_migration(MIG_0011, "s10_mig_0011")
    _run_upgrade(module, engine)
    _run_upgrade(module, engine)

    with engine.connect() as connection:
        count = connection.execute(text(
            "SELECT COUNT(*) FROM subscriptions WHERE source = 'migration'")).scalar()
    assert count == 3, "the second run must be a no-op"


def test_the_backfill_refuses_a_code_it_cannot_map(tmp_path):
    """PART B4: ambiguity is REPORTED and the migration STOPS rather than guessing."""
    db_path = tmp_path / "legacy.db"
    _legacy_database(db_path)
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO user_service_memberships "
                "(user_id, service_key, is_enabled, plan, status, expires_at) "
                "VALUES (1, 'exam_11408', 1, 'mystery_package', 'active', '2099-01-01')")
    con.commit()
    con.close()

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    module = _load_migration(MIG_0011, "s10_mig_0011")
    with pytest.raises(RuntimeError) as raised:
        _run_upgrade(module, engine)
    assert "mystery_package" in str(raised.value)
    assert "refusing to migrate" in str(raised.value)

    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM subscriptions")).scalar()
    assert count == 1, "nothing may be written when the migration refuses"


def test_the_backfill_is_a_noop_on_a_fresh_alembic_only_database(tmp_path):
    """A database built by `alembic upgrade head` alone has no legacy tables. That is not an
    error — there is simply no legacy entitlement to translate, and this is what lets a fresh
    deployment be `alembic upgrade head` and nothing else."""
    db_path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE subscriptions (id INTEGER PRIMARY KEY)")
    module = _load_migration(MIG_0011, "s10_mig_0011")
    _run_upgrade(module, engine)   # must not raise
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM subscriptions")).scalar() == 0


def test_every_migration_still_refuses_to_downgrade():
    for path, name in ((MIG_0011, "m1"), (MIG_0012, "m2")):
        module = _load_migration(path, name)
        with pytest.raises(NotImplementedError):
            module.downgrade()


# ============================================================ PART F/G/H — provenance


def test_a_null_origin_is_not_real_data():
    """Fail-closed: forgetting to stamp a fact must not contribute it to the training set."""
    assert origin.normalize(None) == origin.UNCLASSIFIED
    assert origin.normalize("") == origin.UNCLASSIFIED
    assert origin.normalize("WHATEVER") == origin.UNCLASSIFIED
    assert origin.is_training_admissible(None) is False
    assert origin.is_training_admissible("DEMO") is False
    assert origin.is_training_admissible("learner") is True     # normalize() upper-cases
    assert origin.exclusion_reason(None) == "DATA_ORIGIN_NOT_RECORDED"


def test_the_process_origin_refuses_to_be_demo_in_production(monkeypatch):
    """A demo origin is refused where it would suppress real data, exactly like mock payment."""
    monkeypatch.setenv(origin.ENV_VAR, "DEMO")
    monkeypatch.setattr(origin, "_production", lambda: False)
    assert origin.active_origin() == "DEMO"

    monkeypatch.setattr(origin, "_production", lambda: True)
    assert origin.active_origin() == origin.UNCLASSIFIED


def test_demo_facts_are_excluded_from_the_training_dataset(client, db_session):
    """PART G, the hard gate: DEMO_DATA_USED_FOR_MODEL_TRAINING = NO.

    Every event here carries the SAME canonical concept, so the only thing that can decide
    whether it enters the dataset is its origin. A demo fact that were merely "unused" would
    pass a weaker test; this one has to be actively excluded.
    """
    from data_plane.models import LearningEvent

    profile = register_and_login(client, "s10_demo_exclusion")
    user_id = profile["id"]
    reference = json.dumps({"exam_module_id": "computer_network",
                            "knowledge_point_id": "3.6"})

    def make(event_id: str, origin_value: str | None) -> LearningEvent:
        return LearningEvent(
            event_id=event_id, event_schema_version=2, event_type="question_answered",
            event_granularity="ITEM_LEVEL", source_type="chapter_practice",
            source_attempt_id=event_id, source_item_key="1", source_item_index=1,
            user_id=user_id, service_key="exam_prep", subject_key="computer_network",
            question_id="1", knowledge_point_ref_json=reference,
            answer="A", correct=True, occurred_at=1000.0,
            ingested_at=1000.0, source_payload_version=1,
            idempotency_key=f"k-{event_id}", snapshot_capture_mode="LIVE_EMITTER",
            snapshot_completeness="FULL", data_origin=origin_value)

    keys = ["k-s10-real-1", "k-s10-demo-1", "k-s10-test-1", "k-s10-null-1"]
    for event_id, origin_value in (("s10-real-1", "LEARNER"), ("s10-demo-1", "DEMO"),
                                   ("s10-test-1", "TEST"), ("s10-null-1", None)):
        db_session.add(make(event_id, origin_value))
    db_session.commit()

    try:
        coverage = kt_dataset.interaction_coverage(db_session, service_namespace="exam_prep")
        # the four rows all reached the same bar; only the LEARNER one may be counted
        assert coverage["real_users_with_events"] >= 1
        assert coverage["demo_interactions"] >= 1
        assert coverage["test_interactions"] >= 1
        assert coverage["unclassified_interactions"] >= 1
        # The exclusions are named per origin, so a demo leak is not one anonymous bucket.
        assert coverage["excluded"]["DATASET_ORIGIN_DEMO"] >= 1
        assert coverage["excluded"]["DATASET_ORIGIN_TEST"] >= 1
        assert coverage["excluded"]["DATASET_ORIGIN_UNCLASSIFIED"] >= 1

        # …and the exported dataset carries only the real learner's sequence for this user
        body = kt_dataset.build(db_session, user_id=user_id)
        exported = [i for s in body.get("sequences") or []
                    for i in s.get("interactions") or []]
        assert len(exported) == 1, exported
        assert body["excluded"]["DATASET_ORIGIN_DEMO"] == 1
        assert body["excluded"]["DATASET_ORIGIN_TEST"] == 1
    finally:
        db_session.query(LearningEvent).filter(
            LearningEvent.idempotency_key.in_(keys)).delete(synchronize_session=False)
        db_session.commit()


def test_admin_diagnostics_report_real_and_demo_separately(client, db_session):
    """PART H: the two populations are reported, never combined into one number."""
    register_and_login(client, "s10_diag")
    block = status.data_collection_status(db_session)
    assert block["measured"] is True
    for key in ("real_users_with_events", "real_eligible_interactions",
                "real_concept_level_interactions", "demo_users", "demo_interactions",
                "test_interactions", "synthetic_backfill_interactions",
                "unclassified_interactions", "rows_by_origin"):
        assert key in block, key
    assert block["real_vs_demo_separated"] is True
    # the headline counters ARE the real ones, not a sum
    assert block["users_with_events"] == block["real_users_with_events"]
    assert block["eligible_interactions"] == block["real_eligible_interactions"]


def test_uncollected_telemetry_is_still_reported_as_uncollected(client, db_session):
    """PART J: S10 must not invent a response time or a hint count to feed a model."""
    block = status.data_collection_status(db_session)
    assert block["uncollected_fields"]["response_time_ms"]["state"] == "NOT_COLLECTED"
    assert block["uncollected_fields"]["hint_count"]["state"] == "NOT_AVAILABLE"
    assert block["uncollected_fields"]["response_time_ms"]["coverage"] is None
    assert block["uncollected_fields"]["hint_count"]["coverage"] is None


def test_the_proof_matrix_covers_every_component_and_names_who_may_see_it(client, db_session):
    """PART L: one row per component, for admin/demo documentation only."""
    matrix = status.technical_proof_matrix()
    assert matrix["intended_audience"] == "ADMIN_AND_DEMO_DOCUMENTATION"
    assert len(matrix["rows"]) == len(science_capabilities.REGISTRY)
    for row in matrix["rows"]:
        assert row["self_developed"] is True
        assert row["self_developed_basis"]
        assert "user_visible" in row
        assert "controls_product_decision" in row
        assert "writes_learner_fact" in row
    visible = sorted(r["component"] for r in matrix["rows"] if r["user_visible"])
    # the frozen S10 baseline: exactly one user-visible component
    assert visible == ["student_twin"]
    assert matrix["external_inference"]["self_developed"] is False


def test_the_frozen_scientific_modes_are_unchanged():
    """PART K: S10 promotes nothing."""
    import science.metadata as metadata

    modes = {cap.component: cap.mode for cap in science_capabilities.REGISTRY}
    assert modes["student_twin"] == metadata.MODE_PREVIEW
    for component in ("evidence_reliability", "tutor_policy", "learner_state",
                      "misconception_v2", "memory", "irt", "concept_verifier"):
        assert modes[component] != metadata.MODE_PREVIEW, component
    assert science_capabilities.summary()["totals"]["user_visible"] == 1
