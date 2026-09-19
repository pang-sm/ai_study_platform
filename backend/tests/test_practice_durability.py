"""STEP 7D FINAL RECONCILIATION: programming judged-fact durability.

The STEP7D report claimed `_record_programming_submission_progress` left its writes in
an uncommitted transaction. That claim was WRONG (it was read from a truncated excerpt).
These tests prove the real transaction ownership empirically, under the actual request
session lifecycle (`get_db` yields a session and then closes it without an extra
commit), and prove the mirror-failure recovery path end to end.

Session ownership, as actually implemented:
    submit endpoint
      → _record_programming_exercise_activity(...)          → db.commit()  (progress durable)
      → _record_programming_submission_progress(...)        → db.commit()  (submission durable)
      → Practice mirror (its own session, failure-isolated)
"""
import database
import main
from learning.practice import backfill, service
from learning.practice.adapters import programming as prog_adapter
from learning.practice.adapters.base import safe_mirror
from models import ProgrammingExercise, ProgrammingExerciseProgress, ProgrammingExerciseSubmission, User


def _make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def _make_exercise(session, ex_id: int, *, language="Python") -> ProgrammingExercise:
    ex = ProgrammingExercise(
        id=ex_id, slug=f"dur-{ex_id}", title="Durability", language=language,
        difficulty="easy", description="d", tags_json="[]",
        starter_files_json="[]", reference_files_json="[]", public_tests_json="[]",
        hidden_tests_json="[]", official_test_files_json="[]",
        source_repo="test-fixture", source_path="dur.py", source_commit="0" * 40,
        license="MIT", license_text="MIT", attribution="test", audit_report_json="{}")
    session.add(ex)
    session.commit()
    return ex


def _submit_through_helpers(user, exercise, payload):
    """Drive the exact helper chain the submit endpoint calls, then CLOSE the session
    the way `get_db` does (no extra commit)."""
    session = database.SessionLocal()
    try:
        progress = main._record_programming_exercise_activity(
            user, exercise, session, "submit", payload)
        if payload.get("passed"):
            main._record_programming_submission_progress(user, exercise, session)
        return progress.id, progress.last_submit_at
    finally:
        session.close()          # what get_db() does on request teardown


# ---------------------------------------------------------------- A2 durability

def test_judged_progress_survives_request_session_close(db_session):
    u = _make_user(db_session, "dur1")
    ex = _make_exercise(db_session, 9101)

    progress_id, submitted_at = _submit_through_helpers(
        u, ex, {"passed": True, "passed_count": 5, "total_count": 5})

    # a completely fresh session must see the durable judged fact
    fresh = database.SessionLocal()
    try:
        row = (fresh.query(ProgrammingExerciseProgress)
               .filter(ProgrammingExerciseProgress.id == progress_id).first())
        assert row is not None, "durable judged progress was lost"
        assert row.last_submit_passed is True
        assert row.last_public_passed_count == 5
        assert row.last_public_total_count == 5
        assert row.last_submit_at == submitted_at
        assert row.user_id == u.id
        assert row.exercise_id == ex.id
    finally:
        fresh.close()


def test_pass_submission_row_survives_request_session_close(db_session, monkeypatch):
    """The submission row is only written for exercises linked to knowledge points, so
    the linkage is stubbed here — the point under test is the commit ownership."""
    u = _make_user(db_session, "dur2")
    ex = _make_exercise(db_session, 9102)

    monkeypatch.setattr(main, "_programming_knowledge_points",
                        lambda _ex: [{"code": "kp-dur", "title": "Durability KP"}])

    _submit_through_helpers(u, ex, {"passed": True, "passed_count": 3, "total_count": 3})

    fresh = database.SessionLocal()
    try:
        row = (fresh.query(ProgrammingExerciseSubmission)
               .filter(ProgrammingExerciseSubmission.username == "dur2",
                       ProgrammingExerciseSubmission.exercise_id == ex.id).first())
        assert row is not None, "durable submission row was lost"
        assert row.passed_at is not None
    finally:
        fresh.close()


def test_failed_submission_is_durable_too(db_session):
    u = _make_user(db_session, "dur3")
    ex = _make_exercise(db_session, 9103)

    progress_id, _ = _submit_through_helpers(
        u, ex, {"passed": False, "passed_count": 1, "total_count": 4})

    fresh = database.SessionLocal()
    try:
        row = (fresh.query(ProgrammingExerciseProgress)
               .filter(ProgrammingExerciseProgress.id == progress_id).first())
        assert row is not None and row.last_submit_passed is False
        assert row.last_public_passed_count == 1 and row.last_public_total_count == 4
    finally:
        fresh.close()


