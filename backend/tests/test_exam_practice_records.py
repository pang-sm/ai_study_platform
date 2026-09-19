"""STEP 7H2: CS408 / exam_prep — Practice, Wrong Answers, Records consolidation.

Covers:

  * every real exam answer becomes a canonical PracticeAttempt under ``exam_prep`` with a
    full exam context (track / subject / module), for chapter practice, past papers and
    AI-generated questions alike;
  * the wrong-answer projection follows the facts (ACTIVE → RESOLVED → reopen) and is
    replay-safe;
  * the past-exam scope carries the exam SUBJECT, so a future exam's "2022 question N"
    can never collide with cs_408's;
  * the past-paper builder reconciles by stable key — same input twice yields the same
    ids, changed content updates in place, and nothing is ever wholesale deleted;
  * exam records land in the shared stream with ``service_key = exam_prep``,
    ``subject_key = cs_408`` and the module in the domain-context JSON.
"""
import inspect
import json
from datetime import datetime
from pathlib import Path

import pytest

from conftest import register_and_login
from core.learning_context import ServiceNamespace
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.adapters import exam as exam_adapter
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.exam_prep import catalog, context as exam_context
from learning.spaces.exam_prep.context import cs408_context
from learning.wrong_answers import service as wrong_service
from learning.wrong_answers.project import past_exam_scope, scope_key
from models import ExamPracticeAttempt, PastPaperAttempt, User
from usage import service as usage_service
import main
import past_paper_upsert

COURSE = ServiceNamespace.COURSE_LEARNING
EXAM = ServiceNamespace.EXAM_PREP
CS408 = "cs_408"


# ---------------------------------------------------------------- helpers

