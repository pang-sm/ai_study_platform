"""STEP 7G-C2: every Course production AI call runs the unified AI boundary.

    Endpoint → authenticated user → canonical LearningContext → AIOrchestrator
             → Capability Permission → Router → Estimate → Reserve → Gateway
             → Actual Usage → Settle → domain postprocess

These tests never touch a live provider and never mock the orchestrator: the real
permission / router / pool / estimate / reserve / settle lifecycle runs, and only the
outbound provider call is replaced by ``FakeProvider``. That is the difference between
proving "the boundary is called" and proving "the lifecycle decides".
"""
import dataclasses
import json

import pytest
from fastapi import HTTPException

from ai.providers import FakeProvider
from core.learning_context import LearningContext, ServiceNamespace
from data_plane.models import LearningEvent
from learning.spaces.course_learning.ai import execute_course_ai
from learning.spaces.course_learning.context import build_course_context
from models import CourseLearningPreference, User
from usage import service as usage_service
from usage.models import AIRequest, UsageLedger
from conftest import register_and_login
import main

COURSE = ServiceNamespace.COURSE_LEARNING
NS = "course_learning"

FREE_ALLOWED = ("tutor.chat", "material.qa", "question.explain")
FREE_DENIED = ("question.generate", "knowledge.structure", "planning.generate",
               "report.generate")
STANDARD_ALLOWED = ("question.generate", "planning.generate", "knowledge.structure")
ADVANCED_ALLOWED = ("report.generate",)
ALL_CAPABILITIES = FREE_ALLOWED + FREE_DENIED


# ---------------------------------------------------------------- doubles

class CountingProvider(FakeProvider):
    """FakeProvider that records the outbound calls that actually happened."""

    def __init__(self, calls: list, content: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._calls = calls
        self._content = content

    def complete(self, spec):
        self._calls.append((self.name, spec.model, spec.capability))
        response = super().complete(spec)
        if self._content is None:
            return response
        return dataclasses.replace(response, content=self._content)


def _factory(calls: list, content: str | None = None, behavior: str = "success"):
    def _make(name: str) -> FakeProvider:
        # Small fixed usage keeps actual credits inside the reservation, so the path
        # under test is the normal settlement, not the overage anomaly.
        return CountingProvider(calls, content=content, provider=name, behavior=behavior,
                                input_tokens=50, output_tokens=50)
    return _make


@pytest.fixture
def provider(monkeypatch):
    """Patch the one seam: how the orchestrator obtains a provider adapter."""
    calls: list = []

    def _install(content: str | None = None, behavior: str = "success") -> list:
        monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                            _factory(calls, content, behavior))
        return calls

    return _install


@pytest.fixture(autouse=True)
def no_direct_provider(monkeypatch):
    """A Course path that reaches legacy `call_deepseek` fails loudly, not silently."""
    monkeypatch.setattr(main, "call_deepseek", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Course AI reached a direct provider call")))


# ---------------------------------------------------------------- helpers

def _make_user(session, username, tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        usage_service.activate_subscription(session, u.id, tier, 30)
    return u


def _attach_course(session, user, course_id="data_structure"):
    row = CourseLearningPreference(username=user.username, course_id=course_id,
                                   display_name=course_id, mastery_level="",
                                   learning_goal="")
    session.add(row)
    session.commit()
    return row


def _context(user, course_id="data_structure", **overrides):
    return build_course_context(user, course_id=course_id, **overrides)


def _messages(text="请解释线性表"):
    return [{"role": "user", "content": text}]


def _ledger_rows(db, request_id):
    return db.query(UsageLedger).filter(UsageLedger.request_id == request_id).all()


def _activate(username, tier):
    """Give an existing user a unified subscription at `tier`."""
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        usage_service.activate_subscription(db, user.id, tier, 30)


# ---------------------------------------------------------------- tier matrix

@pytest.mark.parametrize("capability", FREE_ALLOWED)
def test_free_tier_may_use_its_capabilities(db_session, provider, capability):
    u = _make_user(db_session, f"cai-free-{capability.replace('.', '-')}", tier="free")
    calls = provider()
    result = execute_course_ai(db_session, u, capability, _messages(),
                               learning_context=_context(u), max_tokens=200)
    assert result.content == "fake response"
    assert len(calls) == 1

    req = db_session.query(AIRequest).filter(
        AIRequest.request_id == result.request_id).one()
    assert req.status == "settled"
    assert req.capability == capability


@pytest.mark.parametrize("capability", FREE_DENIED)
def test_free_tier_is_denied_without_reaching_a_provider(db_session, provider, capability):
    u = _make_user(db_session, f"cai-freex-{capability.replace('.', '-')}", tier="free")
    calls = provider()
    with pytest.raises(HTTPException) as exc:
        execute_course_ai(db_session, u, capability, _messages(),
                          learning_context=_context(u), max_tokens=200)
    assert exc.value.status_code == 403
    assert calls == [], "a denied capability must not invoke any provider"

    # Denial is decided before any durable request/billing fact is created.
    assert db_session.query(AIRequest).filter(AIRequest.user_id == u.id).count() == 0
    assert db_session.query(UsageLedger).filter(UsageLedger.user_id == u.id).count() == 0

    denied = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == u.id, LearningEvent.event_type == "ai_called")
              .all())
    assert len(denied) == 1
    assert json.loads(denied[0].item_snapshot_json)["status"] == "denied"
    assert denied[0].service_key == NS


