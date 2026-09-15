"""Data Producer foundation tests (eligibility, inference, worker, runtime client)."""
import json
import time
from types import SimpleNamespace

import pytest

import database
from data_plane import eligibility, inference, runtime_client, worker
from data_plane import models as dp_models


# --------------------------------------------------------------------------- #
# Eligibility (pure)
# --------------------------------------------------------------------------- #
def test_13_component_registry():
    assert len(eligibility.COURSE_PRACTICE_MATRIX) == 13


def test_student_twin_eligible():
    r = eligibility.evaluate("student_twin", {})
    assert r["requirement_status"] == "READY"
    assert r["scientific_applicability"] == "SUPPORTED"
    assert r["eligibility_status"] == "ELIGIBLE"


def test_blocked_component_ineligible():
    for cid in ("difficulty_prior", "memory", "irt", "misconception_v2"):
        r = eligibility.evaluate(cid, {})
        assert r["eligibility_status"] == "INELIGIBLE"


def test_partial_not_eligible():
    for cid in ("concept_verifier", "evidence_reliability", "learner_state"):
        r = eligibility.evaluate(cid, {})
        assert r["requirement_status"] == "PARTIAL"
        assert r["eligibility_status"] == "INELIGIBLE"


def test_not_applicable_ineligible():
    for cid in ("domestic_registry", "execution_router"):
        assert eligibility.evaluate(cid, {})["eligibility_status"] == "INELIGIBLE"


def test_eligible_components_only_student_twin():
    assert eligibility.eligible_components({}) == ["student_twin"]


# --------------------------------------------------------------------------- #
# ModelVersion + Inference (DB)
# --------------------------------------------------------------------------- #
def test_student_twin_model_version_idempotent(db_session):
    mv1 = inference.ensure_student_twin_model_version(db_session)
    mv2 = inference.ensure_student_twin_model_version(db_session)
    assert mv1.model_version_id == mv2.model_version_id == inference.STUDENT_TWIN_MODEL_VERSION_ID
    assert mv1.component_id == "student_twin"
    assert mv1.runtime_release_id == "zhixue-runtime-v1-phase1gr-p1"
    assert mv1.product_role == "DATA_PRODUCER"
    assert db_session.query(dp_models.ModelVersion).count() == 1


def test_inference_run_id_deterministic():
    a = inference.inference_run_id("e1", "student_twin", "mv", "h1")
    b = inference.inference_run_id("e1", "student_twin", "mv", "h1")
    assert a == b
    assert len(a) == 36


def test_inference_run_idempotent(db_session):
    run_id = inference.inference_run_id("e1", "student_twin", "mv", "h1")
    ok1 = inference.insert_inference_run(db_session, run_id, "e1", "student_twin", "mv", "h1",
                                         "ELIGIBLE", "SUCCESS")
    ok2 = inference.insert_inference_run(db_session, run_id, "e1", "student_twin", "mv", "h1",
                                         "ELIGIBLE", "SUCCESS")
    assert ok1 is True
    assert ok2 is False  # idempotent
    assert db_session.query(dp_models.ModelInferenceRun).count() == 1


def test_ineligible_not_attempted(db_session):
    run_id = inference.inference_run_id("e2", "student_twin", "mv", "h2")
    inference.insert_inference_run(db_session, run_id, "e2", "student_twin", "mv", "h2",
                                   "INELIGIBLE", "NOT_ATTEMPTED")
    run = db_session.query(dp_models.ModelInferenceRun).filter_by(inference_run_id=run_id).first()
    assert run.execution_status == "NOT_ATTEMPTED"


def test_prediction_idempotent(db_session):
    run_id = "run-x"
    pred_id = inference.prediction_id(run_id, "student_twin_snapshot", "u1")
    ok1 = inference.insert_prediction(db_session, pred_id, run_id, "e1", "student_twin", "mv",
                                      "student_twin_snapshot", target_ref="u1",
                                      score_semantics="deterministic_student_twin_state", payload={"mastery": 0.5})
    ok2 = inference.insert_prediction(db_session, pred_id, run_id, "e1", "student_twin", "mv",
                                      "student_twin_snapshot", target_ref="u1",
                                      score_semantics="deterministic_student_twin_state", payload={"mastery": 0.5})
    assert ok1 is True
    assert ok2 is False


