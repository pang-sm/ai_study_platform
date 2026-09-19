"""STEP 7H1: exam_prep canonical namespace + context compatibility foundation.

Covers the frozen decisions:

  * ``exam_prep`` is the canonical exam namespace; ``exam_11408`` and friends are
    INPUT-only aliases;
  * practice identity keys on a FROZEN token, so a legacy caller and a canonical caller
    produce ONE identity in every environment;
  * exam contexts carry track / subject / module, with ``subject_key`` kept as the legacy
    module mirror while the EVENT's subject_key column carries the exam SUBJECT;
  * an exam request can no longer be filed under ``course_learning`` (D1), and the one
    already-orchestrated exam endpoint now persists a real context (D2).
"""
import dataclasses
import json

import pytest
from fastapi import HTTPException

from ai.providers import FakeProvider
from core.learning_context import (
    LEGACY_NAMESPACE_ALIASES,
    ServiceNamespace,
    is_legacy_namespace_alias,
    is_valid_service_namespace,
    normalize_service_namespace,
)
from data_plane.models import LearningEvent
from learning.practice import identity as practice_identity
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType, resolve_source_type
from learning.spaces.exam_prep import catalog, context as exam_context, scope
from learning.spaces.exam_prep.scope import ExamScopeError
from learning.wrong_answers import service as wrong_service
from models import User
from usage import service as usage_service
from usage.models import AIRequest, UsageLedger
from conftest import register_and_login
import main

COURSE = ServiceNamespace.COURSE_LEARNING
EXAM = ServiceNamespace.EXAM_PREP
MODULES = ("data_structure", "computer_organization", "operating_system", "computer_network")


# ---------------------------------------------------------------- helpers

class CountingProvider(FakeProvider):
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


def _factory(calls: list, content: str | None = None):
    def _make(name: str) -> FakeProvider:
        return CountingProvider(calls, content=content, provider=name,
                                input_tokens=50, output_tokens=50)
    return _make


