"""ACCEL_SPRINT_S2 — CS408 StudentTwin productization gate closure.

The gate is an INPUT-DOMAIN product decision: a factual ``question_answered`` event may
feed StudentTwin when, and only when, it carries an authoritative binary correctness fact.
No scientific algorithm is involved, and these tests hold that line:

  * the eligible/ineligible cases are decided by ONE rule
    (``data_plane.eligibility.student_twin_input_eligibility``), consumed by both the SHADOW
    producer and the product preview;
  * the scientific provenance (release id, source commit, model version, the adapter source
    on disk) is UNCHANGED;
  * the preview is read-only and a runtime outage stays isolated;
  * the SSOT records the explicit governance decision.

Doubles sit below the HTTP/runtime boundary only, exactly as in S1.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from conftest import register_and_login
from fastapi.testclient import TestClient

from core import config
from core.learning_context import ServiceNamespace
from data_plane import eligibility, inference, runtime_client
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import producers, taxonomy
from models import User
from science import client as sci_client
from science import student_twin

EXAM = ServiceNamespace.EXAM_PREP.value
COURSE = ServiceNamespace.COURSE_LEARNING.value

MOMENT = datetime(2026, 9, 19, 6, 30, 0)
FROZEN_RELEASE_ID = "zhixue-runtime-v1-phase1gr-p1"
FROZEN_SOURCE_COMMIT = "a16efa27aac90d9c8d8d9ee703aefe5919f4839e"
OLD_FAMILY_BLOCKER = "INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE"
NEW_EXCLUSION_BLOCKER = "STUDENT_TWIN_INPUT_EXCLUDED"

# S2 ran on 2026-09-19. Any scientific source modified after this instant would mean the
# gate had touched the model rather than the input domain.
SPRINT_START_EPOCH = datetime(2026, 9, 19, 0, 0, 0).timestamp()


# ---------------------------------------------------------------- helpers

def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def _context(user, *, knowledge_point_id=None):
    from learning.spaces.exam_prep.context import cs408_context
    return cs408_context(user, module_key="operating_system",
                         knowledge_point_id=knowledge_point_id)


def cs408_attempt(db, user, qid, *, answer="A", correct=True, judge=None,
                  source_id=None, submitted_at=MOMENT):
    """One real CS408 chapter-practice attempt, mirrored into the canonical facts."""
    source_id = source_id or f"s2-{qid}"
    context = _context(user)
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


def event_for(db, user, qid):
    return (db.query(LearningEvent)
            .filter(LearningEvent.user_id == user.id,
                    LearningEvent.question_id == qid).one())


def verdict_of(db, user, qid):
    return eligibility.student_twin_event_eligibility(event_for(db, user, qid))


# ------------------------------------------------- runtime doubles (below the boundary)

def runtime_app():
    root = Path(__file__).resolve().parents[2]
    path = str(root / "scientific_runtime_service")
    if path not in sys.path:
        sys.path.insert(0, path)
    from app.main import app  # noqa: PLC0415
    return app


def runtime_transport(replay_state):
    test_client = TestClient(runtime_app())
    from app import runtime_bridge  # noqa: PLC0415

    original = runtime_bridge.replay_state
    runtime_bridge.replay_state = replay_state

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(request.method, request.url.path,
                                       content=request.content,
                                       headers={"content-type": "application/json"})
        return httpx.Response(response.status_code, content=response.content,
                              headers={"content-type": "application/json"})

    def restore():
        runtime_bridge.replay_state = original

    return httpx.MockTransport(handler), restore


def fake_state(user_ref, events):
    return {"user_id": user_ref, "global_ability": 0.0,
            "events_seen": len(events),
            "concepts": sorted({e.concept_ref or "unmapped" for e in events})}


def product_client(transport):
    return sci_client.ScientificClient(base_url="http://runtime.test", timeout=5.0,
                                       transport=transport)


def run_preview(client, db, monkeypatch, replay_state=fake_state, module=""):
    transport, restore = runtime_transport(replay_state)
    try:
        monkeypatch.setattr(student_twin, "get_client", lambda: product_client(transport))
        params = {"exam_module_id": module} if module else {}
        return client.get("/exam/prep/scientific/student-twin", params=params).json()
    finally:
        restore()


# ================================================================ 1. the rule

def test_valid_cs408_answered_choice_is_eligible(db_session):
    u = make_user(db_session, "s2_ok")
    cs408_attempt(db_session, u, "ok-1", answer="A", correct=True, judge=None)
    v = verdict_of(db_session, u, "ok-1")
    assert v.eligible is True
    assert v.reason == eligibility.RULE_ELIGIBLE


def test_correct_answered_choice_is_eligible(db_session):
    u = make_user(db_session, "s2_correct")
    cs408_attempt(db_session, u, "ok-true", answer="B", correct=True)
    assert verdict_of(db_session, u, "ok-true").eligible is True


def test_incorrect_answered_choice_is_eligible(db_session):
    u = make_user(db_session, "s2_incorrect")
    cs408_attempt(db_session, u, "ok-false", answer="C", correct=False)
    assert verdict_of(db_session, u, "ok-false").eligible is True


def test_blank_answer_is_excluded(db_session):
    u = make_user(db_session, "s2_blank")
    cs408_attempt(db_session, u, "blank-1", answer="", correct=None)
    v = verdict_of(db_session, u, "blank-1")
    assert v.eligible is False and v.reason == eligibility.REASON_NO_ANSWER


def test_self_review_is_excluded(db_session):
    """The judge marker alone disqualifies, even if a boolean somehow reached `correct`."""
    u = make_user(db_session, "s2_selfreview")
    cs408_attempt(db_session, u, "selfrev-1", answer="A", correct=True,
                  judge="self_review")
    v = verdict_of(db_session, u, "selfrev-1")
    assert v.eligible is False and v.reason == eligibility.REASON_JUDGE


def test_null_correctness_is_excluded(db_session):
    """An AI-graded item has a real SCORE and no binary verdict — not eligible."""
    u = make_user(db_session, "s2_nullcorrect")
    cs408_attempt(db_session, u, "null-1", answer="A", correct=None, judge="ai_graded")
    v = verdict_of(db_session, u, "null-1")
    assert v.eligible is False and v.reason == eligibility.REASON_NOT_BINARY


def test_correctness_is_never_inferred_from_score():
    """A score is not a verdict. Even a perfect score cannot make an event eligible."""
    for score in (0.0, 1.0, 10.0, None):
        v = eligibility.student_twin_input_eligibility(
            answer="A", correct=None, event_type="question_answered")
        assert v.eligible is False
    # and the rule has no way to see a score at all
    import inspect
    params = inspect.signature(
        eligibility.student_twin_input_eligibility).parameters
    assert "score" not in params


def test_rule_is_pure_and_does_not_touch_the_database():
    import inspect
    src = inspect.getsource(eligibility.student_twin_input_eligibility)
    for forbidden in ("db", "session", "query", "commit"):
        assert forbidden not in src.lower()


# ================================================================ 2. the preview

def test_preview_accepts_valid_cs408_evidence_and_drops_the_old_blocker(
        client, db_session, monkeypatch):
    register_and_login(client, "s2_preview")
    u = db_session.query(User).filter(User.username == "s2_preview").first()
    cs408_attempt(db_session, u, "pv-1", answer="A", correct=True)
    cs408_attempt(db_session, u, "pv-2", answer="D", correct=False)

    body = run_preview(client, db_session, monkeypatch)

    blockers = body["metadata"]["blockers"] or []
    assert not any(OLD_FAMILY_BLOCKER in b for b in blockers), blockers
    assert not any(NEW_EXCLUSION_BLOCKER in b for b in blockers), blockers
    assert body["metadata"]["mode"] == "PREVIEW"
    assert body["input_summary"]["event_count"] == 2
    assert body["input_summary"]["excluded_event_count"] == 0
    assert body["input_summary"]["eligibility_rule"] == eligibility.RULE_STATEMENT
    assert body["state"]["events_seen"] == 2


def test_preview_reports_the_real_reason_when_evidence_is_ineligible(
        client, db_session, monkeypatch):
    """The blocker may still appear — but only when the events genuinely do not qualify."""
    register_and_login(client, "s2_preview_bad")
    u = db_session.query(User).filter(User.username == "s2_preview_bad").first()
    cs408_attempt(db_session, u, "bad-1", answer="", correct=None)
    cs408_attempt(db_session, u, "bad-2", answer="A", correct=True, judge="self_review")

    body = run_preview(client, db_session, monkeypatch)

    summary = body["input_summary"]
    assert summary["event_count"] == 0
    assert summary["excluded_event_count"] == 2
    assert summary["excluded_reasons"] == {
        eligibility.REASON_NO_ANSWER: 1, eligibility.REASON_JUDGE: 1}
    blockers = body["metadata"]["blockers"]
    assert any(f"{NEW_EXCLUSION_BLOCKER}: {eligibility.REASON_NO_ANSWER}" in b
               for b in blockers)
    assert any(f"{NEW_EXCLUSION_BLOCKER}: {eligibility.REASON_JUDGE}" in b
               for b in blockers)
    assert not any(OLD_FAMILY_BLOCKER in b for b in blockers)
    assert body["metadata"]["mode"] == "UNAVAILABLE"
    assert "NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE" in blockers


def test_preview_mixed_evidence_uses_only_the_eligible_events(
        client, db_session, monkeypatch):
    register_and_login(client, "s2_mixed")
    u = db_session.query(User).filter(User.username == "s2_mixed").first()
    cs408_attempt(db_session, u, "mx-1", answer="A", correct=True)
    cs408_attempt(db_session, u, "mx-2", answer="", correct=None)
    cs408_attempt(db_session, u, "mx-3", answer="B", correct=False, judge="self_review")

    body = run_preview(client, db_session, monkeypatch)

    assert body["input_summary"]["event_count"] == 1
    assert body["input_summary"]["excluded_event_count"] == 2
    assert body["state"]["events_seen"] == 1


def test_course_practice_family_is_still_eligible(db_session):
    """The pre-existing family keeps working; S2 widened the set, it did not replace it.

    Driven through the REAL emitter so the fields the rule reads are the ones production
    actually writes.
    """
    u = make_user(db_session, "s2_course")
    from data_plane import emitter
    from models import AIQuestionAttempt

    attempt = AIQuestionAttempt(
        username=u.username, subject_key="math", subject_name="数学",
        question_ids_json=json.dumps([1]), status="submitted", submitted_at=MOMENT,
        answers_json=json.dumps({"1": "A"}),
        result_json=json.dumps({"results": [{"question_id": 1, "correct": True}]}))
    db_session.add(attempt)
    db_session.commit()

    from types import SimpleNamespace
    question = SimpleNamespace(id=1, stem="q", subject_key="math", question_type="choice",
                               options_json=None, knowledge_point_id=None,
                               standard_answer="A")
    rows = emitter.build_course_practice_events(attempt, question, "A", True, u)
    event = rows[0]
    event["user_id"] = u.id
    assert event["event_type"] == "course_practice"
    assert event["correct"] is True and event["answer"]
    db_session.add(LearningEvent(**event))
    db_session.commit()

    stored = (db_session.query(LearningEvent)
              .filter(LearningEvent.event_id == event["event_id"]).one())
    assert eligibility.student_twin_event_eligibility(stored).eligible is True


# ================================================================ 3. no science change

def test_no_scientific_algorithm_change():
    """This is an input-domain decision. Nothing scientific moved."""
    assert config.SCIENTIFIC_RUNTIME_RELEASE_ID == FROZEN_RELEASE_ID
    assert runtime_client.SCIENTIFIC_SOURCE_CLASS == "ORIGINAL_ARCHIVE_VERIFIED"
    assert runtime_client.SCIENTIFIC_SOURCE_COMMIT == FROZEN_SOURCE_COMMIT
    assert inference.STUDENT_TWIN_MODEL_VERSION_ID == (
        "student_twin@zhixue-runtime-v1-phase1gr-p1@a16efa2")


def test_runtime_release_id_unchanged():
    from app import config as runtime_config  # the runtime service's own config

    assert runtime_config.RUNTIME_RELEASE_ID == FROZEN_RELEASE_ID
    assert runtime_config.SCIENTIFIC_SOURCE_COMMIT == FROZEN_SOURCE_COMMIT


def test_the_eligibility_gate_contains_no_scientific_computation():
    """The gate must be a pure input-domain predicate: no model, no formula, no adapter.

    (The import boundary itself is proven by S1's scan; this asserts the NEW code added by
    this gate did not smuggle science into the product backend.)
    """
    source = Path(eligibility.__file__).read_text(encoding="utf-8")
    for marker in ("import torch", "import numpy", "zhixue_runtime", "get_adapter(",
                   "IndexFlatIP", "softmax", "embedding"):
        assert marker not in source, marker

    import inspect
    src = inspect.getsource(eligibility.student_twin_input_eligibility)
    # a decision procedure over three facts, nothing more
    assert len(src.splitlines()) < 40


def test_scientific_source_on_disk_was_not_modified():
    """The model source this gate feeds is untouched — verified, not assumed."""
    root = Path(os.environ.get("ZHIXUE_RUNTIME_SRC")
                or r"D:\ZhixueAI\runtime_package\v1\src")
    adapter = root / "zhixue_runtime" / "components" / "adapters" / "student_twin.py"
    if not adapter.exists():
        pytest.skip("scientific source not present on this machine")
    assert adapter.stat().st_mtime < SPRINT_START_EPOCH, (
        "the StudentTwin scientific source was modified during the sprint")


# ================================================================ 4. no product control

def test_preview_writes_no_learner_fact(client, db_session, monkeypatch):
    register_and_login(client, "s2_nowrite")
    u = db_session.query(User).filter(User.username == "s2_nowrite").first()
    cs408_attempt(db_session, u, "nw-1", answer="A", correct=True)

    from learning.wrong_answers.models import WrongAnswerState
    from models import UserKnowledgeProgress

    def snapshot():
        return {
            "events": db_session.query(LearningEvent).count(),
            "wrong": db_session.query(WrongAnswerState).count(),
            "knowledge": db_session.query(UserKnowledgeProgress).count(),
            "predictions": db_session.query(
                __import__("data_plane.models", fromlist=["x"]).ModelPrediction).count(),
        }

    before = snapshot()
    body = run_preview(client, db_session, monkeypatch)
    db_session.expire_all()
    assert body["metadata"]["writes_learner_fact"] is False
    assert body["metadata"]["controls_product_decision"] is False
    assert snapshot() == before


def test_preview_does_not_change_practice_or_past_paper_grading(
        client, db_session, monkeypatch):
    register_and_login(client, "s2_nograde")
    u = db_session.query(User).filter(User.username == "s2_nograde").first()
    attempt = cs408_attempt(db_session, u, "ng-1", answer="A", correct=True,
                            source_id="s2-ng-1").attempt
    before = (attempt.correct, attempt.score, attempt.fact_hash)

    run_preview(client, db_session, monkeypatch)
    db_session.expire_all()
    refreshed = (db_session.query(type(attempt)).filter_by(id=attempt.id).one())
    assert (refreshed.correct, refreshed.score, refreshed.fact_hash) == before


def test_the_worker_producer_writes_no_product_table(db_session, monkeypatch):
    """Even the SHADOW evidence path may only write model_* rows.

    Targeted at ONE event id on purpose: the suite shares one database, and an unbounded
    pass would attempt a runtime call for every eligible event other tests left behind.
    """
    u = make_user(db_session, "s2_worker_nowrite")
    cs408_attempt(db_session, u, "wn-1", answer="A", correct=True)
    target = event_for(db_session, u, "wn-1")
    assert eligibility.student_twin_event_eligibility(target).eligible is True

    from learning.wrong_answers.models import WrongAnswerState
    from models import UserKnowledgeProgress

    before = (db_session.query(WrongAnswerState).count(),
              db_session.query(UserKnowledgeProgress).count())
    monkeypatch.setattr(config, "data_producer_execution_enabled", lambda: True)
    from data_plane import worker
    report = worker.run_once(__import__("database").SessionLocal,
                             event_id=target.event_id)
    db_session.expire_all()
    assert report["events_scanned"] == 1
    assert report["events_eligible"] == 1
    # no runtime is running, so the call fails and is isolated; either way nothing in a
    # product table moved
    assert (db_session.query(WrongAnswerState).count(),
            db_session.query(UserKnowledgeProgress).count()) == before


# ================================================================ 5. failure isolation

def test_runtime_outage_remains_isolated(client, db_session, monkeypatch):
    register_and_login(client, "s2_outage")
    u = db_session.query(User).filter(User.username == "s2_outage").first()
    cs408_attempt(db_session, u, "out-1", answer="A", correct=True)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("runtime down", request=request)

    monkeypatch.setattr(student_twin, "get_client",
                        lambda: product_client(httpx.MockTransport(refuse)))
    body = client.get("/exam/prep/scientific/student-twin")
    assert body.status_code == 200
    payload = body.json()
    assert payload["metadata"]["mode"] == "UNAVAILABLE"
    assert "SCIENTIFIC_RUNTIME_UNAVAILABLE" in payload["metadata"]["blockers"]
    assert payload["state"] is None
    # the eligible input was still recognised before the call failed
    assert payload["input_summary"]["event_count"] == 1

    for path in ("/learning-records", "/exam/prep/records", "/practice/sessions",
                 "/wrong-answers"):
        assert client.get(path).status_code == 200, path


# ================================================================ 6. not promoted

def test_misconception_and_tutor_policy_are_not_promoted(client, db_session):
    assert misconception_mode() == "SHADOW_NOT_USER_VISIBLE"
    assert tutor_policy_mode() == "SHADOW"

    register_and_login(client, "s2_modes")
    tp = client.get("/science/tutor-policy").json()
    assert tp["controls_response"] is False
    assert tp["available"] is False
    assert "TURN_STATE_PREV_ACTIONS_UNAVAILABLE" in " ".join(
        tp["metadata"]["blockers"])


def misconception_mode():
    from science import misconception
    return misconception.PRODUCT_MODE


def tutor_policy_mode():
    from science import tutor_policy
    return tutor_policy.PRODUCT_MODE


def test_provisioning_is_not_ontology_compatibility():
    """RUNTIME_PROVISIONED != PRODUCT_ELIGIBLE: the blocker list must still carry the
    ontology mismatch, and nothing may claim an ontology mapping exists."""
    from science import misconception

    assert misconception.BLOCKER_ONTOLOGY.startswith("ONTOLOGY_MISMATCH")
    source = Path(misconception.__file__).read_text(encoding="utf-8")
    for claim in ("mapped_ontology", "ontology_map =", "MAPPED"):
        assert claim not in source


# ================================================================ 7. SSOT governance

def test_ssot_records_the_explicit_product_direction_change():
    ssot = (Path(__file__).resolve().parents[2]
            / "ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md").read_text(encoding="utf-8")

    assert "MVP_TARGET = USER_VISIBLE_PREVIEW" in ssot
    assert "MVP_USER_VISIBLE_FEATURE = 学习状态实验视图" in ssot
    # the old values survive ONLY as a record of what they used to be, never as CURRENT
    assert "CURRENT: RUNTIME_ONLY = 13" not in ssot
    assert "CURRENT = RUNTIME_ONLY" not in ssot

    # the hard invariants and the allowed vocabulary travel with the decision
    assert "controls_product_decision = false" in ssot
    assert "writes_learner_fact = false" in ssot
    assert "确定性学习状态引擎（实验）" in ssot
    for forbidden in ("AI掌握度预测", "神经网络模型", "掌握概率", "考试预测"):
        assert forbidden in ssot          # present only as the explicit prohibition
    assert "禁止表述" in ssot

    # the governance mechanism is named, and the scientific semantics are preserved
    assert "§74-1" in ssot or "74-1" in ssot
    assert "deterministic rule-based state engine" in ssot
    assert "不是 neural network" in ssot


def test_ssot_still_freezes_the_scientific_semantics():
    ssot = (Path(__file__).resolve().parents[2]
            / "ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md").read_text(encoding="utf-8")
    # the S2 amendment must not have weakened any FROZEN scientific statement
    for frozen in ("cosine-like inner product", "不是 probability",
                   "deterministic rule-based state engine", "不是 neural network"):
        assert frozen in ssot, frozen
    assert "ALLOW / REJECT" in ssot      # present only as the explicit prohibition
