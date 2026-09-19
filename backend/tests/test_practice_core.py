"""STEP 7D: Practice Core — sessions, attempts, isolation, semantics."""
import pytest

from ai.providers import FakeProvider  # noqa: F401  (keeps parity with other suites)
from core.learning_context import LearningContext, ServiceNamespace
from learning.practice import identity, service
from learning.practice.models import (
    SESSION_ABANDONED,
    SESSION_ACTIVE,
    SESSION_COMPLETED,
)
from learning.practice.refs import (
    QuestionRef,
    QuestionSourceType,
    resolve_source_type,
)
from models import User

COURSE = ServiceNamespace.COURSE_LEARNING
EXAM = ServiceNamespace.EXAM_PREP
PROG = ServiceNamespace.PROGRAMMING


def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def ref(ns, source_id="q1", source_type=QuestionSourceType.STATIC_QUESTION_BANK):
    return QuestionRef(source_type=source_type, source_id=source_id,
                       service_namespace=ns)


# ---------------------------------------------------------------- sessions

def test_create_and_get_session(db_session):
    u = make_user(db_session, "pc1")
    s = service.create_session(db_session, u, COURSE, mode="chapter")
    assert s.id is not None and s.status == SESSION_ACTIVE
    assert s.service_namespace == "course_learning"
    assert s.started_at is None            # nothing invented

    got = service.get_session(db_session, u.id, s.id)
    assert got.id == s.id


def test_session_status_transitions_are_idempotent(db_session):
    u = make_user(db_session, "pc2")
    completed = service.create_session(db_session, u, COURSE)
    abandoned = service.create_session(db_session, u, COURSE)

    a = service.complete_session(db_session, u.id, completed.id)
    b = service.complete_session(db_session, u.id, completed.id)      # idempotent
    assert a.status == SESSION_COMPLETED and b.status == SESSION_COMPLETED
    assert b.completed_at is not None

    x = service.abandon_session(db_session, u.id, abandoned.id)
    y = service.abandon_session(db_session, u.id, abandoned.id)       # idempotent
    assert x.status == SESSION_ABANDONED and y.status == SESSION_ABANDONED
    assert y.completed_at is not None


def test_completed_session_rejects_attempts(db_session):
    u = make_user(db_session, "pc3")
    s = service.create_session(db_session, u, COURSE)
    service.complete_session(db_session, u.id, s.id)
    with pytest.raises(service.SessionClosed):
        service.record_attempt(db_session, u, s, ref(COURSE))


def test_abandoned_session_rejects_attempts(db_session):
    u = make_user(db_session, "pc4")
    s = service.create_session(db_session, u, COURSE)
    service.abandon_session(db_session, u.id, s.id)
    with pytest.raises(service.SessionClosed):
        service.record_attempt(db_session, u, s, ref(COURSE))


def test_terminal_session_never_reopens(db_session):
    u = make_user(db_session, "pc5")
    s = service.create_session(db_session, u, COURSE)
    service.complete_session(db_session, u.id, s.id)
    # a completed session cannot be moved to another terminal state (no implicit
    # reopen, no state laundering)
    with pytest.raises(service.SessionClosed):
        service.abandon_session(db_session, u.id, s.id)
    assert service.get_session(db_session, u.id, s.id).status == SESSION_COMPLETED


def test_abandon_is_reachable_only_while_active(db_session):
    u = make_user(db_session, "pc5b")
    s = service.create_session(db_session, u, COURSE)
    assert service.abandon_session(db_session, u.id, s.id).status == SESSION_ABANDONED
    # already terminal → refuses to become completed
    with pytest.raises(service.SessionClosed):
        service.complete_session(db_session, u.id, s.id)


def test_list_sessions_scoped_by_namespace(db_session):
    u = make_user(db_session, "pc6")
    service.create_session(db_session, u, COURSE, mode="a")
    service.create_session(db_session, u, EXAM, mode="b")
    assert len(service.list_sessions(db_session, u.id)) == 2
    exam_only = service.list_sessions(db_session, u.id, service_namespace="exam_prep")
    assert [s.service_namespace for s in exam_only] == ["exam_prep"]


# ---------------------------------------------------------------- attempts

def test_record_attempt_roundtrip(db_session):
    u = make_user(db_session, "pc7")
    s = service.create_session(db_session, u, EXAM)
    res = service.record_attempt(db_session, u, s, ref(EXAM, "42"),
                                 answer="B", correct=True, score=2.0, max_score=2.0)
    assert res.created is True
    a = res.attempt
    assert a.service_namespace == "exam_prep"
    assert a.question_source_type == "static_question_bank"
    assert a.question_source_id == "42"
    assert a.correct is True and a.score == 2.0 and a.max_score == 2.0
    assert service.get_attempt(db_session, u.id, a.id).id == a.id


