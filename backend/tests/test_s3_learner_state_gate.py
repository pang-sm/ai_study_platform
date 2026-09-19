"""ACCEL_SPRINT_S3 — learner_state productization + producer outage hardening.

Two independent contracts are held here.

PART A — the producer's runtime-outage circuit breaker. A run makes one blocking runtime
call per eligible target; when the runtime is confirmed unavailable that is the SAME wait
repeated per target, so the run stops at the first one. The stop must be honest: no faked
prediction, the failed target NOT marked scientifically processed, the remaining targets
untouched, and the next run free to retry. No default ``--limit`` is introduced and
healthy-runtime processing is unchanged.

PART B–M — learner_state. A real trained knowledge-tracing model whose output is
P(correct on the learner's NEXT response). The product CANNOT honestly form its input
(the model reads an index in its own ontology; the product has CS408 knowledge points and
no mapping exists), so the product surface is SHADOW_NOT_USER_VISIBLE and produces no
number. These tests hold that gate rather than lowering it.

Doubles sit below the HTTP/runtime boundary only.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from conftest import register_and_login
from fastapi.testclient import TestClient

from core.learning_context import ServiceNamespace
from data_plane import eligibility, runtime_client, worker
from data_plane import models as dp_models
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from models import User
from science import client as sci_client
from science import learner_state
from science.contract import LearnerStatePreviewResponse

EXAM = ServiceNamespace.EXAM_PREP.value
MOMENT = datetime(2026, 9, 19, 6, 30, 0)


# ================================================================ helpers

def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def cs408_attempt(db, user, qid, *, answer="A", correct=True, judge=None,
                  source_id=None, submitted_at=MOMENT):
    """One real CS408 chapter-practice attempt, mirrored into the canonical facts."""
    from learning.spaces.exam_prep.context import cs408_context
    source_id = source_id or f"s3-{user.id}-{qid}"
    context = cs408_context(user, module_key="operating_system", knowledge_point_id=None)
    session, _ = practice_service.ensure_legacy_session(
        db, user, ServiceNamespace.EXAM_PREP, source_type="exam_practice_attempt",
        source_session_key=abs(hash(source_id)) % 100000, started_at=submitted_at,
        context=context)
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id=qid, service_namespace=ServiceNamespace.EXAM_PREP,
                      context={"subject_key": "operating_system",
                               "exam_module_id": "operating_system"})
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=correct, submitted_at=submitted_at,
        context=context, result={"judge": judge, "standard_answer": "B"},
        source=practice_service.SourceIdentity("exam_practice_attempt", source_id,
                                               f"{qid}:0"))


def _learning_event(session, event_id, user_id, *, correct=True, occurred_at=1000.0):
    ev = dp_models.LearningEvent(
        event_id=event_id, event_schema_version=2, event_type="question_answered",
        event_granularity="ITEM_LEVEL", source_type="exam_practice_attempt",
        source_attempt_id=f"att-{event_id}", source_item_key=f"q-{event_id}:0",
        source_item_index=0, user_id=user_id, source_user_ref=f"user-{user_id}",
        service_key=EXAM, course_id=None, subject_key="operating_system",
        question_id=f"q-{event_id}",
        knowledge_point_ref_json=json.dumps({"value": "kp1"}),
        item_snapshot_json=json.dumps({"question_id": f"q-{event_id}"}),
        item_content_hash="h", answer="A", correct=correct, score=None,
        response_time_ms=None, attempt_no=None, occurred_at=occurred_at,
        ingested_at=occurred_at, source_payload_version=1,
        idempotency_key=f"s3:{event_id}", snapshot_capture_mode="LIVE_EMITTER",
        snapshot_completeness="FULL", snapshot_missing_fields_json="[]")
    session.add(ev)
    session.commit()
    return ev


@pytest.fixture
def clean_data_plane(db_session):
    """Clear the data-plane tables BEFORE and AFTER each test.

    The breaker tests run the real worker, which writes inference rows. Restoring the
    tables afterwards is part of the contract, not tidiness: a later test that asserts a
    GLOBAL row count (``test_data_producer.test_inference_run_idempotent``) would
    otherwise see this file's leftovers and fail.
    """
    def _clear():
        for model in (dp_models.ModelPrediction, dp_models.ModelInferenceRun,
                      dp_models.ModelVersion, dp_models.LearningOutcome,
                      dp_models.LearningEvent):
            db_session.query(model).delete()
        db_session.commit()

    _clear()
    yield db_session
    _clear()


# ================================================================ PART A — circuit breaker

class _OutageClient:
    """Raises the CONFIRMED-OUTAGE class after ``fail_after`` successful calls."""

    calls: list = []
    fail_after: int = 0

    def __init__(self, *args, **kwargs):
        pass

    def infer(self, request):
        _OutageClient.calls.append(request["target_event_id"])
        if len(_OutageClient.calls) > _OutageClient.fail_after:
            raise runtime_client.RuntimeUnavailableError(
                "runtime service unavailable: runtime unreachable")
        return {
            "contract_version": 1, "request_id": request["request_id"],
            "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1",
            "component_id": "student_twin",
            "scientific_source_class": "ORIGINAL_ARCHIVE_VERIFIED",
            "scientific_source_commit": "a16efa27aac90d9c8d8d9ee703aefe5919f4839e",
            "target_event_id": request["target_event_id"],
            "replayed_events": len(request["events"]),
            "state": {"user_id": request["user_ref"]}, "latency_ms": 1.0,
        }


def test_outage_stops_the_run_at_the_first_confirmed_unavailable(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _OutageClient)
    _OutageClient.calls = []
    _OutageClient.fail_after = 1          # first target succeeds, runtime dies after
    for i in range(4):
        _learning_event(clean_data_plane, f"cb-{i}", 1, occurred_at=1000.0 + i)

    report = worker.run_once(__import__("database").SessionLocal)

    assert report["runtime_unavailable"] is True
    assert report["outage"]["component"] == "student_twin"
    assert report["outage"]["target_event_id"] == "cb-1"
    # 1 success + 1 failure; the remaining 2 were never attempted
    assert _OutageClient.calls == ["cb-0", "cb-1"]
    assert report["events_inferred"] == 1
    assert report["targets_not_attempted"] == 2
    assert report["errors"] == 1


def test_outage_fakes_no_prediction_and_leaves_the_failed_item_unprocessed(
        clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _OutageClient)
    _OutageClient.calls = []
    _OutageClient.fail_after = 0          # the runtime is down from the very first target
    _learning_event(clean_data_plane, "cb-x", 1)

    report = worker.run_once(__import__("database").SessionLocal)

    assert report["runtime_unavailable"] is True
    assert report["events_inferred"] == 0
    assert report["predictions_created"] == 0
    assert report["inference_runs_created"] == 0
    # the failed target is NOT marked scientifically processed: no row of any kind
    assert clean_data_plane.query(dp_models.ModelInferenceRun).count() == 0
    assert clean_data_plane.query(dp_models.ModelPrediction).count() == 0


def test_next_run_retries_after_the_runtime_returns(clean_data_plane, monkeypatch):
    """Nothing is lost by stopping — the deferred work is picked up by the next run."""
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _OutageClient)
    for i in range(3):
        _learning_event(clean_data_plane, f"cb-r{i}", 1, occurred_at=1000.0 + i)

    _OutageClient.calls = []
    _OutageClient.fail_after = 0
    first = worker.run_once(__import__("database").SessionLocal)
    assert first["runtime_unavailable"] is True
    assert first["events_inferred"] == 0

    _OutageClient.calls = []
    _OutageClient.fail_after = 99          # runtime healthy again
    second = worker.run_once(__import__("database").SessionLocal)

    assert second["runtime_unavailable"] is False
    assert second["outage"] is None
    assert second["events_inferred"] == 3
    assert len(_OutageClient.calls) == 3


def test_healthy_producer_semantics_unchanged(clean_data_plane, monkeypatch):
    """With a healthy runtime the run is byte-for-byte the pre-S3 behaviour."""
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _OutageClient)
    _OutageClient.calls = []
    _OutageClient.fail_after = 999
    for i in range(3):
        _learning_event(clean_data_plane, f"ok-{i}", 1, occurred_at=1000.0 + i)

    report = worker.run_once(__import__("database").SessionLocal)

    assert report["runtime_unavailable"] is False
    assert report["errors"] == 0
    assert report["targets_not_attempted"] == 0
    assert report["events_scanned"] == 3
    assert report["events_eligible"] == 3
    assert report["events_inferred"] == 3
    assert report["inference_runs_created"] == 3
    assert report["predictions_created"] == 3
    assert _OutageClient.calls == ["ok-0", "ok-1", "ok-2"]


def test_explicit_limit_semantics_unchanged(clean_data_plane, monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _OutageClient)
    _OutageClient.calls = []
    _OutageClient.fail_after = 999
    for i in range(4):
        _learning_event(clean_data_plane, f"lim-{i}", 1, occurred_at=1000.0 + i)

    report = worker.run_once(__import__("database").SessionLocal, limit=2)

    assert report["events_scanned"] == 2
    assert report["events_inferred"] == 2
    assert _OutageClient.calls == ["lim-0", "lim-1"]   # limit still selects TARGETS


def test_no_default_limit_was_added():
    """The breaker must not quietly become a cap: no default limit on the signature."""
    import inspect
    sig = inspect.signature(worker.run_once)
    assert sig.parameters["limit"].default is None
    source = Path(worker.__file__).read_text(encoding="utf-8")
    assert "DEFAULT_LIMIT" not in source


def test_contract_violation_is_not_treated_as_an_outage(clean_data_plane, monkeypatch):
    """A per-target contract bug must NOT trip the breaker — the run carries on."""

    class _ContractBugClient:
        calls: list = []

        def __init__(self, *a, **k):
            pass

        def infer(self, request):
            _ContractBugClient.calls.append(request["target_event_id"])
            if request["target_event_id"] == "bug-0":
                raise runtime_client.RuntimeClientError("runtime response request_id mismatch")
            return _OutageClient().infer(request)

    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(runtime_client, "StudentTwinRuntimeClient", _ContractBugClient)
    _ContractBugClient.calls = []
    _OutageClient.calls = []
    _OutageClient.fail_after = 999
    for i in range(3):
        _learning_event(clean_data_plane, f"bug-{i}", 1, occurred_at=1000.0 + i)

    report = worker.run_once(__import__("database").SessionLocal)

    assert report["runtime_unavailable"] is False
    assert report["errors"] == 1
    assert report["events_inferred"] == 2          # the other two still ran
    assert _ContractBugClient.calls == ["bug-0", "bug-1", "bug-2"]


def test_confirmed_unavailable_is_a_distinct_error_class():
    """The transport layer must separate an OUTAGE from a refused request."""
    assert issubclass(runtime_client.RuntimeUnavailableError, runtime_client.RuntimeClientError)
    assert issubclass(sci_client.ScientificUnavailable, sci_client.ScientificRuntimeError)
    assert not issubclass(sci_client.ScientificRejected, sci_client.ScientificUnavailable)

    def _raise(kind):
        def handler(request):
            if kind == "down":
                raise httpx.ConnectError("connection refused")
            return httpx.Response(400, json={"detail": "bad request"},
                                  headers={"content-type": "application/json"})
        return httpx.MockTransport(handler)

    down = runtime_client.StudentTwinRuntimeClient(
        base_url="http://runtime.test", transport=_raise("down"))
    with pytest.raises(runtime_client.RuntimeUnavailableError):
        down.infer({"request_id": "r", "target_event_id": "e", "events": [],
                    "user_ref": "u", "contract_version": 1})

    refused = runtime_client.StudentTwinRuntimeClient(
        base_url="http://runtime.test", transport=_raise("400"))
    with pytest.raises(runtime_client.RuntimeClientError) as exc:
        refused.infer({"request_id": "r", "target_event_id": "e", "events": [],
                       "user_ref": "u", "contract_version": 1})
    assert not isinstance(exc.value, runtime_client.RuntimeUnavailableError)


# ================================================================ PART E — domain gate

def test_learner_state_is_not_domain_compatible_by_the_frozen_matrix():
    """The product's own eligibility matrix already records the ontology mismatch."""
    verdict = eligibility.evaluate("learner_state", {})
    assert verdict["requirement_status"] == "PARTIAL"
    assert verdict["scientific_applicability"] == "ONTOLOGY_MISMATCH"
    assert verdict["eligibility_status"] == "INELIGIBLE"
    assert verdict["safe_for_data_production"] is False


