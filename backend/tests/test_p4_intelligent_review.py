"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4 — Intelligent Review V1.

WHAT THESE TESTS HOLD
---------------------
1. the schedule is REPRODUCIBLE from its stated inputs (the same facts → the same date), and
   the response always names the policy version, the reason and the facts it used;
2. a first schedule is honest about having NO history ("first_schedule", no previous interval)
   — nothing is fabricated to make the model look smarter;
3. ONLY a real review result moves a schedule: completion requires a result, and the next due
   date follows that result's branch;
4. an item belongs to its owner: another learner's item is a 404, and no cross-user write is
   possible;
5. the review projection shows the computed date WITH its provenance, and the item's own
   knowledge row is updated where such a column exists.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
from datetime import datetime, timedelta

from conftest import register_and_login

from core.learning_context import ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.review_schedule import (
    POLICY_VERSION,
    REASON_AFTER_CORRECT,
    REASON_AFTER_INCORRECT,
    REASON_FIRST_SCHEDULE,
    compute_schedule,
)
from learning.spaces.course_learning.context import build_course_context
from models import AIGeneratedQuestion, CourseLearningPreference, User, UserKnowledgeProgress

REVIEW = "/review"
COURSE = "数据结构"
MOMENT = datetime(2026, 9, 20, 8, 30, 0)


# ---------------------------------------------------------------- helpers

def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _wrong_item(db, user, *, stem="错题", qid=None):
    question = AIGeneratedQuestion(
        username=user.username, subject_key=COURSE, subject_name=COURSE,
        knowledge_point_id="kp_review", knowledge_point_name="复习点", question_type="选择题",
        stem=stem, standard_answer="A", analysis="解析", quality_status="unchecked",
        generation_mode="ai")
    db.add(question)
    db.commit()
    db.refresh(question)
    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p4_review",
        source_session_key="p4:review", mode="p4", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p4_review_attempt", f"q{question.id}", "0"))
    return question


def _knowledge_item(db, user, *, code="kp_review", due_days_ago=1):
    row = UserKnowledgeProgress(
        username=user.username, course_id=COURSE, knowledge_point_id=7701,
        knowledge_point_code=code, knowledge_point_title="复习点", status="learning",
        practice_count=2, review_interval_days=7,
        review_due_at=datetime.utcnow() - timedelta(days=due_days_ago))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _items(client, namespace="course_learning"):
    response = client.get(REVIEW, params={"service_namespace": namespace})
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _item_by_id(client, item_id, namespace="course_learning"):
    return next(item for item in _items(client, namespace) if item["id"] == item_id)


# ================================================================ 1. the policy


def test_the_policy_is_pure_and_reproducible():
    """The same inputs — INCLUDING the same 'now' — always produce the same date."""
    clock = datetime(2026, 9, 20, 9, 0, 0)
    first = compute_schedule(last_review_result="correct", previous_interval_days=6,
                             repeated_wrong_count=0, item_status="learning", now=clock)
    second = compute_schedule(last_review_result="correct", previous_interval_days=6,
                              repeated_wrong_count=0, item_status="learning", now=clock)
    assert first == second
    assert first["reason"] == REASON_AFTER_CORRECT
    assert first["interval_days"] == 12          # 6 → 12 (×2)
    assert first["due_at"] == (clock + timedelta(days=12)).isoformat()
    assert first["policy_version"] == POLICY_VERSION

    worse = compute_schedule(last_review_result="incorrect", previous_interval_days=12,
                             repeated_wrong_count=0, item_status="learning", now=clock)
    assert worse["reason"] == REASON_AFTER_INCORRECT
    assert worse["interval_days"] == 1

    repeated = compute_schedule(last_review_result=None, previous_interval_days=None,
                                repeated_wrong_count=3, item_status="learning", now=clock)
    assert repeated["reason"] == "repeated_wrong"
    assert repeated["interval_days"] == 2

    # the policy also saturates: a long interval cannot grow without bound
    capped = compute_schedule(last_review_result="correct", previous_interval_days=45,
                              repeated_wrong_count=0, item_status="learning", now=clock)
    assert capped["interval_days"] == 60


def test_a_first_schedule_does_not_invent_history():
    schedule = compute_schedule(last_review_result=None, previous_interval_days=None,
                                repeated_wrong_count=0, item_status="learning")
    assert schedule["reason"] == REASON_FIRST_SCHEDULE
    assert schedule["facts"]["last_review_result"] is None
    assert schedule["facts"]["previous_interval_days"] is None


# ================================================================ 2. scheduling endpoints


