"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5 §H — the review storage decision, verified.

THE QUESTION
------------
P4 left review schedules in the canonical event stream (a wrong-answer or programming item has
no due column; a knowledge item does). Before proposing any migration, the existing projection
must be able to: RECOVER after a restart, PAGINATE stably, be queried BY DUE DATE, and UPDATE
correctly when a new review happens.

These tests answer that directly, from a SEPARATE database session — which is exactly what a
restarted process sees.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
from datetime import datetime, timedelta

from conftest import register_and_login

from core.learning_context import ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import producers
from learning.review_schedule import latest_scheduled_due, scheduled_dues
from learning.spaces.course_learning.context import build_course_context
from models import AIGeneratedQuestion, CourseLearningPreference, User, UserKnowledgeProgress

REVIEW = "/review"
COURSE = "数据结构"
MOMENT = datetime(2026, 9, 20, 10, 0, 0)


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _wrong_state(db, user):
    question = AIGeneratedQuestion(
        username=user.username, subject_key=COURSE, subject_name=COURSE,
        knowledge_point_id="kp_persist", knowledge_point_name="持久化点", question_type="选择题",
        stem="持久化题", standard_answer="A", analysis="解析", quality_status="unchecked",
        generation_mode="ai")
    db.add(question)
    db.commit()
    db.refresh(question)
    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p5_persist",
        source_session_key="p5:persist", mode="p5", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p5_persist_attempt", f"q{question.id}", "0"))
    from learning.wrong_answers import service as wrong_service
    return wrong_service.list_states(db, user.id, service_namespace="course_learning")[0]


def _knowledge(db, user, *, code, title):
    row = UserKnowledgeProgress(
        username=user.username, course_id=COURSE, knowledge_point_id=abs(hash(code)) % 10**6,
        knowledge_point_code=code, knowledge_point_title=title, status="learning",
        practice_count=1, review_interval_days=7,
        review_due_at=datetime.utcnow() - timedelta(days=1))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _fresh_session():
    """A NEW session on the same database — what a restarted process sees."""
    import database
    return database.SessionLocal()


def _items(client, query=""):
    response = client.get(REVIEW + query)
    assert response.status_code == 200, response.text
    return response.json()


# ================================================================ 1. recovery


def test_a_schedule_is_recovered_from_a_fresh_session(client, db_session):
    register_and_login(client, "p5_rp_restart")
    user = _user(db_session, "p5_rp_restart")
    _own_course(db_session, user.username)
    state = _wrong_state(db_session, user)
    item_id = f"wrong:course_learning:{state.id}"

    scheduled = client.post(f"{REVIEW}/schedule", json={"item_ids": [item_id]}).json()
    due_at = scheduled["scheduled"][0]["due_at"]

    # a brand-new session (a restart) still knows the schedule, and knows where it came from
    with _fresh_session() as fresh:
        recovered = latest_scheduled_due(fresh, user.id, item_id)
    assert recovered is not None
    assert recovered["due_at"] == due_at
    assert recovered["policy_version"] == "review_policy_v1"
    assert recovered["reason"]

    # …and the projection served from a fresh read agrees
    refreshed = [item for item in _items(client)["items"] if item["id"] == item_id][0]
    assert refreshed["due_at"] == due_at
    assert refreshed["due_source"].startswith("review_policy.review_policy_v1")


def test_pagination_is_stable_across_reads(client, db_session):
    register_and_login(client, "p5_rp_paging")
    user = _user(db_session, "p5_rp_paging")
    _own_course(db_session, user.username)
    ids = []
    for index in range(3):
        state = _wrong_state(db_session, user)
        item_id = f"wrong:course_learning:{state.id}"
        producers.emit_review_scheduled(
            user_id=user.id, item_id=item_id,
            due_at=(datetime.utcnow() - timedelta(days=1)).isoformat(),
            policy_version="review_policy_v1", service_namespace="course_learning",
            interval_days=3, reason="first_schedule",
            scheduled_at=datetime.utcnow().isoformat(), facts={}, occurred_at=None,
            source_user_ref=user.username)
        ids.append(item_id)

    first_page = [item["id"] for item in _items(client, "?limit=2&offset=0")["items"]]
    second_page = [item["id"] for item in _items(client, "?limit=2&offset=2")["items"]]
    again_first = [item["id"] for item in _items(client, "?limit=2&offset=0")["items"]]

    assert first_page == again_first, "a page is stable across reads"
    assert len(first_page) == 2 and len(second_page) >= 1
    assert set(first_page) | set(second_page) == set(ids), "every item is reachable"


