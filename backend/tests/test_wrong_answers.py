"""STEP 7E: Wrong Answer Core — projection, lifecycle, isolation, legacy merge."""
from datetime import datetime, timedelta

import database
import main
from core.learning_context import ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.wrong_answers import legacy, service
from learning.wrong_answers.models import STATUS_ACTIVE, STATUS_RESOLVED, WrongAnswerState
from models import ExamWrongQuestion, PastPaperWrongQuestion, User

EXAM = ServiceNamespace.EXAM_PREP
COURSE = ServiceNamespace.COURSE_LEARNING
PROG = ServiceNamespace.PROGRAMMING
BANK = QuestionSourceType.STATIC_QUESTION_BANK
AI_GEN = QuestionSourceType.AI_GENERATED
PROG_EX = QuestionSourceType.PROGRAMMING_EXERCISE


def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def record(db, user, ns, *, qid="1001", source_type=BANK, correct, when=None,
           answer="A", tag=None):
    session = practice_service.create_session(db, user, ns)
    ref = QuestionRef(source_type=source_type, source_id=qid,
                      service_namespace=ns,
                      context=({"year": 2024} if source_type == QuestionSourceType.PAST_EXAM
                               else {}))
    src = (practice_service.SourceIdentity(tag, f"{qid}-{when}-{correct}", None)
           if tag else None)
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=correct, submitted_at=when,
        source=src).attempt


def states(db, user, ns=None):
    return service.list_states(db, user.id, service_namespace=ns)


# ---------------------------------------------------------------- lifecycle

def test_first_wrong_creates_active_state(db_session):
    u = make_user(db_session, "wa1")
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 1, 9, 0))
    rows = states(db_session, u)
    assert len(rows) == 1
    assert rows[0].status == STATUS_ACTIVE
    assert rows[0].wrong_count == 1
    assert rows[0].question_source_id == "1001"
    assert rows[0].service_namespace == "exam_prep"


def test_second_wrong_increments_wrong_count(db_session):
    u = make_user(db_session, "wa2")
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 1, 9, 0))
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 2, 9, 0))
    rows = states(db_session, u)
    assert len(rows) == 1                      # one state, not two
    assert rows[0].wrong_count == 2            # two distinct incorrect attempts
    assert rows[0].status == STATUS_ACTIVE


def test_attempt_replay_does_not_double_count(db_session):
    u = make_user(db_session, "wa3")
    src = practice_service.SourceIdentity("exam_practice_attempt", "same", "1:0")
    session = practice_service.create_session(db_session, u, EXAM)
    ref = QuestionRef(source_type=BANK, source_id="1001", service_namespace=EXAM)
    for _ in range(2):
        practice_service.record_attempt(db_session, u, session, ref, answer="A",
                                        correct=False, source=src)
    rows = states(db_session, u)
    assert len(rows) == 1
    assert rows[0].wrong_count == 1            # replay folded once


def test_later_correct_resolves(db_session):
    u = make_user(db_session, "wa4")
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 1, 9, 0))
    record(db_session, u, EXAM, correct=True, when=datetime(2024, 1, 2, 9, 0))
    row = states(db_session, u)[0]
    assert row.status == STATUS_RESOLVED
    assert row.resolved_at is not None
    assert row.wrong_count == 1                # history preserved, not erased
    assert row.resolved_attempt_id is not None


def test_later_wrong_after_resolution_reopens(db_session):
    u = make_user(db_session, "wa5")
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 1, 9, 0))
    record(db_session, u, EXAM, correct=True, when=datetime(2024, 1, 2, 9, 0))
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 3, 9, 0))
    row = states(db_session, u)[0]
    assert row.status == STATUS_ACTIVE          # reopened, not permanently resolved
    assert row.wrong_count == 2
    assert row.resolved_at is None


