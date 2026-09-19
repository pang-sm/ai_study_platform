"""ACCEL_SPRINT_S6 PARTS F/G/H/I/J/K/L/M/N/O — the scientific data flywheel.

The sprint's premise is that the product now records facts a future CS408-native model can
be trained from, and that it does so without promoting any model that is not ready. These
tests hold the flywheel to that: every telemetry field says where its value comes from,
the export is byte-identical across runs, the split can never leak a learner, and every
scientific component stays in the state S1-S5 froze it at.

Nothing here trains a model, and no test asserts a scientific threshold — there are none.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from conftest import register_and_login

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"

CS408_CTX = {"service_namespace": "exam_prep", "subject_key": "operating_system",
             "exam_module_id": "operating_system", "knowledge_point_id": "2.1"}


# ============================================================ PART F — telemetry audit

def test_every_telemetry_field_states_its_own_source_of_truth():
    """A field with no recorded provenance cannot be told from a fabricated one."""
    from learning.practice.telemetry import TELEMETRY_CONTRACT

    for name, spec in TELEMETRY_CONTRACT["columns"].items():
        assert spec["unit"], name
        assert spec["null_semantics"], name
        assert spec["source_of_truth"], name


def test_null_and_zero_are_different_facts():
    """PART G's core requirement: 'never observed' must not read as 'observed zero'."""
    from learning.practice.telemetry import TELEMETRY_CONTRACT

    index = TELEMETRY_CONTRACT["columns"]["attempt_index"]
    assert "NOT OBSERVED" in index["null_semantics"]
    assert "no zero" in index["null_semantics"] or "NULL and 1 are different" in index["null_semantics"]

    duration = TELEMETRY_CONTRACT["columns"]["response_time_ms"]
    assert "0" in duration["null_semantics"]


def test_telemetry_records_the_release_that_first_wrote_a_value():
    """The columns existed before anything wrote them; the two are recorded separately."""
    from learning.practice.telemetry import (TELEMETRY_COLLECTION_START_VERSION,
                                             TELEMETRY_COLUMNS_SINCE_REVISION,
                                             TELEMETRY_SCHEMA_VERSION)

    assert TELEMETRY_SCHEMA_VERSION == "attempt-telemetry-v1"
    assert TELEMETRY_COLLECTION_START_VERSION == "ACCEL_SPRINT_S6"
    assert TELEMETRY_COLUMNS_SINCE_REVISION == "20260919_0010"
    assert TELEMETRY_COLUMNS_SINCE_REVISION != TELEMETRY_COLLECTION_START_VERSION


def test_telemetry_emission_is_the_durable_business_write_not_a_client_event():
    """PART F: the values are stamped by the write that creates the durable fact.

    The envelope's only projection is ``to_fact_fields``, the practice service is its only
    production consumer, and no frontend module constructs one.
    """
    import learning.practice.service as practice_service
    from learning.practice.telemetry import AttemptTelemetry

    assert set(AttemptTelemetry().to_fact_fields()) == {
        "response_time_ms", "response_time_source", "attempt_index"}

    source = (BACKEND / "learning" / "practice" / "service.py").read_text(encoding="utf-8")
    assert "response_time_source=telemetry.duration_source" in source
    assert "attempt_index=attempt_index" in source
    assert practice_service is not None

    # no frontend module constructs a telemetry envelope; the only occurrence of the name
    # is the generated type for the request body
    frontend = REPO_ROOT / "frontend" / "src"
    if frontend.exists():
        hits = [p for p in frontend.rglob("*.ts*")
                if "AttemptTelemetry" in p.read_text(encoding="utf-8", errors="ignore")]
        assert all(p.name == "api.ts" for p in hits), [str(p) for p in hits]


