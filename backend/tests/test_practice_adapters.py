"""STEP 7D: legacy adapters, backfill, and the LearningEvent bridge."""
import json

import database
import main
from core.learning_context import ServiceNamespace
from data_plane.models import LearningEvent
from learning.practice import backfill, events, service
from learning.practice.adapters import base as adapter_base
from learning.practice.adapters import course as course_adapter
from learning.practice.adapters import exam as exam_adapter
from learning.practice.adapters import programming as prog_adapter
from models import (
    AIGeneratedQuestion,
    AIQuestionAttempt,
    ExamPracticeAttempt,
    PastPaperAttempt,
    ProgrammingExercise,
    ProgrammingExerciseProgress,
    Question,
    QuestionAttempt,
    User,
)


def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


# ---------------------------------------------------------------- course

def _ai_attempt(session, username, *, mode="course_learning", results, qids,
                status="submitted"):
    row = AIQuestionAttempt(
        username=username, mode=mode, subject_key="ds", subject_name="数据结构",
        question_ids_json=json.dumps(qids), status=status,
        total_questions=len(qids), submitted_at=main.utc_now(),
        answers_json=json.dumps({str(q): "A" for q in qids}),
        result_json=json.dumps(results, ensure_ascii=False),
    )
    session.add(row)
    session.commit()
    return row


def test_course_adapter_fans_out_one_attempt_per_question(db_session):
    u = make_user(db_session, "ad_c1")
    row = _ai_attempt(db_session, "ad_c1", qids=[11, 12], results={
        "correct": 1, "total": 2,
        "results": [
            {"question_id": 11, "correct": True, "user_answer": "A",
             "question_type": "选择题"},
            {"question_id": 12, "correct": None, "user_answer": "x",
             "question_type": "big", "judge": "self_review"},
        ]})

    outcome = course_adapter.mirror_ai_question_attempt(db_session, u, row)
    assert outcome.mirrored == 2 and outcome.failed == 0

    attempts = service.list_attempts(db_session, u.id,
                                     service_namespace="course_learning")
    assert len(attempts) == 2
    by_qid = {a.question_source_id: a for a in attempts}
    assert by_qid["11"].correct is True
    assert by_qid["12"].correct is None          # ungraded stays None
    # CONTRACT CORRECTION (P1.2). This assertion used to read "material_generated". It was
    # wrong about where a course AI question lives: ``question_ids_json`` holds
    # ``ai_generated_questions`` primary keys (main._create_course_learning_attempt is handed
    # an AIGeneratedQuestion), so declaring the static ``questions`` table made every course
    # AI attempt resolve against an id space it never belonged to — an empty stem for a real
    # question, and another learner's question where the two tables' ids happened to overlap.
    # The declared source now states the table the id really is in.
    assert by_qid["11"].question_source_type == "AI_generated"
    ref = json.loads(by_qid["11"].question_ref_json)
    assert ref["raw_source"]["table"] == "ai_generated_questions"
    assert by_qid["11"].source_attempt_id == str(row.id)


def test_course_adapter_exam_mode_uses_ai_generated_source(db_session):
    u = make_user(db_session, "ad_c2")
    row = _ai_attempt(db_session, "ad_c2", mode="11408", qids=[21], results={
        "correct": 1, "total": 1,
        "results": [{"question_id": 21, "correct": True, "user_answer": "B",
                     "question_type": "选择题"}]})
    course_adapter.mirror_ai_question_attempt(db_session, u, row)
    a = service.list_attempts(db_session, u.id, service_namespace="exam_prep")[0]
    assert a.question_source_type == "AI_generated"
    assert a.service_namespace == "exam_prep"


def test_course_adapter_ignores_unsubmitted(db_session):
    u = make_user(db_session, "ad_c3")
    row = _ai_attempt(db_session, "ad_c3", qids=[1], results={}, status="in_progress")
    outcome = course_adapter.mirror_ai_question_attempt(db_session, u, row)
    assert outcome.mirrored == 0 and outcome.reason == "not_submitted"


def test_course_mirror_is_idempotent(db_session):
    u = make_user(db_session, "ad_c4")
    row = _ai_attempt(db_session, "ad_c4", qids=[31], results={
        "results": [{"question_id": 31, "correct": True, "question_type": "选择题"}]})
    first = course_adapter.mirror_ai_question_attempt(db_session, u, row)
    second = course_adapter.mirror_ai_question_attempt(db_session, u, row)
    assert first.mirrored == 1
    assert second.mirrored == 0 and second.deduped == 1
    assert len(service.list_attempts(db_session, u.id)) == 1