@pytest.mark.parametrize("capability", STANDARD_ALLOWED)
def test_standard_tier_may_use_its_capabilities(db_session, provider, capability):
    u = _make_user(db_session, f"cai-std-{capability.replace('.', '-')}", tier="standard")
    calls = provider()
    result = execute_course_ai(db_session, u, capability, _messages(),
                               learning_context=_context(u), max_tokens=200)
    assert result.content == "fake response"
    assert len(calls) == 1


@pytest.mark.parametrize("capability", ADVANCED_ALLOWED)
def test_advanced_tier_may_use_report_generate(db_session, provider, capability):
    u = _make_user(db_session, f"cai-adv-{capability.replace('.', '-')}", tier="advanced")
    calls = provider()
    result = execute_course_ai(db_session, u, capability, _messages(),
                               learning_context=_context(u), max_tokens=200)
    assert result.content == "fake response"
    assert len(calls) == 1


def test_standard_tier_is_denied_report_generate(db_session, provider):
    """The tier policy is a real boundary, not a superset handed to everyone."""
    u = _make_user(db_session, "cai-std-report", tier="standard")
    calls = provider()
    with pytest.raises(HTTPException) as exc:
        execute_course_ai(db_session, u, "report.generate", _messages(),
                          learning_context=_context(u), max_tokens=200)
    assert exc.value.status_code == 403
    assert calls == []


def test_knowledge_structure_inherits_the_question_generate_pool():
    """STRUCTURED_GENERATION_PROXY_V1 — a product capability, not a new benchmark."""
    from ai.pool import (
        CAPABILITY_QUALIFICATION_PROXIES, QUALIFIED_POOL, qualified_models_for,
    )
    assert CAPABILITY_QUALIFICATION_PROXIES["knowledge.structure"] == "question.generate"

    for tier in ("standard", "advanced"):
        inherited = {e.model for e in qualified_models_for(tier, "knowledge.structure")}
        assert inherited, f"knowledge.structure/{tier} must inherit a qualified model"
        assert inherited == {e.model for e in qualified_models_for(tier, "question.generate")}
    assert any("knowledge.structure" in e.capabilities for e in QUALIFIED_POOL)


def test_knowledge_structure_tier_policy():
    from usage.capabilities import check_capability_permission
    assert check_capability_permission("free", "knowledge.structure")["allowed"] is False
    assert check_capability_permission("standard", "knowledge.structure")["allowed"] is True
    assert check_capability_permission("advanced", "knowledge.structure")["allowed"] is True


# ---------------------------------------------------------------- budget

def test_insufficient_budget_denies_before_any_provider_call(db_session, provider):
    u = _make_user(db_session, "cai-budget", tier="standard")
    calls = provider()

    budget = usage_service.get_or_create_budget(db_session, u.id, "daily")
    budget.settled_amount = budget.budget_amount   # nothing left
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        execute_course_ai(db_session, u, "tutor.chat", _messages(),
                          learning_context=_context(u), max_tokens=200)
    assert exc.value.status_code == 429
    assert calls == [], "budget denial must happen before the provider is invoked"

    # A reservation that never succeeded leaves no request and no ledger fact.
    assert db_session.query(AIRequest).filter(AIRequest.user_id == u.id).count() == 0
    assert db_session.query(UsageLedger).filter(UsageLedger.user_id == u.id).count() == 0