def test_attempt_index_is_derived_from_a_real_canonical_count(client):
    """The live path counts canonical rows; it does not guess and does not take a hint."""
    user = register_and_login(client, f"s6idx{uuid.uuid4().hex[:8]}")
    assert user
    session = client.post("/practice/sessions",
                          json={"service_namespace": "exam_prep", "context": CS408_CTX})
    assert session.status_code == 200, session.text
    sid = session.json()["id"]

    def answer(question_id: str, correct: bool):
        response = client.post(f"/practice/sessions/{sid}/attempts", json={
            "question_source_type": "static_question_bank",
            "question_source_id": question_id,
            "answer": "A", "correct": correct, "question_context": CS408_CTX})
        assert response.status_code == 200, response.text
        return response.json()["attempt"]["attempt_index"]

    assert [answer("Q-A", True), answer("Q-A", False), answer("Q-A", True)] == [1, 2, 3]
    # a different question is a different ordinal, not a continuation of the session
    assert answer("Q-B", True) == 1


def test_attempt_index_is_never_assigned_to_a_mirrored_attempt(db_session):
    """A replayed legacy row gets NULL: the ordinal would describe the import, not the learner."""
    from learning.practice import service as practice_service
    from learning.practice.refs import QuestionRef, QuestionSourceType
    from models import User
    from core.learning_context import ServiceNamespace
    from learning.spaces.exam_prep.context import cs408_context

    user = db_session.query(User).first()
    if user is None:
        user = User(username=f"s6mirror{uuid.uuid4().hex[:8]}", hashed_password="x",
                    is_active=True)
        db_session.add(user)
        db_session.commit()
    ctx = cs408_context(user, module_key="operating_system", knowledge_point_id="2.1")
    session, _ = practice_service.ensure_legacy_session(
        db_session, user, ServiceNamespace.EXAM_PREP, source_type="exam_practice_attempt",
        source_session_key=uuid.uuid4().int % 100000, started_at=datetime(2026, 9, 1),
        context=ctx)
    result = practice_service.record_attempt(
        db_session, user, session,
        QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                    source_id=f"mirror-{uuid.uuid4().hex[:6]}",
                    service_namespace=ServiceNamespace.EXAM_PREP,
                    context={"subject_key": "operating_system",
                             "exam_module_id": "operating_system"}),
        answer="A", correct=True, submitted_at=datetime(2026, 9, 1), context=ctx,
        source=practice_service.SourceIdentity("exam_practice_attempt",
                                               uuid.uuid4().hex[:8], "k:0"))
    assert result.attempt.attempt_index is None


def test_the_recorded_index_reaches_the_canonical_event(client, db_session):
    """The fact must survive the trip from the attempt to the event stream."""
    from data_plane.models import LearningEvent

    user = register_and_login(client, f"s6ev{uuid.uuid4().hex[:8]}")
    assert user
    session = client.post("/practice/sessions",
                          json={"service_namespace": "exam_prep", "context": CS408_CTX})
    sid = session.json()["id"]
    qid = f"Q-EV-{uuid.uuid4().hex[:6]}"
    for _ in range(2):
        client.post(f"/practice/sessions/{sid}/attempts", json={
            "question_source_type": "static_question_bank", "question_source_id": qid,
            "answer": "A", "correct": True, "question_context": CS408_CTX})

    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.question_id == qid)
              .order_by(LearningEvent.occurred_at.asc()).all())
    assert [e.attempt_index for e in events] == [1, 2], [e.attempt_index for e in events]


def test_a_duration_without_a_boundary_is_still_refused(client):
    """The S5 rule survives the S6 activation: activation did not loosen a guard."""
    user = register_and_login(client, f"s6dur{uuid.uuid4().hex[:8]}")
    assert user
    session = client.post("/practice/sessions",
                          json={"service_namespace": "exam_prep", "context": CS408_CTX})
    sid = session.json()["id"]
    refused = client.post(f"/practice/sessions/{sid}/attempts", json={
        "question_source_type": "static_question_bank", "question_source_id": "Q-D",
        "answer": "A", "correct": True, "question_context": CS408_CTX,
        "telemetry": {"duration_ms": 4200, "duration_source": "UNAVAILABLE"}})
    assert refused.status_code == 400
    assert "duration" in refused.json()["detail"].lower()


# ============================================================ PART I — coverage audit