def test_correct_true_false_and_null_are_distinct(db_session):
    u = make_user(db_session, "pc8")
    s = service.create_session(db_session, u, EXAM)
    t = service.record_attempt(db_session, u, s, ref(EXAM, "t"), correct=True).attempt
    f = service.record_attempt(db_session, u, s, ref(EXAM, "f"), correct=False).attempt
    n = service.record_attempt(db_session, u, s, ref(EXAM, "n"), correct=None).attempt

    assert t.correct is True
    assert f.correct is False
    assert n.correct is None            # ungraded is NOT False
    assert n.correct is not False


def test_score_only_attempt_keeps_no_boolean(db_session):
    u = make_user(db_session, "pc9")
    s = service.create_session(db_session, u, EXAM)
    a = service.record_attempt(db_session, u, s, ref(EXAM, "big"),
                               answer="...", correct=None, score=7.5, max_score=10.0).attempt
    assert a.correct is None
    assert a.score == 7.5 and a.max_score == 10.0


def test_same_question_can_be_answered_repeatedly(db_session):
    u = make_user(db_session, "pc10")
    s = service.create_session(db_session, u, EXAM)
    r = ref(EXAM, "same-question")
    a1 = service.record_attempt(db_session, u, s, r, answer="A", correct=False).attempt
    a2 = service.record_attempt(db_session, u, s, r, answer="B", correct=True).attempt
    assert a1.id != a2.id                       # question identity != attempt identity
    assert len(service.list_attempts(db_session, u.id, session_id=s.id)) == 2


def test_attempt_no_and_history_preserved(db_session):
    u = make_user(db_session, "pc11")
    s = service.create_session(db_session, u, EXAM)
    a = service.record_attempt(db_session, u, s, ref(EXAM, "q"),
                               attempt_no=3, response_time_ms=4200).attempt
    assert a.attempt_no == 3 and a.response_time_ms == 4200


def test_session_summary_computed_from_attempts(db_session):
    u = make_user(db_session, "pc12")
    s = service.create_session(db_session, u, EXAM)
    service.record_attempt(db_session, u, s, ref(EXAM, "1"), correct=True)
    service.record_attempt(db_session, u, s, ref(EXAM, "2"), correct=False)
    service.record_attempt(db_session, u, s, ref(EXAM, "3"), correct=None)
    summary = service.session_summary(db_session, u.id, s.id)
    assert summary["attempt_count"] == 3
    assert summary["graded_count"] == 2
    assert summary["correct_count"] == 1
    assert summary["ungraded_count"] == 1


# ---------------------------------------------------------------- isolation

def test_user_cannot_read_another_users_session(db_session):
    a = make_user(db_session, "iso_a")
    b = make_user(db_session, "iso_b")
    s = service.create_session(db_session, a, COURSE)
    with pytest.raises(service.SessionNotFound):
        service.get_session(db_session, b.id, s.id)


def test_user_cannot_add_attempt_to_another_users_session(db_session):
    a = make_user(db_session, "iso_c")
    b = make_user(db_session, "iso_d")
    s = service.create_session(db_session, a, COURSE)
    with pytest.raises(service.CrossUserAccess):
        service.record_attempt(db_session, b, s, ref(COURSE))


def test_session_list_excludes_other_users(db_session):
    a = make_user(db_session, "iso_e")
    b = make_user(db_session, "iso_f")
    service.create_session(db_session, a, COURSE)
    service.create_session(db_session, b, COURSE)
    assert len(service.list_sessions(db_session, a.id)) == 1


def test_attempt_query_is_user_scoped(db_session):
    a = make_user(db_session, "iso_g")
    b = make_user(db_session, "iso_h")
    s = service.create_session(db_session, a, COURSE)
    attempt = service.record_attempt(db_session, a, s, ref(COURSE)).attempt
    assert [x.id for x in service.list_attempts(db_session, a.id)] == [attempt.id]
    assert service.list_attempts(db_session, b.id) == []
    with pytest.raises(service.SessionNotFound):
        service.get_attempt(db_session, b.id, attempt.id)


def test_course_session_rejects_exam_attempt(db_session):
    u = make_user(db_session, "ns1")
    s = service.create_session(db_session, u, COURSE)
    with pytest.raises(service.NamespaceMismatch):
        service.record_attempt(db_session, u, s, ref(EXAM))


def test_exam_session_rejects_programming_attempt(db_session):
    u = make_user(db_session, "ns2")
    s = service.create_session(db_session, u, EXAM)
    with pytest.raises(service.NamespaceMismatch):
        service.record_attempt(db_session, u, s,
                               ref(PROG, source_type=QuestionSourceType.PROGRAMMING_EXERCISE))


def test_context_namespace_must_match_session(db_session):
    u = make_user(db_session, "ns3")
    with pytest.raises(service.NamespaceMismatch):
        service.create_session(db_session, u, EXAM,
                               context=LearningContext(user_id=u.id, service_namespace=COURSE))