def _user(session, username, tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        usage_service.activate_subscription(session, u.id, tier, 30)
    return u


def _activate(username, tier):
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        usage_service.activate_subscription(db, user.id, tier, 30)


def _latest_request(username) -> AIRequest:
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        req = (db.query(AIRequest).filter(AIRequest.user_id == user.id)
               .order_by(AIRequest.id.desc()).first())
        assert req is not None, f"no AIRequest row for {username}"
        return req


# ---------------------------------------------------------------- A / B / C: namespace

@pytest.mark.parametrize("alias", ("exam", "exam_408", "exam-11408", "exam_11408", "11408",
                                   "exam408", "exam-prep", "exam_prep"))
def test_legacy_exam_alias_normalizes_to_exam_prep(alias):
    assert normalize_service_namespace(alias) == "exam_prep"


def test_exam_prep_is_the_only_valid_exam_namespace():
    assert is_valid_service_namespace("exam_prep") is True
    for legacy in ("exam_11408", "exam", "exam_408", "11408"):
        assert is_valid_service_namespace(legacy) is False, legacy


def test_exam_11408_is_a_legacy_input_alias_only():
    assert is_legacy_namespace_alias("exam_11408") is True
    assert is_legacy_namespace_alias("exam_prep") is False
    assert LEGACY_NAMESPACE_ALIASES["exam_11408"] == "exam_prep"


def test_three_canonical_spaces_only():
    assert {ns.value for ns in ServiceNamespace} == {
        "course_learning", "exam_prep", "programming"}


# ---------------------------------------------------------------- F: frozen identity token

def test_identity_token_is_frozen_for_exam_prep():
    """The token is a contract, not a function of the current namespace name."""
    assert practice_identity.IDENTITY_TOKEN_BY_NAMESPACE == {
        "course_learning": "course_learning",
        "exam_prep": "exam_11408",
        "programming": "programming",
    }


@pytest.mark.parametrize("legacy", ("exam_11408", "exam", "exam_408", "11408"))
def test_legacy_and_canonical_exam_inputs_produce_one_practice_identity(legacy):
    """Same logical legacy attempt → same uid, whichever spelling arrives."""
    assert practice_identity.session_uid(legacy, "exam_practice_attempt", 11, user_id=7) == \
        practice_identity.session_uid("exam_prep", "exam_practice_attempt", 11, user_id=7)
    assert practice_identity.attempt_uid(legacy, "exam_practice_attempt", 11, "q:0",
                                         user_id=7) == \
        practice_identity.attempt_uid("exam_prep", "exam_practice_attempt", 11, "q:0",
                                      user_id=7)


def test_identity_does_not_depend_on_stored_rows(db_session):
    """The uid is a pure function of the frozen token — it never reads the database."""
    uid = practice_identity.attempt_uid("exam_prep", "t", 1, "k:0", user_id=1)
    with db_session.no_autoflush:
        assert practice_identity.attempt_uid(
            "exam_11408", "t", 1, "k:0", user_id=1) == uid


def test_one_legacy_attempt_never_becomes_two_canonical_attempts(db_session):
    """Mirroring the SAME legacy row via the alias and via the canonical name dedupes.

    This is the replay shape that matters: the same legacy container + the same source
    row, arriving once as ``exam_11408`` (old code) and once as ``exam_prep`` (new code).
    """
    u = _user(db_session, "h1_idem")
    ctx = exam_context.cs408_context(u, module_key="data_structure")
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id="1001", service_namespace=EXAM,
                      context={"module": "data_structure"})
    src = practice_service.SourceIdentity("exam_legacy_row", "55", "1001:0")

    def mirror(namespace):
        session, _created = practice_service.ensure_legacy_session(
            db_session, u, namespace, source_type="exam_practice_attempt",
            source_session_key=55, mode="chapter", context=ctx, started_at=None)
        return practice_service.record_attempt(db_session, u, session, ref, answer="A",
                                               correct=False, source=src, context=ctx)

    first = mirror("exam_11408")
    second = mirror("exam_prep")

    assert first.attempt.attempt_uid == second.attempt.attempt_uid
    assert first.created is True and second.created is False, "replay must dedupe"
    rows = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(rows) == 1
    assert rows[0].service_namespace == "exam_prep"


# ---------------------------------------------------------------- D / L: CS408 context

def test_cs408_context_carries_track_subject_and_module(db_session):
    u = _user(db_session, "h1_ctx")
    ctx = exam_context.cs408_context(u, module_key="data_structure")
    assert ctx.service_namespace == EXAM
    assert ctx.exam_track_id == "cs_408"
    assert ctx.exam_subject_id == "cs_408"
    assert ctx.exam_module_id == "data_structure"
    assert ctx.subject_key == "data_structure", "legacy module mirror"


@pytest.mark.parametrize("value,idx", (
    ("data_structure_11408", 0), ("data_structure", 1),
    ("11408 数据结构", 2), ("数据结构", 3)))
def test_cs408_adapter_resolves_every_legacy_scope_form(db_session, value, idx):
    u = _user(db_session, f"h1_scope_{idx}")
    ctx = exam_context.cs408_context_from_values(u, value)
    assert (ctx.exam_track_id, ctx.exam_subject_id, ctx.exam_module_id) == \
        ("cs_408", "cs_408", "data_structure")
    assert ctx.subject_key == "data_structure"


def test_event_context_carries_subject_but_not_track(db_session):
    u = _user(db_session, "h1_evt")
    ctx = exam_context.cs408_context(u, module_key="data_structure")
    assert ctx.event_subject_key() == "cs_408"
    ec = ctx.to_event_context()
    assert ec["service_namespace"] == "exam_prep"
    assert ec["subject_key"] == "cs_408"
    assert ec["exam_module_id"] == "data_structure"
    assert "exam_track_id" not in ec, "a track is the learner's bundle, not a fact attribute"