def _seed_questions(db, module: str, pairs) -> None:
    """Insert active questions with the given stored concept ids. Test-only."""
    from models import ExamQuestionBank

    for knowledge_point_id, count in pairs:
        for _ in range(count):
            db.add(ExamQuestionBank(subject_key=module, subject_name=module,
                                    source_type="chapter", visibility="public",
                                    knowledge_point_id=knowledge_point_id,
                                    stem="x", is_active=True))
    db.commit()


def test_concept_coverage_is_measured_against_the_canonical_seeds(db_session):
    """The three levels, on content whose answers are known by construction.

    Measured as a DELTA: the whole test session shares one database, and other modules may
    have added rows to the same bank.
    """
    from science import concept_coverage

    module = "operating_system"
    before = concept_coverage.question_bank_coverage(
        db_session, modules=(module,))["per_module"][module]

    _seed_questions(db_session, module, [("1.1", 3), ("1.1 操作系统的基本特征", 2), ("", 1)])

    report = concept_coverage.question_bank_coverage(db_session, modules=(module,))
    row = report["per_module"][module]
    assert report["measured_against"].startswith("backend/seed_data/knowledge_maps")
    assert "NOT_PERFORMED" in report["repair"]
    assert row["questions"] == row["concept"] + row["chapter"] + row["module_only"]
    assert row["questions"] - before["questions"] == 6
    assert row["concept"] - before["concept"] == 3
    # the id that embeds its title is NOT the canonical leaf code: chapter at best
    assert row["chapter"] - before["chapter"] == 2
    assert row["module_only"] - before["module_only"] == 1


def test_inactive_questions_are_excluded_from_the_audit(db_session):
    from models import ExamQuestionBank
    from science import concept_coverage

    db_session.add(ExamQuestionBank(subject_key="data_structure", subject_name="data_structure",
                                    source_type="chapter", visibility="public",
                                    knowledge_point_id="1.1", stem="x", is_active=False))
    db_session.commit()
    active = concept_coverage.question_bank_coverage(
        db_session, modules=("data_structure",))["per_module"]["data_structure"]
    everything = concept_coverage.question_bank_coverage(
        db_session, modules=("data_structure",), active_only=False)["per_module"]["data_structure"]
    assert everything["questions"] == active["questions"] + 1


def test_a_near_match_is_not_a_concept():
    """The rule the audit exists to detect: '<code> <title>' is not a canonical leaf code."""
    from science import concept_coverage

    concepts = {"seed_present": True, "chapters": {"1"}, "concepts": {"1.1", "1.2"}}
    assert concept_coverage.level_of("1.1", concepts)[0] == "concept"
    assert concept_coverage.level_of("1.1 some title", concepts) == (
        "chapter", concept_coverage.UNRESOLVED_NOT_A_LEAF)
    assert concept_coverage.level_of("", concepts) == (
        "module_only", concept_coverage.UNRESOLVED_NO_CODE)
    assert concept_coverage.level_of("9.9", concepts)[0] == "module_only"


def test_a_module_without_a_seed_is_reported_rather_than_counted(db_session):
    from science import concept_coverage

    report = concept_coverage.question_bank_coverage(db_session, modules=("no_such_module",))
    row = report["per_module"]["no_such_module"]
    assert row["seed_present"] is False
    assert row["concept"] == 0


# ============================================================ PART H — dataset contract

def test_dataset_carries_every_required_factual_field(client, db_session):
    from science import kt_dataset

    user = register_and_login(client, f"s6ds{uuid.uuid4().hex[:8]}")
    assert user
    session = client.post("/practice/sessions",
                          json={"service_namespace": "exam_prep", "context": CS408_CTX})
    sid = session.json()["id"]
    client.post(f"/practice/sessions/{sid}/attempts", json={
        "question_source_type": "static_question_bank",
        "question_source_id": f"Q-DS-{uuid.uuid4().hex[:6]}",
        "answer": "A", "correct": True, "question_context": CS408_CTX})

    body = kt_dataset.build(db_session, service_namespace="exam_prep")
    sequences = body["sequences"]
    assert sequences, "no sequences were exported"
    sequence, sample = sequences[0], sequences[0]["interactions"][0]
    # the sequence is one learner's ordered interactions with one concept
    for field in ("learner_ref", "concept_key", "concept_level", "exam_subject_id"):
        assert field in sequence, field
    # the interaction is what happened, and carries its own module and source
    for field in ("attempt_ref", "occurred_at", "item_ref", "exam_module_id",
                  "source_type", "correct"):
        assert field in sample, field
    assert isinstance(sample["correct"], bool)
    assert isinstance(sample["occurred_at"], float)


