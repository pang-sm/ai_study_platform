"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3A — Unified Review foundation.

WHAT THESE TESTS HOLD
---------------------
1. the three learning spaces map to review items from the facts they ALREADY store — course
   and exam wrong-answer states, programming status, and stored knowledge review dates;
2. isolation is total: a namespace filter narrows the caller's OWN projection and one learner
   never sees another learner's review work;
3. NO FABRICATION: a due date appears only where a space stored one
   (``user_knowledge_progress.review_due_at``); everything else is ``needs_attention`` with
   ``due_at = null``, and a knowledge row without a stored date contributes nothing;
4. the summary counts exactly what the list serves (one projection, no second aggregation);
5. no prediction-shaped field is exposed — the projection reports facts, not weakness guesses.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import json
from datetime import datetime, timedelta

from conftest import register_and_login

from core.learning_context import LearningContext, ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.course_learning.context import build_course_context
from models import (CourseLearningPreference, ProgrammingExercise,
                    ProgrammingExerciseProgress, User, UserKnowledgeProgress)

REVIEW = "/review"
COURSE = "数据结构"
OTHER_COURSE = "操作系统"
MODULE = "operating_system"
MOMENT = datetime(2026, 9, 20, 6, 0, 0)

FORBIDDEN_KEY_TOKENS = frozenset({
    "probability", "predicted", "prediction", "readiness", "confidence", "weakness",
    "estimate", "mastery", "ability", "theta", "score_predicted", "memory",
})


# ---------------------------------------------------------------- helpers

def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _exam_context(user, module=MODULE):
    return LearningContext(user_id=user.id, service_namespace=ServiceNamespace.EXAM_PREP,
                           subject_key=module, exam_subject_id="cs_408",
                           exam_module_id=module)


def _record(db, user, *, namespace, qid, correct, source_type, context, when=MOMENT,
            source_id=None):
    """One canonical attempt through the real Practice Core (which projects the state)."""
    session, _ = practice_service.ensure_legacy_session(
        db, user, namespace, source_type="p3a_review", source_session_key=f"{namespace}:{qid}",
        mode="p3a", context=context, started_at=None)
    ref = QuestionRef(source_type=source_type, source_id=str(qid),
                      service_namespace=ServiceNamespace(namespace),
                      context=dict(context.to_dict()))
    return practice_service.record_attempt(
        db, user, session, ref, answer="A", correct=correct, submitted_at=when,
        context=context,
        source=practice_service.SourceIdentity("p3a_review_attempt",
                                               source_id or f"{namespace}:{qid}", f"{qid}:0"))


def _knowledge(db, username, *, code, title, due_at, course_id=COURSE):
    row = UserKnowledgeProgress(
        username=username, course_id=course_id, knowledge_point_id=abs(hash(code)) % 10**6,
        knowledge_point_code=code, knowledge_point_title=title, status="learning",
        mastery_score=40, practice_count=3, review_due_at=due_at,
        review_interval_days=7)
    db.add(row)
    db.commit()
    return row


def _programming(db, username, *, exercise_id, status="needs_work", passed=False,
                 last_submit_at=MOMENT):
    exercise = db.query(ProgrammingExercise).filter(
        ProgrammingExercise.id == exercise_id).first()
    if exercise is None:
        exercise = ProgrammingExercise(
            id=exercise_id, slug=f"p3a-review-{exercise_id}", title="两数之和",
            language="Python", difficulty="easy", description="d", tags_json="[]",
            starter_files_json="[]", reference_files_json="[]", public_tests_json="[]",
            hidden_tests_json="[]", official_test_files_json="[]", source_repo="fixture",
            source_path="two_sum.py", source_commit="0" * 40, license="MIT",
            license_text="MIT", attribution="test", audit_report_json="{}",
            is_active=True, quality_status="approved")
        db.add(exercise)
        db.commit()
    progress = ProgrammingExerciseProgress(
        user_id=_user(db, username).id, username=username, exercise_id=exercise_id,
        personal_status=status, last_action="submit", last_submit_at=last_submit_at,
        last_submit_passed=passed, last_public_passed_count=1, last_public_total_count=3)
    db.add(progress)
    db.commit()
    return progress


def _key_paths(payload, prefix=""):
    out = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            out.append(f"{prefix}{key}")
            out.extend(_key_paths(value, f"{prefix}{key}."))
    elif isinstance(payload, list):
        for item in payload:
            out.extend(_key_paths(item, prefix))
    return out


# ================================================================ 1. the three spaces