def test_exam_event_row_stores_subject_and_module(db_session):
    """The stored event: service_key=exam_prep, subject_key=cs_408, module in context JSON."""
    u = _user(db_session, "h1_evt_row")
    ctx = exam_context.cs408_context(u, module_key="operating_system")
    session = practice_service.create_session(db_session, u, EXAM, context=ctx)
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id="2001", service_namespace=EXAM,
                      context={"module": "operating_system"})
    practice_service.record_attempt(
        db_session, u, session, ref, answer="B", correct=False,
        source=practice_service.SourceIdentity("exam_legacy_row", "77", "2001:0"),
        context=ctx)
    db_session.expire_all()

    event = (db_session.query(LearningEvent)
             .filter(LearningEvent.user_id == u.id,
                     LearningEvent.event_type == "question_answered").one())
    assert event.service_key == "exam_prep"
    assert event.subject_key == "cs_408"
    assert json.loads(event.knowledge_point_ref_json)["exam_module_id"] == "operating_system"


def test_exam_track_is_absent_from_every_identity_and_event():
    """A track must not be able to re-identify a fact or split one event into two."""
    from learning.records.envelope import domain_context_json
    assert "exam_track_id" not in domain_context_json(
        {"exam_track_id": "cs_408", "exam_module_id": "data_structure"})
    assert "exam_track_id" not in practice_identity.IDENTITY_TOKEN_BY_NAMESPACE


# ---------------------------------------------------------------- legacy scope id adapter

@pytest.mark.parametrize("module", MODULES)
def test_legacy_scope_id_round_trip(module):
    parsed = scope.parse_legacy_exam_scope_id(f"{module}_11408")
    assert parsed.exam_track_id == "cs_408"
    assert parsed.exam_subject_id == "cs_408"
    assert parsed.exam_module_id == module
    assert scope.build_legacy_exam_scope_id(module) == f"{module}_11408"


def test_legacy_scope_adapter_fails_closed():
    with pytest.raises(ExamScopeError):
        scope.parse_legacy_exam_scope_id("algebra_11408")
    with pytest.raises(ExamScopeError):
        scope.build_legacy_exam_scope_id("algebra")
    # a non-scope value is not an error, it simply is not a scope
    assert scope.parse_legacy_exam_scope_id("data_structure") is None
    assert scope.parse_legacy_exam_scope_id("") is None


def test_legacy_scope_adapter_is_pure(db_session):
    """The adapter interprets ids; it must never write to storage."""
    u = _user(db_session, "h1_pure")
    before = db_session.query(User).count()
    exam_context.cs408_context_from_values(u, "data_structure_11408")
    assert db_session.query(User).count() == before


# ---------------------------------------------------------------- catalog scope (H4 excluded)

def test_catalog_ships_only_cs408():
    assert catalog.CS408_TRACK == "cs_408"
    assert catalog.CS408_SUBJECT == "cs_408"
    assert set(catalog.CS408_MODULES) == set(MODULES)
    for h4_only in ("math_1", "politics", "english_1", "law_jm_law", "management_joint"):
        assert h4_only not in catalog.CS408_MODULES


# ---------------------------------------------------------------- E: course vs exam isolation

def test_course_and_exam_data_structure_do_not_share_state(db_session):
    """The same module string in two spaces stays two isolated facts."""
    u = _user(db_session, "h1_iso")
    course_ref = QuestionRef(source_type=QuestionSourceType.MATERIAL_GENERATED,
                             source_id="3001", service_namespace=COURSE,
                             context={"course_id": "data_structure"})
    exam_ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                           source_id="3001", service_namespace=EXAM,
                           context={"module": "data_structure"})

    cs = practice_service.create_session(db_session, u, COURSE)
    practice_service.record_attempt(db_session, u, cs, course_ref, answer="A", correct=False)
    es = practice_service.create_session(db_session, u, EXAM)
    practice_service.record_attempt(db_session, u, es, exam_ref, answer="A", correct=False)

    course_states = wrong_service.list_states(db_session, u.id,
                                              service_namespace="course_learning")
    exam_states = wrong_service.list_states(db_session, u.id, service_namespace="exam_prep")
    assert len(course_states) == 1 and len(exam_states) == 1
    assert course_states[0].id != exam_states[0].id
    assert course_states[0].service_namespace == "course_learning"
    assert exam_states[0].service_namespace == "exam_prep"


