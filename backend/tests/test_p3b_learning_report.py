"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3B — Structured Learning Report.

WHAT THESE TESTS HOLD
---------------------
1. every figure is DERIVED from stored rows: the tests seed real practice attempts, a real
   wrong-answer state, real knowledge review dates, real plan tasks and real material events,
   then assert the exact numbers;
2. the report is scoped twice — by user AND by learning space — so neither another learner's
   facts nor another space's facts can appear in it;
3. a metric that does not exist for a space is ``null`` with a stated reason, never 0;
4. the AI narrative receives the STRUCTURED REPORT ONLY: the prompt contains the computed
   metrics and none of the learner's raw study text;
5. the narrative is gated by the unified ``report.generate`` capability, and a technical
   failure of the narrative returns the deterministic report rather than discarding it.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json
from datetime import datetime, timedelta

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from core.learning_context import ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import producers
from learning.spaces.course_learning.context import build_course_context
from models import (CourseLearningPreference, ExamStudyPlanTask, User,
                    UserKnowledgeProgress)

REPORT = "/ai/learning-report"
COURSE = "数据结构"
OTHER_COURSE = "操作系统"
MOMENT = datetime(2026, 9, 20, 6, 0, 0)
NARRATIVE_TEXT = "本周期你有 2 次练习记录，其中 1 次做对。建议先订正错题。"

SECRET_STEM = "这是一道不该出现在叙述提示词里的题面"


class _ScriptedProvider(FakeProvider):
    def __init__(self, content, capture=None, **kwargs):
        super().__init__(**kwargs)
        self._content = content
        self._capture = capture

    def complete(self, spec):
        if self._capture is not None:
            self._capture.append("\n".join(m.content for m in spec.messages))
        return dataclasses.replace(super().complete(spec), content=self._content)


def _provider(content: str = NARRATIVE_TEXT, capture: list | None = None):
    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, capture=capture, provider=name,
                                 input_tokens=100, output_tokens=80)
    return _make


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _record(db, user, *, course_id=COURSE, qid, correct, when=MOMENT, answer="A"):
    context = build_course_context(user, course_id=course_id)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p3b_report",
        source_session_key=f"p3b:{course_id}", mode="p3b", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED, source_id=str(qid),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": course_id})
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=correct, submitted_at=when,
        context=context,
        source=practice_service.SourceIdentity("p3b_attempt", f"{course_id}:{qid}", "0")).attempt


def _plan_subject_key(course_id):
    import main
    return main._course_learning_task_subject_key(course_id)