def test_course_and_exam_wrong_answers_are_mapped_from_their_own_facts(client, db_session):
    register_and_login(client, "p3a_rev_wrong")
    user = _user(db_session, "p3a_rev_wrong")
    _own_course(db_session, user.username, COURSE)

    _record(db_session, user, namespace="course_learning", qid=901, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(user, course_id=COURSE))
    _record(db_session, user, namespace="exam_prep", qid=902, correct=False,
            source_type=QuestionSourceType.STATIC_QUESTION_BANK,
            context=_exam_context(user))

    body = client.get(REVIEW).json()
    assert body["total"] == 2
    by_namespace = {item["service_namespace"]: item for item in body["items"]}
    assert set(by_namespace) == {"course_learning", "exam_prep"}

    course_item = by_namespace["course_learning"]
    assert course_item["source_type"] == "wrong_answer"
    assert course_item["reason"] == "wrong_answer_active"
    assert course_item["review_status"] == "needs_attention"
    assert course_item["domain_context"]["course_id"] == COURSE
    assert course_item["deep_link"] == f"/course/{COURSE}/wrong"
    assert course_item["question_identity"]["question_source_id"] == "901"

    exam_item = by_namespace["exam_prep"]
    assert exam_item["domain_context"]["exam_module_id"] == MODULE
    assert exam_item["deep_link"].startswith("/exam/cs408/wrong")
    assert exam_item["question_identity"]["question_source_id"] == "902"


def test_programming_needs_work_is_mapped_from_the_progress_row(client, db_session):
    register_and_login(client, "p3a_rev_prog")
    _programming(db_session, "p3a_rev_prog", exercise_id=8801, status="needs_work")
    _programming(db_session, "p3a_rev_prog", exercise_id=8802, status="passed",
                 passed=False, last_submit_at=MOMENT - timedelta(days=1))

    body = client.get(REVIEW, params={"service_namespace": "programming"}).json()
    by_source = {item["source_id"]: item for item in body["items"]}
    assert set(by_source) == {"8801", "8802"}

    needs_work = by_source["8801"]
    assert needs_work["reason"] == "exercise_needs_work"
    assert needs_work["domain_context"]["language"] == "Python"
    assert needs_work["deep_link"] == "/programming/Python/exercises/8801"
    assert needs_work["due_at"] is None

    # a submission that failed is a real fact too, and it names itself honestly
    failed = by_source["8802"]
    assert failed["reason"] == "exercise_last_submit_failed"
    assert failed["metrics"]["passed_count"] == 1
    assert failed["metrics"]["total_count"] == 3


def test_the_three_spaces_are_isolated_by_the_namespace_filter(client, db_session):
    register_and_login(client, "p3a_rev_iso")
    user = _user(db_session, "p3a_rev_iso")
    _own_course(db_session, user.username, COURSE)
    _record(db_session, user, namespace="course_learning", qid=911, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(user, course_id=COURSE))
    _record(db_session, user, namespace="exam_prep", qid=912, correct=False,
            source_type=QuestionSourceType.STATIC_QUESTION_BANK, context=_exam_context(user))
    _programming(db_session, user.username, exercise_id=8803)

    everything = client.get(REVIEW).json()
    assert {item["service_namespace"] for item in everything["items"]} == {
        "course_learning", "exam_prep", "programming"}

    for request_value, expected in (("course_learning", {"course_learning"}),
                                    ("exam_11408", {"exam_prep"}),
                                    ("programming", {"programming"})):
        filtered = client.get(REVIEW, params={"service_namespace": request_value}).json()
        assert filtered["items"], request_value
        assert {item["service_namespace"] for item in filtered["items"]} == expected


def test_review_never_shows_another_learners_facts(client, db_session):
    register_and_login(client, "p3a_rev_owner")
    owner = _user(db_session, "p3a_rev_owner")
    _own_course(db_session, owner.username, COURSE)
    _record(db_session, owner, namespace="course_learning", qid=921, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(owner, course_id=COURSE))
    _knowledge(db_session, owner.username, code="kp_rev", title="线性表",
               due_at=MOMENT - timedelta(days=1))
    _programming(db_session, owner.username, exercise_id=8804)
    assert client.get(REVIEW).json()["total"] >= 3

    # a different learner on the same platform sees their own (empty) review, not this one
    register_and_login(client, "p3a_rev_other")
    other = client.get(REVIEW).json()
    assert other["total"] == 0
    assert other["items"] == []
    assert client.get(REVIEW + "/summary").json()["total"] == 0


# ================================================================ 2. no fabricated dates


def test_a_due_date_exists_only_where_one_is_stored(client, db_session):
    register_and_login(client, "p3a_rev_due")
    user = _user(db_session, "p3a_rev_due")
    _own_course(db_session, user.username, COURSE)

    now = datetime.utcnow()
    _knowledge(db_session, user.username, code="kp_no_date", title="没有排期",
               due_at=None)
    _knowledge(db_session, user.username, code="kp_overdue", title="已到期",
               due_at=now - timedelta(days=2))
    _knowledge(db_session, user.username, code="kp_future", title="未来复习",
               due_at=now + timedelta(days=3))

    body = client.get(REVIEW).json()
    by_reason = {item["reason"]: item for item in body["items"]}
    assert set(by_reason) == {"knowledge_review_due", "knowledge_review_scheduled"}

    overdue = by_reason["knowledge_review_due"]
    assert overdue["review_status"] == "due"
    assert overdue["due_at"] is not None
    assert overdue["due_source"] == "user_knowledge_progress.review_due_at"
    assert overdue["title"] == "已到期"

    scheduled = by_reason["knowledge_review_scheduled"]
    assert scheduled["review_status"] == "scheduled"
    assert scheduled["due_at"] is not None

    # the row with NO stored date produced NO item at all
    assert "没有排期" not in json.dumps(body, ensure_ascii=False)
    assert body["buckets"]["due"] == 1