def test_budget_denial_is_reported_as_a_budget_failure(db_session, provider):
    from ai.orchestrator import AIOrchestrator

    u = _make_user(db_session, "cai-budget-reason", tier="standard")
    calls = provider()
    budget = usage_service.get_or_create_budget(db_session, u.id, "daily")
    budget.settled_amount = budget.budget_amount
    db_session.commit()

    result = AIOrchestrator().execute(db_session, u.id, "tutor.chat", _messages(),
                                      learning_context=_context(u), max_tokens=200)
    assert result.ok is False
    assert result.status == "denied"
    assert result.error_category == "budget_incompatible"
    assert calls == []


# ---------------------------------------------------------------- context

def test_course_context_is_persisted_and_reaches_the_ai_event(db_session, provider):
    """AIRequest / ai_called / UsageLedger carry ONE canonical course context."""
    u = _make_user(db_session, "cai-context", tier="standard")
    _attach_course(db_session, u)
    calls = provider()
    context = _context(u, chapter_id="1", knowledge_point_id="3",
                       material_ids=["7"], session_id=11)
    result = execute_course_ai(db_session, u, "material.qa", _messages(),
                               learning_context=context, max_tokens=200)
    db_session.expire_all()

    req = db_session.query(AIRequest).filter(
        AIRequest.request_id == result.request_id).one()
    assert req.service_namespace == NS
    assert req.context_json == context.to_dict()

    rows = _ledger_rows(db_session, result.request_id)
    assert rows, "a settled request must have ledger facts"
    assert {r.service_namespace for r in rows} == {NS}

    event = (db_session.query(LearningEvent)
             .filter(LearningEvent.source_attempt_id == result.request_id,
                     LearningEvent.event_type == "ai_called")
             .one())
    assert event.service_key == NS
    assert event.course_id == "data_structure"
    assert json.loads(event.knowledge_point_ref_json) == {"knowledge_point_id": "3"}


def test_course_ai_refuses_a_context_from_another_space(db_session):
    u = _make_user(db_session, "cai-wrongid", tier="standard")
    foreign = LearningContext(user_id=u.id, service_namespace=ServiceNamespace.EXAM_PREP,
                              course_id="data_structure")
    with pytest.raises(ValueError):
        execute_course_ai(db_session, u, "tutor.chat", _messages(),
                          learning_context=foreign, max_tokens=200)


def test_course_ai_refuses_a_context_owned_by_another_user(db_session):
    owner = _make_user(db_session, "cai-owner", tier="standard")
    other = _make_user(db_session, "cai-other", tier="standard")
    with pytest.raises(ValueError):
        execute_course_ai(db_session, other, "tutor.chat", _messages(),
                          learning_context=_context(owner), max_tokens=200)


# ---------------------------------------------------------------- routes

def _kb_items():
    return json.dumps(
        {"items": [{"title": "线性表", "description": "顺序存储结构",
                    "children": [{"title": "顺序表", "description": ""}]}]},
        ensure_ascii=False)


def test_knowledge_points_preview_runs_through_the_orchestrator(client, provider):
    register_and_login(client, "cai-kp-std")
    _activate("cai-kp-std", "standard")
    calls = provider(content=_kb_items())

    r = client.post("/knowledge-points/generate-preview",
                    json={"username": "cai-kp-std", "course_id": "data_structure",
                          "course_name": "数据结构", "mode": "course_name"})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["title"] == "线性表"
    assert len(calls) == 1
    assert calls[0][2] == "knowledge.structure"
    # a preview stays a preview: nothing is persisted as learner knowledge
    assert "knowledge_point_id" not in r.json()["items"][0]