# --------------------------------------------------------------------------- #
# LearningEvent -> contract-v1 event mapping (pure)
# --------------------------------------------------------------------------- #
def _le(**kw):
    base = dict(event_id="e1", user_id=7, source_user_ref="alice", occurred_at=1000.0,
                source_type="course_practice", course_id=None, subject_key="math",
                question_id="q1", answer="B", correct=True, response_time_ms=None,
                attempt_no=None, knowledge_point_ref_json=json.dumps({"type": "FREE_TEXT", "value": "kp1"}))
    base.update(kw)
    return SimpleNamespace(**base)


def test_map_event_optional_fields_not_fabricated():
    m = runtime_client.map_learning_event(_le())
    assert m["response_time_ms"] is None
    assert m["attempt_no"] is None
    assert m["hints"] is None  # not recorded -> None, not 0


def test_map_event_concept_ref_provenance():
    m = runtime_client.map_learning_event(_le())
    assert m["concept_ref"] == "kp1"  # FREE_TEXT value, NOT a scientific ontology id
    assert m["activity_type"] == "PRACTICE"
    assert m["item_id"] == "q1"


def test_map_event_concept_null_when_missing():
    m = runtime_client.map_learning_event(_le(knowledge_point_ref_json=None))
    assert m["concept_ref"] is None


# --------------------------------------------------------------------------- #
# runtime client (pure, no real HTTP)
# --------------------------------------------------------------------------- #
def test_build_request_contract_shape():
    target = _le()
    history = [_le(event_id="e0", occurred_at=500.0, correct=False), target]
    req = runtime_client.build_request(target, history)
    assert req["contract_version"] == 1
    assert req["runtime_release_id"] == "zhixue-runtime-v1-phase1gr-p1"
    assert req["user_ref"] == "7"
    assert req["target_event_id"] == "e1"
    assert [e["event_id"] for e in req["events"]] == ["e0", "e1"]


# --------------------------------------------------------------------------- #
# Worker (DB, no runtime execution)
# --------------------------------------------------------------------------- #
def test_worker_not_enabled_skips(monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "false")
    report = worker.run_once(database.SessionLocal)
    assert report["skipped_not_enabled"] is True
    assert report["events_inferred"] == 0


def test_worker_enabled_flag_separate():
    # DATA_PLANE_WRITE_ENABLED and DATA_PRODUCER_EXECUTION_ENABLED are distinct
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "true")
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "false")
    assert worker.execution_enabled() is False
    monkeypatch.undo()


# --------------------------------------------------------------------------- #
# Worker (DB + fake runtime client)
# --------------------------------------------------------------------------- #
class _FakeRuntimeClient:
    """Stand-in for the Scientific Runtime Service HTTP client (no real HTTP)."""
    targets: list = []     # target_event_id per call, in order
    requests: list = []    # (target_event_id, [event_id, ...]) per call, in order
    fail_users: set = set()

    def __init__(self, *args, **kwargs):
        pass

    def infer(self, request):
        user = request["user_ref"]
        if user in _FakeRuntimeClient.fail_users:
            raise RuntimeError(f"injected failure for user {user}")
        event_ids = [e["event_id"] for e in request["events"]]
        _FakeRuntimeClient.targets.append(request["target_event_id"])
        _FakeRuntimeClient.requests.append((request["target_event_id"], event_ids))
        return {
            "contract_version": 1,
            "request_id": request["request_id"],
            "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1",
            "component_id": "student_twin",
            "scientific_source_class": "ORIGINAL_ARCHIVE_VERIFIED",
            "scientific_source_commit": "a16efa27aac90d9c8d8d9ee703aefe5919f4839e",
            "target_event_id": request["target_event_id"],
            "replayed_events": len(request["events"]),
            "state": {"user_id": user, "event_count": len(request["events"])},
            "latency_ms": 1.0,
        }


def _make_event(session, event_id, user_id, correct=True, occurred_at=1000.0, question_id="q1"):
    ev = dp_models.LearningEvent(
        event_id=event_id, event_schema_version=2, event_type="course_practice",
        event_granularity="ITEM_LEVEL", source_type="course_practice",
        source_attempt_id=f"att-{event_id}", source_item_key=f"{question_id}:0",
        source_item_index=0, user_id=user_id, source_user_ref=f"user-{user_id}",
        service_key="course_learning", course_id=None, subject_key="math",
        question_id=question_id,
        knowledge_point_ref_json=json.dumps({"type": "FREE_TEXT", "value": "kp1"}),
        item_snapshot_json=json.dumps({"question_id": question_id, "question_text": "stem"}),
        item_content_hash="h", answer="B", correct=correct, score=None,
        response_time_ms=None, attempt_no=None, occurred_at=occurred_at,
        ingested_at=time.time(), source_payload_version=1,
        idempotency_key=f"course_practice:att-{event_id}:{question_id}:0",
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="FULL",
        snapshot_missing_fields_json="[]",
    )
    session.add(ev)
    session.commit()
    return ev