def test_domains_without_a_stored_schedule_stay_needs_attention(client, db_session):
    register_and_login(client, "p3a_rev_manual")
    user = _user(db_session, "p3a_rev_manual")
    _own_course(db_session, user.username, COURSE)
    _record(db_session, user, namespace="course_learning", qid=931, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(user, course_id=COURSE))
    _programming(db_session, user.username, exercise_id=8805)

    body = client.get(REVIEW, params={"status": "needs_attention"}).json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["review_status"] == "needs_attention"
        assert item["due_at"] is None
        assert item["due_source"] is None

    # …and the "due" bucket is empty rather than filled with invented schedules
    assert client.get(REVIEW, params={"status": "due"}).json()["total"] == 0


def test_exam_knowledge_rows_are_classified_into_the_exam_space(client, db_session):
    """A knowledge row stored under the legacy exam scope id is an EXAM item, not a course."""
    register_and_login(client, "p3a_rev_exam_kp")
    user = _user(db_session, "p3a_rev_exam_kp")
    _own_course(db_session, user.username, COURSE)
    _knowledge(db_session, user.username, code="kp_exam", title="操作系统复习",
               due_at=MOMENT - timedelta(hours=1), course_id="operating_system_11408")
    _knowledge(db_session, user.username, code="kp_course", title="课程复习",
               due_at=MOMENT - timedelta(hours=2), course_id=COURSE)

    body = client.get(REVIEW).json()
    by_namespace = {item["service_namespace"]: item for item in body["items"]}
    assert set(by_namespace) == {"course_learning", "exam_prep"}

    exam_item = by_namespace["exam_prep"]
    assert exam_item["domain_context"]["exam_module_id"] == "operating_system"
    assert exam_item["domain_context"].get("course_id") is None
    assert exam_item["deep_link"] == "/exam/cs408/knowledge?module=operating_system"

    course_item = by_namespace["course_learning"]
    assert course_item["domain_context"]["course_id"] == COURSE
    assert course_item["deep_link"] == f"/course/{COURSE}/knowledge"

    # the exam item answers the exam filter, and only it does
    exam_only = client.get(REVIEW, params={"service_namespace": "exam_11408"}).json()
    assert [item["id"] for item in exam_only["items"]] == [exam_item["id"]]


# ================================================================ 3. summary & shape


def test_the_summary_counts_exactly_what_the_list_serves(client, db_session):
    register_and_login(client, "p3a_rev_summary")
    user = _user(db_session, "p3a_rev_summary")
    _own_course(db_session, user.username, COURSE)
    _record(db_session, user, namespace="course_learning", qid=941, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(user, course_id=COURSE))
    _knowledge(db_session, user.username, code="kp_s", title="到期", due_at=MOMENT)
    _programming(db_session, user.username, exercise_id=8806)

    listed = client.get(REVIEW).json()
    summary = client.get(REVIEW + "/summary").json()

    assert summary["total"] == listed["total"] == 3
    assert summary["by_status"] == listed["buckets"]
    assert summary["by_namespace"] == {"course_learning": 2, "programming": 1}
    assert summary["has_stored_due_dates"] is True

    only_course = client.get(REVIEW + "/summary",
                             params={"service_namespace": "course_learning"}).json()
    assert only_course["total"] == 2
    assert only_course["by_namespace"] == {"course_learning": 2}


def test_review_exposes_no_prediction_shaped_field(client, db_session):
    register_and_login(client, "p3a_rev_shape")
    user = _user(db_session, "p3a_rev_shape")
    _own_course(db_session, user.username, COURSE)
    _record(db_session, user, namespace="course_learning", qid=951, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(user, course_id=COURSE))
    _knowledge(db_session, user.username, code="kp_shape", title="形状", due_at=MOMENT)
    _programming(db_session, user.username, exercise_id=8807)

    hits = []
    for path in (client.get(REVIEW).json(), client.get(REVIEW + "/summary").json()):
        for key_path in _key_paths(path):
            tokens = {token for chunk in key_path.lower().split(".")
                      for token in chunk.split("_") if token}
            offenders = tokens & FORBIDDEN_KEY_TOKENS
            if offenders:
                hits.append((key_path, sorted(offenders)))
    assert not hits, f"review exposes a prediction-shaped field: {hits}"