def test_correct_then_correct_stays_resolved(db_session):
    u = make_user(db_session, "wa6")
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 1))
    record(db_session, u, EXAM, correct=True, when=datetime(2024, 1, 2))
    record(db_session, u, EXAM, correct=True, when=datetime(2024, 1, 3))
    assert states(db_session, u)[0].status == STATUS_RESOLVED


# ---------------------------------------------------------------- tri-state

def test_null_correctness_never_creates_a_wrong_state(db_session):
    u = make_user(db_session, "wa7")
    record(db_session, u, EXAM, correct=None, when=datetime(2024, 1, 1))
    assert states(db_session, u) == []          # NULL is not a failure


def test_null_correctness_does_not_resolve(db_session):
    u = make_user(db_session, "wa8")
    record(db_session, u, EXAM, correct=False, when=datetime(2024, 1, 1))
    record(db_session, u, EXAM, correct=None, when=datetime(2024, 1, 2))
    row = states(db_session, u)[0]
    assert row.status == STATUS_ACTIVE          # NULL neither fails nor resolves
    assert row.wrong_count == 1


def test_score_only_attempt_never_becomes_a_wrong_answer(db_session):
    u = make_user(db_session, "wa9")
    session = practice_service.create_session(db_session, u, EXAM)
    ref = QuestionRef(source_type=BANK, source_id="9001", service_namespace=EXAM)
    practice_service.record_attempt(db_session, u, session, ref, answer="...",
                                    correct=None, score=3.0, max_score=10.0,
                                    submitted_at=datetime(2024, 1, 1))
    assert states(db_session, u) == []          # score alone is not correctness


def test_false_stays_false_and_is_not_confused_with_null(db_session):
    u = make_user(db_session, "wa10")
    record(db_session, u, EXAM, qid="1", correct=False, when=datetime(2024, 1, 1))
    record(db_session, u, EXAM, qid="2", correct=None, when=datetime(2024, 1, 1))
    rows = {r.question_source_id: r for r in states(db_session, u)}
    assert set(rows) == {"1"}                   # only the factual failure


# ---------------------------------------------------------------- per-space

def test_course_wrong_state(db_session):
    u = make_user(db_session, "wa11")
    record(db_session, u, COURSE, qid="c1",
           source_type=QuestionSourceType.MATERIAL_GENERATED, correct=False,
           when=datetime(2024, 1, 1))
    row = states(db_session, u, "course_learning")[0]
    assert row.question_source_type == "material_generated"


def test_ai_generated_wrong_state_keeps_its_source_identity(db_session):
    u = make_user(db_session, "wa12")
    record(db_session, u, EXAM, qid="77", source_type=AI_GEN, correct=False,
           when=datetime(2024, 1, 1))
    row = states(db_session, u)[0]
    assert row.question_source_type == "AI_generated"     # not the generating model
    assert row.question_source_id == "77"


def test_past_paper_wrong_state_carries_subject_and_year_scope(db_session):
    """STEP7H2 §8: the scope carries the exam SUBJECT so a future exam's "2022 question N"
    can never be folded onto cs_408's. The module is not encoded — the question id is
    already unique inside a subject-year."""
    u = make_user(db_session, "wa13")
    record(db_session, u, EXAM, qid="pp1", source_type=QuestionSourceType.PAST_EXAM,
           correct=False, when=datetime(2024, 1, 1))
    row = states(db_session, u)[0]
    assert row.question_source_type == "past_exam"
    assert row.question_scope_key == "subject:cs_408|year:2024"


def test_programming_real_judge_failure_then_pass(db_session):
    u = make_user(db_session, "wa14")
    record(db_session, u, PROG, qid="501", source_type=PROG_EX, correct=False,
           when=datetime(2024, 1, 1))
    row = states(db_session, u, "programming")[0]
    assert row.status == STATUS_ACTIVE
    record(db_session, u, PROG, qid="501", source_type=PROG_EX, correct=True,
           when=datetime(2024, 1, 2))
    assert states(db_session, u, "programming")[0].status == STATUS_RESOLVED


# ---------------------------------------------------------------- identity

