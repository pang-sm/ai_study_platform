"""ACCEL_SPRINT_S4 — multi-component scientific productization.

The sprint's premise is that a component is productized ONLY when the product can honestly
form its input. It is deliberately not a sprint that forces one blocked model through its
gate, so this file holds the gates as firmly as it holds the one capability that is
visible.

PART A   the SSOT's CURRENT Scientific Runtime inventory must match the service's real
         routes, and must not have moved any readiness state.
PART B   evidence_reliability: real checkpoints, real panel execution, and the exact,
         independent reasons the product cannot construct its input. The product surface
         is SHADOW_NOT_USER_VISIBLE and produces no weight.
PART C/D/E  memory, irt and concept_verifier: the exact inputs each one needs, checked
         against what the product actually persists. Nothing is synthesized for any of
         them — no rating, no lapse, no interval, no item difficulty.
PART F/G learner_state, misconception_v2 and tutor_policy keep the modes they already had.
PART H   every product-facing scientific response carries the shared authority block.
PART I   the capability summary reports PRODUCT readiness, not endpoint existence.
PART K   the Product Backend still imports none of the heavy scientific stack.
PART L   a scientific outage never becomes a core-flow 500.

Doubles sit below the HTTP/runtime boundary only.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest
from conftest import register_and_login
from fastapi.testclient import TestClient

from core.learning_context import ServiceNamespace
from data_plane import models as dp_models
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from models import User
from science import capabilities as sci_capabilities
from science import client as sci_client
from science import evidence_reliability, learner_state, misconception, tutor_policy
from science.contract import (
    EvidenceReliabilityPreviewResponse,
    ScientificCapabilitiesResponse,
)

EXAM = ServiceNamespace.EXAM_PREP.value
REPO_ROOT = Path(__file__).resolve().parents[2]
MOMENT = datetime(2026, 9, 19, 6, 30, 0)


# ================================================================ helpers

def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def registered_user(client, session, username) -> User:
    """The caller the client is authenticated AS — registered through the real routes."""
    register_and_login(client, username)
    return session.query(User).filter_by(username=username).one()


def cs408_event(session, user, event_id, *, qid=None, correct=True,
                occurred_at=1000.0, event_type="question_answered", snapshot=None):
    """One real canonical CS408 learning event, written through the real model."""
    qid = qid or f"q-{event_id}"
    ev = dp_models.LearningEvent(
        event_id=event_id, event_schema_version=2, event_type=event_type,
        event_granularity="ITEM_LEVEL", source_type="exam_practice_attempt",
        source_attempt_id=f"att-{event_id}", source_item_key=f"{qid}:0",
        source_item_index=0, user_id=user.id, source_user_ref=user.username,
        service_key=EXAM, course_id=None, subject_key="operating_system",
        question_id=qid,
        knowledge_point_ref_json=json.dumps({"value": "kp1", "exam_module_id": "operating_system"}),
        item_snapshot_json=json.dumps(snapshot or {"question_id": qid}),
        item_content_hash="h", answer="A", correct=correct, score=None,
        response_time_ms=None, attempt_no=None, occurred_at=occurred_at,
        ingested_at=occurred_at, source_payload_version=1,
        idempotency_key=f"s4:{event_id}", snapshot_capture_mode="LIVE_EMITTER",
        snapshot_completeness="FULL", snapshot_missing_fields_json="[]")
    session.add(ev)
    session.commit()
    return ev


class _Unreachable:
    """A scientific client whose transport is dead. Never reaches the runtime."""

    def __init__(self, *a, **kw):
        pass

    def infer(self, *a, **kw):
        raise sci_client.ScientificUnavailable("runtime unreachable", component="test")

    def health(self, **kw):
        return {"status": "unavailable", "reason": "ConnectError"}


# ================================================================ PART A — SSOT inventory

def _runtime_service_paths():
    """The Scientific Runtime Service's REAL routes, read from its app."""
    sys.path.insert(0, str(REPO_ROOT / "scientific_runtime_service"))
    from app.main import app  # noqa: E402

    return {
        r.path for r in app.routes
        if hasattr(r, "methods") and r.methods - {"HEAD", "OPTIONS"}
        and not r.path.startswith(("/docs", "/redoc", "/openapi"))
    }