def test_knowledge_points_preview_mode_materials_carries_material_context(client, provider):
    """mode=materials must pass its material ids — the interrupted batch read an
    undefined name here, so this asserts the whole branch, not just the happy path."""
    register_and_login(client, "cai-kp-materials")
    _activate("cai-kp-materials", "standard")
    calls = provider(content=_kb_items())

    _add_material("cai-kp-materials")

    r = client.post("/knowledge-points/generate-preview",
                    json={"username": "cai-kp-materials", "course_id": "data_structure",
                          "course_name": "数据结构", "mode": "materials"})
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    assert calls[0][2] == "knowledge.structure"

    import database
    with database.SessionLocal() as db:
        req = (db.query(AIRequest).filter(AIRequest.capability == "knowledge.structure")
               .order_by(AIRequest.id.desc()).first())
    assert req.context_json["material_ids"], "the cited materials must reach the context"


def test_knowledge_points_preview_denies_free_before_the_provider(client, provider):
    register_and_login(client, "cai-kp-free")
    calls = provider(content=_kb_items())
    r = client.post("/knowledge-points/generate-preview",
                    json={"username": "cai-kp-free", "course_id": "data_structure",
                          "course_name": "数据结构", "mode": "course_name"})
    assert r.status_code == 403, r.text
    assert calls == []


def test_course_chat_never_accepts_a_client_supplied_capability(client, provider):
    """The SERVER chooses material.qa vs tutor.chat; the client cannot name a capability."""
    from schemas import ChatRequest
    assert "capability" not in ChatRequest.model_fields

    register_and_login(client, "cai-chat")
    calls = provider()
    # /chat resolves its scope to the course DISPLAY name, so the material must match it.
    material_id = _add_material("cai-chat", subject="数据结构")

    plain = client.post("/chat", json={"message": "什么是线性表",
                                       "subject": "data_structure"})
    assert plain.status_code == 200, plain.text
    assert calls[-1][2] == "tutor.chat"

    grounded = client.post("/chat", json={"message": "这道题为什么选 A",
                                          "subject": "data_structure",
                                          "material_ids": [material_id]})
    assert grounded.status_code == 200, grounded.text
    assert calls[-1][2] == "material.qa"


def _add_material(username, subject="data_structure", text="线性表是 n 个数据元素的有限序列。"):
    import database
    from models import StudyMaterial
    with database.SessionLocal() as db:
        row = StudyMaterial(username=username, subject=subject,
                            original_filename="线性表.txt", file_type="text",
                            file_path=f"test/{username}-linear-list.txt",
                            extracted_text=text, summary=text[:80],
                            parse_status="success", chunk_count=1, is_deleted=False)
        db.add(row)
        db.commit()
        return row.id


def test_course_chat_request_context_is_course_learning(client, provider):
    register_and_login(client, "cai-chat-ctx")
    provider()
    r = client.post("/chat", json={"message": "什么是线性表", "subject": "data_structure"})
    assert r.status_code == 200, r.text

    import database
    with database.SessionLocal() as db:
        req = (db.query(AIRequest).filter(AIRequest.capability == "tutor.chat")
               .order_by(AIRequest.id.desc()).first())
    assert req.service_namespace == NS
    assert req.context_json["service_namespace"] == NS