def test_source_id_collision_across_namespaces_keeps_states_separate(db_session):
    u = make_user(db_session, "wa15")
    record(db_session, u, EXAM, qid="123", correct=False, when=datetime(2024, 1, 1))
    record(db_session, u, PROG, qid="123", source_type=PROG_EX, correct=False,
           when=datetime(2024, 1, 1))
    rows = states(db_session, u)
    assert len(rows) == 2
    assert {r.service_namespace for r in rows} == {"exam_prep", "programming"}


def test_source_id_collision_across_source_types_keeps_states_separate(db_session):
    u = make_user(db_session, "wa16")
    record(db_session, u, EXAM, qid="123", source_type=BANK, correct=False,
           when=datetime(2024, 1, 1))
    record(db_session, u, EXAM, qid="123", source_type=AI_GEN, correct=False,
           when=datetime(2024, 1, 1))
    rows = states(db_session, u)
    assert len(rows) == 2
    assert {r.question_source_type for r in rows} == {"static_question_bank", "AI_generated"}


def test_question_identity_is_not_attempt_identity(db_session):
    u = make_user(db_session, "wa17")
    for i in range(3):
        record(db_session, u, EXAM, qid="555", correct=False,
               when=datetime(2024, 1, 1 + i))
    rows = states(db_session, u)
    assert len(rows) == 1                       # one question …
    assert rows[0].wrong_count == 3             # … three distinct wrong attempts
    detail = service.state_detail(db_session, u.id, rows[0].id)
    assert len(detail["attempt_history"]) == 3


# ---------------------------------------------------------------- isolation

def test_cross_user_isolation(db_session):
    a = make_user(db_session, "wa_a")
    b = make_user(db_session, "wa_b")
    record(db_session, a, EXAM, correct=False, when=datetime(2024, 1, 1))
    assert states(db_session, b) == []
    with pytest_raises_state_not_found():
        service.get_state(db_session, b.id, states(db_session, a)[0].id)


def pytest_raises_state_not_found():
    import contextlib

    @contextlib.contextmanager
    def _cm():
        try:
            yield
        except service.StateNotFound:
            return
        raise AssertionError("expected StateNotFound")
    return _cm()


def test_cross_user_cannot_resolve_another_users_state(db_session):
    a = make_user(db_session, "wa_c")
    b = make_user(db_session, "wa_d")
    record(db_session, a, EXAM, correct=False, when=datetime(2024, 1, 1))
    state_id = states(db_session, a)[0].id
    try:
        service.set_status(db_session, b.id, state_id, resolved=True)
        raise AssertionError("expected StateNotFound")
    except service.StateNotFound:
        pass
    assert states(db_session, a)[0].status == STATUS_ACTIVE    # untouched


def test_cross_namespace_filter(db_session):
    u = make_user(db_session, "wa18")
    record(db_session, u, EXAM, qid="e1", correct=False, when=datetime(2024, 1, 1))
    record(db_session, u, PROG, qid="p1", source_type=PROG_EX, correct=False,
           when=datetime(2024, 1, 1))
    assert [r.service_namespace for r in states(db_session, u, "programming")] == \
        ["programming"]


# ---------------------------------------------------------------- ordering / rebuild

def test_out_of_order_replay_matches_chronological_replay(db_session):
    u = make_user(db_session, "wa19")
    # inserted wrong → wrong → correct, but with timestamps that make the correct
    # attempt the OLDEST; chronological semantics must still win
    record(db_session, u, EXAM, qid="q", correct=True, when=datetime(2024, 1, 1))
    record(db_session, u, EXAM, qid="q", correct=False, when=datetime(2024, 1, 2))
    record(db_session, u, EXAM, qid="q", correct=False, when=datetime(2024, 1, 3))
    after_inorder = states(db_session, u)[0]
    assert after_inorder.status == STATUS_ACTIVE
    assert after_inorder.wrong_count == 2

    # a full rebuild from the same facts converges to exactly the same state
    service.rebuild_states(db_session, user_id=u.id)
    rebuilt = states(db_session, u)[0]
    assert rebuilt.status == after_inorder.status
    assert rebuilt.wrong_count == after_inorder.wrong_count
    assert rebuilt.resolved_attempt_id == after_inorder.resolved_attempt_id