def test_scheduled_items_are_queryable_by_due(client, db_session):
    register_and_login(client, "p5_rp_due")
    user = _user(db_session, "p5_rp_due")
    _own_course(db_session, user.username)
    state = _wrong_state(db_session, user)
    item_id = f"wrong:course_learning:{state.id}"

    # not due yet
    scheduled = client.post(f"{REVIEW}/schedule", json={"item_ids": [item_id]}).json()
    assert scheduled["scheduled"][0]["due_at"] > datetime.utcnow().isoformat()

    due_now = [item["id"] for item in _items(client, "?status=due")["items"]]
    assert item_id not in due_now
    scheduled_now = [item["id"] for item in _items(client, "?status=scheduled")["items"]]
    assert item_id in scheduled_now

    # a PAST schedule makes it due — the due bucket is queryable, not just displayable
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    producers.emit_review_scheduled(
        user_id=user.id, item_id=item_id, due_at=past,
        policy_version="review_policy_v1", service_namespace="course_learning",
        interval_days=1, reason="after_incorrect",
        scheduled_at=datetime.utcnow().isoformat(), facts={}, occurred_at=None,
        source_user_ref=user.username)
    due_now = [item["id"] for item in _items(client, "?status=due")["items"]]
    assert item_id in due_now


def test_the_latest_schedule_wins(client, db_session):
    register_and_login(client, "p5_rp_latest")
    user = _user(db_session, "p5_rp_latest")
    _own_course(db_session, user.username)
    state = _wrong_state(db_session, user)
    item_id = f"wrong:course_learning:{state.id}"

    old = (datetime.utcnow() + timedelta(days=1)).isoformat()
    new = (datetime.utcnow() + timedelta(days=20)).isoformat()
    for due, interval in ((old, 1), (new, 20)):
        producers.emit_review_scheduled(
            user_id=user.id, item_id=item_id, due_at=due,
            policy_version="review_policy_v1", service_namespace="course_learning",
            interval_days=interval, reason="after_correct",
            scheduled_at=datetime.utcnow().isoformat(), facts={}, occurred_at=None,
            source_user_ref=user.username)

    with _fresh_session() as fresh:
        assert scheduled_dues(fresh, user.id, [item_id])[item_id]["due_at"] == new
    shown = [item for item in _items(client)["items"] if item["id"] == item_id][0]
    assert shown["due_at"] == new
    assert shown["schedule"]["interval_days"] == 20


def test_completion_updates_the_row_and_the_projection_together(client, db_session):
    register_and_login(client, "p5_rp_complete")
    user = _user(db_session, "p5_rp_complete")
    _own_course(db_session, user.username)
    knowledge = _knowledge(db_session, user, code="kp_persist_1", title="持久化点")

    item_id = f"knowledge:{knowledge.id}"
    completed = client.post(f"{REVIEW}/{item_id}/complete", json={"result": "correct"}).json()

    with _fresh_session() as fresh:
        row = fresh.query(UserKnowledgeProgress).filter(
            UserKnowledgeProgress.id == knowledge.id).one()
        assert row.review_due_at.isoformat() == completed["due_at"]
        assert row.review_interval_days == completed["interval_days"]

    shown = [item for item in _items(client)["items"] if item["id"] == item_id][0]
    assert shown["due_at"] == completed["due_at"]
    assert shown["review_status"] == "scheduled"      # the new date is in the future