def _report(client, **overrides):
    payload = {"service_key": "course_learning", "course_id": COURSE, "period_days": 7}
    payload.update(overrides)
    response = client.post(REPORT, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# ================================================================ 1. metrics from facts


def test_the_report_is_computed_from_stored_facts(client, db_session):
    register_and_login(client, "p3b_report_facts")
    user = _user(db_session, "p3b_report_facts")
    _own_course(db_session, user.username)

    # two graded attempts: one correct, one wrong (the wrong one also creates a wrong state)
    _record(db_session, user, qid=9801, correct=True, answer="A")
    _record(db_session, user, qid=9802, correct=False, answer="B")

    # a knowledge point whose review date has passed (a STORED date)
    now = datetime.utcnow()
    db_session.add(UserKnowledgeProgress(
        username=user.username, course_id=COURSE, knowledge_point_id=9801,
        knowledge_point_code="kp_report", knowledge_point_title="线性表", status="learning",
        mastery_score=40, practice_count=2, review_due_at=now - timedelta(days=1),
        review_interval_days=7))
    # the plan: one completed task, one overdue task
    key = _plan_subject_key(COURSE)
    db_session.add(ExamStudyPlanTask(username=user.username, subject_key=key,
                                     title="已完成任务", task_type="knowledge",
                                     status="completed", due_date="2026-09-10"))
    db_session.add(ExamStudyPlanTask(username=user.username, subject_key=key,
                                     title="逾期任务", task_type="review",
                                     status="not_started", due_date="2026-09-01"))
    db_session.commit()

    # a material opened today, through the canonical producer
    producers.emit_material_opened(user_id=user.id, material_id=9801, occurred_at=None,
                                   service_namespace="course_learning",
                                   source_user_ref=user.username)

    body = _report(client)
    metrics = body["structured_metrics"]

    assert body["report_period"]["days"] == 7
    assert body["context"]["course_id"] == COURSE

    assert metrics["practice"]["attempts"] == 2
    assert metrics["practice"]["factual_correct"] == 1
    assert metrics["practice"]["factual_incorrect"] == 1
    assert metrics["practice"]["ungraded"] == 0

    assert metrics["review"]["total"] == 2          # one wrong answer + one due knowledge point
    assert metrics["review"]["by_status"]["due"] == 1
    assert metrics["review"]["by_source"]["wrong_answer"] == 1
    assert metrics["review"]["by_source"]["knowledge_review"] == 1

    assert metrics["plan"]["total"] == 2
    assert metrics["plan"]["completed"] == 1
    assert metrics["plan"]["overdue"] == 1

    assert metrics["materials"]["opened"] == 1
    assert metrics["activity"]["events"] >= 1
    assert metrics["activity"]["active_days"] >= 1

    # highlights and attention items are RULES over those numbers, and say so
    rules = {item["rule"] for item in body["highlights"]}
    assert {"practice_attempts", "plan_completed"} <= rules
    assert all(item["origin"] == "deterministic" for item in body["highlights"])
    attention = {item["rule"] for item in body["attention_items"]}
    assert {"wrong_answers_active", "review_due", "plan_overdue"} <= attention
    assert all(item["origin"] == "deterministic" for item in body["attention_items"])

    # no narrative was requested → none is invented
    assert body["narrative"] is None
    assert body["narrative_error"] is None


def test_the_report_is_scoped_by_user_and_by_space(client, db_session):
    register_and_login(client, "p3b_report_owner")
    owner = _user(db_session, "p3b_report_owner")
    _own_course(db_session, owner.username)
    _record(db_session, owner, qid=9811, correct=False, answer="C")

    # another learner with their own facts in the SAME course
    register_and_login(client, "p3b_report_stranger")
    stranger = _user(db_session, "p3b_report_stranger")
    _own_course(db_session, stranger.username)
    _record(db_session, stranger, qid=9812, correct=True)

    # back to the owner: re-login by registering a fresh session for the same user is not
    # possible, so the owner's page is asserted FIRST via its own session below.
    stranger_body = _report(client)
    assert stranger_body["structured_metrics"]["practice"]["attempts"] == 1
    assert stranger_body["structured_metrics"]["practice"]["factual_correct"] == 1
    assert stranger_body["structured_metrics"]["review"]["total"] == 0

    # the owner's own report (a separate login on a second client) sees only their facts
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as owner_client:
        register_and_login(owner_client, "p3b_report_owner2")
        owner2 = _user(db_session, "p3b_report_owner2")
        _own_course(db_session, owner2.username)
        _record(db_session, owner2, qid=9813, correct=False, answer="D")
        body = _report(owner_client)
        assert body["structured_metrics"]["practice"]["attempts"] == 1
        assert body["structured_metrics"]["practice"]["factual_correct"] == 0
        assert body["structured_metrics"]["practice"]["factual_incorrect"] == 1
        assert body["structured_metrics"]["review"]["by_source"]["wrong_answer"] == 1


def test_a_course_report_does_not_count_other_spaces(client, db_session):
    """Facts of another learning space never enter this space's report."""
    register_and_login(client, "p3b_report_space")
    user = _user(db_session, "p3b_report_space")
    _own_course(db_session, user.username)
    _record(db_session, user, qid=9821, correct=True)

    # a programming fact (a run event) through the canonical producer
    from learning.spaces.programming import events as programming_events
    from types import SimpleNamespace
    programming_events.emit_exercise_activity(
        user_id=user.id, exercise=SimpleNamespace(id=9821, language="Python"),
        action="run", occurred_at=None, language="Python",
        observed={"passed_count": 1, "total_count": 2}, source_user_ref=user.username)

    body = _report(client)
    metrics = body["structured_metrics"]
    assert metrics["practice"]["attempts"] == 1
    assert metrics["activity"]["by_event_type"].get("code_run") is None
    assert all(record["event_type"] != "code_run"
               for record in body["data_coverage"]["recent_events"])


# ================================================================ 2. missing stays missing


def test_a_metric_that_does_not_exist_for_the_space_is_null(client, db_session):
    register_and_login(client, "p3b_report_missing")
    user = _user(db_session, "p3b_report_missing")
    _own_course(db_session, user.username)

    course_report = _report(client)
    assert course_report["structured_metrics"]["programming"] is None
    unavailable = {item["block"]: item["reason"]
                   for item in course_report["data_coverage"]["unavailable"]}
    assert unavailable.get("programming") == "not_applicable_in_this_space"
    assert "programming" not in course_report["data_coverage"]["available_blocks"]

    # …and the programming space reports materials as unavailable rather than zero
    programming = _report(client, service_key="programming", course_id="",
                          language="Python")
    assert programming["structured_metrics"]["materials"] is None
    assert programming["structured_metrics"]["programming"] is not None
    assert programming["structured_metrics"]["programming"]["runs"] == 0   # a real zero


# ================================================================ 3. the narrative


def test_the_narrative_receives_the_structured_report_only(client, db_session, monkeypatch):
    register_and_login(client, "p3b_report_narrative")
    grant_unified_tier(db_session, "p3b_report_narrative", "advanced")
    user = _user(db_session, "p3b_report_narrative")
    _own_course(db_session, user.username)
    # a distinctive string that lives in the learner's raw study data
    _record(db_session, user, qid=9831, correct=False, answer=SECRET_STEM)

    captured: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider(capture=captured))

    body = _report(client, include_narrative=True)
    assert body["narrative"]["text"] == NARRATIVE_TEXT
    assert body["narrative"]["origin"] == "ai"
    assert body["narrative"]["capability"] == "report.generate"
    assert body["narrative"]["request_id"]

    assert captured, "the narrative must go through the provider seam"
    prompt = captured[0]
    # it sees the computed metrics …
    assert "structured_metrics" in prompt
    assert '"attempts"' in prompt
    # … and NONE of the learner's raw study text
    assert SECRET_STEM not in prompt
    assert "user_answer" not in prompt
    assert "attempt_history" not in prompt