def test_no_product_to_scientific_ontology_mapping_exists():
    """The blocker is a MISSING MAPPING, and this asserts we did not quietly invent one."""
    assert learner_state.SCIENTIFIC_ONTOLOGIES == {"base": 123, "junyi": 835}
    assert learner_state.SCIENTIFIC_SOURCE_COMMIT == "06d4366"
    requirement = learner_state.model_requirement()
    assert requirement["ontology_mapping"] == "NONE"
    assert requirement["active_product_variant"] is None
    assert requirement["missing_input"] == [
        "concept index in the ASSISTments (123) / Junyi (835) ontology"]


def test_the_gate_module_contains_no_scientific_computation():
    """No model, no formula, no adapter in the Product Backend — asserted over the CODE.

    Prose is not computation: the module legitimately NAMES the model it declines to run,
    so this parses the AST and inspects imports and identifiers rather than substrings.
    """
    import ast

    tree = ast.parse(Path(learner_state.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)

    scientific = {"torch", "numpy", "faiss", "sklearn", "transformers", "zhixue_runtime",
                  "sentence_transformers"}
    assert imported.isdisjoint(scientific), imported & scientific
    assert identifiers.isdisjoint({"get_adapter", "softmax", "IndexFlatIP", "embedding",
                                   "checkpoint"}), identifiers
    assert "_num_skills" not in identifiers
    # and it reaches the runtime ONLY through the one transport owner
    assert "client" in imported


# ================================================================ PART H/L — product surface

def _preview(client, params=None):
    return client.get("/exam/prep/scientific/learner-state", params=params or {})


def test_endpoint_requires_authentication():
    import main as backend_main
    with TestClient(backend_main.app) as anon:
        assert anon.get("/exam/prep/scientific/learner-state").status_code in (401, 403)


def test_endpoint_produces_no_number_and_names_the_blockers(client, db_session):
    register_and_login(client, "s3_gate_user")
    u = db_session.query(User).filter_by(username="s3_gate_user").one()
    cs408_attempt(db_session, u, "q-paging")
    cs408_attempt(db_session, u, "q-deadlock", correct=False)

    body = _preview(client).json()
    LearnerStatePreviewResponse.model_validate(body)      # contract is exact

    assert body["metadata"]["component"] == "learner_state"
    assert body["metadata"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert body["metadata"]["controls_product_decision"] is False
    assert body["metadata"]["writes_learner_fact"] is False
    # NO number, and no field that could be read as one
    assert body["next_response_probability"] is None
    assert "prediction" not in body
    assert body["runtime_provenance"]["executed_for_this_request"] is False
    blockers = " ".join(body["metadata"]["blockers"])
    assert learner_state.BLOCKER_ONTOLOGY in blockers
    assert learner_state.BLOCKER_CALIBRATION in blockers


def test_response_uses_no_mastery_vocabulary(client, db_session):
    """No field may be NAMED after the forbidden readings, and no sentence may ASSERT one.

    Two separate rules, because they fail differently: a field name is a claim that
    survives in the contract, while prose may only mention these readings in a negation.
    """
    def keys_of(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield key
                yield from keys_of(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from keys_of(item)

    register_and_login(client, "s3_wording_user")
    u = db_session.query(User).filter_by(username="s3_wording_user").one()
    cs408_attempt(db_session, u, "q-wording")
    body = _preview(client).json()

    # 1. no field may be named after a forbidden reading
    forbidden_names = {"prediction", "probability", "mastery", "mastery_probability",
                       "mastery_score", "ability", "ability_score", "difficulty",
                       "confidence", "exam_pass_probability"}
    assert forbidden_names.isdisjoint(set(keys_of(body))), \
        forbidden_names & set(keys_of(body))

    # 2. the Chinese term for mastery must not appear at all
    assert "掌握" not in json.dumps(body, ensure_ascii=False)

    # 3. prose may only mention a wrong reading in order to deny it
    for text in (body["score_semantics"], body["metadata"]["semantics"]):
        for sentence in text.replace(";", ".").split("."):
            lowered = sentence.lower()
            for reading in ("probability", "mastery", "ability", "difficulty"):
                if reading in lowered:
                    assert "not" in lowered, sentence


def test_evidence_window_counts_real_canonical_facts(client, db_session):
    register_and_login(client, "s3_evidence_user")
    u = db_session.query(User).filter_by(username="s3_evidence_user").one()
    cs408_attempt(db_session, u, "q-1", submitted_at=MOMENT)
    cs408_attempt(db_session, u, "q-2", correct=False, submitted_at=MOMENT)
    # an ungraded past-paper style item: a real score, NO boolean verdict
    cs408_attempt(db_session, u, "q-3", correct=None, judge="ai_grade",
                  submitted_at=MOMENT)

    window = _preview(client).json()["evidence_window"]
    assert window["event_count"] == 2                 # only the authoritative facts
    assert window["window"]["first_occurred_at"] is not None
    assert window["window"]["last_occurred_at"] is not None
    assert window["scope"]["service_namespace"] == EXAM
    assert window["semantics"].startswith("real canonical practice facts")
    assert "no derived or invented feature" in window["semantics"]


def test_cross_user_isolation(client, db_session):
    register_and_login(client, "s3_owner")
    owner = db_session.query(User).filter_by(username="s3_owner").one()
    other = make_user(db_session, "s3_other")
    cs408_attempt(db_session, owner, "q-owner")
    cs408_attempt(db_session, other, "q-other")

    assert _preview(client).json()["evidence_window"]["event_count"] == 1


def test_no_learner_fact_mutation(client, db_session):
    register_and_login(client, "s3_readonly_user")
    u = db_session.query(User).filter_by(username="s3_readonly_user").one()
    cs408_attempt(db_session, u, "q-ro")

    def snapshot():
        return (db_session.query(dp_models.LearningEvent).count(),
                db_session.query(dp_models.ModelPrediction).count(),
                db_session.query(dp_models.ModelInferenceRun).count())

    before = snapshot()
    _preview(client)
    db_session.expire_all()
    assert snapshot() == before


def test_runtime_outage_never_becomes_a_product_failure(client, db_session, monkeypatch):
    """PART M: a scientific outage is isolated — no 500, and the gate still answers."""
    register_and_login(client, "s3_outage_user")
    u = db_session.query(User).filter_by(username="s3_outage_user").one()
    cs408_attempt(db_session, u, "q-outage")

    class _DownRuntime:
        """Exactly what the real client does for a down runtime: answers, never raises."""

        def health(self, **kwargs):
            return {"status": "unavailable", "reason": "ConnectError"}

    monkeypatch.setattr(learner_state, "get_client", lambda: _DownRuntime())
    response = _preview(client, {"probe_runtime": "true"})
    assert response.status_code == 200
    assert response.json()["runtime_reachable"] is False

    # even a probe that blows up in an unforeseen way stays bounded
    class _ExplodingRuntime:
        def health(self, **kwargs):
            raise sci_client.ScientificUnavailable("runtime unreachable",
                                                   component="learner_state")

    monkeypatch.setattr(learner_state, "get_client", lambda: _ExplodingRuntime())
    assert _preview(client, {"probe_runtime": "true"}).json()["runtime_reachable"] is False

    # and with the default (no probe) the endpoint never touches the runtime at all
    monkeypatch.setattr(learner_state, "get_client",
                        lambda: pytest.fail("the default path must not call the runtime"))
    assert _preview(client).status_code == 200


def test_runtime_probe_is_bounded_and_reports_reachability(client, db_session, monkeypatch):
    register_and_login(client, "s3_probe_user")
    u = db_session.query(User).filter_by(username="s3_probe_user").one()
    cs408_attempt(db_session, u, "q-probe")

    class _Healthy:
        def health(self, **kwargs):
            return {"status": "ok", "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1"}

    monkeypatch.setattr(learner_state, "get_client", lambda: _Healthy())
    body = _preview(client, {"probe_runtime": "true"}).json()
    assert body["runtime_reachable"] is True
    assert _preview(client).json()["runtime_reachable"] is None


def test_unknown_exam_module_is_rejected(client):
    register_and_login(client, "s3_module_user")
    r = _preview(client, {"exam_module_id": "not_a_module"})
    assert r.status_code == 400


# ================================================================ PART O — contract guards

def test_openapi_is_concrete(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in ("LearnerStatePreviewResponse", "LearnerStateModelRequirement",
                 "LearnerStateEvidenceWindow"):
        assert name in schemas and schemas[name].get("properties"), name

    operation = client.get("/openapi.json").json()["paths"][
        "/exam/prep/scientific/learner-state"]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in ref, f"GET learner-state 200 is untyped: {ref}"


def test_product_backend_still_imports_no_scientific_stack():
    """PART F/O: the Product Backend must remain deployable without the heavy stack."""
    loaded = [m for m in ("torch", "transformers", "faiss", "zhixue_runtime",
                          "sentence_transformers", "sklearn") if m in sys.modules]
    assert loaded == [], f"heavy scientific modules loaded in-process: {loaded}"

    source = Path(learner_state.__file__).read_text(encoding="utf-8")
    assert "httpx" not in source          # transport stays owned by science.client
    assert "from .client import" in source