def test_chronologically_later_correct_resolves_even_if_recorded_first(db_session):
    u = make_user(db_session, "wa20")
    record(db_session, u, EXAM, qid="q", correct=False, when=datetime(2024, 1, 1))
    record(db_session, u, EXAM, qid="q", correct=True, when=datetime(2024, 1, 5))
    service.rebuild_states(db_session, user_id=u.id)
    assert states(db_session, u)[0].status == STATUS_RESOLVED


def test_rebuild_is_idempotent(db_session):
    u = make_user(db_session, "wa21")
    record(db_session, u, EXAM, qid="q", correct=False, when=datetime(2024, 1, 1))
    first = service.rebuild_states(db_session, user_id=u.id)
    second = service.rebuild_states(db_session, user_id=u.id)
    assert first["created"] == 0 and first["updated"] == 1
    assert second["updated"] == 1
    assert len(states(db_session, u)) == 1
    assert states(db_session, u)[0].wrong_count == 1


def test_rebuild_dry_run_changes_nothing(db_session):
    u = make_user(db_session, "wa22")
    record(db_session, u, EXAM, qid="new", correct=False, when=datetime(2024, 1, 1))
    before = len(states(db_session, u))
    # a question with facts but no state yet: simulate by deleting then dry-running
    db_session.query(WrongAnswerState).filter_by(user_id=u.id).delete()
    db_session.commit()
    preview = service.rebuild_states(db_session, user_id=u.id, dry_run=True)
    assert preview["created"] == 1
    assert len(states(db_session, u)) == 0           # dry run wrote nothing
    service.rebuild_states(db_session, user_id=u.id)
    assert len(states(db_session, u)) == 1
    assert before == 1


# ---------------------------------------------------------------- concurrency

CONCURRENCY_ROUNDS = 50