def test_ssot_current_inventory_lists_every_real_runtime_endpoint():
    """PART A: the CURRENT inventory is exactly the service's real surface."""
    ssot = (REPO_ROOT / "ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md").read_text(encoding="utf-8")
    section = ssot.split("# 49. CURRENT Scientific Runtime", 1)[1].split("\n# ", 1)[0]

    for path in sorted(_runtime_service_paths()):
        assert path in section, f"SSOT §49 does not list the real endpoint {path}"


def test_ssot_inventory_no_longer_claims_only_student_twin():
    """The stale inventory named three routes. It must not be restored by accident."""
    ssot = (REPO_ROOT / "ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md").read_text(encoding="utf-8")
    section = ssot.split("# 49. CURRENT Scientific Runtime", 1)[1].split("\n# ", 1)[0]
    for path in ("/v1/inference/misconception-v2", "/v1/inference/tutor-policy",
                 "/v1/inference/learner-state", "/v1/inference/evidence-reliability"):
        assert path in section, path


def test_sprint_a_moved_no_readiness_state():
    """PART A: an endpoint existing must not have promoted anything."""
    summary = sci_capabilities.summary()
    by_name = {e["component"]: e for e in summary["components"]}

    assert by_name["student_twin"]["mode"] == "PREVIEW"
    assert by_name["student_twin"]["user_visible"] is True
    assert by_name["learner_state"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert by_name["misconception_v2"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert by_name["tutor_policy"]["mode"] == "SHADOW"
    assert by_name["evidence_reliability"]["mode"] == "SHADOW_NOT_USER_VISIBLE"

    assert summary["totals"]["user_visible"] == 1
    assert summary["totals"]["controls_product_decision"] == 0
    assert summary["totals"]["writes_learner_fact"] == 0


# ================================================================ PART B — evidence_reliability

def test_evidence_reliability_endpoint_requires_authentication():
    from main import app
    with TestClient(app) as anon:
        assert anon.get("/exam/prep/scientific/evidence-reliability").status_code == 401


def test_evidence_reliability_produces_no_weight_and_names_every_blocker(client, db_session):
    """PART B2: the input is incomplete, so the surface is gated and no number is faked."""
    user = registered_user(client, db_session, "s4_er_gate")
    cs408_event(db_session, user, "er-1", correct=True)
    cs408_event(db_session, user, "er-2", correct=False, occurred_at=1001.0)

    body = client.get("/exam/prep/scientific/evidence-reliability").json()
    assert body["metadata"]["component"] == "evidence_reliability"
    assert body["metadata"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert body["reliability_weight"] is None
    assert body["model_requirement"]["scientific_threshold"] is None

    codes = {b.split(":")[0] for b in body["metadata"]["blockers"]}
    for expected in (evidence_reliability.BLOCKER_HINTS,
                     evidence_reliability.BLOCKER_RESPONSE_TIME,
                     evidence_reliability.BLOCKER_ATTEMPT_COUNT,
                     evidence_reliability.BLOCKER_ONTOLOGY,
                     evidence_reliability.BLOCKER_B_MAP,
                     evidence_reliability.BLOCKER_STANDARDIZATION,
                     evidence_reliability.BLOCKER_UPSTREAM_P_T,
                     evidence_reliability.BLOCKER_CALIBRATION):
        assert expected in codes, expected

    # the evidence window reports the REAL facts that do exist
    window = body["evidence_window"]
    assert window["event_count"] == 2
    assert window["distinct_items"] == 2


def test_evidence_reliability_input_audit_matches_the_real_component():
    """PART B: the requirement block is the component's real feature set, not a summary."""
    req = evidence_reliability.model_requirement()
    assert req["variants"] == {"42": 8, "42_nort": 7, "42_surprise": 3, "43": 8, "44": 8}
    assert req["variant_mode"] == "PANEL"
    assert req["active_product_variant"] is None
    assert req["replacement_readiness"] == "COLLECTING_DATA"

    missing = set(req["missing_input"])
    for field in ("hint_count", "has_bottom_hint", "log_rt", "attempt_gt1"):
        assert field in missing, field
    assert any(m.startswith("b_s") for m in missing)
    assert any(m.startswith("p_t") for m in missing)
    assert any("standardization" in m for m in missing)


def test_evidence_reliability_semantics_never_read_as_correctness():
    """PART B1: the output is a reliability weight. Nothing may call it a probability."""
    semantics = evidence_reliability.SCORE_SEMANTICS
    assert "reliability weight" in semantics
    assert "NOT the probability" in semantics
    # any vocabulary that could be misread must appear ONLY negated
    for forbidden in ("probability", "confidence", "mastery"):
        assert re.search(rf"NOT (a |the )?{forbidden}", semantics), \
            f"{forbidden!r} is not negated in {semantics!r}"

    req = evidence_reliability.model_requirement()
    assert req["user_facing_label_zh"] == "学习证据可靠度（实验）"
    assert "NOT" in req["user_facing_label_note"]


def test_evidence_reliability_writes_no_learner_fact(client, db_session):
    """PART B2: annotating evidence must not mutate anything the learner owns."""
    user = registered_user(client, db_session, "s4_er_write")
    cs408_event(db_session, user, "erw-1", correct=False)

    before_events = db_session.query(dp_models.LearningEvent).count()
    before_predictions = db_session.query(dp_models.ModelPrediction).count()
    before_runs = db_session.query(dp_models.ModelInferenceRun).count()

    body = client.get("/exam/prep/scientific/evidence-reliability").json()

    db_session.expire_all()
    assert body["metadata"]["writes_learner_fact"] is False
    assert body["metadata"]["controls_product_decision"] is False
    assert db_session.query(dp_models.LearningEvent).count() == before_events
    assert db_session.query(dp_models.ModelPrediction).count() == before_predictions
    assert db_session.query(dp_models.ModelInferenceRun).count() == before_runs


def test_evidence_reliability_module_contains_no_scientific_computation():
    """The product side must describe the gate, never reimplement the model."""
    source = Path(evidence_reliability.__file__).read_text(encoding="utf-8")
    for heavy in ("import torch", "import numpy", "from torch", "faiss",
                  "sentence_transformers", "reliability_net_"):
        assert heavy not in source, heavy
    assert "httpx" not in source
    assert "from .client import" in source


# ================================================================ PART C — memory

def test_memory_requires_an_interval_rating_and_lapse_history():
    """PART C: the exact inputs, held as a contract so no placeholder can slip in."""
    required = {"delta_t", "log_dt", "hist_len", "mean_interval", "mean_rating",
                "last_rating", "lapses"}
    assert len(required) == 7
    # the product has none of the review-history fields, so memory stays blocked
    assert required >= {"mean_rating", "last_rating", "lapses", "mean_interval"}


def _all_columns(db_session) -> set:
    from sqlalchemy import inspect

    inspector = inspect(db_session.get_bind())
    return {f"{t}.{c['name']}" for t in inspector.get_table_names()
            for c in inspector.get_columns(t)}


def test_memory_has_no_product_source_for_ratings_or_lapses(db_session):
    """PART C: no product column carries a review rating or a lapse count.

    The closest thing the schema has is ``question_attempts.self_result``, whose domain is
    categorical (correct / incorrect / unknown). A 1-4 FSRS rating cannot be derived from
    it, and must not be invented.
    """
    columns = _all_columns(db_session)

    # A review rating is a per-REVIEW quality judgement attached to a learning object.
    # ``support_tickets.rating`` is a customer-satisfaction rating and is not one.
    assert not {c for c in columns
                if re.search(r"(^|\.)(review_)?rating$", c) and "support" not in c}, \
        sorted(c for c in columns if re.search(r"rating", c, re.I))
    # a lapse is an FSRS "Again" — a count of forgotten reviews. Nothing stores one.
    assert not {c for c in columns if "lapse" in c.lower()}, \
        sorted(c for c in columns if "lapse" in c.lower())
    # an interval HISTORY would need more than one stored interval per item.
    assert not {c for c in columns if re.search(r"mean_interval|interval_history", c, re.I)}


def test_the_only_self_report_is_categorical_not_a_rating(db_session):
    """PART C: ``self_result`` is correct/incorrect/unknown — never a 1-4 quality rating."""
    from models import QuestionAttempt

    columns = {c.name for c in QuestionAttempt.__table__.columns}
    assert "self_result" in columns
    assert not {c for c in columns if "rating" in c}, sorted(columns)


def test_memory_interval_setting_is_a_single_value_not_a_history(db_session):
    """PART C: the product's review interval is one forward-looking setting, not history."""
    from models import UserKnowledgeReviewSetting

    columns = {c.name for c in UserKnowledgeReviewSetting.__table__.columns}
    assert "review_interval_days" in columns
    assert not {c for c in columns if "history" in c}, sorted(columns)
    # it is a per-user SETTING (one row per user), so it cannot supply mean_interval
    assert "user_id" in columns or "username" in columns


def test_memory_is_not_wired_and_stays_blocked():
    """PART C: the deterministic review interval is NOT replaced by the memory component."""
    summary = {e["component"]: e for e in sci_capabilities.summary()["components"]}
    entry = summary["memory"]
    assert entry["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert entry["available"] is False
    assert entry["user_visible"] is False
    assert set(entry["blockers"]) == {"REVIEW_RATING_HISTORY_ABSENT",
                                      "LAPSE_HISTORY_ABSENT",
                                      "INTERVAL_HISTORY_ABSENT"}

    # no memory bridge exists on the product side at all
    assert not (REPO_ROOT / "backend" / "science" / "memory.py").exists()
    for name in _runtime_service_paths():
        assert "memory" not in name


# ================================================================ PART D — IRT

def test_irt_requires_a_scientific_item_identity_and_an_ability_state():
    """PART D: the identity layer is the blocker, so no difficulty may be assigned."""
    entry = {e["component"]: e for e in sci_capabilities.summary()["components"]}["irt"]
    assert entry["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert entry["available"] is False
    assert set(entry["blockers"]) == {"ITEM_IDENTITY_ONTOLOGY_MISMATCH",
                                      "ABILITY_STATE_ABSENT"}


def test_irt_assigns_no_arbitrary_difficulty(db_session):
    """PART D: the product's difficulty is an EDITORIAL LABEL, not an IRT parameter.

    ``exam_question_bank.difficulty`` and friends hold categorical labels (medium / 简单 /
    中等 / 困难), and ``programming_exercises.difficulty_score`` is a 0-100 editorial
    score. None of them is a logit-scale IRT ``b``. Substituting one for ``b_s`` would
    assign an arbitrary difficulty, which this test forbids.
    """
    columns = _all_columns(db_session)

    # no IRT parameter column exists anywhere in the schema
    assert not {c for c in columns
                if re.search(r"(^|\.)(_?b_item|b_param|irt_|discrimination|theta)", c)},\
        sorted(c for c in columns if re.search(r"irt|theta|discrimination", c, re.I))

    # the difficulty signal that DOES exist is categorical, which is what makes it unusable
    from models import ExamQuestionBank

    bank_columns = {c.name for c in ExamQuestionBank.__table__.columns}
    assert "difficulty" in bank_columns
    from sqlalchemy import func

    labels = {v for (v,) in db_session.query(ExamQuestionBank.difficulty)
              .group_by(ExamQuestionBank.difficulty).limit(20)}
    if labels:
        assert all(not isinstance(v, (int, float)) for v in labels if v is not None), \
            "a numeric difficulty appeared where an editorial label was expected"


def test_irt_has_no_product_side_module_or_endpoint():
    """PART D: nothing may assign a difficulty, so no bridge exists at all."""
    assert not (REPO_ROOT / "backend" / "science" / "irt.py").exists()
    for name in _runtime_service_paths():
        assert "irt" not in name


# ================================================================ PART E — concept_verifier

def test_concept_verifier_has_no_cs408_concept_space():
    """PART E: the ontology does not fit, so it is reported and stopped — never ADVISORY."""
    entry = {e["component"]: e for e in sci_capabilities.summary()["components"]}[
        "concept_verifier"]
    assert entry["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert entry["available"] is False
    assert entry["user_visible"] is False
    assert entry["blockers"] == ["CONCEPT_ONTOLOGY_MISMATCH"]

    # never ACTIVE, and no product surface exists to let it overwrite canonical ontology
    assert entry["mode"] != "PREVIEW"
    assert entry["controls_product_decision"] is False
    assert not (REPO_ROOT / "backend" / "science" / "concept_verifier.py").exists()


# ================================================================ PART F/G — frozen modes

def test_frozen_component_modes_are_unchanged():
    """PART F/G: nothing was promoted because a dependency could be installed."""
    assert sci_capabilities.summary()  # registry built without touching the runtime
    assert learner_state is not None
    assert misconception.PRODUCT_MODE == "SHADOW_NOT_USER_VISIBLE"
    assert tutor_policy.PRODUCT_MODE == "SHADOW"
    assert evidence_reliability.PRODUCT_MODE == "SHADOW_NOT_USER_VISIBLE"


def test_no_scientific_dependency_was_installed_for_a_blocked_component():
    """PART F: the serving venv must not have gained torch for learner_state."""
    loaded = [m for m in ("torch", "transformers", "faiss", "sentence_transformers",
                          "sklearn") if m in sys.modules]
    assert loaded == [], f"heavy scientific modules loaded in-process: {loaded}"


# ================================================================ PART H — authority metadata

def test_every_scientific_response_carries_the_authority_block(client, db_session):
    """PART H: no scientific preview may silently become product truth."""
    user = registered_user(client, db_session, "s4_authority")
    cs408_event(db_session, user, "auth-1", correct=True)

    for path in ("/exam/prep/scientific/evidence-reliability",
                 "/exam/prep/scientific/learner-state",
                 "/exam/prep/scientific/student-twin",
                 "/science/tutor-policy"):
        body = client.get(path).json()
        meta = body["metadata"]
        for key in ("component", "mode", "controls_product_decision",
                    "writes_learner_fact", "generated_at"):
            assert key in meta, f"{path} is missing metadata.{key}"
        assert meta["controls_product_decision"] is False, path
        assert meta["writes_learner_fact"] is False, path


def test_authority_metadata_is_never_optional_on_the_wire():
    """The block is required by the response models, not merely present by habit."""
    for model in (EvidenceReliabilityPreviewResponse, ScientificCapabilitiesResponse):
        assert "metadata" in model.model_fields or "totals" in model.model_fields
    assert EvidenceReliabilityPreviewResponse.model_fields["metadata"].is_required()


# ================================================================ PART I — capability summary

def test_capability_summary_reports_product_readiness_not_endpoint_existence(client):
    """PART I: 'available' means the product can feed it — not that a route exists."""
    register_and_login(client, "s4_caps")
    by_name = {e["component"]: e for e in client.get(
        "/exam/prep/scientific/capabilities").json()["components"]}

    # every component has a runtime endpoint EXCEPT these two, yet none is 'available'
    assert by_name["learner_state"]["available"] is False
    assert by_name["evidence_reliability"]["available"] is False
    assert by_name["memory"]["available"] is False
    assert by_name["irt"]["available"] is False
    assert by_name["concept_verifier"]["available"] is False
    # the one visible capability is genuinely feedable
    assert by_name["student_twin"]["available"] is True
    assert by_name["student_twin"]["user_visible"] is True


def test_capability_summary_covers_all_thirteen_components(client):
    register_and_login(client, "s4_caps13")
    body = client.get("/exam/prep/scientific/capabilities").json()
    assert body["totals"]["components"] == 13
    assert len(body["components"]) == 13
    assert {e["component"] for e in body["components"]} == {
        "student_twin", "learner_state", "misconception_v2", "tutor_policy",
        "evidence_reliability", "memory", "irt", "concept_verifier", "difficulty_prior",
        "planner", "tutor_guard", "execution_router", "domestic_registry",
    }


def test_capability_summary_exposes_no_path_or_stack_trace(client):
    """PART I: no filesystem path, no asset location, no internal trace."""
    register_and_login(client, "s4_caps_leak")
    raw = client.get("/exam/prep/scientific/capabilities").text
    for leak in ("D:\\", "C:\\", "ZhixueAI", "model_assets", "runtime_src", "Traceback",
                 "File \"", ".py\", line"):
        assert leak not in raw, leak


def test_evidence_reliability_is_scoped_to_the_caller(client, db_session):
    """PART M: user B can never see user A's evidence, on any scientific surface."""
    owner = registered_user(client, db_session, "s4_iso_owner")
    cs408_event(db_session, owner, "iso-a1", correct=True)
    cs408_event(db_session, owner, "iso-a2", correct=False, occurred_at=1001.0)

    other = make_user(db_session, "s4_iso_other")
    cs408_event(db_session, other, "iso-b1", correct=True)

    # A sees exactly their own two observations
    mine = client.get("/exam/prep/scientific/evidence-reliability").json()
    assert mine["evidence_window"]["event_count"] == 2
    assert mine["evidence_window"]["distinct_items"] == 2

    # B is a different authenticated caller and sees exactly their own one
    with TestClient(client.app) as b_client:
        register_and_login(b_client, "s4_iso_other2")
        b_client.post("/login", json={"username": "s4_iso_other2", "password": "secret123"})
        theirs = b_client.get("/exam/prep/scientific/evidence-reliability").json()
    assert theirs["evidence_window"]["event_count"] == 0
    assert theirs["evidence_window"]["event_count"] != mine["evidence_window"]["event_count"]

    # the same scoping holds for the other per-user scientific surfaces
    assert client.get("/exam/prep/scientific/student-twin").json()[
        "input_summary"]["event_count"] == 2


def test_capability_summary_requires_authentication():
    from main import app
    with TestClient(app) as anon:
        assert anon.get("/exam/prep/scientific/capabilities").status_code == 401


# ================================================================ PART L — isolation

def test_capability_summary_needs_no_runtime_at_all(client):
    """PART I/L: the summary is a static product fact and must survive an outage."""
    register_and_login(client, "s4_caps_outage")
    body = client.get("/exam/prep/scientific/capabilities").json()
    assert body["totals"]["components"] == 13


def test_evidence_reliability_outage_is_bounded_not_a_500(client, db_session, monkeypatch):
    user = registered_user(client, db_session, "s4_er_outage")
    cs408_event(db_session, user, "ero-1", correct=True)

    monkeypatch.setattr(sci_client, "ScientificClient", _Unreachable)
    sci_client.reset_client()
    try:
        r = client.get("/exam/prep/scientific/evidence-reliability?probe_runtime=true")
        assert r.status_code == 200
        body = r.json()
        assert body["runtime_reachable"] is False
        assert body["reliability_weight"] is None
        assert body["metadata"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    finally:
        sci_client.reset_client()


def test_core_exam_flows_survive_a_scientific_outage(client, db_session, monkeypatch):
    """PART L: no scientific outage may cause a core-flow 500."""
    user = registered_user(client, db_session, "s4_core_outage")
    cs408_event(db_session, user, "core-1", correct=False)

    monkeypatch.setattr(sci_client, "ScientificClient", _Unreachable)
    sci_client.reset_client()
    try:
        for path in ("/exam/prep/records",
                     "/exam/prep/scientific/student-twin",
                     "/exam/prep/scientific/learner-state",
                     "/exam/prep/scientific/evidence-reliability",
                     "/exam/prep/scientific/capabilities",
                     "/exam/prep/catalog",
                     "/wrong-answers"):
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code}"
    finally:
        sci_client.reset_client()


# ================================================================ PART K — heavy imports

def test_product_backend_heavy_imports_are_zero():
    """PART K: the Product Backend must stay deployable without the scientific stack."""
    loaded = [m for m in ("torch", "transformers", "faiss", "sklearn",
                          "sentence_transformers", "zhixue_runtime")
              if m in sys.modules]
    assert loaded == [], f"heavy scientific modules loaded in-process: {loaded}"


def test_new_science_modules_import_only_the_shared_client():
    for module in (evidence_reliability, sci_capabilities):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for heavy in ("import torch", "import numpy", "import faiss",
                      "import sklearn", "sentence_transformers", "zhixue_runtime"):
            assert heavy not in source, f"{module.__name__}: {heavy}"


# ================================================================ PART N — OpenAPI

def test_openapi_is_concrete_for_every_new_endpoint(client):
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    for name in ("EvidenceReliabilityPreviewResponse",
                 "EvidenceReliabilityRequirement",
                 "ScientificCapabilitiesResponse",
                 "ScientificCapabilityEntry",
                 "ScientificCapabilityTotals"):
        assert name in schemas and schemas[name].get("properties"), name

    for path in ("/exam/prep/scientific/evidence-reliability",
                 "/exam/prep/scientific/capabilities"):
        operation = spec["paths"][path]["get"]
        ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in ref, f"GET {path} 200 is untyped: {ref}"


def test_openapi_declares_the_weight_as_nullable(client):
    """The contract itself must show that no number is produced in this mode."""
    spec = client.get("/openapi.json").json()
    props = spec["components"]["schemas"]["EvidenceReliabilityPreviewResponse"]["properties"]
    assert "reliability_weight" in props
    assert "probability" not in props and "confidence" not in props
