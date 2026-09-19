"""STEP 7G: Course Learning Space — namespace, identity, shared-core wiring, isolation."""
from datetime import datetime

import pytest
from core.learning_context import (
    LEGACY_NAMESPACE_ALIASES,
    ServiceNamespace,
    is_valid_service_namespace,
    normalize_service_namespace,
)
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import service as records_service
from learning.spaces.course_learning import context as course_context
from learning.spaces.course_learning import knowledge as course_knowledge
from learning.spaces.course_learning import service as course_service
from learning.wrong_answers import service as wrong_service
from models import CourseLearningPreference, KnowledgePoint, User, UserKnowledgeProgress

COURSE = ServiceNamespace.COURSE_LEARNING


def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def attach_course(session, user, course_id, *, display_name=None):
    row = CourseLearningPreference(username=user.username, course_id=course_id,
                                   display_name=display_name or course_id,
                                   mastery_level="", learning_goal="")
    session.add(row)
    session.commit()
    return row


def make_knowledge_point(session, user, course_id, *, node_key, title="kp"):
    point = KnowledgePoint(username=user.username, course_id=course_id,
                           node_key=node_key, title=title, level=1)
    session.add(point)
    session.commit()
    return point


def record(db, user, course_id, *, qid, correct, when=None, source=None):
    ctx = course_context.build_course_context(user, course_id=course_id)
    session = practice_service.create_session(db, user, COURSE, context=ctx)
    ref = QuestionRef(source_type=QuestionSourceType.MATERIAL_GENERATED,
                      source_id=qid, service_namespace=COURSE,
                      context={"course_id": course_id})
    source_identity = (practice_service.SourceIdentity(*source) if source else None)
    return practice_service.record_attempt(
        db, user, session, ref, answer="A", correct=correct, submitted_at=when,
        source=source_identity, context=ctx).attempt


def events_for(db, user_id, event_type=None):
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


# ---------------------------------------------------------------- namespace

def test_course_alias_normalizes_to_the_canonical_namespace():
    assert normalize_service_namespace("course") == "course_learning"
    assert normalize_service_namespace("course_learning") == "course_learning"
    assert normalize_service_namespace(ServiceNamespace.COURSE_LEARNING) == "course_learning"


def test_canonical_namespace_is_the_only_valid_storage_value():
    assert is_valid_service_namespace("course_learning") is True
    assert is_valid_service_namespace("course") is False      # alias is INPUT only


def test_unknown_namespace_fails_loudly():
    with pytest.raises(ValueError):
        normalize_service_namespace("not_a_space")


def test_alias_and_canonical_input_produce_identical_storage(db_session):
    """The alias is normalized ONCE at the boundary — never stored."""
    a = practice_service._namespace_value("course")
    b = practice_service._namespace_value("course_learning")
    assert a == b == "course_learning"
    for module in (wrong_service, records_service):
        assert module._namespace_value("course") == "course_learning"


def test_every_alias_targets_a_real_namespace():
    for alias, target in LEGACY_NAMESPACE_ALIASES.items():
        assert target in {ns.value for ns in ServiceNamespace}, alias


# ---------------------------------------------------------------- identity

def test_course_id_is_normalized_by_whitespace_only():
    # case-folding would silently split or merge real courses
    assert course_context.normalize_course_id("  DataStruct  ") == "DataStruct"
    with pytest.raises(course_context.CourseContextError):
        course_context.normalize_course_id("   ")


def test_course_context_carries_chapter_and_knowledge_identity(db_session):
    u = make_user(db_session, "cs_ctx")
    ctx = course_context.build_course_context(
        u, course_id="ds", chapter_id="1.2", knowledge_point_id="kp-7",
        material_ids=[3, 4])
    assert ctx.service_namespace == COURSE
    assert ctx.course_id == "ds"
    assert ctx.chapter_id == "1.2"
    assert ctx.knowledge_point_id == "kp-7"
    assert ctx.material_ids == ["3", "4"]


def test_context_requires_the_user_to_actually_have_the_course(db_session):
    u = make_user(db_session, "cs_ctx2")
    with pytest.raises(course_context.CourseContextError):
        course_context.resolve_course_context(db_session, u, "ghost-course")