def test_course_adapter_refuses_an_unknown_mode_instead_of_defaulting(db_session):
    """CONTRACT CORRECTION (P1.2): an unmapped ``mode`` used to be filed as course_learning /
    material_generated — an identity invented for a row that states none — and the invented
    table is what made a bare id resolvable against the wrong id space. A row whose
    provenance cannot be named now records nothing.
    """
    u = make_user(db_session, "ad_c5")
    row = _ai_attempt(db_session, "ad_c5", mode="some_future_mode", qids=[41], results={
        "results": [{"question_id": 41, "correct": True, "question_type": "选择题"}]})

    outcome = course_adapter.mirror_ai_question_attempt(db_session, u, row)
    assert outcome.mirrored == 0 and outcome.failed == 0
    assert outcome.reason == "unknown_mode"
    assert service.list_attempts(db_session, u.id) == []


# ---------------------------------------------------------------- exam

def test_exam_chapter_adapter_preserves_tri_state(db_session):
    u = make_user(db_session, "ad_e1")
    row = ExamPracticeAttempt(
        username="ad_e1", subject_key="ds", practice_type="chapter", status="submitted",
        question_ids_json=json.dumps([1, 2]), total_questions=2,
        submitted_at=main.utc_now(),
        result_json=json.dumps({"correct": 1, "total": 2, "results": [
            {"question_id": 1, "correct": True, "user_answer": "A",
             "question_type": "选择题"},
            {"question_id": 2, "correct": None, "user_answer": "答案",
             "question_type": "big", "judge": "self_review"},
        ]}, ensure_ascii=False))
    db_session.add(row)
    db_session.commit()

    outcome = exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    assert outcome.mirrored == 2
    attempts = {a.question_source_id: a for a in
                service.list_attempts(db_session, u.id, service_namespace="exam_prep")}
    assert attempts["1"].correct is True
    assert attempts["2"].correct is None
    assert attempts["1"].question_source_type == "static_question_bank"
    assert json.loads(attempts["2"].result_json)["judge"] == "self_review"


def test_exam_past_paper_adapter_preserves_scores_and_attempt_no(db_session):
    u = make_user(db_session, "ad_e2")
    row = PastPaperAttempt(
        username="ad_e2", mode="11408", subject_key="ds", subject_name="数据结构",
        year=2024, attempt_no=2, status="submitted", total_questions=2,
        submitted_at=main.utc_now(),
        result_json=json.dumps({"results": [
            {"question_id": "1001", "number": 1, "type": "选择题", "correct": True,
             "score": 2, "full_score": 2, "user_answer": "A"},
            {"question_id": "1002", "number": 2, "type": "综合题", "correct": None,
             "score": 7.5, "full_score": 10, "user_answer": "...", "feedback": "部分正确"},
        ]}, ensure_ascii=False))
    db_session.add(row)
    db_session.commit()

    outcome = exam_adapter.mirror_past_paper_attempt(db_session, u, row)
    assert outcome.mirrored == 2
    attempts = {a.question_source_id: a for a in
                service.list_attempts(db_session, u.id, service_namespace="exam_prep")}
    assert attempts["1001"].correct is True
    assert attempts["1002"].correct is None          # score-only big question
    assert attempts["1002"].score == 7.5 and attempts["1002"].max_score == 10.0
    assert attempts["1001"].attempt_no == 2          # multiple sittings distinguishable
    assert attempts["1001"].question_source_type == "past_exam"
    assert json.loads(attempts["1002"].result_json)["feedback"] == "部分正确"


# ---------------------------------------------------------------- programming

def _exercise(session, *, ex_id, language="Python"):
    ex = ProgrammingExercise(
        id=ex_id, slug=f"two-sum-{ex_id}", title="Two Sum", language=language,
        difficulty="easy", description="d", tags_json="[]",
        starter_files_json="[]", reference_files_json="[]", public_tests_json="[]",
        hidden_tests_json="[]", official_test_files_json="[]",
        source_repo="test-fixture", source_path="two_sum.py", source_commit="0" * 40,
        license="MIT", license_text="MIT", attribution="test", audit_report_json="{}")
    session.add(ex)
    session.commit()
    return ex


