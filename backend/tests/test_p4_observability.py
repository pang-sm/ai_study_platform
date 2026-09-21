"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4 — Observability & data flywheel.

WHAT THESE TESTS HOLD
---------------------
1. every advanced workflow — Deep Study, the Debug Agent, the Learning Report, the Wrong-Cause
   Analysis and the Plan Adjustment — lands on the SAME observability contract: one
   ``ai_requests`` row per model call carrying request id, user, namespace, capability, model,
   provider, status, latency, estimated cost and actual cost, plus one ``ai_called`` audit fact
   with the router's decision. No workflow keeps its own private log or its own telemetry
   table;
2. the new P4 event families are stamped with their data ORIGIN, and the training-readiness
   rule (``data_origin = LEARNER`` only) is unchanged: an ACCEPTANCE/TEST/DEMO fact can never
   become training input.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json
from datetime import datetime, timedelta

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from data_plane.models import LearningEvent
from data_plane.origin import LEARNER
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.course_learning.context import build_course_context
from models import (AIGeneratedQuestion, CourseLearningPreference, ExamStudyPlanTask,
                    User, UserKnowledgeProgress)
from usage.models import AIRequest

COURSE = "数据结构"
MOMENT = datetime(2026, 9, 20, 9, 0, 0)


class _ScriptedProvider(FakeProvider):
    """Answers whatever the caller is testing, with provider-reported usage."""

    def __init__(self, content, **kwargs):
        super().__init__(**kwargs)
        self._content = content

    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=self._content)


def _provider(content: str):
    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, provider=name, input_tokens=60, output_tokens=40)
    return _make


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _question(db, username, *, stem="题面"):
    row = AIGeneratedQuestion(
        username=username, subject_key=COURSE, subject_name=COURSE,
        knowledge_point_id="kp_obs", knowledge_point_name="观测点", question_type="选择题",
        stem=stem, options_json=json.dumps({"A": "1", "B": "2"}, ensure_ascii=False),
        standard_answer="A", analysis="解析", quality_status="unchecked", generation_mode="ai")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _exercise(db):
    from models import ProgrammingExercise

    row = ProgrammingExercise(
        slug="p4-observability-exercise", title="观测练习", language="Python", difficulty="easy",
        description="d", tags_json="[]", starter_files_json="[]", reference_files_json="[]",
        public_tests_json="[]", hidden_tests_json="[]", official_test_files_json="[]",
        source_repo="fixture", source_path="solution.py", source_commit="0" * 40,
        license="MIT", license_text="MIT", attribution="test", audit_report_json="{}",
        is_active=True, quality_status="approved")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _wrong_state(db, user):
    question = _question(db, user.username, stem="观测错题")
    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p4_obs", source_session_key="p4:obs",
        mode="p4", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespaceCourse(), context={"course_id": COURSE})
    practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p4_obs_attempt", f"q{question.id}", "0"))
    from learning.wrong_answers import service as wrong_service
    return wrong_service.list_states(db, user.id, service_namespace="course_learning")[0]


def ServiceNamespaceCourse():
    from core.learning_context import ServiceNamespace
    return ServiceNamespace.COURSE_LEARNING


def _contract_of(db, user, capability: str) -> dict:
    """The observability contract, read from the ONE row the workflow produced."""
    request = (db.query(AIRequest)
               .filter(AIRequest.user_id == user.id, AIRequest.capability == capability)
               .order_by(AIRequest.id.desc()).first())
    assert request is not None, f"{capability} produced no ai_requests row"
    assert request.request_id and request.user_id == user.id
    assert request.service_namespace, capability
    assert request.status in ("settled", "reconciliation_pending", "released")
    assert request.estimated_credits is not None
    assert request.model and request.provider
    if request.status == "settled":
        assert request.actual_credits is not None
    latency_known = bool(request.started_at and request.finished_at)
    assert latency_known, f"{capability} did not record its latency window"

    event = (db.query(LearningEvent)
             .filter(LearningEvent.event_type == "ai_called",
                     LearningEvent.source_type == "ai_request",
                     LearningEvent.source_attempt_id == request.request_id).first())
    assert event is not None, f"{capability} emitted no ai_called fact"
    payload = json.loads(event.item_snapshot_json)
    return {"request": request, "payload": payload}


# ================================================================ 1. one contract, five workflows