def test_context_course_mismatch_is_refused(db_session):
    u = make_user(db_session, "cs_ctx3")
    ctx = course_context.build_course_context(u, course_id="A")
    course_context.assert_course_matches(ctx, "A")
    with pytest.raises(course_context.CourseContextError):
        course_context.assert_course_matches(ctx, "B")


def test_no_course_table_is_introduced():
    """Course identity stays the free-form key the data already uses."""
    import models
    assert not [n for n in dir(models) if n in ("Course", "CourseChapter", "Courses")]


# ---------------------------------------------------------------- knowledge writer

def test_canonical_writer_derives_status_and_emits_on_transition(db_session):
    u = make_user(db_session, "cs_kw1")
    attach_course(db_session, u, "ds")
    point = make_knowledge_point(db_session, u, "ds", node_key="kp1")

    t = course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw1", course_id="ds", event_type="question_correct",
        knowledge_point_id=point.id, delta=45)
    assert t.old_status == "not_started" and t.new_status == "reviewing"
    course_knowledge.commit_and_emit(db_session, t)

    rows = events_for(db_session, u.id, "knowledge_status_changed")
    assert len(rows) == 1
    assert rows[0].service_key == "course_learning"


def test_canonical_writer_does_not_emit_when_status_is_unchanged(db_session):
    u = make_user(db_session, "cs_kw2")
    attach_course(db_session, u, "ds")
    point = make_knowledge_point(db_session, u, "ds", node_key="kp2")

    t1 = course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw2", course_id="ds", event_type="question_correct",
        knowledge_point_id=point.id, delta=45)
    course_knowledge.commit_and_emit(db_session, t1)
    t2 = course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw2", course_id="ds", event_type="question_correct",
        knowledge_point_id=point.id, delta=1)
    result = course_knowledge.commit_and_emit(db_session, t2)
    assert result["reason"] == "status_unchanged"
    assert len(events_for(db_session, u.id, "knowledge_status_changed")) == 1


def test_writer_refuses_a_knowledge_point_from_another_course(db_session):
    u = make_user(db_session, "cs_kw3")
    attach_course(db_session, u, "A")
    attach_course(db_session, u, "B")
    point_b = make_knowledge_point(db_session, u, "B", node_key="kpB")

    t = course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw3", course_id="A", event_type="question_correct",
        knowledge_point_id=point_b.id, delta=10)
    assert t is None                      # cross-course write refused


def test_user_confirmed_status_is_protected_from_practice_suggestions(db_session):
    u = make_user(db_session, "cs_kw4")
    attach_course(db_session, u, "ds")
    make_knowledge_point(db_session, u, "ds", node_key="kp4")
    # learner explicitly confirms 'learning'
    course_knowledge.commit_and_emit(db_session, course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw4", course_id="ds", event_type="manual_update",
        knowledge_point_code="kp4", target_status="learning", confirm=True))

    # a practice suggestion must not overwrite it
    course_knowledge.commit_and_emit(db_session, course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw4", course_id="ds", event_type="question_correct",
        knowledge_point_code="kp4", delta=15, protect_user_confirmed=True,
        set_system_suggested=True))

    row = db_session.query(UserKnowledgeProgress).filter_by(
        username="cs_kw4", course_id="ds", knowledge_point_code="kp4").first()
    assert row.status == "learning"                 # learner's choice stands
    assert row.system_suggested_status == "learning"


def test_writer_lands_on_the_callers_pending_row(db_session):
    """autoflush=False means the writer must flush, or it would create a duplicate."""
    u = make_user(db_session, "cs_kw5")
    attach_course(db_session, u, "ds")
    pending = UserKnowledgeProgress(username="cs_kw5", course_id="ds",
                                    knowledge_point_id=0, knowledge_point_code="kp5",
                                    mastery_score=0, status="not_started",
                                    practice_count=0, task_count=0)
    db_session.add(pending)                        # deliberately NOT flushed
    course_knowledge.apply_knowledge_change(
        db_session, username="cs_kw5", course_id="ds", event_type="question_correct",
        knowledge_point_code="kp5", delta=10)
    db_session.commit()
    rows = db_session.query(UserKnowledgeProgress).filter_by(
        username="cs_kw5", course_id="ds", knowledge_point_code="kp5").all()
    assert len(rows) == 1