def test_programming_adapter_maps_real_judge_result(db_session):
    u = make_user(db_session, "ad_p1")
    ex = _exercise(db_session, ex_id=901)
    progress = ProgrammingExerciseProgress(
        user_id=u.id, username="ad_p1", exercise_id=901, personal_status="passed",
        last_action="submit", last_submit_at=main.utc_now(), last_submit_passed=True,
        last_public_passed_count=5, last_public_total_count=5)
    db_session.add(progress)
    db_session.commit()

    outcome = prog_adapter.mirror_programming_submission(
        db_session, u, ex, progress.id,
        {"passed": True, "passed_count": 5, "total_count": 5},
        submitted_at=progress.last_submit_at, language="Python")
    assert outcome.mirrored == 1

    a = service.list_attempts(db_session, u.id, service_namespace="programming")[0]
    assert a.correct is True
    assert a.score == 5.0 and a.max_score == 5.0
    assert a.question_source_type == "programming_exercise"
    assert json.loads(a.result_json)["source"] == "execution"
    assert json.loads(a.question_ref_json)["context"]["language"] == "Python"


def test_programming_adapter_maps_failure_as_false_not_none(db_session):
    u = make_user(db_session, "ad_p2")
    ex = _exercise(db_session, ex_id=902)
    progress = ProgrammingExerciseProgress(
        user_id=u.id, username="ad_p2", exercise_id=902, personal_status="needs_work",
        last_action="submit", last_submit_at=main.utc_now(), last_submit_passed=False,
        last_public_passed_count=2, last_public_total_count=5)
    db_session.add(progress)
    db_session.commit()

    prog_adapter.mirror_programming_submission(
        db_session, u, ex, progress.id,
        {"passed": False, "passed_count": 2, "total_count": 5},
        submitted_at=progress.last_submit_at)
    a = service.list_attempts(db_session, u.id, service_namespace="programming")[0]
    assert a.correct is False          # the judge did return a verdict
    assert a.score == 2.0 and a.max_score == 5.0


def test_programming_adapter_refuses_without_real_timestamp(db_session):
    u = make_user(db_session, "ad_p3")
    ex = _exercise(db_session, ex_id=903)
    progress = ProgrammingExerciseProgress(user_id=u.id, username="ad_p3",
                                           exercise_id=903)
    db_session.add(progress)
    db_session.commit()
    outcome = prog_adapter.mirror_programming_submission(
        db_session, u, ex, progress.id, {"passed": True}, submitted_at=None)
    assert outcome.mirrored == 0 and outcome.reason == "no_submission_timestamp"


def test_llm_derived_challenge_status_is_not_a_correctness_source():
    # code_challenge_attempts.status comes from keyword-matching AI prose; using it as
    # correctness would fabricate a verdict. It must stay excluded.
    matrix = {row["source"]: row for row in backfill.classification_matrix()}
    row = matrix["code_challenge_attempts"]
    assert row["classification"] == "INELIGIBLE"
    assert "prose" in row["reason"]
    assert prog_adapter.LLM_DERIVED_STATUS_SOURCE == "code_challenge_attempt"


def test_programming_submissions_source_is_ineligible_to_avoid_double_count():
    matrix = {row["source"]: row for row in backfill.classification_matrix()}
    assert matrix["programming_exercise_submissions"]["classification"] == "INELIGIBLE"


# ---------------------------------------------------------------- backfill

def test_backfill_classification_lists_missing_fields():
    matrix = {row["source"]: row for row in backfill.classification_matrix()}
    assert matrix["past_paper_attempts"]["classification"] == "PARTIAL"
    assert "response_time_ms" in matrix["past_paper_attempts"]["missing_fields"]
    assert matrix["question_attempts"]["missing_fields"]
    # every PARTIAL states what it cannot carry
    for row in matrix.values():
        if row["classification"] == "PARTIAL":
            assert row["missing_fields"], row["source"]


def test_question_attempts_backfill_maps_self_result(db_session):
    u = make_user(db_session, "bf1")
    q = Question(username="bf1", course_id="c_programming", title="t", content="c",
                 type="choice", answer="A")
    db_session.add(q)
    db_session.commit()
    for sr, _ in (("correct", True), ("incorrect", False), ("unknown", None)):
        db_session.add(QuestionAttempt(username="bf1", question_id=q.id,
                                       course_id="c_programming", user_answer="A",
                                       self_result=sr))
    db_session.commit()

    report = backfill.run_backfill(db_session, sources=["question_attempts"])
    assert report["totals"]["mirrored"] == 3
    attempts = service.list_attempts(db_session, u.id, service_namespace="course_learning")
    assert {a.correct for a in attempts} == {True, False, None}
    assert [a.question_source_type for a in attempts] == ["material_generated"] * 3