def test_learning_context_is_reused_not_reinvented(db_session):
    u = make_user(db_session, "ns4")
    ctx = LearningContext(user_id=u.id, service_namespace=EXAM, subject_key="ds",
                          chapter_id="ch1")
    s = service.create_session(db_session, u, EXAM, context=ctx)
    assert '"service_namespace":"exam_prep"' in s.context_json
    assert '"subject_key":"ds"' in s.context_json


# ---------------------------------------------------------------- identity

def test_question_source_mapping_is_explicit():
    assert resolve_source_type("exam_prep", "exam_question_bank") == \
        QuestionSourceType.STATIC_QUESTION_BANK
    assert resolve_source_type("exam_prep", "past_paper") == QuestionSourceType.PAST_EXAM
    assert resolve_source_type("course_learning", "ai_generated_questions") == \
        QuestionSourceType.AI_GENERATED
    assert resolve_source_type("programming", "programming_exercises") == \
        QuestionSourceType.PROGRAMMING_EXERCISE
    # an unknown origin is a loud failure, never a default
    with pytest.raises(KeyError):
        resolve_source_type("course_learning", "mystery_table")


def test_question_ref_preserves_raw_provenance():
    r = QuestionRef(source_type=QuestionSourceType.AI_GENERATED, source_id="7",
                    service_namespace=EXAM, raw_source={"table": "ai_generated_questions"})
    assert r.to_dict()["raw_source"] == {"table": "ai_generated_questions"}
    assert QuestionRef.from_dict(r.to_dict()).question_identity == ("AI_generated", "7")


def test_legacy_session_identity_is_deterministic(db_session):
    u = make_user(db_session, "id1")
    s1, created1 = service.ensure_legacy_session(
        db_session, u, EXAM, source_type="exam_practice_attempt", source_session_key=99)
    s2, created2 = service.ensure_legacy_session(
        db_session, u, EXAM, source_type="exam_practice_attempt", source_session_key=99)
    assert created1 is True and created2 is False
    assert s1.id == s2.id
    assert s1.session_uid == identity.session_uid(
        "exam_prep", "exam_practice_attempt", 99, u.id)


def test_attempt_uid_is_deterministic():
    a = identity.attempt_uid("exam_prep", "exam_practice_attempt", "5", "42:0")
    b = identity.attempt_uid("exam_prep", "exam_practice_attempt", "5", "42:0")
    c = identity.attempt_uid("exam_prep", "exam_practice_attempt", "5", "43:1")
    assert a == b and a != c


# ---------------------------------------------------------------- idempotency

def test_same_source_identity_is_idempotent(db_session):
    u = make_user(db_session, "idem1")
    s = service.create_session(db_session, u, EXAM)
    src = service.SourceIdentity("exam_practice_attempt", "77", "1:0")
    first = service.record_attempt(db_session, u, s, ref(EXAM, "1"),
                                   answer="A", correct=True, source=src)
    second = service.record_attempt(db_session, u, s, ref(EXAM, "1"),
                                    answer="A", correct=True, source=src)
    assert first.created is True and second.created is False
    assert first.attempt.id == second.attempt.id
    assert len(service.list_attempts(db_session, u.id, session_id=s.id)) == 1


def test_conflicting_fact_for_same_identity_fails_loudly(db_session):
    u = make_user(db_session, "idem2")
    s = service.create_session(db_session, u, EXAM)
    src = service.SourceIdentity("exam_practice_attempt", "88", "1:0")
    service.record_attempt(db_session, u, s, ref(EXAM, "1"), answer="A", correct=True,
                           source=src)
    with pytest.raises(service.AttemptConflict):
        service.record_attempt(db_session, u, s, ref(EXAM, "1"), answer="B",
                               correct=False, source=src)
    # the original fact is untouched
    kept = service.list_attempts(db_session, u.id, session_id=s.id)
    assert len(kept) == 1 and kept[0].answer == "A" and kept[0].correct is True


def test_concurrent_mirror_produces_exactly_one_attempt(db_session):
    import threading

    import database

    u = make_user(db_session, "conc1")
    s = service.create_session(db_session, u, EXAM)
    src = service.SourceIdentity("exam_practice_attempt", "99", "1:0")

    errors = []

    def worker():
        session = database.SessionLocal()
        try:
            s2 = session.query(type(s)).filter(type(s).id == s.id).first()
            service.record_attempt(session, u, s2, ref(EXAM, "1"), answer="A",
                                   correct=True, source=src)
        except service.AttemptConflict:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(type(exc).__name__)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    attempts = service.list_attempts(db_session, u.id, session_id=s.id)
    assert len(attempts) == 1, f"expected exactly one attempt, got {len(attempts)}"
    assert errors == [], errors