def test_durable_source_carries_every_field_needed_to_rebuild(db_session):
    """A2: the durable source must let us rebuild the canonical attempt without guessing."""
    u = _make_user(db_session, "dur4")
    ex = _make_exercise(db_session, 9104, language="Python")

    progress_id, submitted_at = _submit_through_helpers(
        u, ex, {"passed": False, "passed_count": 2, "total_count": 4})

    fresh = database.SessionLocal()
    try:
        row = fresh.query(ProgrammingExerciseProgress).filter_by(id=progress_id).first()
        exercise = fresh.query(ProgrammingExercise).filter_by(id=row.exercise_id).first()
        # user identity
        assert row.user_id == u.id and row.username == "dur4"
        # exercise identity + language (language comes from the durable static exercise)
        assert row.exercise_id == ex.id and exercise.language == "Python"
        # submission identity + timestamp
        assert row.id is not None and row.last_submit_at == submitted_at
        # real judge outcome + real case metadata
        assert row.last_submit_passed is False
        assert row.last_public_passed_count == 2 and row.last_public_total_count == 4
    finally:
        fresh.close()


# ---------------------------------------------------------------- A5 recovery

def test_mirror_failure_is_recoverable_from_the_durable_source(db_session, monkeypatch):
    """Full A5 sequence: judge → durable commit → mirror fails → backfill rebuilds."""
    u = _make_user(db_session, "rec1")
    ex = _make_exercise(db_session, 9105)

    # 1-2. real judge verdict, durable domain record committed
    progress_id, submitted_at = _submit_through_helpers(
        u, ex, {"passed": False, "passed_count": 2, "total_count": 4})

    # 3. force the Practice mirror to fail, exactly as the endpoint's safe path would
    def boom(*_a, **_kw):
        raise RuntimeError("mirror unavailable")

    with monkeypatch.context() as patched:
        patched.setattr(service, "ensure_legacy_session", boom)
        failed = safe_mirror(
            "programming.exercise_submission", "programming_exercise_progress", ex.id,
            lambda: prog_adapter.mirror_programming_submission(
                db_session, u, ex, progress_id,
                {"passed": False, "passed_count": 2, "total_count": 4},
                submitted_at=submitted_at),
            db=db_session)
    assert failed.failed == 1 and failed.reason == "RuntimeError"

    # 5. no canonical attempt exists yet
    assert service.list_attempts(db_session, u.id, service_namespace="programming") == []

    # 6. reconciliation rebuilds it from the durable source
    report = backfill.run_backfill(db_session, sources=["programming_exercise_progress"])
    assert report["per_source"]["programming_exercise_progress"]["mirrored"] >= 1

    rebuilt = service.list_attempts(db_session, u.id, service_namespace="programming")
    assert len(rebuilt) == 1
    a = rebuilt[0]

    # 7. the rebuilt fact matches the original durable fact exactly
    assert a.user_id == u.id
    assert a.service_namespace == "programming"
    assert a.question_source_type == "programming_exercise"
    assert a.question_source_id == str(ex.id)
    assert a.correct is False                     # real judge verdict, not inferred
    assert a.score == 2.0 and a.max_score == 4.0
    assert a.submitted_at == submitted_at
    assert a.source_attempt_type == "programming_exercise_progress"
    assert a.source_attempt_id == str(progress_id)
    assert a.source_item_key == submitted_at.isoformat()

    # 8. re-running changes nothing
    second = backfill.run_backfill(db_session, sources=["programming_exercise_progress"])
    assert second["totals"]["mirrored"] == 0
    assert len(service.list_attempts(db_session, u.id,
                                     service_namespace="programming")) == 1


def test_recovery_reproduces_the_same_identity_as_live_mirror(db_session):
    """Live mirror and backfill must land on the SAME canonical row, not two."""
    u = _make_user(db_session, "rec2")
    ex = _make_exercise(db_session, 9106)
    progress_id, submitted_at = _submit_through_helpers(
        u, ex, {"passed": True, "passed_count": 4, "total_count": 4})

    # live mirror first
    outcome = prog_adapter.mirror_programming_submission(
        db_session, u, ex, progress_id,
        {"passed": True, "passed_count": 4, "total_count": 4},
        submitted_at=submitted_at, language="Python")
    assert outcome.mirrored == 1

    # a later reconciliation must NOT add a second row for the same submission
    report = backfill.run_backfill(db_session, sources=["programming_exercise_progress"])
    assert report["per_source"]["programming_exercise_progress"]["deduped"] >= 1
    assert len(service.list_attempts(db_session, u.id,
                                     service_namespace="programming")) == 1
    _ = progress_id


# ---------------------------------------------------------------- A6 no AI judge

def test_ai_prose_status_never_becomes_a_judged_fact():
    matrix = {row["source"]: row for row in backfill.classification_matrix()}
    assert matrix["code_challenge_attempts"]["classification"] == "INELIGIBLE"
    assert prog_adapter.LLM_DERIVED_STATUS_SOURCE == "code_challenge_attempt"