def test_backfill_is_idempotent_across_runs(db_session):
    u = make_user(db_session, "bf2")
    q = Question(username="bf2", course_id="c", title="t", content="c",
                 type="choice", answer="A")
    db_session.add(q)
    db_session.commit()
    db_session.add(QuestionAttempt(username="bf2", question_id=q.id, course_id="c",
                                   user_answer="A", self_result="correct"))
    db_session.commit()

    first = backfill.run_backfill(db_session, sources=["question_attempts"])
    second = backfill.run_backfill(db_session, sources=["question_attempts"])

    assert first["totals"]["mirrored"] >= 1        # this new row is mirrored
    assert second["totals"]["mirrored"] == 0       # nothing new on re-run
    assert second["totals"]["deduped"] >= 1
    # scoped to this user: exactly one attempt, one session, reused not recreated
    assert len(service.list_attempts(db_session, u.id)) == 1
    assert len(service.list_sessions(db_session, u.id)) == 1


def test_backfill_does_not_invent_attempts_without_item_detail(db_session):
    # a submitted row whose result_json carries no per-question detail states no
    # attempt fact; mirroring it would fabricate an answer the learner never gave
    u = make_user(db_session, "ghost")
    db_session.add(AIQuestionAttempt(username="ghost", mode="course_learning",
                                     subject_key="c", subject_name="c",
                                     status="submitted", question_ids_json="[1]",
                                     result_json="{}"))
    db_session.commit()
    report = backfill.run_backfill(db_session, sources=["ai_question_attempts"])
    assert report["per_source"]["ai_question_attempts"]["mirrored"] == 0
    assert report["totals"]["failed"] == 0
    assert service.list_attempts(db_session, u.id) == []


def test_backfill_flags_rows_whose_user_no_longer_exists(db_session):
    # an orphaned legacy row cannot be scoped to a user, so it is reported, not guessed
    db_session.add(AIQuestionAttempt(username="deleted_user", mode="course_learning",
                                     subject_key="c", subject_name="c",
                                     status="submitted", question_ids_json="[1]",
                                     result_json='{"results":[{"question_id":1,'
                                                '"correct":true,"question_type":"选择题"}]}'))
    db_session.commit()
    report = backfill.run_backfill(db_session, sources=["ai_question_attempts"])
    assert report["per_source"]["ai_question_attempts"]["failed"] >= 1


def test_backfill_report_shape(db_session):
    report = backfill.run_backfill(db_session, sources=["past_paper_attempts"])
    assert set(report) == {"per_source", "totals", "classification"}
    assert set(report["totals"]) == {"mirrored", "deduped", "conflicts", "failed"}
    assert report["per_source"]["past_paper_attempts"]["conflicts"] == 0


# ---------------------------------------------------------------- events

def _mirror_one_exam_attempt(db_session, user, *, session_key=501, qid="7001"):
    row = ExamPracticeAttempt(
        username=user.username, subject_key="ds", practice_type="chapter",
        status="submitted", question_ids_json=json.dumps([int(qid)]),
        total_questions=1, submitted_at=main.utc_now(),
        result_json=json.dumps({"results": [
            {"question_id": int(qid), "correct": True, "user_answer": "A",
             "question_type": "选择题"}]}))
    db_session.add(row)
    db_session.commit()
    exam_adapter.mirror_exam_practice_attempt(db_session, user, row)
    return service.list_attempts(db_session, user.id,
                                 service_namespace="exam_prep")[0]


def test_exam_attempt_emits_its_own_event_type(db_session):
    u = make_user(db_session, "ev1")
    attempt = _mirror_one_exam_attempt(db_session, u)

    event = events.build_event(attempt)
    assert event is not None
    assert event["event_type"] == "question_answered"
    assert event["event_type"] != "course_practice"      # never StudentTwin-eligible
    assert event["correct"] is True
    assert event["snapshot_completeness"] == "PARTIAL"   # questions are referenced, not copied

    # STEP 7F: the practice service already emitted it on the write path, so the
    # explicit call is a no-op rather than a second event
    res = events.emit_for_attempt(db_session, attempt)
    assert res["emitted"] == 0

    session = database.SessionLocal()
    try:
        row = session.query(LearningEvent).filter(
            LearningEvent.event_id == event["event_id"]).first()
        assert row is not None
    finally:
        session.close()