def _race_once(u, *, qid, errors):
    """Two concurrent, DISTINCT wrong facts for one question, on fresh sessions."""
    import threading
    from datetime import datetime as dt

    # Read the pk on the TEST's thread BEFORE spawning. `u` belongs to the fixture session;
    # touching an expired attribute of it from a worker thread makes SQLAlchemy refresh it
    # through that same session concurrently, which surfaces as a bogus ObjectDeletedError
    # and silently loses one of the two facts. Harness artifact, not a product fact.
    uid = u.id

    def worker(i):
        session = database.SessionLocal()
        try:
            user = session.query(User).filter(User.id == uid).first()
            record(session, user, EXAM, qid=qid, correct=False,
                   when=dt(2024, 1, 1, 0, i), tag=f"concurrent-{qid}-{i}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_concurrent_wrong_attempts_yield_one_state(db_session):
    """STRESS (STEP7H2-C1): this used to be an occasionally-red test.

    Two distinct wrong facts racing for the same question must ALWAYS converge on one
    state with ``wrong_count == 2``. The projection is recompute-not-increment, so the
    pass that writes last must have derived from the complete fact set — the projector
    verifies its own read and redoes a stale pass. One green run is not evidence, hence
    the loop: a stale-read regression shows up as a wrong count in some round.
    """
    u = make_user(db_session, "wa23")
    errors = []

    for round_no in range(CONCURRENCY_ROUNDS):
        _race_once(u, qid=f"race-{round_no}", errors=errors)
        # read the COMMITTED state through a fresh session: the test's own session has a
        # long-lived identity map/transaction and would report its snapshot, not the DB.
        with database.SessionLocal() as fresh:
            rows = [r for r in service.list_states(fresh, u.id,
                                                   service_namespace="exam_prep")
                    if r.question_source_id == f"race-{round_no}"]
            observed = (len(rows), rows[0].wrong_count if rows else None)
        assert errors == [], f"round {round_no}: worker error(s) {errors}"
        assert observed[0] == 1, f"round {round_no}: expected one state, got {observed[0]}"
        assert observed[1] == 2, (
            f"round {round_no}: stale projection, wrong_count={observed[1]}")
    assert errors == [], errors


def test_concurrent_replay_of_one_fact_stays_one(db_session):
    """The same DURABLE legacy fact mirrored concurrently stays one attempt.

    This is the real replay shape: the mirror resolves the session through
    ``ensure_legacy_session``, so both racers land on the same container and the same
    fact — the deterministic uid has to fold them into one attempt, hence one wrong.
    """
    import threading
    from datetime import datetime as dt

    u = make_user(db_session, "wa23b")
    errors = []
    when = dt(2024, 1, 1, 0, 0)
    uid = u.id

    def worker():
        session = database.SessionLocal()
        try:
            user = session.query(User).filter(User.id == uid).first()
            container, _created = practice_service.ensure_legacy_session(
                session, user, EXAM, source_type="exam_practice_attempt",
                source_session_key=4242, mode="chapter", context=None, started_at=when)
            ref = QuestionRef(source_type=BANK, source_id="replay-race",
                              service_namespace=EXAM)
            practice_service.record_attempt(
                session, user, container, ref, answer="A", correct=False,
                submitted_at=when,
                source=practice_service.SourceIdentity("exam_practice_attempt",
                                                       "4242", "replay-race:0"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = states(db_session, u)
    assert len(rows) == 1
    assert rows[0].wrong_count == 1, "a replayed fact is not a second failure"
    assert errors == [], errors


def test_concurrent_wrong_then_correct_resolves_with_full_count(db_session):
    """wrong A + wrong B + later correct C → RESOLVED, wrong_count = 2 (not 1)."""
    from datetime import datetime as dt

    u = make_user(db_session, "wa23c")
    errors = []
    _race_once(u, qid="abc", errors=errors)
    assert errors == [], errors
    record(db_session, u, EXAM, qid="abc", correct=True,
           when=dt(2024, 1, 1, 1, 0), tag="abc-correct")
    rows = [r for r in states(db_session, u) if r.question_source_id == "abc"]
    assert len(rows) == 1
    assert rows[0].status == "resolved"
    assert rows[0].wrong_count == 2, "resolving must not erase either failure"


# ---------------------------------------------------------------- legacy merge

def test_legacy_exam_wrong_backfill_creates_state(db_session):
    u = make_user(db_session, "wa24")
    db_session.add(ExamWrongQuestion(
        username="wa24", subject_key="ds", question_bank_id=4242,
        practice_attempt_id=None, source_type="chapter", practice_type="chapter",
        question_type="选择题", stem_snapshot="s", user_answer="B",
        standard_answer_snapshot="A", status="active", mastered=False,
        review_count=2, created_at=datetime(2024, 1, 1)))
    db_session.commit()

    report = legacy.run_legacy_wrong_backfill(db_session)
    assert report["created"] >= 1
    row = next(r for r in states(db_session, u) if r.question_source_id == "4242")
    assert row.status == STATUS_ACTIVE
    assert row.origin == "legacy"
    assert row.legacy_source_type == "exam_wrong_question"
    assert row.legacy_review_count == 2          # compatibility metadata preserved


def test_legacy_mastered_imports_as_resolved(db_session):
    u = make_user(db_session, "wa25")
    db_session.add(ExamWrongQuestion(
        username="wa25", subject_key="ds", question_bank_id=4243,
        question_type="选择题", status="mastered", mastered=True,
        user_answer="B", resolved_at=datetime(2024, 2, 1), created_at=datetime(2024, 1, 1)))
    db_session.commit()
    legacy.run_legacy_wrong_backfill(db_session)
    row = next(r for r in states(db_session, u) if r.question_source_id == "4243")
    assert row.status == STATUS_RESOLVED
    assert row.legacy_mastered is True


def test_legacy_past_paper_backfill_carries_year_scope(db_session):
    u = make_user(db_session, "wa26")
    db_session.add(PastPaperWrongQuestion(
        username="wa26", subject_key="ds", year=2023, attempt_id=1,
        question_id="pp-9", question_type="选择题", status="active", mastered=False,
        user_answer="B", created_at=datetime(2024, 1, 1)))
    db_session.commit()
    legacy.run_legacy_wrong_backfill(db_session)
    row = next(r for r in states(db_session, u) if r.question_source_id == "pp-9")
    # the legacy row's subject_key IS the module, so it is carried into the scope
    assert row.question_scope_key == "subject:cs_408|module:ds|year:2023"
    assert row.legacy_source_type == "past_paper_wrong_question"


def test_legacy_backfill_is_idempotent(db_session):
    u = make_user(db_session, "wa27")
    db_session.add(ExamWrongQuestion(username="wa27", subject_key="ds",
                                     question_bank_id=4300, question_type="选择题",
                                     status="active", mastered=False, user_answer="B",
                                     created_at=datetime(2024, 1, 1)))
    db_session.commit()
    legacy.run_legacy_wrong_backfill(db_session)
    first = len(states(db_session, u))
    legacy.run_legacy_wrong_backfill(db_session)
    assert len(states(db_session, u)) == first
    assert len([r for r in states(db_session, u)
                if r.question_source_id == "4300"]) == 1


def test_legacy_does_not_override_newer_canonical_correctness(db_session):
    """A legacy `active` row must not beat a newer factual correct attempt (§17)."""
    u = make_user(db_session, "wa28")
    record(db_session, u, EXAM, qid="7001", correct=True, when=datetime(2024, 5, 1))
    db_session.add(ExamWrongQuestion(username="wa28", subject_key="ds",
                                     question_bank_id=7001, question_type="选择题",
                                     status="active", mastered=False, user_answer="B",
                                     created_at=datetime(2024, 1, 1)))
    db_session.commit()

    legacy.run_legacy_wrong_backfill(db_session)
    rows = [r for r in states(db_session, u) if r.question_source_id == "7001"]
    assert len(rows) == 1
    assert rows[0].origin == "legacy_merged"
    assert rows[0].legacy_source_type == "exam_wrong_question"   # metadata kept
    # the newer factual CORRECT attempt decides the status, not the legacy flag
    assert rows[0].status == STATUS_RESOLVED
    assert rows[0].wrong_count == 0
    assert rows[0].legacy_source_id is not None


def test_legacy_and_canonical_do_not_double_count(db_session):
    """Legacy row + canonical wrong attempt for the same question → ONE state."""
    u = make_user(db_session, "wa29")
    record(db_session, u, EXAM, qid="8001", correct=False, when=datetime(2024, 5, 1))
    db_session.add(ExamWrongQuestion(username="wa29", subject_key="ds",
                                     question_bank_id=8001, question_type="选择题",
                                     status="active", mastered=False, user_answer="B",
                                     created_at=datetime(2024, 1, 1)))
    db_session.commit()

    legacy.run_legacy_wrong_backfill(db_session)
    rows = [r for r in states(db_session, u) if r.question_source_id == "8001"]
    assert len(rows) == 1, f"expected one state, got {len(rows)}"
    # the canonical facts remain authoritative for the count
    assert rows[0].wrong_count == 1


def test_legacy_rows_without_a_user_are_skipped_not_guessed(db_session):
    db_session.add(ExamWrongQuestion(username="ghost_user", subject_key="ds",
                                     question_bank_id=9999, question_type="选择题",
                                     status="active", created_at=datetime(2024, 1, 1)))
    db_session.commit()
    report = legacy.run_legacy_wrong_backfill(db_session)
    assert report["skipped"] >= 1


def test_legacy_matrix_is_audited_not_guessed():
    rows = {r["table"]: r for r in legacy.legacy_wrong_matrix()}
    assert rows["exam_wrong_questions"]["fidelity"] == "PARTIAL"
    assert rows["past_paper_wrong_questions"]["fidelity"] == "PARTIAL"
    assert rows["code_challenge_attempts"]["fidelity"] == "INELIGIBLE_AS_CORRECTNESS"
    assert rows["programming_exercise_progress"]["fidelity"] == "INELIGIBLE_AS_HISTORY"


# ---------------------------------------------------------------- boundaries

def test_review_fields_are_metadata_not_a_review_core(db_session):
    u = make_user(db_session, "wa30")
    db_session.add(ExamWrongQuestion(username="wa30", subject_key="ds",
                                     question_bank_id=5000, question_type="选择题",
                                     status="active", mastered=False, review_count=4,
                                     user_answer="B", created_at=datetime(2024, 1, 1)))
    db_session.commit()
    legacy.run_legacy_wrong_backfill(db_session)
    row = next(r for r in states(db_session, u) if r.question_source_id == "5000")
    # carried as legacy metadata; NOT the canonical wrong_count and no review tables
    assert row.legacy_review_count == 4
    assert row.legacy_source_type is not None
    tables = {t for t in _tables(db_session)}
    assert not {t for t in tables if t.startswith("review_item") or
                t.startswith("review_attempt") or t.startswith("review_schedule")}


def _tables(db_session):
    from sqlalchemy import text
    return [r[0] for r in db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]


def test_wrong_answer_projection_does_not_touch_learning_events(db_session):
    """The wrong-answer projection writes NO events, and in particular never a
    StudentTwin-eligible course_practice event."""
    from data_plane.models import LearningEvent

    u = make_user(db_session, "wa31")
    cp_before = db_session.query(LearningEvent).filter(
        LearningEvent.event_type == "course_practice").count()
    record(db_session, u, EXAM, qid="evt", correct=False, when=datetime(2024, 1, 1))
    assert states(db_session, u)[0].status == STATUS_ACTIVE

    mine = db_session.query(LearningEvent).filter(LearningEvent.user_id == u.id).all()
    assert {e.event_type for e in mine} == {"question_answered"}    # the practice fact only
    assert db_session.query(LearningEvent).filter(
        LearningEvent.event_type == "course_practice").count() == cp_before


def test_manual_resolve_via_service(db_session):
    u = make_user(db_session, "wa32")
    record(db_session, u, EXAM, qid="m1", correct=False, when=datetime(2024, 1, 1))
    state_id = states(db_session, u)[0].id
    row = service.set_status(db_session, u.id, state_id, resolved=True)
    assert row.status == STATUS_RESOLVED
    row = service.set_status(db_session, u.id, state_id, resolved=False)
    assert row.status == STATUS_ACTIVE


def test_state_detail_reads_display_data_from_facts(db_session):
    u = make_user(db_session, "wa33")
    record(db_session, u, EXAM, qid="d1", correct=False, when=datetime(2024, 1, 1),
           answer="B")
    state_id = states(db_session, u)[0].id
    detail = service.state_detail(db_session, u.id, state_id)
    assert detail["user_answer"] == "B"
    assert detail["question"]["source_id"] == "d1"
    assert detail["review_status"] == STATUS_ACTIVE
    assert detail["error_analysis"] is None       # null, never an LLM guess
    assert len(detail["attempt_history"]) == 1


def test_no_historical_row_duplication_of_the_question(db_session):
    """The state must not become a second copy of the question or of the history."""
    u = make_user(db_session, "wa34")
    record(db_session, u, EXAM, qid="dup", correct=False, when=datetime(2024, 1, 1))
    row = states(db_session, u)[0]
    for column in ("stem_snapshot", "options_snapshot_json", "standard_answer_snapshot",
                   "analysis_snapshot", "user_answer", "answer_history_json"):
        assert not hasattr(row, column)
    _ = timedelta