@pytest.fixture
def clean_data_plane(db_session):
    """Isolate the worker tests: clear all data-plane tables before each test."""
    for model in (dp_models.ModelPrediction, dp_models.ModelInferenceRun,
                  dp_models.ModelVersion, dp_models.LearningOutcome, dp_models.LearningEvent):
        db_session.query(model).delete()
    db_session.commit()
    return db_session


def test_worker_once_creates_runs_and_predictions(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _FakeRuntimeClient.targets = []
    _make_event(clean_data_plane, "e-once-1", 1, correct=True, occurred_at=1000.0)
    _make_event(clean_data_plane, "e-once-2", 1, correct=False, occurred_at=2000.0)

    report = worker.run_once(database.SessionLocal)

    assert report["events_scanned"] == 2
    assert report["events_eligible"] == 2
    assert report["events_inferred"] == 2
    assert report["inference_runs_created"] == 2
    assert report["predictions_created"] == 2
    assert report["errors"] == 0
    # deterministic multi-event ordering (occurred_at asc, then event_id)
    assert _FakeRuntimeClient.targets == ["e-once-1", "e-once-2"]
    preds = (clean_data_plane.query(dp_models.ModelPrediction)
             .order_by(dp_models.ModelPrediction.event_id).all())
    assert [p.prediction_type for p in preds] == ["student_twin_snapshot", "student_twin_snapshot"]
    assert all(p.score_semantics == "deterministic_student_twin_state" for p in preds)


def test_worker_second_run_no_duplicates(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _make_event(clean_data_plane, "e-second-1", 1, correct=True)

    r1 = worker.run_once(database.SessionLocal)
    r2 = worker.run_once(database.SessionLocal)

    assert r1["inference_runs_created"] == 1
    assert r1["predictions_created"] == 1
    # second pass is fully idempotent: zero new rows
    assert r2["inference_runs_created"] == 0
    assert r2["predictions_created"] == 0
    assert clean_data_plane.query(dp_models.ModelInferenceRun).count() == 1
    assert clean_data_plane.query(dp_models.ModelPrediction).count() == 1


def test_worker_one_user_failure_does_not_break_others(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = {"2"}
    _FakeRuntimeClient.targets = []
    _make_event(clean_data_plane, "e-fail-1", 1, correct=True, occurred_at=1000.0)
    _make_event(clean_data_plane, "e-fail-2", 2, correct=True, occurred_at=2000.0)

    report = worker.run_once(database.SessionLocal)

    assert report["errors"] >= 1          # user 2's event failed
    assert _FakeRuntimeClient.targets == ["e-fail-1"]  # user 2 never inferred
    runs = clean_data_plane.query(dp_models.ModelInferenceRun).all()
    assert [r.event_id for r in runs] == ["e-fail-1"]  # user 1 still inferred


def test_worker_none_correct_not_fabricated(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _make_event(clean_data_plane, "e-none-1", 1, correct=None)

    report = worker.run_once(database.SessionLocal)

    assert report["events_scanned"] == 0    # None-outcome event is not even a target
    assert report["events_eligible"] == 0   # None outcome is not an observation
    assert report["events_inferred"] == 0
    assert clean_data_plane.query(dp_models.ModelInferenceRun).count() == 0
    assert clean_data_plane.query(dp_models.ModelPrediction).count() == 0


def test_worker_no_product_control(clean_data_plane, monkeypatch):
    from models import User

    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _make_event(clean_data_plane, "e-control-1", 1, correct=True)

    users_before = clean_data_plane.query(User).count()
    worker.run_once(database.SessionLocal)
    users_after = clean_data_plane.query(User).count()

    # DATA_PRODUCER never mutates product rows
    assert users_before == users_after
    pred = clean_data_plane.query(dp_models.ModelPrediction).first()
    # no score / label / rank that could drive a product decision
    assert pred.raw_score is None and pred.normalized_score is None
    assert pred.predicted_label is None and pred.rank is None
    assert pred.weak_label is False
    assert pred.score_semantics == "deterministic_student_twin_state"


# --------------------------------------------------------------------------- #
# Phase 6R semantic regression: target vs history separation
# --------------------------------------------------------------------------- #
def test_event_id_target_replays_prior_history(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _FakeRuntimeClient.requests = []
    _make_event(clean_data_plane, "e1", 1, correct=True, occurred_at=100.0)
    _make_event(clean_data_plane, "e2", 1, correct=True, occurred_at=200.0)
    _make_event(clean_data_plane, "e3", 1, correct=True, occurred_at=300.0)

    report = worker.run_once(database.SessionLocal, event_id="e3")

    assert report["events_inferred"] == 1
    # full history [e1,e2,e3], NOT [e3]
    assert _FakeRuntimeClient.requests == [("e3", ["e1", "e2", "e3"])]


def test_no_future_leakage(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _FakeRuntimeClient.requests = []
    _make_event(clean_data_plane, "e1", 1, correct=True, occurred_at=100.0)
    _make_event(clean_data_plane, "e2", 1, correct=True, occurred_at=200.0)
    _make_event(clean_data_plane, "e3", 1, correct=True, occurred_at=300.0)
    _make_event(clean_data_plane, "e4", 1, correct=True, occurred_at=400.0)  # future

    worker.run_once(database.SessionLocal, event_id="e3")

    assert _FakeRuntimeClient.requests == [("e3", ["e1", "e2", "e3"])]  # no e4


def test_other_users_excluded(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _FakeRuntimeClient.requests = []
    _make_event(clean_data_plane, "u1-e1", 1, correct=True, occurred_at=100.0)
    _make_event(clean_data_plane, "u2-e1", 2, correct=True, occurred_at=150.0)  # other user
    _make_event(clean_data_plane, "u1-e2", 1, correct=True, occurred_at=200.0)

    worker.run_once(database.SessionLocal, event_id="u1-e2")

    assert _FakeRuntimeClient.requests == [("u1-e2", ["u1-e1", "u1-e2"])]  # no u2


def test_same_timestamp_tie_break(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _FakeRuntimeClient.requests = []
    _make_event(clean_data_plane, "e-a", 1, correct=True, occurred_at=100.0)
    _make_event(clean_data_plane, "e-b", 1, correct=True, occurred_at=100.0)

    worker.run_once(database.SessionLocal, event_id="e-b")

    # same timestamp -> event_id tie-break, e-b is the boundary (e-a <= e-b)
    assert _FakeRuntimeClient.requests == [("e-b", ["e-a", "e-b"])]


def test_limit_does_not_truncate_history(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _FakeRuntimeClient.requests = []
    _make_event(clean_data_plane, "e1", 1, correct=True, occurred_at=100.0)
    _make_event(clean_data_plane, "e2", 1, correct=True, occurred_at=200.0)
    _make_event(clean_data_plane, "e3", 1, correct=True, occurred_at=300.0)

    report = worker.run_once(database.SessionLocal, limit=1)

    # limit=1 -> only ONE target (e1), but e1's history is still [e1]
    assert report["events_inferred"] == 1
    assert _FakeRuntimeClient.requests == [("e1", ["e1"])]


def test_hash_history_sensitive():
    e0 = _le(event_id="e0", occurred_at=50.0, correct=True)
    e1 = _le(event_id="e1", occurred_at=100.0, correct=True)
    e2 = _le(event_id="e2", occurred_at=200.0, correct=True)
    h_short = runtime_client.canonical_input_hash(runtime_client.build_request(e2, [e1, e2]))
    h_long = runtime_client.canonical_input_hash(runtime_client.build_request(e2, [e0, e1, e2]))
    assert h_short != h_long  # different history -> different hash


def test_hash_stable_same_input():
    e1 = _le(event_id="e1", occurred_at=100.0, correct=True)
    e2 = _le(event_id="e2", occurred_at=200.0, correct=True)
    req = runtime_client.build_request(e2, [e1, e2])
    assert runtime_client.canonical_input_hash(req) == runtime_client.canonical_input_hash(req)


def test_event_id_rerun_idempotent(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _FakeRuntimeClient)
    _FakeRuntimeClient.fail_users = set()
    _make_event(clean_data_plane, "e1", 1, correct=True, occurred_at=100.0)
    _make_event(clean_data_plane, "e2", 1, correct=True, occurred_at=200.0)

    r1 = worker.run_once(database.SessionLocal, event_id="e2")
    r2 = worker.run_once(database.SessionLocal, event_id="e2")

    assert r1["inference_runs_created"] == 1
    assert r2["inference_runs_created"] == 0   # same history -> same run id -> no new row
    assert r2["predictions_created"] == 0
    assert clean_data_plane.query(dp_models.ModelInferenceRun).count() == 1
    assert clean_data_plane.query(dp_models.ModelPrediction).count() == 1