def test_the_dataset_carries_no_pii_and_no_content(db_session):
    from science import kt_dataset

    body = kt_dataset.build(db_session, service_namespace="exam_prep")
    # FORBIDDEN_FIELDS is itself a list inside the body, so the check is on the ROWS
    rows = json.dumps({"sequences": body["sequences"]}, ensure_ascii=False)
    for forbidden in kt_dataset.FORBIDDEN_FIELDS:
        assert forbidden not in rows, forbidden
    for sequence in body["sequences"]:
        # a fixed-domain digest, never a name or a raw id
        assert len(sequence["learner_ref"]) == 16
        assert sequence["learner_ref"].isalnum()


def test_a_fact_without_a_native_concept_is_excluded_not_grouped(db_session):
    """Grouping at the subject would teach a concept boundary no fact asserts."""
    from science import kt_dataset

    assert kt_dataset.EXCLUDED_NO_CONCEPT in kt_dataset.build(
        db_session, service_namespace="exam_prep")["exclusion_semantics"]


def test_track_is_reported_from_the_catalog_and_never_from_a_fact(db_session):
    from science import kt_dataset

    body = kt_dataset.build(db_session, service_namespace="exam_prep")
    assert isinstance(body["scope"]["exam_track_ids"], list)
    # no interaction may carry a track: it is the learner's bundle, not a fact attribute
    for sequence in body["sequences"]:
        for interaction in sequence["interactions"]:
            assert "exam_track_id" not in interaction