def test_the_narrative_requires_the_capability_and_degrades_honestly(client, db_session,
                                                                     monkeypatch):
    register_and_login(client, "p3b_report_gate")
    user = _user(db_session, "p3b_report_gate")
    _own_course(db_session, user.username)
    calls: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider(capture=calls))

    # Standard does not hold report.generate → no narrative is produced, no model is called,
    # and the reason is STATED on the report the learner can still read
    grant_unified_tier(db_session, "p3b_report_gate", "standard")
    denied = client.post(REPORT, json={"service_key": "course_learning", "course_id": COURSE,
                                       "include_narrative": True})
    assert denied.status_code == 200, denied.text
    assert denied.json()["narrative"] is None
    assert denied.json()["narrative_error"] == "capability_not_permitted"
    assert calls == []
    # …and the deterministic report itself is available without asking for a narrative
    assert _report(client)["narrative"] is None

    # Advanced holds it: the narrative is produced, billed and settled
    grant_unified_tier(db_session, "p3b_report_gate", "advanced")
    body = _report(client, include_narrative=True)
    assert body["narrative"]["text"] == NARRATIVE_TEXT

    from usage.models import AIRequest
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user.id,
                       AIRequest.capability == "report.generate").one())
    assert request.status == "settled"
    assert request.service_namespace == "course_learning"

    from data_plane.models import LearningEvent
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id,
                      LearningEvent.event_type == "report_generated").all())
    assert events, "a generated report is a canonical fact"
    assert all(event.service_key == "course_learning" for event in events)


def test_a_narrative_failure_keeps_the_deterministic_report(client, db_session, monkeypatch):
    register_and_login(client, "p3b_report_fail")
    grant_unified_tier(db_session, "p3b_report_fail", "advanced")
    user = _user(db_session, "p3b_report_fail")
    _own_course(db_session, user.username)
    _record(db_session, user, qid=9841, correct=True)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: FakeProvider(behavior="raise_timeout", provider=name))

    body = _report(client, include_narrative=True)
    assert body["narrative"] is None
    # the boundary's refusal code is reported as itself (429: the usage answer, which is also
    # what this boundary maps a technical failure to), and NOT simulated with text
    assert body["narrative_error"] == "http_429"
    # the metrics are still there — a failed add-on never discards the deliverable
    assert body["structured_metrics"]["practice"]["attempts"] == 1