def test_source_type_resolution_accepts_both_spellings():
    assert resolve_source_type("exam_prep", "exam_question_bank") == \
        QuestionSourceType.STATIC_QUESTION_BANK
    assert resolve_source_type("exam_11408", "exam_question_bank") == \
        QuestionSourceType.STATIC_QUESTION_BANK
    assert resolve_source_type("exam", "past_paper") == QuestionSourceType.PAST_EXAM


# ---------------------------------------------------------------- G / I: D1

EXAM_SCOPE = {"course_id": "data_structure_11408", "course_name": "11408 数据结构"}
COURSE_SCOPE = {"course_id": "data_structure", "course_name": "数据结构"}

D1_CASES = (
    ("/practice/questions/generate", "standard", "question.generate",
     {"type": "choice", "count": 1}),
    ("/practice/generate-task-preview", "standard", "question.generate",
     {"knowledge_point_title": "线性表", "count": 1}),
    ("/learning/reports/generate-preview", "advanced", "report.generate",
     {"report_type": "weekly"}),
    ("/learning-report/ai-generate", "advanced", "report.generate",
     {"range_type": "7d"}),
)


@pytest.fixture
def provider(monkeypatch):
    calls: list = []

    def _install(content: str | None = None) -> list:
        monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                            _factory(calls, content))
        return calls
    return _install


@pytest.fixture
def legacy_exam_gates(monkeypatch):
    """Neutralise the LEGACY exam gates: this test targets namespace routing, not quota."""
    monkeypatch.setattr(main, "check_exam_408_usage_limit",
                        lambda *a, **k: {"allowed": True})
    monkeypatch.setattr(main, "require_learning_context_feature",
                        lambda *a, **k: {"allowed": True})


@pytest.mark.parametrize("path,tier,capability,extra", D1_CASES)
def test_exam_request_is_never_filed_as_course(client, provider, legacy_exam_gates,
                                               path, tier, capability, extra):
    name = "h1_d1x_" + path.strip("/").replace("/", "_")
    register_and_login(client, name)
    _activate(name, tier)
    provider()

    payload = {"username": name, **EXAM_SCOPE, **extra}
    client.post(path, json=payload)      # the response shape is not the subject here

    req = _latest_request(name)
    assert req.capability == capability
    assert req.service_namespace == "exam_prep", f"{path} filed an exam fact as course"
    assert req.context_json["service_namespace"] == "exam_prep"
    assert req.context_json["exam_subject_id"] == "cs_408"
    assert req.context_json["exam_module_id"] == "data_structure"


@pytest.mark.parametrize("path,tier,capability,extra", D1_CASES)
def test_course_request_through_the_same_endpoint_stays_course(client, provider,
                                                               path, tier, capability, extra):
    name = "h1_d1c_" + path.strip("/").replace("/", "_")
    register_and_login(client, name)
    _activate(name, tier)
    provider()

    payload = {"username": name, **COURSE_SCOPE, **extra}
    client.post(path, json=payload)

    req = _latest_request(name)
    assert req.capability == capability
    assert req.service_namespace == "course_learning"


def test_course_helper_defends_against_an_exam_scope(db_session, provider):
    """Even a caller reaching for the course helper cannot file an exam scope as course."""
    u = _user(db_session, "h1_defense", tier="standard")
    calls = provider()
    main._course_ai_content(db_session, u, "question.generate",
                            [{"role": "user", "content": "hi"}],
                            course_id="data_structure_11408", max_tokens=200)
    assert len(calls) == 1
    req = (db_session.query(AIRequest).filter(AIRequest.user_id == u.id)
           .order_by(AIRequest.id.desc()).first())
    assert req.service_namespace == "exam_prep"