def test_the_dataset_hash_is_a_hash_of_its_own_body(db_session):
    from science import kt_dataset

    body = kt_dataset.build(db_session, service_namespace="exam_prep")
    without = {k: v for k, v in body.items() if k != "dataset_hash"}
    recomputed = hashlib.sha256(
        json.dumps(without, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    assert body["dataset_hash"] == recomputed


# ============================================================ PART K — split policy

def test_the_split_never_puts_one_learner_in_two_splits():
    from science import kt_dataset

    sequences = [{"learner_ref": f"{i:016x}", "interactions": [{}] * 3} for i in range(400)]
    split = kt_dataset.user_grouped_split({"sequences": sequences})
    assert split["overlap_is_empty"] is True
    assert split["learner_overlap_between_splits"] == []
    assert split["counts"]["train"]["learners"] > split["counts"]["test"]["learners"]


def test_the_split_is_deterministic_and_stable_as_the_cohort_grows():
    from science import kt_dataset

    first = [{"learner_ref": f"{i:016x}", "interactions": [{}]} for i in range(50)]
    before = {s["learner_ref"]: kt_dataset.split_of(s["learner_ref"]) for s in first}
    # a new learner arriving must not move anyone who was already there
    grown = first + [{"learner_ref": f"{i:016x}", "interactions": [{}]}
                     for i in range(50, 120)]
    kt_dataset.user_grouped_split({"sequences": grown})
    after = {ref: kt_dataset.split_of(ref) for ref in before}
    assert before == after


def test_the_split_trains_nothing():
    from science import kt_dataset

    split = kt_dataset.user_grouped_split({"sequences": []})
    assert split["trained"] is False
    assert "NOT DEFINED" in split["temporal_evaluation"]
    assert split["temporal_evaluation"]


# ============================================================ PART J — export determinism

_EXPORT_PROBE = r'''
import json, os, sys
sys.path.insert(0, os.environ["S6_BACKEND"])
sys.path.insert(0, os.environ["S6_REPO"])
from scripts.export_kt_dataset import build_export, canonical_json
export = build_export(database_url=os.environ["DATABASE_URL"],
                      service_namespace="exam_prep", with_split=True)
sys.stdout.write(canonical_json(export) + "\n")
'''


@pytest.fixture(scope="module")
def exportable_db():
    """A TEMP database with real, product-path interactions. Never the real app.db."""
    if not PYTHON.exists():
        pytest.skip("backend venv python is not present on this machine")
    workdir = Path(tempfile.mkdtemp(prefix="s6-export-"))
    database = workdir / "export.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}",
           "UPLOAD_ROOT": str(workdir / "uploads"), "STUDENT_TWIN_MODE": "internal"}

    seed = r'''
import os, sys
sys.path.insert(0, os.environ["S6_BACKEND"])
import main
from datetime import datetime, timedelta
from database import SessionLocal
from models import User
from core.learning_context import ServiceNamespace
from learning.practice import service as ps
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.exam_prep.context import cs408_context

db = SessionLocal()
for ui in range(4):
    user = User(username="exp%d" % ui, hashed_password="x", is_active=True)
    db.add(user); db.commit()
    for qi in range(5):
        ctx = cs408_context(user, module_key="operating_system", knowledge_point_id="2.1")
        session, _ = ps.ensure_legacy_session(
            db, user, ServiceNamespace.EXAM_PREP, source_type="exam_practice_attempt",
            source_session_key=5000 + ui * 10 + qi,
            started_at=datetime(2026, 9, 10) + timedelta(days=ui, hours=qi), context=ctx)
        ps.record_attempt(
            db, user, session,
            QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                        source_id="Q-%d" % qi, service_namespace=ServiceNamespace.EXAM_PREP,
                        context={"subject_key": "operating_system",
                                 "exam_module_id": "operating_system",
                                 "knowledge_point_id": "2.1"}),
            answer="A", correct=bool(qi % 2),
            submitted_at=datetime(2026, 9, 10) + timedelta(days=ui, hours=qi),
            context=ctx,
            source=ps.SourceIdentity("exam_practice_attempt",
                                     "%d-%d" % (ui, qi), "q%d:0" % qi))
db.close()
'''
    seeded = subprocess.run([str(PYTHON), "-c", seed],
                            env={**env, "S6_BACKEND": str(BACKEND)},
                            capture_output=True, text=True, cwd=str(BACKEND))
    assert seeded.returncode == 0, seeded.stderr[-3000:]
    yield database
    import shutil
    shutil.rmtree(workdir, ignore_errors=True)


def _run_export(database: Path) -> str:
    completed = subprocess.run([str(PYTHON), "-c", _EXPORT_PROBE],
                               env={**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}",
                                    "S6_BACKEND": str(BACKEND), "S6_REPO": str(REPO_ROOT)},
                               capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert completed.returncode == 0, completed.stderr[-4000:]
    return completed.stdout


def test_the_same_snapshot_exports_byte_identically(exportable_db):
    first = _run_export(exportable_db)
    second = _run_export(exportable_db)
    assert first == second
    assert first.strip()


def test_the_export_contains_real_interactions_and_no_wall_clock(exportable_db):
    export = json.loads(_run_export(exportable_db))
    dataset = export["dataset"]
    assert dataset["interaction_count"] > 0
    assert dataset["sequence_count"] > 0
    assert export["split"]["overlap_is_empty"] is True
    # a wall clock inside the hashed body would make the hash meaningless
    assert "generated_at" not in dataset
    assert "exported_at" not in export


def test_the_export_hash_covers_every_field_it_should(exportable_db):
    export = json.loads(_run_export(exportable_db))
    recorded = export["export_hash"]
    without = {k: v for k, v in export.items() if k != "export_hash"}
    recomputed = hashlib.sha256(
        json.dumps(without, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    assert recorded == recomputed


# ============================================================ PARTS L/M/N/O — modes

def test_evidence_reliability_stays_shadow_and_the_scaler_gate_stays_open():
    """PARTS L/M: the gate decides the mode, so the two can never drift apart."""
    from science import evidence_reliability as er

    assert er.production_mode() == "SHADOW_NOT_USER_VISIBLE"
    gate = er.scaler_gate()
    assert gate, "the scaler gate carries no evidence"
    # no standardizer may be applied: the gate is what makes the surface closed
    assert er.SCALER_RECOVERY_METHOD not in er.SCALER_GATE_ACCEPTED_METHODS
    assert er.blockers(), "a blocked component must say why"


def test_no_calibration_threshold_has_been_invented():
    from science import evidence_reliability as er

    assert er.SCIENTIFIC_THRESHOLD is None


def test_the_scientific_component_states_are_unchanged_by_s6():
    from science import capabilities

    rows = {c["component"]: c for c in capabilities.summary()["components"]}
    # the runtime vocabulary for the SSOT's USER_VISIBLE_PREVIEW
    assert rows["student_twin"]["mode"] == "PREVIEW"
    assert rows["student_twin"]["user_visible"] is True
    for component in ("learner_state", "misconception_v2", "evidence_reliability"):
        assert rows[component]["mode"] == "SHADOW_NOT_USER_VISIBLE", component
        assert rows[component]["user_visible"] is False, component
    assert rows["tutor_policy"]["mode"] == "SHADOW"
    assert rows["tutor_policy"]["user_visible"] is False
    assert capabilities.summary()["totals"]["user_visible"] == 1


def test_no_component_increases_its_authority():
    """PARTS L/N/O: no promotion in S6 — nothing may control a decision or write a fact."""
    from science import capabilities

    for row in capabilities.summary()["components"]:
        assert row["controls_product_decision"] is False, row["component"]
        assert row["writes_learner_fact"] is False, row["component"]


def test_raw_evidence_features_are_carried_without_a_scaler():
    """PART M: the measurable features are described; no standardizer is applied anywhere."""
    from science import evidence_reliability as er

    assert er.STANDARDIZATION, "the standardization contract must stay documented"
    assert er.PRODUCT_FEATURE_COMPATIBILITY == "INCOMPATIBLE"
    statuses = {f["name"]: f["product_status"] for f in er.FEATURE_AVAILABILITY}
    assert statuses["y"] == er.AVAILABLE_NOW
    assert statuses["attempt_gt1"] == er.CAN_BE_COLLECTED_FACTUALLY
    assert statuses["has_bottom_hint"] == er.NOT_AVAILABLE
    assert statuses["b_s"] == er.SEMANTICALLY_INCOMPATIBLE


def test_collecting_a_quantity_is_not_the_same_as_satisfying_the_feature():
    """S6 starts producing an attempt ordinal; it does NOT claim the ER feature is usable.

    ``attempt_gt1`` counts re-attempts WITHIN one problem presentation in the source's
    domain. The product's ``attempt_index`` counts attempts on the same QUESTION across
    sessions. The two are related and are not the same quantity, so the classification
    stays where S5 froze it and the semantic question is left to be answered on its own
    evidence rather than assumed away.
    """
    import learning.practice.telemetry as telemetry
    from science import evidence_reliability as er

    assert "SAME question" in telemetry.ATTEMPT_INDEX_SEMANTICS
    assert "NOT a session position" in telemetry.ATTEMPT_INDEX_SEMANTICS
    assert "NOT a paper-sitting number" in telemetry.ATTEMPT_INDEX_SEMANTICS
    row = next(f for f in er.FEATURE_AVAILABILITY if f["name"] == "attempt_gt1")
    assert row["product_status"] == er.CAN_BE_COLLECTED_FACTUALLY
    assert er.SCALER_RECOVERY_METHOD not in er.SCALER_GATE_ACCEPTED_METHODS


def test_student_twin_input_eligibility_is_unchanged():
    """PART N: the same one predicate still decides what may feed the preview."""
    from data_plane import eligibility

    rule = eligibility.student_twin_input_eligibility
    assert rule(answer="A", correct=True, event_type="question_answered").eligible is True
    assert rule(answer="", correct=True, event_type="question_answered").eligible is False
    assert rule(answer="A", correct=None, event_type="question_answered").eligible is False
    assert rule(answer="A", correct=True, judge="self_review",
                event_type="question_answered").eligible is False
    assert rule(answer="A", correct=True, event_type="course_learning").eligible is False
    # 0/1 smuggled in as ints is NOT a boolean verdict
    assert rule(answer="A", correct=1, event_type="question_answered").eligible is False