def test_course_mutation_paths_are_consolidated():
    """§56 gate: no course path may silently bypass the canonical writer."""
    remaining = course_knowledge.course_paths_not_consolidated()
    assert remaining == [], f"course paths still bypassing the writer: {remaining}"
    inventory = {row["path"]: row["status"] for row in course_knowledge.course_mutation_paths()}
    assert inventory["PATCH /knowledge-map/progress"] == "CANONICAL_WRITER"
    assert inventory["POST /practice/submit-result"] == "CANONICAL_WRITER"
    # Regenerating the knowledge tree replaces content; it is declared, not hidden.
    assert inventory["POST /knowledge-path/generate-from-materials"] \
        == "CONTENT_REPLACEMENT_NO_EVENT"


def test_every_course_knowledge_writer_is_declared():
    """A writer may only bypass the canonical writer under a declared status."""
    allowed = {"CANONICAL_WRITER", "SYSTEM_DERIVED_NO_EVENT", "CONTENT_REPLACEMENT_NO_EVENT"}
    for row in course_knowledge.course_mutation_paths():
        assert row["status"] in allowed, row
        assert row.get("note"), f"{row['path']} must state why it is classified this way"


def test_out_of_scope_spaces_are_declared_not_silently_skipped():
    statuses = {(row["space"], row["path"]): row["status"]
                for row in course_knowledge.mutation_path_inventory()}
    assert statuses[("exam_prep", "PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}")] \
        == "OUT_OF_SCOPE_SPACE"
    assert any(space == "programming" for space, _ in statuses)


# ---------------------------------------------------------------- shared core

def test_course_practice_reaches_the_shared_core(db_session):
    u = make_user(db_session, "cs_p1")
    attach_course(db_session, u, "ds")
    course_context.resolve_course_context(db_session, u, "ds")
    attempt = record(db_session, u, "ds", qid="q1", correct=False,
                     when=datetime(2024, 4, 1), source=("course_practice_mirror", "1", None))
    assert attempt.service_namespace == "course_learning"
    # the shared emitter produced the canonical event
    assert events_for(db_session, u.id, "question_answered")


def test_course_wrong_state_reaches_the_shared_core(db_session):
    u = make_user(db_session, "cs_w1")
    attach_course(db_session, u, "ds")
    record(db_session, u, "ds", qid="q1", correct=False, when=datetime(2024, 4, 1),
           source=("c", "1", None))
    states = wrong_service.list_states(db_session, u.id, service_namespace="course_learning")
    assert len(states) == 1 and states[0].status == "active"


def test_course_space_views_delegate_to_the_shared_cores(db_session):
    u = make_user(db_session, "cs_v1")
    attach_course(db_session, u, "ds")
    record(db_session, u, "ds", qid="q1", correct=False, when=datetime(2024, 4, 1),
           source=("c", "1", None))
    practice_view = course_service.course_practice_view(db_session, u, "ds")
    assert practice_view["attempt_count"] == 1
    wrong_view = course_service.course_wrong_view(db_session, u, "ds")
    assert wrong_view["active_count"] == 1


# ---------------------------------------------------------------- isolation

def test_multi_course_isolation(db_session):
    """Same user, two courses: no view may bleed into the other."""
    u = make_user(db_session, "cs_iso")
    attach_course(db_session, u, "A")
    attach_course(db_session, u, "B")
    record(db_session, u, "A", qid="shared-id", correct=False, when=datetime(2024, 4, 1),
           source=("cA", "1", None))
    record(db_session, u, "B", qid="shared-id", correct=True, when=datetime(2024, 4, 2),
           source=("cB", "2", None))

    view_a = course_service.course_practice_view(db_session, u, "A")
    view_b = course_service.course_practice_view(db_session, u, "B")
    assert view_a["attempt_count"] == 1 and view_b["attempt_count"] == 1
    assert {a["correct"] for a in view_a["attempts"]} == {False}
    assert {a["correct"] for a in view_b["attempts"]} == {True}

    wrong_a = course_service.course_wrong_view(db_session, u, "A")
    wrong_b = course_service.course_wrong_view(db_session, u, "B")
    assert wrong_a["active_count"] == 1 and wrong_b["active_count"] == 0

    records_a = course_service.course_records(db_session, u, "A")
    assert all(r["context"]["course_id"] == "A" for r in records_a["records"] if r["context"])
    assert records_a["records"], "course A should have its own records"