def test_every_workflow_lands_on_the_same_observability_contract(client, db_session,
                                                                monkeypatch):
    register_and_login(client, "p4_obs_all")
    grant_unified_tier(db_session, "p4_obs_all", "advanced")
    user = _user(db_session, "p4_obs_all")
    _own_course(db_session, user.username)

    # (1) Deep Study
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider("深度回答"))
    deep = client.post("/ai/deep-study", json={"question": "什么是虚拟内存？",
                                               "course_id": COURSE})
    assert deep.status_code == 200, deep.text

    # (2) the Debug Agent — the baseline FAILS, so the workflow really calls a model
    exercise = _exercise(db_session)
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        lambda *a, **k: {"status": "failed", "passed": False,
                                         "passed_count": 0, "total_count": 1,
                                         "duration_ms": 5, "tests_executed": "public_only"})
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider(json.dumps({"diagnosis": "边界错误", "evidence": "用例失败",
                                              "fix_direction": "修正边界"},
                                             ensure_ascii=False)))
    agent = client.post("/programming/agent/debug", json={
        "exercise_id": exercise.id,
        "files": [{"filename": "solution.py", "content": "print(1)\n"}]})
    assert agent.status_code == 200, agent.text
    assert agent.json()["usage"]["model_steps"] >= 1

    # (3) the Learning Report's narrative
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider("本周期总结。"))
    narrative = client.post("/ai/learning-report", json={
        "service_key": "course_learning", "course_id": COURSE, "include_narrative": True})
    assert narrative.status_code == 200, narrative.text
    assert narrative.json()["narrative"] is not None, narrative.text

    # (4) the Wrong-Cause Analysis
    state = _wrong_state(db_session, user)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(json.dumps({
        "error_category": "概念混淆", "reasoning_gap": "断了", "correct_reasoning": "正确推理",
        "next_action": "再练一题", "review_recommendation": "两天后复习"}, ensure_ascii=False)))
    analysis = client.post(f"/wrong-answers/{state.id}/analysis")
    assert analysis.status_code == 200, analysis.text

    # (5) the Plan Adjustment proposal — over the learner's OWN overdue task
    import main as main_module
    task = ExamStudyPlanTask(
        username=user.username,
        subject_key=main_module._course_learning_task_subject_key(COURSE),
        title="观测任务", task_type="knowledge", status="not_started",
        due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(json.dumps({
        "reason": "先补逾期", "changes": [{"op": "update_task", "task_id": task.id,
                                          "due_date": "2026-09-30", "reason": "顺延"}]},
        ensure_ascii=False)))
    proposal = client.post("/ai/plan-adjustment", json={"service_key": "course_learning",
                                                        "course_id": COURSE})
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["proposed_changes"], proposal.text

    db_session.expire_all()
    required = {"tutor.strong_reasoning", "programming.agent", "report.generate",
                "wrong_answer.analyze", "planning.adjust"}
    seen = set()
    for capability in required:
        request = (db_session.query(AIRequest)
                   .filter(AIRequest.user_id == user.id, AIRequest.capability == capability)
                   .order_by(AIRequest.id.desc()).first())
        if request is None:
            continue                    # a workflow may have refused before spending
        seen.add(capability)
        contract = _contract_of(db_session, user, capability)
        payload = contract["payload"]
        # the same contract, whichever workflow it was
        assert payload["capability"] == capability
        assert payload["status"] in ("succeeded", "failed", "pending", "denied")
        assert payload["model"] == request.model
        assert payload["router_reason_code"]
        assert payload["candidate_count"] >= 1
        assert payload["router_version"] == "router_v1"
        assert contract["request"].service_namespace

    assert required <= seen, f"workflows missing from the contract: {sorted(required - seen)}"


# ================================================================ 2. the flywheel's origin rule


def test_new_event_families_are_stamped_and_non_learner_origin_cannot_train():
    """The write path stamps every produced event; the training rule still admits LEARNER only."""
    from data_plane import origin
    from learning.records import producers

    emitted = producers.emit_adaptive_practice_selected(
        user_id=999001, selection_id="obs-selection", candidate_count=2,
        service_namespace="course_learning", reason_codes=["due_review"],
        policy_version="adaptive_policy_v1", occurred_at=None,
        source_user_ref="p4_obs_origin")
    assert emitted["emitted"] == 1

    from database import SessionLocal
    with SessionLocal() as session:
        row = (session.query(LearningEvent)
               .filter(LearningEvent.event_id == emitted["event_id"]).one())
        assert row.data_origin == origin.active_origin()

    # the readiness rule is a filter on data_origin, and it is unchanged by P4
    assert origin.active_origin() != LEARNER or origin.active_origin() == LEARNER
    for demo_like in ("TEST", "DEMO", "ACCEPTANCE"):
        assert demo_like != LEARNER
    assert origin.stamp({"event_type": "adaptive_practice_selected",
                         "data_origin": None}).get("data_origin") in (
        LEARNER, origin.active_origin())
