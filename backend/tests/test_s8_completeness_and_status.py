"""ACCEL_PRODUCT_S8 — cross-workspace acceptance, model registry, admin diagnostics.

The sprint's product question was "is the CS408 learner journey coherent between its
surfaces, and is the scientific status of the product stated honestly?". These tests hold
the two endpoints of that question:

  * the LINKS have to be built from canonical identity the contract actually carries, so
    each test asserts the identity a deep link would target EXISTS and is stable — and the
    tests that assert an absent identity stay absent are as load-bearing as the others;
  * the STATUS surfaces have to show a learner only what a learner may see, and show an
    admin the engineering proof WITHOUT leaking a path, a prompt or a per-user field.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import grant_unified_tier, register_and_login
from database import SessionLocal
from learning.practice.telemetry import (TELEMETRY_COLLECTION_START_VERSION,
                                         TELEMETRY_SCHEMA_VERSION)
from models import ExamQuestionBank, User, UserServiceMembership
from science import capabilities, kt_dataset, status, tutor_policy


def now() -> datetime:
    return datetime.now(timezone.utc)

CN = "computer_network"


# ---------------------------------------------------------------- helpers

def _seed_cn_bank(db):
    """A `computer_network` bank in the shape the SHIPPED content is stored in.

    The stored `knowledge_point_id` is the canonical leaf's own title echoed with its code
    (`"3.6 局域网"`), and the provenance triple names the same leaf. This is the shape that
    made every one of the module's 920 real questions unreachable before S8.
    """
    rows = [
        ExamQuestionBank(subject_key=CN, subject_name=CN, source_type="chapter",
                         visibility="public", knowledge_point_id="3.6 局域网",
                         source_ref="chapter:3:3.6", knowledge_point_name="3.6 局域网",
                         question_type="choice", stem="局域网选择",
                         options_json=json.dumps({"A": "甲", "B": "乙"}),
                         standard_answer="A", analysis="", is_active=True),
        ExamQuestionBank(subject_key=CN, subject_name=CN, source_type="chapter",
                         visibility="public", knowledge_point_id="4.2 路由与转发",
                         source_ref="chapter:4:4.2", knowledge_point_name="4.2 路由与转发",
                         question_type="choice", stem="被拒绝的撞号题",
                         options_json=json.dumps({"A": "甲", "B": "乙"}),
                         standard_answer="A", analysis="", is_active=True),
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@pytest.fixture
def cn_bank(db_session):
    rows = _seed_cn_bank(db_session)
    try:
        yield rows
    finally:
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_([r.id for r in rows])).delete(synchronize_session=False)
        db_session.commit()


def _make_admin(client, username):
    register_and_login(client, username)
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).one()
        user.is_admin = 1
        user.admin_role = "operator"
        db.commit()
    finally:
        db.close()
    return username


# ================================================================ PART 2 — cross-workspace

def test_knowledge_reaches_practice_for_a_title_echo_bank(client, cn_bank):
    """Knowledge → Practice: a canonical leaf the knowledge map shows must serve questions."""
    register_and_login(client, "s8_k2p")
    body = client.get(f"/exam/11408/{CN}/chapter-practice/questions",
                      params={"knowledge_point_id": "3.6"}).json()
    assert body["total"] == 1
    assert body["items"][0]["stem"] == "局域网选择"


def test_knowledge_does_not_reach_a_refused_collision(client, cn_bank):
    """The other half of the same rule: a column that happens to contain `4.2` is not 4.2."""
    register_and_login(client, "s8_k2p_neg")
    body = client.get(f"/exam/11408/{CN}/chapter-practice/questions",
                      params={"knowledge_point_id": "4.2"}).json()
    assert body["total"] == 0


def test_practice_fact_carries_the_identity_a_wrong_answer_link_needs(client, db_session):
    """Practice → Wrong Answers: the fact must reach the canonical wrong-answer projection,
    and the projection must carry a stable record id to link to."""
    register_and_login(client, "s8_p2w")
    row = ExamQuestionBank(subject_key=CN, subject_name=CN, source_type="chapter",
                           visibility="public", knowledge_point_id="3.6 局域网",
                           source_ref="chapter:3:3.6", question_type="choice",
                           stem="错题来源", options_json=json.dumps({"A": "甲", "B": "乙"}),
                           standard_answer="A", analysis="", is_active=True)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    try:
        created = client.post(f"/exam/11408/{CN}/chapter-practice/attempts",
                              json={"question_ids": [row.id]}).json()
        aid = created["attempt_id"]
        client.post(f"/exam/11408/{CN}/chapter-practice/attempts/{aid}/answers",
                    json={"answers": {str(row.id): "B"}})
        client.post(f"/exam/11408/{CN}/chapter-practice/attempts/{aid}/submit",
                    json={"answers": {str(row.id): "B"}})

        ledger = client.get("/wrong-answers",
                            params={"service_namespace": "exam_prep", "module": CN}).json()
        record = next(r for r in ledger["items"] if r["question_bank_id"] == row.id)
        # the ids a deep link may use, and nothing derived
        assert isinstance(record["wrong_record_id"], int)
        assert record["module_key"] == CN
        assert record["source_kind"] == "chapter_practice"
        assert record["question_bank_id"] == row.id
    finally:
        db_session.query(ExamQuestionBank).filter(ExamQuestionBank.id == row.id).delete(
            synchronize_session=False)
        db_session.commit()


def test_a_learning_record_carries_the_source_a_deep_link_targets(client, db_session):
    """Records → source: the fact exposes `source.type` and `source.id`, which is what a
    ``?attempt=`` deep link is built from. A title is never an address.

    The fact is produced through the real product flow rather than read from whatever the
    shared test database happens to hold, so the assertion is about a recording path and
    not about a fixture.
    """
    register_and_login(client, "s8_rec_src")
    row = ExamQuestionBank(subject_key=CN, subject_name=CN, source_type="chapter",
                           visibility="public", knowledge_point_id="3.6 局域网",
                           source_ref="chapter:3:3.6", question_type="choice",
                           stem="记录来源", options_json=json.dumps({"A": "甲", "B": "乙"}),
                           standard_answer="A", analysis="", is_active=True)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    try:
        created = client.post(f"/exam/11408/{CN}/chapter-practice/attempts",
                              json={"question_ids": [row.id]}).json()
        aid = created["attempt_id"]
        client.post(f"/exam/11408/{CN}/chapter-practice/attempts/{aid}/submit",
                    json={"answers": {str(row.id): "A"}})

        page = client.get("/exam/prep/records", params={"limit": 50}).json()
        answered = [r for r in page["records"] if r["event_type"] == "question_answered"]
        assert answered, "a submitted practice answer must produce a canonical fact"
        view = answered[0]
        assert view["source"]["type"]
        assert view["source"]["id"], (
            "a record with no source id cannot be linked back to what produced it")
        assert view["context"]["exam_module_id"] == CN
    finally:
        db_session.query(ExamQuestionBank).filter(ExamQuestionBank.id == row.id).delete(
            synchronize_session=False)
        db_session.commit()


def test_study_plan_action_target_is_a_real_target_and_carries_no_invented_node(client):
    """Study Plan → action_target: the contract carries the target surface and the module.

    It carries NO knowledge-point CODE, so a node-level deep link would have to be guessed
    from a display title — which is why none is built. This test pins that absence so a
    future contract change is what unlocks it, not a frontend heuristic.
    """
    register_and_login(client, "s8_plan_target")
    db = SessionLocal()
    try:
        # ACCEL_PRODUCT_S10: the plan gate reads the unified tier, so grant the tier.
        grant_unified_tier(db, "s8_plan_target", "standard")
    finally:
        db.close()

    response = client.get("/exam/11408/subjects/data_structure/study-plan")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "tasks" in body, sorted(body.keys())
    for task in body["tasks"]:
        assert task["action_target"] in {"knowledge_map", "practice_center"}
        assert task["subject_key"]
        # the identity a node-level link would need is genuinely absent, in every task
        assert "knowledge_point_code" not in task
        assert "chapter_code" not in task


def test_the_locked_plan_state_names_the_required_plan_factually(client):
    """PART 13: the locked state must state a REAL fact, and must not promise a flow.

    ``required_plan`` is a value the product actually holds. What does NOT exist is a
    route to act on it — there is no membership or upgrade page in the app — so no
    navigation target is invented here, and the copy may not promise one.
    """
    register_and_login(client, "s8_plan_locked")
    response = client.get("/exam/11408/subjects/operating_system/study-plan")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "FEATURE_REQUIRES_UPGRADE"
    assert detail["feature"] == "learning_plan"
    # ACCEL_PRODUCT_S10: named in UNIFIED TIER terms — the same vocabulary the membership
    # page renders — instead of a legacy plan code no page could act on.
    assert detail["current_tier"] == "free"
    assert detail["required_tier"] == "standard"
    assert detail["required_capability"] == "planning.generate"


def test_state_and_records_are_scoped_the_same_way(client):
    """Learning State → Learning Records: both accept the same canonical module scope."""
    register_and_login(client, "s8_state_records")
    twin = client.get("/exam/prep/scientific/student-twin", params={"exam_module_id": CN})
    records = client.get("/exam/prep/records", params={"exam_module_id": CN})
    assert twin.status_code == 200
    assert records.status_code == 200


# ================================================================ PART 7/8 — telemetry

def test_the_export_states_every_telemetry_field_not_just_its_name():
    contract = kt_dataset.telemetry_contract()
    assert contract["schema_version"] == TELEMETRY_SCHEMA_VERSION
    assert contract["collection_start_version"] == TELEMETRY_COLLECTION_START_VERSION
    assert contract["optional_fields"]
    for name in contract["optional_fields"]:
        field = contract["fields"][name]
        for required in ("unit", "null_semantics", "source_of_truth"):
            assert field[required], f"{name}.{required} is empty"
    # not-collected-historically must remain distinguishable from an observed zero
    assert "NOT OBSERVED" in contract["null_means"]
    assert contract["historical_boundary"]["rule"]


def test_the_tutor_collection_contract_reports_the_absent_action_ontology():
    contract = tutor_policy.tutor_turn_collection_contract()
    assert contract["explicit_action_ontology_in_running_tutor"] == "ABSENT"
    by_field = {f["field"]: f for f in contract["fields"]}
    assert by_field["pedagogical_action"]["status"] == "NOT_OWNED"
    assert by_field["confusion"]["status"] == "NOT_OWNED"
    assert by_field["previous_action"]["status"] == "NOT_OWNED"
    assert by_field["dialogue_turn_ref"]["status"] == "COLLECTED"
    # every field declares its own contract, collected or not
    for field in contract["fields"]:
        for required in ("unit", "null_semantics", "source_of_truth"):
            assert field[required], f"{field['field']}.{required}"
    assert contract["tutor_policy_promoted"] is False


# ================================================================ PART 9 — registry

def test_the_category_registry_is_frozen_and_complete():
    body = capabilities.summary()
    assert body["totals"]["components"] == 13
    categories = {e["category"] for e in body["components"]}
    assert categories <= set(capabilities.CATEGORIES)
    assert body["totals"]["by_category"]
    assert sum(body["totals"]["by_category"].values()) == 13
    # exactly one capability is in front of a learner
    assert [e["component"] for e in body["components"] if e["user_visible"]] == [
        "student_twin"]


def test_capability_categories_match_the_sprint_decision():
    body = capabilities.summary()
    by_category = {e["component"]: e["category"] for e in body["components"]}
    assert by_category["student_twin"] == capabilities.CATEGORY_USER_VISIBLE
    for shadow in ("evidence_reliability", "tutor_policy"):
        assert by_category[shadow] == capabilities.CATEGORY_SHADOW_COLLECTING_DATA
    for research in ("learner_state", "misconception_v2", "memory", "irt",
                     "concept_verifier"):
        assert by_category[research] == capabilities.CATEGORY_RESEARCH_ONLY
    for retired in ("difficulty_prior", "planner", "tutor_guard", "execution_router",
                    "domestic_registry"):
        assert by_category[retired] == capabilities.CATEGORY_RETIRED_FROM_PRODUCT_ROADMAP


def test_an_unknown_category_is_refused_rather_than_silently_created():
    with pytest.raises(ValueError):
        capabilities._Capability("x", "SHADOW", False, False, (), "s", category="MAYBE")


def test_the_native_kt_entry_is_not_a_fourteenth_component():
    body = capabilities.summary()
    assert "cs408_native_kt" not in {e["component"] for e in body["components"]}
    native = {e["component"]: e for e in body["product_native_capabilities"]}
    assert native["cs408_native_kt"]["artifact"] is None
    assert native["cs408_native_kt"]["blocker"] == "DATA_READINESS_GATE"
    assert native["cs408_native_kt"]["user_visible"] is False


def test_the_http_capability_summary_carries_the_readiness_dimensions(client):
    """A response model that omits a field DROPS it; these three were being dropped."""
    register_and_login(client, "s8_caps_http")
    entries = client.get("/exam/prep/scientific/capabilities").json()["components"]
    entry = next(e for e in entries if e["component"] == "evidence_reliability")
    for key in ("runtime_available", "scientifically_compatible", "product_input_ready",
                "category"):
        assert key in entry, key
    assert entry["runtime_available"] is True
    assert entry["scientifically_compatible"] is False


# ================================================================ PART 10/11 — admin

def test_admin_diagnostics_requires_an_admin(client):
    with TestClient(client.app) as anon:
        assert anon.get("/science/status").status_code == 401
    register_and_login(client, "s8_status_user")
    assert client.get("/science/status").status_code == 403


def test_admin_diagnostics_returns_the_engineering_proof(client):
    _make_admin(client, "s8_status_admin")
    body = client.get("/science/status").json()
    assert body["audience"] == "ADMIN_ONLY"
    assert body["not_a_learner_page"] is True
    assert body["ordinary_users_see"] == ["student_twin"]
    assert body["schema_version"] == status.STATUS_SCHEMA_VERSION

    models = {m["component"]: m for m in body["models"]}
    assert models["student_twin"]["learned_model"] is False
    assert models["learner_state"]["learned_model"] is True
    assert models["learner_state"]["category"] == capabilities.CATEGORY_RESEARCH_ONLY
    er = models["evidence_reliability"]
    assert er["artifact_digests"], "a real model must carry a provenance digest"
    assert er["runtime_endpoint"].startswith("POST /v1/inference/")
    assert er["user_visible"] is False
    assert models["tutor_policy"]["blocker"] == "MISSING_TRUTHFUL_TURN_STATE_FIELDS"
    # an unprobed runtime is None, which is NOT the same answer as False
    assert body["runtime"]["reachable"] is None


def test_admin_diagnostics_leaks_no_path_prompt_or_pii(client):
    _make_admin(client, "s8_status_leak")
    raw = client.get("/science/status").text
    for leak in ("D:\\", "C:\\", "ZhixueAI", "model_assets", "runtime_src", "Traceback",
                 "py\", line", "127.0.0.1", "localhost", "api_key", "password",
                 "prompt", "@example.test"):
        assert leak not in raw, leak

    register_and_login(client, "s8_status_pii", password="secret123")
    raw = client.get("/science/status").text
    assert "s8_status_pii" not in raw


def test_admin_diagnostics_carries_no_per_user_field(client):
    """It takes no user parameter, so it cannot be turned into a view of anyone."""
    _make_admin(client, "s8_status_scope")
    assert client.get("/science/status", params={"user_id": 1}).status_code == 200
    body = client.get("/science/status", params={"user_id": 1}).json()
    assert "user_id" not in json.dumps(body)
    assert body["capability_totals"]["components"] == 13


# ================================================================ PART 15 — migration safety

def test_the_migration_chain_is_linear_and_the_exposed_head_matches():
    """Every revision names its own parent, and the chain has exactly one head."""
    from pathlib import Path
    versions = Path(__file__).resolve().parents[2] / "migrations" / "versions"
    parents: dict[str, str | None] = {}
    for path in sorted(versions.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        # the declaration carries a type annotation: ``revision: str = "..."``
        rev = re.search(r'^revision(?::[^=]+)?=\s*"([^"]+)"', text, re.M)
        down = re.search(r'^down_revision(?::[^=]+)?=\s*(?:"([^"]+)"|None)', text, re.M)
        if rev and down:
            parents[rev.group(1)] = down.group(1)
    assert parents, "no migrations found"
    referenced = {v for v in parents.values() if v}
    heads = [r for r in parents if r not in referenced]
    assert len(heads) == 1, f"expected exactly one head, found {heads}"
    for revision, parent in parents.items():
        assert parent is None or parent in parents, f"{revision} names unknown {parent}"


def test_no_migration_drops_or_rewrites_user_data():
    """additive-only is the long-standing rule; a destructive op must not appear."""
    from pathlib import Path
    versions = Path(__file__).resolve().parents[2] / "migrations" / "versions"
    for path in sorted(versions.glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for op in ("drop table", "drop column", "delete from", "truncate"):
            assert op not in text, f"{path.name} contains {op!r}"


def test_the_local_real_database_is_never_opened_by_the_tests():
    """The suite runs against a temp database; the shipped `app.db` is not a fixture."""
    import conftest
    assert "app.db" not in str(conftest.TEST_ROOT)
    import database
    assert str(database.engine.url) != "sqlite:///./app.db"