def _user(session, username, tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        usage_service.activate_subscription(session, u.id, tier, 30)
    return u


def _chapter_attempt_row(session, username, *, module="operating_system",
                         results=None, status="submitted", attempt_id=None):
    row = ExamPracticeAttempt(
        username=username, subject_key=module, practice_type="chapter",
        source_type="chapter", status=status, title="章节练习",
        question_ids_json=json.dumps([r["question_id"] for r in (results or [])]),
        answers_json=json.dumps({}),
        result_json=json.dumps({"results": results or []}, ensure_ascii=False),
        total_questions=len(results or []), correct_count=0, wrong_count=0, accuracy=0.0,
        started_at=datetime(2024, 5, 1, 9, 0), submitted_at=datetime(2024, 5, 1, 9, 30),
    )
    if attempt_id is not None:
        row.id = attempt_id
    session.add(row)
    session.commit()
    return row


def _past_paper_attempt_row(session, username, *, module="computer_network", year=2022,
                            results=None, attempt_no=1):
    row = PastPaperAttempt(
        username=username, mode="11408", subject_key=module, subject_name=module,
        year=year, attempt_no=attempt_no, status="submitted",
        total_questions=len(results or []), choice_correct=0, big_avg_score=0.0,
        total_score=0, max_score=0, wrong_count=0,
        answers_json=json.dumps({}),
        result_json=json.dumps({"results": results or []}, ensure_ascii=False),
        started_at=datetime(2024, 5, 1, 9, 0), submitted_at=datetime(2024, 5, 1, 9, 30),
    )
    session.add(row)
    session.commit()
    return row


def _states(db, user, source_type=None):
    rows = wrong_service.list_states(db, user.id, service_namespace="exam_prep")
    if source_type:
        rows = [r for r in rows if r.question_source_type == source_type]
    return rows


def _events(db, user_id, event_type=None):
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


# ---------------------------------------------------------------- A: chapter practice

def test_chapter_practice_mirrors_to_exam_prep_attempts(db_session):
    u = _user(db_session, "h2_chap")
    row = _chapter_attempt_row(db_session, u.username, module="operating_system", results=[
        {"question_id": 9001, "correct": True, "standard_answer": "A", "user_answer": "A"},
        {"question_id": 9002, "correct": False, "standard_answer": "B", "user_answer": "C"},
        {"question_id": 9003, "judge": "self_review", "standard_answer": "D", "user_answer": ""},
    ])
    outcome = exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    assert outcome.mirrored == 3

    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(attempts) == 3
    assert {a.question_source_type for a in attempts} == {"static_question_bank"}
    # tri-state preserved: the self-reviewed big question is neither correct nor wrong
    by_id = {a.question_source_id: a for a in attempts}
    assert by_id["9001"].correct is True
    assert by_id["9002"].correct is False
    assert by_id["9003"].correct is None


def test_chapter_practice_context_carries_track_subject_and_module(db_session):
    u = _user(db_session, "h2_chap_ctx")
    row = _chapter_attempt_row(db_session, u.username, module="computer_organization",
                               results=[{"question_id": 9100, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    attempt = practice_service.list_attempts(db_session, u.id,
                                             service_namespace="exam_prep")[0]
    ctx = json.loads(attempt.context_json)
    assert ctx["service_namespace"] == "exam_prep"
    assert ctx["exam_track_id"] == CS408
    assert ctx["exam_subject_id"] == CS408
    assert ctx["exam_module_id"] == "computer_organization"
    assert ctx["subject_key"] == "computer_organization", "legacy module mirror"
    ref = json.loads(attempt.question_ref_json)
    assert ref["context"]["exam_subject_id"] == CS408
    assert ref["context"]["exam_module_id"] == "computer_organization"


# ---------------------------------------------------------------- B: past paper

def test_past_paper_mirrors_with_question_year_and_attempt_no(db_session):
    u = _user(db_session, "h2_pp")
    row = _past_paper_attempt_row(db_session, u.username, module="computer_network",
                                  year=2023, attempt_no=2, results=[
        {"question_id": 9301, "number": 33, "type": "选择题", "correct": False,
         "score": 0, "full_score": 2, "user_answer": "A", "standard_answer": "B"},
        {"question_id": 9302, "number": 34, "type": "大题", "score": 5, "full_score": 10},
    ])
    outcome = exam_adapter.mirror_past_paper_attempt(db_session, u, row)
    assert outcome.mirrored == 2

    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert {a.question_source_type for a in attempts} == {"past_exam"}
    assert {a.attempt_no for a in attempts} == {2}
    ref = json.loads(attempts[0].question_ref_json)
    assert ref["context"]["question_year"] == 2023
    assert ref["context"]["exam_subject_id"] == CS408


# ---------------------------------------------------------------- C/D/E: wrong lifecycle

def test_wrong_goes_active_then_resolved_then_reopens(db_session):
    u = _user(db_session, "h2_life")
    _chapter_attempt_row(db_session, u.username, module="operating_system",
                         results=[{"question_id": 9401, "correct": False, "user_answer": "C"}])
    row = db_session.query(ExamPracticeAttempt).filter_by(username=u.username).one()
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    assert [s.status for s in _states(db_session, u)] == ["active"]

    _chapter_attempt_row(db_session, u.username, module="operating_system",
                         results=[{"question_id": 9401, "correct": True, "user_answer": "A"}])
    row2 = db_session.query(ExamPracticeAttempt).order_by(ExamPracticeAttempt.id.desc()).first()
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row2)
    db_session.expire_all()
    assert [s.status for s in _states(db_session, u)] == ["resolved"]

    _chapter_attempt_row(db_session, u.username, module="operating_system",
                         results=[{"question_id": 9401, "correct": False, "user_answer": "C"}])
    row3 = db_session.query(ExamPracticeAttempt).order_by(ExamPracticeAttempt.id.desc()).first()
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row3)
    db_session.expire_all()
    state = _states(db_session, u)[0]
    assert state.status == "active"
    assert state.wrong_count == 2, "two distinct incorrect attempts, not a projector run count"


# ---------------------------------------------------------------- F: replay safety

def test_mirror_replay_does_not_duplicate_attempts_or_wrong_count(db_session):
    u = _user(db_session, "h2_replay")
    row = _chapter_attempt_row(db_session, u.username, module="operating_system",
                               results=[{"question_id": 9501, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    db_session.expire_all()
    first = _states(db_session, u)[0]

    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    db_session.expire_all()

    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(attempts) == 1, "one legacy row is one canonical attempt"
    state = _states(db_session, u)[0]
    assert state.wrong_count == 1
    assert state.id == first.id
    events = _events(db_session, u.id, "question_answered")
    assert len(events) == 1, "replay must not add a second event"


def test_legacy_and_canonical_namespace_produce_one_attempt(db_session):
    """Same logical legacy row, mirrored once as exam_11408 and once as exam_prep."""
    u = _user(db_session, "h2_alias")
    row = _chapter_attempt_row(db_session, u.username, module="operating_system",
                               results=[{"question_id": 9601, "correct": False, "user_answer": "C"}])
    ctx = cs408_context(u, module_key="operating_system")
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id="9601", service_namespace=EXAM,
                      context={"exam_subject_id": CS408, "exam_module_id": "operating_system"})
    src = practice_service.SourceIdentity("exam_practice_attempt", str(row.id), "9601:0")

    def mirror(namespace):
        session, created = practice_service.ensure_legacy_session(
            db_session, u, namespace, source_type="exam_practice_attempt",
            source_session_key=row.id, mode="chapter", context=ctx, started_at=None)
        return practice_service.record_attempt(db_session, u, session, ref, answer="A",
                                               correct=False, source=src, context=ctx)

    a = mirror("exam_11408")
    b = mirror("exam_prep")
    assert a.attempt.attempt_uid == b.attempt.attempt_uid
    assert a.created and not b.created


# ---------------------------------------------------------------- G/H: isolation

def test_course_and_exam_same_source_id_stay_isolated(db_session):
    u = _user(db_session, "h2_cross")
    course_ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                             source_id="777", service_namespace=COURSE,
                             context={"course_id": "data_structure"})
    exam_ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                           source_id="777", service_namespace=EXAM,
                           context={"exam_subject_id": CS408, "exam_module_id": "data_structure"})
    cs = practice_service.create_session(db_session, u, COURSE)
    practice_service.record_attempt(db_session, u, cs, course_ref, answer="A", correct=False)
    es = practice_service.create_session(db_session, u, EXAM)
    practice_service.record_attempt(db_session, u, es, exam_ref, answer="A", correct=False)

    assert len(wrong_service.list_states(db_session, u.id,
                                         service_namespace="course_learning")) == 1
    assert len(wrong_service.list_states(db_session, u.id,
                                         service_namespace="exam_prep")) == 1


@pytest.mark.parametrize("module", ("data_structure", "computer_organization",
                                    "operating_system", "computer_network"))
def test_two_exam_modules_same_question_number_and_year_stay_separate(db_session, module):
    """Identical (year, question_number, source_id) in two modules must not merge."""
    u = _user(db_session, f"h2_mod_{module}")
    other = next(m for m in catalog.CS408_MODULES if m != module)
    for m in (module, other):
        s = practice_service.create_session(db_session, u, EXAM)
        ref = QuestionRef(
            source_type=QuestionSourceType.PAST_EXAM, source_id="4242",
            service_namespace=EXAM,
            context={"exam_subject_id": CS408, "exam_module_id": m,
                     "question_year": 2022, "year": 2022})
        practice_service.record_attempt(db_session, u, s, ref, answer="A", correct=False)
    states = _states(db_session, u, source_type="past_exam")
    assert len(states) == 2, "one wrong state per module"
    assert len({s.id for s in states}) == 2


# ---------------------------------------------------------------- I/J: multi-subject safety

def test_past_exam_scope_encodes_subject_and_year():
    assert past_exam_scope(exam_subject_id="cs_408", question_year=2022) == \
        "subject:cs_408|year:2022"
    # a reference that predates the subject field is still cs_408 — the only corpus there is
    assert past_exam_scope(question_year=2022) == "subject:cs_408|year:2022"
    assert past_exam_scope() == "subject:cs_408"


def test_future_second_subject_cannot_collide_with_cs408(db_session):
    """Identity function only — no real math_1 data is imported (that is STEP7H4)."""
    u = _user(db_session, "h2_future")
    scopes = set()
    for subject in ("cs_408", "math_1", "math_2", "math_3"):
        ref = QuestionRef(source_type=QuestionSourceType.PAST_EXAM, source_id="12",
                          service_namespace=EXAM,
                          context={"exam_subject_id": subject, "exam_module_id": "m",
                                   "question_year": 2022})
        scopes.add(scope_key(EXAM.value, QuestionSourceType.PAST_EXAM.value,
                             {"exam_subject_id": subject, "question_year": 2022}))
        s = practice_service.create_session(db_session, u, EXAM)
        practice_service.record_attempt(db_session, u, s, ref, answer="A", correct=False)
    assert len(scopes) == 4, f"each exam subject needs its own scope: {scopes}"
    states = _states(db_session, u, source_type="past_exam")
    assert len(states) == 4, "no two subjects may share a wrong state"


def test_legacy_year_scope_is_adopted_not_duplicated(db_session):
    """A row written under the OLD ``year:<y>`` scope must not become a second state."""
    u = _user(db_session, "h2_adopt")
    legacy_ref = QuestionRef(source_type=QuestionSourceType.PAST_EXAM, source_id="5150",
                             service_namespace=EXAM,
                             context={"year": 2021},      # pre-STEP7H2 shape
                             )
    s = practice_service.create_session(db_session, u, EXAM)
    practice_service.record_attempt(db_session, u, s, legacy_ref, answer="A", correct=False)
    legacy_state = _states(db_session, u, source_type="past_exam")[0]
    # The shared derivation is total, so even this old ref already resolves canonically.
    assert legacy_state.question_scope_key == "subject:cs_408|year:2021"

    # And a legacy row that DOES exist under the raw old form is adopted, not duplicated.
    legacy_state.question_scope_key = "year:2021"
    db_session.commit()
    ref = QuestionRef(source_type=QuestionSourceType.PAST_EXAM, source_id="5150",
                      service_namespace=EXAM,
                      context={"exam_subject_id": CS408, "question_year": 2021})
    s2 = practice_service.create_session(db_session, u, EXAM)
    practice_service.record_attempt(db_session, u, s2, ref, answer="B", correct=False)
    db_session.expire_all()
    states = _states(db_session, u, source_type="past_exam")
    assert len(states) == 1
    assert states[0].question_scope_key == "subject:cs_408|year:2021"


# ---------------------------------------------------------------- K/L: records

def test_exam_records_carry_subject_and_module_not_track(db_session):
    u = _user(db_session, "h2_rec")
    row = _chapter_attempt_row(db_session, u.username, module="data_structure",
                               results=[{"question_id": 9701, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    db_session.expire_all()

    event = _events(db_session, u.id, "question_answered")[0]
    assert event.service_key == "exam_prep"
    assert event.subject_key == CS408
    ctx = json.loads(event.knowledge_point_ref_json)
    assert ctx.get("exam_module_id") == "data_structure"
    assert "exam_track_id" not in ctx

    attempt = practice_service.list_attempts(db_session, u.id,
                                             service_namespace="exam_prep")[0]
    assert "cs_408" not in attempt.attempt_uid
    assert "cs_408" not in attempt.question_ref_json.split("exam_subject_id")[0]


def test_track_is_not_part_of_any_identity():
    """A track is the learner's bundle choice: it must not reach any identity."""
    assert "track" not in past_exam_scope(exam_subject_id="cs_408",
                                          exam_module_id="operating_system",
                                          question_year=2022)
    ref = QuestionRef(source_type=QuestionSourceType.MATERIAL_GENERATED, source_id="1",
                      service_namespace=COURSE, context={"exam_track_id": "cs_408"})
    assert "cs_408" not in ref.source_id
    # and a track smuggled into a past-exam ref context changes nothing
    assert scope_key(EXAM.value, QuestionSourceType.PAST_EXAM.value,
                     {"exam_subject_id": "cs_408", "exam_module_id": "os",
                      "question_year": 2022, "exam_track_id": "law_jm_law"}) == \
        scope_key(EXAM.value, QuestionSourceType.PAST_EXAM.value,
                  {"exam_subject_id": "cs_408", "exam_module_id": "os",
                   "question_year": 2022, "exam_track_id": "cs_408"})


# ---------------------------------------------------------------- P: free user

def test_free_user_exam_facts_are_persisted(db_session):
    u = _user(db_session, "h2_free")               # no subscription → Free
    row = _chapter_attempt_row(db_session, u.username, module="operating_system",
                               results=[{"question_id": 9801, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    assert practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert _states(db_session, u)
    assert _events(db_session, u.id, "question_answered")


# ---------------------------------------------------------------- Q: event ownership

def test_ai_question_attempt_has_exactly_one_event_owner(db_session):
    """mode=11408 is owned by the practice spine; course mode is owned by the emitter."""
    from models import AIQuestionAttempt
    u = _user(db_session, "h2_aione")
    row = AIQuestionAttempt(
        username=u.username, mode="11408", subject_key="data_structure",
        subject_name="数据结构", question_ids_json=json.dumps([9911]),
        status="submitted", total_questions=1, correct_count=0, accuracy=0.0,
        answers_json=json.dumps({}),
        result_json=json.dumps({"results": [{"question_id": 9911, "correct": False, "user_answer": "C"}]}),
        started_at=datetime(2024, 5, 1), submitted_at=datetime(2024, 5, 1, 1, 0))
    db_session.add(row)
    db_session.commit()

    from learning.practice.adapters import course as course_adapter
    course_adapter.mirror_ai_question_attempt(db_session, u, row)
    db_session.expire_all()

    events = _events(db_session, u.id, "question_answered")
    assert len(events) == 1
    assert events[0].service_key == "exam_prep"
    assert all(e.event_type != "course_practice" for e in _events(db_session, u.id))
    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(attempts) == 1
    assert attempts[0].question_source_type == "AI_generated"
    ctx = json.loads(attempts[0].context_json)
    assert ctx["exam_module_id"] == "data_structure"


# ---------------------------------------------------------------- R: knowledge

def test_exam_mirror_applies_no_second_knowledge_delta(db_session):
    """The mirror records facts; it must not also run a pedagogical delta."""
    from models import UserKnowledgeProgress
    u = _user(db_session, "h2_kp")
    before = db_session.query(UserKnowledgeProgress).count()
    row = _chapter_attempt_row(db_session, u.username, module="operating_system",
                               results=[{"question_id": 9990, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    assert db_session.query(UserKnowledgeProgress).count() == before

    src = inspect.getsource(exam_adapter)
    assert "apply_knowledge" not in src
    assert "UserKnowledgeProgress" not in src


def test_only_the_study_plan_route_mutates_exam_knowledge():
    """Audited inventory: the sole exam route that WRITES knowledge state."""
    from learning.spaces.course_learning.knowledge import mutation_path_inventory
    rows = {r["path"]: r for r in mutation_path_inventory()}
    row = rows["PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}"]
    assert row["status"] == "OUT_OF_SCOPE_SPACE"
    assert row["space"] == "exam_prep"


# ---------------------------------------------------------------- M/N/O: builder

def _paste_rows():
    return [
        {"year": 2022, "question_number": 33, "question_type": "choice",
         "question_text": "Q33 v1", "options": {"A": "1"}, "answer": "A",
         "source_ref": "2022-Q33", "text_quality": "ready"},
        {"year": 2022, "question_number": 34, "question_type": "big",
         "question_text": "Q34 v1", "options": {}, "answer": "", "source_ref": "2022-Q34",
         "text_quality": "need_review"},
    ]


def _build_row(q):
    return dict(subject_name="计算机网络", visibility="public",
                knowledge_point_id="", knowledge_point_name="", knowledge_point_path="",
                question_type=q["question_type"], stem=q["question_text"],
                options_json=json.dumps(q.get("options", {}), ensure_ascii=False),
                standard_answer=q.get("answer", ""), analysis="", difficulty="基础",
                source_ref=f"past_paper:{q['source_ref']}",
                quality_status=q["text_quality"])


def test_builder_same_source_twice_keeps_ids_and_content(db_session):
    import models
    subject = "zz_builder_test"
    ins, upd, deact, dup, unkeyed = past_paper_upsert.upsert_past_paper_questions(
        db_session, models, subject, _paste_rows(), _build_row)
    assert (ins, upd) == (2, 0)
    first = {r.question_number: (r.id, r.stem)
             for r in db_session.query(models.ExamQuestionBank)
             .filter_by(subject_key=subject).all()}

    ins2, upd2, deact2, _, _ = past_paper_upsert.upsert_past_paper_questions(
        db_session, models, subject, _paste_rows(), _build_row)
    assert (ins2, upd2) == (0, 2), "a re-run updates, never re-inserts"
    second = {r.question_number: (r.id, r.stem)
              for r in db_session.query(models.ExamQuestionBank)
              .filter_by(subject_key=subject).all()}
    assert first == second, "ids and content must be byte-identical"
    assert db_session.query(models.ExamQuestionBank).filter_by(subject_key=subject).count() == 2


def test_builder_content_update_keeps_the_same_id(db_session):
    import models
    subject = "zz_builder_update"
    past_paper_upsert.upsert_past_paper_questions(db_session, models, subject,
                                                  _paste_rows(), _build_row)
    before = {r.question_number: r.id for r in db_session.query(models.ExamQuestionBank)
              .filter_by(subject_key=subject).all()}

    changed = _paste_rows()
    changed[0]["question_text"] = "Q33 v2 (corrected)"
    changed[0]["answer"] = "B"
    ins, upd, *_ = past_paper_upsert.upsert_past_paper_questions(db_session, models, subject,
                                                                changed, _build_row)
    assert (ins, upd) == (0, 2)
    db_session.expire_all()
    rows = {r.question_number: r for r in db_session.query(models.ExamQuestionBank)
            .filter_by(subject_key=subject).all()}
    assert rows[33].id == before[33], "content changes in place"
    assert rows[33].stem == "Q33 v2 (corrected)"
    assert rows[33].standard_answer == "B"


def test_builder_never_deletes(db_session):
    import models
    subject = "zz_builder_no_delete"
    past_paper_upsert.upsert_past_paper_questions(db_session, models, subject,
                                                  _paste_rows(), _build_row)
    # a source that no longer contains Q34
    ins, upd, deact, _, _ = past_paper_upsert.upsert_past_paper_questions(
        db_session, models, subject, _paste_rows()[:1], _build_row)
    assert deact == 1, "the vanished question is deactivated (soft), not deleted"
    rows = db_session.query(models.ExamQuestionBank).filter_by(subject_key=subject).all()
    assert len(rows) == 2, "the row survives so existing references stay valid"
    assert [r.is_active for r in rows].count(False) == 1


def test_builder_survivor_rule_picks_the_active_row(db_session):
    """Legacy duplicate groups: the ACTIVE row is updated, the superseded one is left."""
    import models
    subject = "zz_builder_dup"
    stale = models.ExamQuestionBank(
        subject_key=subject, source_type="past_paper", year=2022, question_number=33,
        question_type="choice", stem='{"text": "见图"}', is_active=False,
        standard_answer="A", source_ref="past_paper:2022-Q33")
    live = models.ExamQuestionBank(
        subject_key=subject, source_type="past_paper", year=2022, question_number=33,
        question_type="choice", stem="real text", is_active=True,
        standard_answer="A", source_ref="past_paper:2022-Q33")
    db_session.add_all([stale, live])
    db_session.commit()

    ins, upd, deact, dup_groups, _ = past_paper_upsert.upsert_past_paper_questions(
        db_session, models, subject, _paste_rows()[:1], _build_row)
    assert (ins, upd, deact) == (0, 1, 0)
    assert dup_groups == 1, "the legacy duplicate group is reported, not hidden"
    db_session.expire_all()
    rows = {r.id: r for r in db_session.query(models.ExamQuestionBank)
            .filter_by(subject_key=subject).all()}
    assert len(rows) == 2, "nothing was deleted"
    assert rows[live.id].stem == "Q33 v1"
    assert rows[stale.id].stem == '{"text": "见图"}', "the superseded row is untouched"


def test_no_exam_builder_deletes_question_bank_rows():
    """Static invariant: the past-paper / chapter builders must not wholesale delete."""
    backend = Path(__file__).resolve().parents[1]
    offenders = []
    for path in (backend / "exam_resources").rglob("build_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if ".delete()" in line and "ExamQuestionBank" in text:
                # only flag a delete that targets the bank
                window = text[max(0, text.find(line) - 400): text.find(line) + len(line)]
                if "ExamQuestionBank" in window:
                    offenders.append(f"{path.relative_to(backend)}: {line.strip()}")
    assert offenders == [], f"wholesale delete still present: {offenders}"


def test_stable_key_matches_the_audited_past_paper_shape(db_session):
    """Every ACTIVE past-paper row must have a non-null year and question number."""
    import models
    rows = (db_session.query(models.ExamQuestionBank)
            .filter(models.ExamQuestionBank.source_type == "past_paper").all())
    for row in rows:                       # the temp DB is empty; assert the contract
        key = past_paper_upsert.past_paper_stable_key(row.subject_key, row.year,
                                                      row.question_number)
        assert isinstance(key, tuple) and len(key) == 3


# ---------------------------------------------------------------- S: protected assets

def test_protected_question_bank_count_is_unchanged():
    """The real bank is a protected asset: 9333 / 1923 / 32, read-only checked."""
    import sqlite3
    from pathlib import Path as P
    db = P(__file__).resolve().parents[1] / "app.db"
    if not db.exists():
        pytest.skip("no working database")
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM exam_question_bank").fetchone()[0] == 9333
        assert con.execute("SELECT COUNT(*) FROM programming_exercises").fetchone()[0] == 1923
        assert con.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0] == 32
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()


# ---------------------------------------------------------------- full E2E (§34)

def test_full_exam_chapter_e2e_free_user(db_session):
    """Free user, CS408 operating_system: practice → wrong ACTIVE → correct → RESOLVED
    → records visible → and the mirror never touches knowledge state."""
    from learning.records import service as records_service
    from models import UserKnowledgeProgress

    u = _user(db_session, "h2_e2e_chap")           # no subscription → Free
    kp_before = db_session.query(UserKnowledgeProgress).count()

    wrong_row = _chapter_attempt_row(db_session, u.username, module="operating_system",
                                     results=[{"question_id": 8801, "correct": False,
                                               "standard_answer": "A", "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, wrong_row)
    db_session.expire_all()

    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(attempts) == 1 and attempts[0].correct is False
    assert attempts[0].service_namespace == "exam_prep"
    state = _states(db_session, u)[0]
    assert state.status == "active" and state.wrong_count == 1

    events = _events(db_session, u.id, "question_answered")
    assert len(events) == 1
    assert events[0].service_key == "exam_prep"
    assert events[0].subject_key == CS408

    correct_row = _chapter_attempt_row(db_session, u.username, module="operating_system",
                                       results=[{"question_id": 8801, "correct": True,
                                                 "standard_answer": "A", "user_answer": "A"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, correct_row)
    db_session.expire_all()
    state = _states(db_session, u)[0]
    assert state.status == "resolved"
    assert state.wrong_count == 1, "resolving does not erase the failure it resolved"

    page = records_service.list_records(db_session, u.id, service_namespace="exam_prep")
    records = page["records"]
    assert records, "exam facts must be visible through the shared records read model"
    assert {r["service_namespace"] for r in records} == {"exam_prep"}
    assert {r["context"]["subject_key"] for r in records} == {CS408}
    assert {r["context"]["exam_module_id"] for r in records} == {"operating_system"}

    assert db_session.query(UserKnowledgeProgress).count() == kp_before


def test_full_exam_past_paper_e2e_is_replay_idempotent(db_session):
    """Past-paper sitting: question_year + stable question ref + wrong identity + replay."""
    u = _user(db_session, "h2_e2e_pp")
    results = [{"question_id": 7701, "number": 33, "type": "选择题", "correct": False,
                "score": 0, "full_score": 2, "user_answer": "A", "standard_answer": "B"}]
    row = _past_paper_attempt_row(db_session, u.username, module="computer_network",
                                  year=2024, attempt_no=1, results=results)
    exam_adapter.mirror_past_paper_attempt(db_session, u, row)
    db_session.expire_all()

    attempt = practice_service.list_attempts(db_session, u.id,
                                             service_namespace="exam_prep")[0]
    ref = json.loads(attempt.question_ref_json)
    assert ref["source_type"] == "past_exam"
    assert ref["source_id"] == "7701"
    assert ref["context"]["question_year"] == 2024
    state = _states(db_session, u, source_type="past_exam")[0]
    assert state.question_scope_key == "subject:cs_408|module:computer_network|year:2024"
    assert state.status == "active"

    for _ in range(3):
        exam_adapter.mirror_past_paper_attempt(db_session, u, row)
    db_session.expire_all()
    assert len(practice_service.list_attempts(db_session, u.id,
                                              service_namespace="exam_prep")) == 1
    assert _states(db_session, u, source_type="past_exam")[0].wrong_count == 1
    assert len(_events(db_session, u.id, "question_answered")) == 1