def test_same_knowledge_code_in_two_courses_stays_separate(db_session):
    u = make_user(db_session, "cs_iso2")
    attach_course(db_session, u, "A")
    attach_course(db_session, u, "B")
    make_knowledge_point(db_session, u, "A", node_key="1.1")
    make_knowledge_point(db_session, u, "B", node_key="1.1")

    course_knowledge.commit_and_emit(db_session, course_knowledge.apply_knowledge_change(
        db_session, username="cs_iso2", course_id="A", event_type="question_correct",
        knowledge_point_code="1.1", delta=45))
    a = course_service.course_knowledge_state(db_session, u, "A")
    b = course_service.course_knowledge_state(db_session, u, "B")
    assert a["by_status"].get("reviewing") == 1
    assert not b["by_status"]                       # course B untouched


def test_user_without_the_course_is_refused(db_session):
    a = make_user(db_session, "cs_x1")
    b = make_user(db_session, "cs_x2")
    attach_course(db_session, a, "private")
    with pytest.raises(course_context.CourseContextError):
        course_service.assert_owned_course(db_session, b, "private")
    assert course_service.list_user_courses(db_session, b) == []


def test_course_records_do_not_include_other_namespaces(db_session):
    u = make_user(db_session, "cs_ns")
    attach_course(db_session, u, "ds")
    record(db_session, u, "ds", qid="q1", correct=True, when=datetime(2024, 4, 1),
           source=("c", "1", None))
    # an exam_11408 record for the same user must not appear in the course view
    exam_session = practice_service.create_session(db_session, u, ServiceNamespace.EXAM_PREP)
    practice_service.record_attempt(
        db_session, u, exam_session,
        QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK, source_id="e1",
                    service_namespace=ServiceNamespace.EXAM_PREP),
        correct=True, submitted_at=datetime(2024, 4, 2))
    records = course_service.course_records(db_session, u, "ds")
    assert all(r["service_namespace"] == "course_learning" for r in records["records"])


# ---------------------------------------------------------------- E2E

def test_backend_course_learning_e2e(db_session):
    """Full backend course loop: context → practice → wrong → resolve → records."""
    u = make_user(db_session, "cs_e2e")
    attach_course(db_session, u, "ds", display_name="数据结构")

    # 1. course context resolves
    ref, ctx = course_context.resolve_course_context(db_session, u, "ds")
    assert ref.course_id == "ds" and ctx.service_namespace == COURSE

    # 2. practice through the shared core (wrong)
    record(db_session, u, "ds", qid="e2e-1", correct=False, when=datetime(2024, 5, 1),
           source=("e2e", "1", None))
    # 3. wrong state ACTIVE
    assert wrong_service.list_states(db_session, u.id,
                                     service_namespace="course_learning")[0].status == "active"

    # 4. later correct → RESOLVED
    record(db_session, u, "ds", qid="e2e-1", correct=True, when=datetime(2024, 5, 2),
           source=("e2e", "2", None))
    assert wrong_service.list_states(db_session, u.id,
                                     service_namespace="course_learning")[0].status == "resolved"

    # 5. knowledge state through the canonical writer
    point = make_knowledge_point(db_session, u, "ds", node_key="e2e-kp")
    course_knowledge.commit_and_emit(db_session, course_knowledge.apply_knowledge_change(
        db_session, username="cs_e2e", course_id="ds", event_type="question_correct",
        knowledge_point_id=point.id, delta=45))

    # 6. records contain the canonical activity
    records = course_service.course_records(db_session, u, "ds")
    types = {r["event_type"] for r in records["records"]}
    assert "question_answered" in types and "knowledge_status_changed" in types
    assert all(r["service_namespace"] == "course_learning" for r in records["records"])


def test_free_user_can_complete_the_course_loop(db_session):
    """The Free tier keeps the full basic course loop (§54) — events still persist."""
    u = make_user(db_session, "cs_free")           # no subscription → Free
    attach_course(db_session, u, "ds")
    record(db_session, u, "ds", qid="free-1", correct=False, when=datetime(2024, 6, 1),
           source=("free", "1", None))

    assert wrong_service.list_states(db_session, u.id,
                                     service_namespace="course_learning")[0].status == "active"
    assert events_for(db_session, u.id, "question_answered")
    assert course_service.course_records(db_session, u, "ds")["records"]