# ---------------------------------------------------------------- H: D2

def test_question_analysis_persists_a_full_exam_context(client, provider, monkeypatch):
    register_and_login(client, "h1_d2")
    provider()
    r = client.post("/exam/11408/data_structure/question-analysis",
                    json={"stem": "什么是线性表？", "question_type": "选择题",
                          "standard_answer": "A", "user_answer": "B",
                          "options": {"A": "顺序存储", "B": "链式存储"}})
    assert r.status_code == 200, r.text
    request_id = r.json()["request_id"]

    import database
    with database.SessionLocal() as db:
        req = db.query(AIRequest).filter(AIRequest.request_id == request_id).one()
        ledger = db.query(UsageLedger).filter(UsageLedger.request_id == request_id).all()
        event = (db.query(LearningEvent)
                 .filter(LearningEvent.source_attempt_id == request_id,
                         LearningEvent.event_type == "ai_called").one())

    assert req.service_namespace == "exam_prep"
    assert req.context_json["exam_track_id"] == "cs_408"
    assert req.context_json["exam_subject_id"] == "cs_408"
    assert req.context_json["exam_module_id"] == "data_structure"
    assert ledger, "a settled request must have ledger facts"
    assert {row.service_namespace for row in ledger} == {"exam_prep"}
    assert event.service_key == "exam_prep"


# ---------------------------------------------------------------- J: duplicate routes

def test_no_duplicate_method_and_path_is_registered():
    from collections import Counter
    pairs = [(m, getattr(r, "path", ""))
             for r in main.app.routes
             for m in (getattr(r, "methods", None) or [])
             if m not in ("HEAD", "OPTIONS")]
    dupes = {k: v for k, v in Counter(pairs).items() if v > 1}
    assert dupes == {}, f"duplicate route registrations: {dupes}"


def test_exam_study_plan_tasks_summary_has_exactly_one_handler():
    handlers = [r for r in main.app.routes
                if getattr(r, "path", "") == "/exam/11408/study-plan/tasks/summary"
                and "GET" in (getattr(r, "methods", None) or [])]
    assert len(handlers) == 1
    assert handlers[0].endpoint.__name__ == "get_exam_study_plan_tasks_summary"


# ---------------------------------------------------------------- answer.grade capability

def test_answer_grade_capability_is_registered():
    from usage.capabilities import ALL_CAPABILITIES, check_capability_permission
    assert "answer.grade" in ALL_CAPABILITIES
    assert check_capability_permission("free", "answer.grade")["allowed"] is False
    assert check_capability_permission("standard", "answer.grade")["allowed"] is True
    assert check_capability_permission("advanced", "answer.grade")["allowed"] is True


def test_answer_grade_inherits_the_question_explain_pool():
    from ai.pool import (
        ANSWER_GRADE_PROFILE, CAPABILITY_QUALIFICATION_PROXIES, qualified_models_for,
    )
    assert ANSWER_GRADE_PROFILE == "QUESTION_EXPLAIN_PROXY_V1"
    assert CAPABILITY_QUALIFICATION_PROXIES["answer.grade"] == "question.explain"
    for tier in ("standard", "advanced"):
        inherited = {e.model for e in qualified_models_for(tier, "answer.grade")}
        assert inherited
        assert inherited == {e.model for e in qualified_models_for(tier, "question.explain")}


def test_grading_flow_was_registered_in_h1_and_migrated_in_h3():
    """H1 only registered the capability; STEP7H3 moved the grading call to the boundary."""
    import inspect
    import exam_paper_parser
    assert not hasattr(exam_paper_parser, "_grade_big_question"), "migrated in STEP7H3"
    src = inspect.getsource(exam_paper_parser)
    assert "OpenAI(" not in src and "DEEPSEEK_API_KEY" not in src
