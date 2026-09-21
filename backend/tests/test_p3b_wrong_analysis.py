"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3B — Deep Wrong-Cause Analysis.

WHAT THESE TESTS HOLD
---------------------
1. the FACT half is the learner's real record (their question, their answer, the reference
   answer, the real attempt history) and the AI half is a labelled hypothesis — the two are
   never merged, and the response says which is which;
2. ownership is total: another learner's state is a 404, and a state whose QUESTION cannot be
   proven to belong to the caller is refused instead of analysed from an empty stem;
3. the capability follows the unified policy, the call is billed through the ONE usage chain,
   and it is filed under the state's OWN space (a course analysis is a course request);
4. the fact that an analysis happened is durable (canonical event + the AI request), and the
   response states honestly that the analysis TEXT has no owned store this round.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json
from datetime import datetime

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from core.learning_context import LearningContext, ServiceNamespace
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.course_learning.context import build_course_context
from models import AIGeneratedQuestion, CourseLearningPreference, User
from usage.models import AIRequest

COURSE = "数据结构"
MODULE = "operating_system"
MOMENT = datetime(2026, 9, 20, 6, 30, 0)

ANALYSIS = {
    "error_category": "概念混淆",
    "reasoning_gap": "把顺序存储的下标访问复杂度当成了 O(n)",
    "correct_reasoning": "顺序存储可由基址与下标直接算出地址，因此是 O(1)",
    "next_action": "复习线性表的存储结构并做 3 道同类型题",
    "review_recommendation": "48 小时后重做该题",
}


class _ScriptedProvider(FakeProvider):
    def __init__(self, content, capture=None, **kwargs):
        super().__init__(**kwargs)
        self._content = content
        self._capture = capture

    def complete(self, spec):
        if self._capture is not None:
            self._capture.append("\n".join(m.content for m in spec.messages))
        return dataclasses.replace(super().complete(spec), content=self._content)


def _provider(capture: list | None = None):
    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(json.dumps(ANALYSIS, ensure_ascii=False),
                                 capture=capture, provider=name,
                                 input_tokens=120, output_tokens=90)
    return _make


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _ai_question(db, username, *, module=COURSE, stem, answer="A"):
    row = AIGeneratedQuestion(
        username=username, subject_key=module, subject_name=module, question_type="选择题",
        stem=stem, options_json=json.dumps({"A": "O(1)", "B": "O(n)"}, ensure_ascii=False),
        standard_answer=answer, analysis="顺序存储按下标计算地址。", quality_status="unchecked",
        generation_mode="ai")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _course_state(db, user, *, question, answer="B", source_id=None):
    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p3b_analysis",
        source_session_key=f"p3b:{COURSE}", mode="p3b", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p3b_analysis_attempt",
                                               source_id or f"q{question.id}", "0"))
    from learning.wrong_answers import service as wrong_service
    return wrong_service.list_states(db, user.id, service_namespace="course_learning")[0]


def _exam_state(db, user, *, question, answer="B"):
    context = LearningContext(user_id=user.id, service_namespace=ServiceNamespace.EXAM_PREP,
                              subject_key=MODULE, exam_subject_id="cs_408",
                              exam_module_id=MODULE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "exam_prep", source_type="p3b_exam", source_session_key="p3b:exam",
        mode="p3b", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.EXAM_PREP,
                      context={"exam_module_id": MODULE, "exam_subject_id": "cs_408",
                               "subject_key": MODULE})
    practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p3b_exam_attempt", f"e{question.id}", "0"))
    from learning.wrong_answers import service as wrong_service
    return wrong_service.list_states(db, user.id, service_namespace="exam_prep")[0]


def _analyze(client, state_id):
    return client.post(f"/wrong-answers/{state_id}/analysis")


# ================================================================ 1. facts vs analysis