def test_scheduling_an_item_records_the_policy_and_its_facts(client, db_session):
    register_and_login(client, "p4_rev_schedule")
    user = _user(db_session, "p4_rev_schedule")
    _own_course(db_session, user.username)
    _wrong_item(db_session, user)
    knowledge = _knowledge_item(db_session, user)

    item = _item_by_id(client, f"knowledge:{knowledge.id}")
    response = client.post(f"{REVIEW}/schedule", json={"item_ids": [item["id"]]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["policy_version"] == POLICY_VERSION
    assert body["count"] == 1
    scheduled = body["scheduled"][0]
    assert scheduled["item_id"] == item["id"]
    assert scheduled["reason"] == REASON_FIRST_SCHEDULE
    assert scheduled["due_at"] and scheduled["scheduled_at"]
    # the previous interval is the row's OWN stored value (7 days) — a real fact, not a guess
    assert scheduled["facts"]["previous_interval_days"] == 7
    assert scheduled["facts"]["last_review_result"] is None

    # the knowledge row's OWN columns were updated (they exist), so the page agrees
    db_session.expire_all()
    row = db_session.query(UserKnowledgeProgress).filter(
        UserKnowledgeProgress.id == knowledge.id).one()
    assert row.review_due_at is not None
    assert row.review_interval_days == scheduled["interval_days"]

    # …and the projection now shows the date WITH its provenance
    refreshed = _item_by_id(client, item["id"])
    assert refreshed["review_status"] in ("due", "scheduled")
    assert refreshed["due_at"] == scheduled["due_at"]
    assert refreshed["due_source"] == f"review_policy.{POLICY_VERSION}.{REASON_FIRST_SCHEDULE}"
    assert refreshed["schedule"]["policy_version"] == POLICY_VERSION


def test_completion_requires_a_real_result_and_moves_the_schedule(client, db_session):
    register_and_login(client, "p4_rev_complete")
    user = _user(db_session, "p4_rev_complete")
    _own_course(db_session, user.username)
    knowledge = _knowledge_item(db_session, user)
    item_id = f"knowledge:{knowledge.id}"

    # no result → the request is refused by the contract itself
    assert client.post(f"{REVIEW}/{item_id}/complete", json={}).status_code == 422

    correct = client.post(f"{REVIEW}/{item_id}/complete", json={"result": "correct"})
    assert correct.status_code == 200, correct.text
    body = correct.json()
    assert body["result"] == "correct"
    # the RESULT drives the branch, and the interval doubles the row's OWN stored interval
    assert body["reason"] == REASON_AFTER_CORRECT
    assert body["source_facts"]["previous_interval_days"] == 7      # the stored value
    assert body["interval_days"] == 14                              # 7 → 14 (×2)
    assert body["previous_review_result"] is None
    assert body["source_facts"]["last_review_result"] == "correct"

    # a SECOND, incorrect review shortens it — from the REAL result, not from a guess
    again = client.post(f"{REVIEW}/{item_id}/complete", json={"result": "incorrect"})
    assert again.status_code == 200, again.text
    second = again.json()
    assert second["previous_review_result"] == "correct"
    assert second["reason"] == REASON_AFTER_INCORRECT
    assert second["interval_days"] == 1

    from data_plane.models import LearningEvent
    db_session.expire_all()
    events = {row.event_type for row in
              db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id,
                      LearningEvent.source_type == "review_item",
                      LearningEvent.source_attempt_id == item_id).all()}
    assert {"review_completed", "review_scheduled"} <= events


def test_another_learners_item_is_a_404(client, db_session):
    register_and_login(client, "p4_rev_owner")
    owner = _user(db_session, "p4_rev_owner")
    _own_course(db_session, owner.username)
    knowledge = _knowledge_item(db_session, owner)
    item_id = f"knowledge:{knowledge.id}"

    register_and_login(client, "p4_rev_caller")
    caller = _user(db_session, "p4_rev_caller")
    _own_course(db_session, caller.username)

    assert client.post(f"{REVIEW}/schedule", json={"item_ids": [item_id]}).status_code == 404
    assert client.post(f"{REVIEW}/{item_id}/complete",
                       json={"result": "correct"}).status_code == 404
    assert _items(client) == []


def test_namespace_isolation_holds_for_scheduling(client, db_session):
    register_and_login(client, "p4_rev_namespace")
    user = _user(db_session, "p4_rev_namespace")
    _own_course(db_session, user.username)
    _wrong_item(db_session, user)

    course_items = _items(client, "course_learning")
    assert course_items, "the seeded wrong answer is a course review item"
    assert all(item["service_namespace"] == "course_learning" for item in course_items)
    assert _items(client, "exam_11408") == []

    # the wrong-answer item schedules from its OWN facts (one recorded wrong, so far)
    item = course_items[0]
    scheduled = client.post(f"{REVIEW}/schedule", json={"item_ids": [item["id"]]}).json()
    entry = scheduled["scheduled"][0]
    assert entry["item_id"] == item["id"]
    assert entry["facts"]["repeated_wrong_count"] == 1
    # one wrong is not yet "repeated" — the policy says exactly what its inputs justify
    assert entry["reason"] == REASON_FIRST_SCHEDULE
    assert entry["interval_days"] == 3