def test_course_attempts_are_not_emitted_by_practice_core(db_session):
    u = make_user(db_session, "ev2")
    row = _ai_attempt(db_session, "ev2", qids=[61], results={
        "results": [{"question_id": 61, "correct": True, "question_type": "选择题"}]})
    course_adapter.mirror_ai_question_attempt(db_session, u, row)
    attempt = service.list_attempts(db_session, u.id,
                                    service_namespace="course_learning")[0]

    # the existing data_plane emitter is the single authoritative owner for
    # course_practice; the practice core must not add a second event for that lineage.
    assert events.build_event(attempt) is None
    assert events.emit_for_attempt(db_session, attempt)["reason"] == "not_practice_owned"
    assert ("course_learning", "ai_question_attempt") in events.FOREIGN_OWNED_SOURCES
    # course_learning IS otherwise covered by the practice spine (STEP 7G)
    assert events.EVENT_TYPE_BY_NAMESPACE["course_learning"] == "question_answered"


def test_event_emission_is_idempotent(db_session):
    u = make_user(db_session, "ev3")
    attempt = _mirror_one_exam_attempt(db_session, u, session_key=502, qid="7002")
    # already emitted on the write path; replaying must not add a second row
    assert events.emit_for_attempt(db_session, attempt)["emitted"] == 0
    assert events.emit_for_attempt(db_session, attempt)["emitted"] == 0

    # scoped by the exact event identity: source_attempt_id alone is not unique across
    # source types in a shared test database
    expected_id = events.build_event(attempt)["event_id"]
    session = database.SessionLocal()
    try:
        n = session.query(LearningEvent).filter(
            LearningEvent.event_id == expected_id).count()
    finally:
        session.close()
    assert n == 1


def test_event_recovery_restores_a_missing_event(db_session):
    u = make_user(db_session, "ev4")
    attempt = _mirror_one_exam_attempt(db_session, u, session_key=503, qid="7003")
    # simulate an emission that never landed by removing the row the write path wrote
    session = database.SessionLocal()
    try:
        session.query(LearningEvent).filter(
            LearningEvent.event_id == events.build_event(attempt)["event_id"]
        ).delete()
        session.commit()
    finally:
        session.close()

    report = events.recover_events(db_session)
    assert report["recovered"] >= 1

    session = database.SessionLocal()
    try:
        row = session.query(LearningEvent).filter(
            LearningEvent.event_id == events.build_event(attempt)["event_id"]).first()
        assert row is not None
    finally:
        session.close()


def test_event_id_is_deterministic_and_stable(db_session):
    u = make_user(db_session, "ev5")
    attempt = _mirror_one_exam_attempt(db_session, u, session_key=504, qid="7004")
    first = events.build_event(attempt)["event_id"]
    second = events.build_event(attempt)["event_id"]
    assert first == second           # replay/backfill agree; never random


def test_student_twin_eligibility_is_not_expanded(db_session):
    """Practice Core rows must not become StudentTwin input by existing."""
    # the producer only selects course_practice events
    assert "course_practice" not in events.EVENT_TYPE_BY_NAMESPACE.values()
    for ns, etype in events.EVENT_TYPE_BY_NAMESPACE.items():
        assert etype != "course_practice", ns
    # and exam / programming attempts are not course_practice
    u = make_user(db_session, "ev6")
    attempt = _mirror_one_exam_attempt(db_session, u, session_key=505, qid="7005")
    assert attempt.service_namespace == "exam_prep"
    assert events.build_event(attempt)["event_type"] == "question_answered"


def test_mirror_failure_is_absorbed_and_observable(db_session, monkeypatch):
    u = make_user(db_session, "ev7")
    row = _ai_attempt(db_session, "ev7", qids=[71], results={
        "results": [{"question_id": 71, "correct": True, "question_type": "选择题"}]})

    def boom(*_a, **_kw):
        raise RuntimeError("mirror exploded")

    monkeypatch.setattr(service, "ensure_legacy_session", boom)
    outcome = course_adapter.mirror_ai_question_attempt(db_session, u, row)
    assert outcome.failed == 1
    assert outcome.reason == "RuntimeError"      # observable, not swallowed silently


def test_adapter_never_raises_through_safe_mirror(db_session):
    def boom():
        raise ValueError("nope")

    outcome = adapter_base.safe_mirror("t", "src", 1, boom, db=None)
    assert outcome.failed == 1 and outcome.ok is False