def test_the_analysis_separates_facts_from_the_ai_reading(client, db_session, monkeypatch):
    register_and_login(client, "p3b_analysis_ok")
    grant_unified_tier(db_session, "p3b_analysis_ok", "standard")
    user = _user(db_session, "p3b_analysis_ok")
    _own_course(db_session, user.username)
    question = _ai_question(db_session, user.username, stem="顺序表按下标访问的复杂度？",
                            answer="A")
    state = _course_state(db_session, user, question=question, answer="B")

    captured: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(captured))

    response = _analyze(client, state.id)
    assert response.status_code == 200, response.text
    body = response.json()

    # ── the FACT half is the learner's real record
    assert body["fact_origin"] == "deterministic"
    facts = body["facts"]
    assert facts["question"]["stem"] == "顺序表按下标访问的复杂度？"
    assert facts["question"]["reference_answer"] == "A"
    assert facts["question"]["explanation"] == "顺序存储按下标计算地址。"
    assert facts["user_answer"] == "B"
    assert facts["wrong_count"] == 1
    assert facts["attempt_history"][-1]["correct"] is False
    assert facts["source"]["question_source_id"] == str(question.id)

    # ── the AI half is labelled as such
    assert body["analysis_origin"] == "ai"
    assert body["analysis"]["error_category"] == ANALYSIS["error_category"]
    assert body["analysis"]["next_action"] == ANALYSIS["next_action"]
    assert "不是对学习者能力的测量" in body["analysis_semantics"]

    # the model saw the recorded facts (and only them)
    assert captured and "顺序表按下标访问的复杂度？" in captured[0]

    # ── billed through the ONE chain, filed under the state's own space
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user.id,
                       AIRequest.capability == "wrong_answer.analyze").one())
    assert request.status == "settled"
    assert request.service_namespace == "course_learning"
    assert body["request_id"] == request.request_id
    assert body["usage"]["actual_credits"] == request.actual_credits

    # ── the FACT that an analysis happened is durable; the text is not (stated honestly)
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id,
                      LearningEvent.event_type == "wrong_analysis_generated").all())
    assert events and all(event.service_key == "course_learning" for event in events)
    payload = json.loads(events[0].item_snapshot_json)
    assert payload["state_id"] == str(state.id)
    assert ANALYSIS["reasoning_gap"] not in events[0].item_snapshot_json   # no AI text
    assert body["persistence"]["stored"] is False
    assert body["persistence"]["reason"] == "no_owned_store_for_ai_analysis_text"


def test_an_exam_state_is_analysed_in_the_exam_context(client, db_session, monkeypatch):
    register_and_login(client, "p3b_analysis_exam")
    grant_unified_tier(db_session, "p3b_analysis_exam", "standard")
    user = _user(db_session, "p3b_analysis_exam")
    question = _ai_question(db_session, user.username, module=MODULE,
                            stem="进程调度的时机？", answer="A")
    state = _exam_state(db_session, user, question=question)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    body = _analyze(client, state.id).json()
    assert body["service_namespace"] == "exam_prep"
    assert body["facts"]["context"]["exam_module_id"] == MODULE

    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user.id,
                       AIRequest.capability == "wrong_answer.analyze").one())
    assert request.service_namespace == "exam_prep"


# ================================================================ 2. isolation & gating


def test_another_learners_state_is_a_404(client, db_session, monkeypatch):
    register_and_login(client, "p3b_analysis_stranger")
    grant_unified_tier(db_session, "p3b_analysis_stranger", "standard")
    stranger = _user(db_session, "p3b_analysis_stranger")
    _own_course(db_session, stranger.username)
    question = _ai_question(db_session, stranger.username, stem="别人的错题")
    state = _course_state(db_session, stranger, question=question)

    register_and_login(client, "p3b_analysis_caller")
    grant_unified_tier(db_session, "p3b_analysis_caller", "standard")
    calls: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(calls))

    refused = _analyze(client, state.id)
    assert refused.status_code == 404, refused.text
    assert calls == []


def test_a_state_whose_question_cannot_be_proven_is_not_analysed(client, db_session,
                                                                monkeypatch):
    """A state pointing at ANOTHER learner's question must not be analysed (no empty-stem
    analysis, and no cross-user read through the analysis path)."""
    register_and_login(client, "p3b_analysis_owner2")
    stranger_question = _ai_question(db_session, "p3b_analysis_owner2", stem="陌生人的题面")

    register_and_login(client, "p3b_analysis_me")
    grant_unified_tier(db_session, "p3b_analysis_me", "standard")
    me = _user(db_session, "p3b_analysis_me")
    _own_course(db_session, me.username)
    state = _course_state(db_session, me, question=stranger_question)
    calls: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(calls))

    refused = _analyze(client, state.id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "question_content_unavailable"
    assert calls == []
    assert db_session.query(AIRequest).filter(
        AIRequest.user_id == me.id,
        AIRequest.capability == "wrong_answer.analyze").count() == 0


def test_the_analysis_follows_the_capability_policy(client, db_session, monkeypatch):
    register_and_login(client, "p3b_analysis_free")
    user = _user(db_session, "p3b_analysis_free")
    _own_course(db_session, user.username)
    question = _ai_question(db_session, user.username, stem="免费档的错题")
    state = _course_state(db_session, user, question=question)
    calls: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(calls))

    denied = _analyze(client, state.id)
    assert denied.status_code == 403, denied.text
    assert calls == []

    grant_unified_tier(db_session, "p3b_analysis_free", "standard")
    allowed = _analyze(client, state.id)
    assert allowed.status_code == 200, allowed.text
    assert calls, "an allowed analysis really reaches the provider seam"