def test_feedback_commits_the_answer_before_the_ai_runs(client, provider):
    """§11: the learner's answer is the durable fact; the AI feedback enriches it.

    A provider outage must not erase what the learner did, and a retry must not be able
    to fabricate a second attempt.
    """
    register_and_login(client, "cai-feedback")
    question_id = _add_question("cai-feedback")

    provider(behavior="raise_timeout")
    r = client.post(f"/practice/questions/{question_id}/feedback",
                    json={"username": "cai-feedback", "user_answer": "A"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai_feedback_available"] is False
    assert body["feedback"] is None
    assert body["attempt"]["user_answer"] == "A"

    import database
    from models import QuestionAttempt
    with database.SessionLocal() as db:
        attempts = (db.query(QuestionAttempt)
                    .filter(QuestionAttempt.question_id == question_id).all())
    assert len(attempts) == 1, "the answer fact must survive the AI failure"
    assert attempts[0].user_answer == "A"


def _add_question(username, course_id="data_structure"):
    import database
    from models import Question
    with database.SessionLocal() as db:
        row = Question(username=username, course_id=course_id, title="线性表",
                       content="以下哪个是线性表？", type="choice",
                       options="A. 数组\nB. 树", answer="A", source="manual")
        db.add(row)
        db.commit()
        return row.id


# ---------------------------------------------------------------- full E2E

def test_free_user_course_ai_e2e(db_session, provider):
    """Free user, full course loop INCLUDING the AI hop.

    course context → material.qa → AIRequest/ledger/settlement → practice attempt →
    WrongAnswer ACTIVE → later correct → RESOLVED → knowledge moves once → Records carry
    ai_called + question_answered + knowledge_status_changed, all in course_learning.
    """
    from datetime import datetime

    from learning.practice import service as practice_service
    from learning.practice.refs import QuestionRef, QuestionSourceType
    from learning.spaces.course_learning import knowledge as course_knowledge
    from learning.spaces.course_learning import service as course_service
    from learning.wrong_answers import service as wrong_service
    from models import KnowledgePoint
    from usage.models import AICostRecord

    u = _make_user(db_session, "cai-e2e", tier="free")     # Free: no subscription
    _attach_course(db_session, u, "ds")
    calls = provider()

    # 1. one orchestrated AI call, owned by the course space
    result = execute_course_ai(db_session, u, "material.qa", _messages(),
                               learning_context=_context(u, "ds"), max_tokens=200)
    assert result.status == "settled"

    # 2. one provider invocation → exactly one request, one cost record, one settlement
    req = db_session.query(AIRequest).filter(AIRequest.request_id == result.request_id).one()
    assert (db_session.query(AICostRecord)
            .filter(AICostRecord.request_id == result.request_id).count() == 1)
    settle_rows = [r for r in _ledger_rows(db_session, result.request_id)
                   if r.entry_type == "settle"]
    assert len(settle_rows) == 1, "one invocation must settle exactly once"
    assert "reserve" not in {r.entry_type for r in settle_rows}
    assert req.service_namespace == NS

    # 3. practice through the shared core, then the wrong-answer lifecycle
    context = _context(u, "ds")
    session = practice_service.create_session(db_session, u, COURSE, context=context)
    ref = QuestionRef(source_type=QuestionSourceType.MATERIAL_GENERATED,
                      source_id="e2e-ai-1", service_namespace=COURSE,
                      context={"course_id": "ds"})
    practice_service.record_attempt(db_session, u, session, ref, answer="A", correct=False,
                                    submitted_at=datetime(2024, 5, 1),
                                    source=practice_service.SourceIdentity("cai_e2e", "1", None),
                                    context=context)
    states = wrong_service.list_states(db_session, u.id, service_namespace=NS)
    assert [s.status for s in states] == ["active"]

    practice_service.record_attempt(db_session, u, session, ref, answer="A", correct=True,
                                    submitted_at=datetime(2024, 5, 2),
                                    source=practice_service.SourceIdentity("cai_e2e", "2", None),
                                    context=context)
    db_session.expire_all()
    assert [s.status for s in wrong_service.list_states(db_session, u.id,
                                                        service_namespace=NS)] == ["resolved"]

    # 4. knowledge moves exactly once, through the canonical writer
    point = KnowledgePoint(username=u.username, course_id="ds", node_key="e2e-kp",
                           title="线性表", level=1)
    db_session.add(point)
    db_session.commit()
    course_knowledge.commit_and_emit(db_session, course_knowledge.apply_knowledge_change(
        db_session, username=u.username, course_id="ds", event_type="question_correct",
        knowledge_point_id=point.id, delta=45))

    # 5. records carry the answer and the knowledge move — one namespace.
    #    The AI call is an AUDIT fact, not study history: it is excluded from the
    #    user-facing course timeline (F1C6) and preserved in the database.
    records = course_service.course_records(db_session, u, "ds")["records"]
    types = [r["event_type"] for r in records]
    assert "ai_called" not in types
    assert "question_answered" in types
    assert types.count("knowledge_status_changed") == 1
    assert {r["service_namespace"] for r in records} == {NS}
    audit = (db_session.query(LearningEvent)
             .filter(LearningEvent.user_id == u.id,
                     LearningEvent.event_type == "ai_called").all())
    assert len(audit) == 1, "the AI audit fact must be preserved, only hidden"
