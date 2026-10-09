"""Deterministic review recommendation projection over real learner facts."""
from datetime import datetime, timedelta, timezone

from conftest import register_and_login

from data_plane.models import LearningEvent
from learning import review_recommendations
from learning import review_snoozes as snoozes
from test_p3a_unified_review import (
    COURSE,
    _knowledge,
    _own_course,
    _programming,
    _record,
    _user,
)
from learning.practice.refs import QuestionSourceType
from learning.practice.refs import QuestionRef
from learning.practice import service as practice_service
from core.learning_context import LearningContext, ServiceNamespace
from models import User
from learning.spaces.course_learning.context import build_course_context


AS_OF = datetime(2026, 10, 9, 12, 0, 0)


def test_recommendations_rank_only_due_and_factual_signals_without_writing(client, db_session):
    register_and_login(client, "recommendation_facts")
    user = _user(db_session, "recommendation_facts")
    _own_course(db_session, user.username, COURSE)

    due = _knowledge(db_session, user.username, code="due_node", title="到期知识点",
                     due_at=AS_OF - timedelta(days=4))
    _knowledge(db_session, user.username, code="future_node", title="未来知识点",
               due_at=AS_OF + timedelta(days=1))
    _knowledge(db_session, user.username, code="no_schedule", title="无可靠周期",
               due_at=None)

    context = build_course_context(user, course_id=COURSE)
    _record(db_session, user, namespace="course_learning", qid=901, correct=False,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(days=2), source_id="wrong-attempt-1")
    _record(db_session, user, namespace="course_learning", qid=901, correct=False,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(days=1), source_id="wrong-attempt-2")
    _record(db_session, user, namespace="course_learning", qid=902, correct=False,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(hours=2), source_id="single-wrong")
    _programming(db_session, user.username, exercise_id=8801, status="needs_work",
                 passed=False, last_submit_at=AS_OF - timedelta(hours=1))

    db_session.flush()
    events_before = db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id).count()
    schedule_before = due.review_due_at

    result = review_recommendations.build_recommendations(
        db_session, user, as_of=AS_OF)
    items = result["items"]

    assert result["policy_version"] == review_recommendations.POLICY_VERSION
    assert [item["reason_code"] for item in items] == [
        "scheduled_overdue",
        "repeated_wrong",
        "programming_single_failure",
        "single_wrong",
    ]
    assert len({item["recommendation_key"] for item in items}) == len(items)
    assert items[0]["title"] == "到期知识点"
    assert items[0]["evidence"]["due_at"] == schedule_before.isoformat()
    assert "遗忘" not in " ".join(item["reason"] for item in items)
    assert "无可靠周期" not in " ".join(item["title"] for item in items)

    # Reading recommendations is a pure projection: no new facts or schedule writes.
    assert db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id).count() == events_before
    db_session.refresh(due)
    assert due.review_due_at == schedule_before


def test_exam_11408_recommendation_uses_canonical_module_identity(client, db_session):
    register_and_login(client, "recommendation_exam")
    user = _user(db_session, "recommendation_exam")
    due = _knowledge(db_session, user.username, code="exam_due_node", title="数据结构知识点",
                     due_at=AS_OF - timedelta(days=2), course_id="data_structure_11408")
    result = review_recommendations.build_recommendations(
        db_session, user, service_namespace="exam_11408", as_of=AS_OF)
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["service_namespace"] == "exam_prep"
    assert item["direction"].startswith("11408 ·")
    assert item["title"] == "数据结构知识点"


def test_recommendation_order_and_identity_are_stable_for_the_same_as_of(client, db_session):
    register_and_login(client, "recommendation_stable")
    user = _user(db_session, "recommendation_stable")
    _own_course(db_session, user.username, COURSE)
    _knowledge(db_session, user.username, code="stable_due", title="稳定到期项",
               due_at=AS_OF - timedelta(days=1))
    _record(db_session, user, namespace="course_learning", qid=920, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=build_course_context(user, course_id=COURSE),
            when=AS_OF - timedelta(hours=1), source_id="stable-attempt")

    first = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)
    second = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)

    assert first == second
    assert first["items"] == sorted(first["items"], key=lambda item: item["sort_key"])


def test_snooze_filtering_counts_and_pages_all_bounded_candidates(client, db_session, monkeypatch):
    candidates = [{"recommendation_key": f"{index:064x}", "sort_key": [index]}
                  for index in range(405)]

    def fake_build(_db, _user, *, limit, offset, **_kwargs):
        page = candidates[offset:offset + limit]
        return {"items": page, "total": len(candidates), "limit": limit,
                "offset": offset, "generated_at": "2026-10-09T00:00:00",
                "policy_version": "test", "semantics": "test", "service_namespace": None}

    monkeypatch.setattr(review_recommendations, "build_recommendations", fake_build)
    monkeypatch.setattr(snoozes, "active_keys", lambda *_args, **_kwargs: set())
    register_and_login(client, "recommendation_visible_paging")
    user = _user(db_session, "recommendation_visible_paging")
    result = review_recommendations.visible_recommendations(
        db_session, user, limit=25, offset=380)
    assert result["total"] == 405
    assert [item["recommendation_key"] for item in result["items"]] == [
        f"{index:064x}" for index in range(380, 405)]


def test_empty_and_future_only_sources_produce_no_recommendations(client, db_session):
    register_and_login(client, "recommendation_empty")
    user = _user(db_session, "recommendation_empty")
    _own_course(db_session, user.username, COURSE)
    _knowledge(db_session, user.username, code="future_only", title="尚未到期",
               due_at=AS_OF + timedelta(days=2))

    result = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)

    assert result["items"] == []
    assert result["total"] == 0


def test_explicit_question_to_knowledge_mapping_merges_due_and_wrong_evidence(client, db_session):
    register_and_login(client, "recommendation_merged_identity")
    user = _user(db_session, "recommendation_merged_identity")
    _own_course(db_session, user.username, COURSE)
    point = _knowledge(db_session, user.username, code="mapped_point", title="映射知识点",
                       due_at=AS_OF - timedelta(days=1))
    context = build_course_context(user, course_id=COURSE,
                                   knowledge_point_id=str(point.knowledge_point_id))
    _record(db_session, user, namespace="course_learning", qid=944, correct=False,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(hours=1))
    result = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)
    assert len(result["items"]) == 1
    merged = result["items"][0]
    assert merged["kind"] == "knowledge"
    assert merged["reason_code"] == "scheduled_overdue"
    assert len(merged["evidence_sources"]) == 2


def test_real_course_correction_removes_the_active_wrong_recommendation(client, db_session):
    register_and_login(client, "recommendation_course_closed_loop")
    user = _user(db_session, "recommendation_course_closed_loop")
    _own_course(db_session, user.username, COURSE)
    context = build_course_context(user, course_id=COURSE)
    _record(db_session, user, namespace="course_learning", qid=945, correct=False,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(hours=2), source_id="course-wrong")
    pending = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)
    assert [item["reason_code"] for item in pending["items"]] == ["single_wrong"]

    _record(db_session, user, namespace="course_learning", qid=945, correct=True,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(hours=1), source_id="course-correction")
    refreshed = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)
    assert refreshed["items"] == []


def test_mapped_wrong_recommendation_opens_existing_wrong_answer_workflow(client, db_session):
    register_and_login(client, "recommendation_mapped_wrong_action")
    user = _user(db_session, "recommendation_mapped_wrong_action")
    _own_course(db_session, user.username, COURSE)
    point = _knowledge(db_session, user.username, code="wrong_mapping_point",
                       title="关联错题知识点", due_at=None)
    context = build_course_context(user, course_id=COURSE,
                                   knowledge_point_id=str(point.knowledge_point_id))
    _record(db_session, user, namespace="course_learning", qid=946, correct=False,
            source_type=QuestionSourceType.AI_GENERATED, context=context,
            when=AS_OF - timedelta(hours=1), source_id="mapped-wrong")
    item = review_recommendations.build_recommendations(
        db_session, user, as_of=AS_OF)["items"][0]
    assert item["kind"] == "knowledge"
    assert item["action"]["deep_link"] == f"/course/{COURSE}/wrong"


def test_programming_repeats_count_distinct_real_failed_submissions_once(client, db_session):
    register_and_login(client, "recommendation_programming_history")
    user = _user(db_session, "recommendation_programming_history")
    progress = _programming(db_session, user.username, exercise_id=8820,
                            status="needs_work", passed=False,
                            last_submit_at=AS_OF - timedelta(minutes=1))
    context = LearningContext(user_id=user.id,
                              service_namespace=ServiceNamespace.PROGRAMMING,
                              programming_language="Python", exercise_id=8820)
    session, _ = practice_service.ensure_legacy_session(
        db_session, user, ServiceNamespace.PROGRAMMING,
        source_type="programming_exercise", source_session_key="8820",
        mode="exercise", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
                      source_id="8820", service_namespace=ServiceNamespace.PROGRAMMING,
                      context={"exercise_id": 8820, "language": "Python"})
    for index, when in enumerate((AS_OF - timedelta(days=2), AS_OF - timedelta(days=1))):
        practice_service.record_attempt(
            db_session, user, session, ref, answer=None, correct=False,
            submitted_at=when, context=context,
            source=practice_service.SourceIdentity(
                "programming_exercise_progress", str(progress.id), when.isoformat()))

    result = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)
    recommendation = next(item for item in result["items"]
                          if item["kind"] == "programming_exercise")
    assert recommendation["reason_code"] == "programming_repeated_failure"
    assert recommendation["evidence"]["failed_attempt_count"] == 2

    # A later passing attempt closes this weakness evidence even if old failures remain.
    when = AS_OF - timedelta(hours=2)
    practice_service.record_attempt(
        db_session, user, session, ref, answer=None, correct=True,
        submitted_at=when, context=context,
        source=practice_service.SourceIdentity(
            "programming_exercise_progress", str(progress.id), when.isoformat()))
    refreshed = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)
    assert all(item["kind"] != "programming_exercise" for item in refreshed["items"])


def test_snooze_is_user_scoped_idempotent_and_expires_without_touching_learning_facts(client, db_session):
    snoozes.ReviewRecommendationSnooze.__table__.create(
        bind=db_session.get_bind(), checkfirst=True)
    register_and_login(client, "recommendation_snooze_owner")
    user = _user(db_session, "recommendation_snooze_owner")
    _own_course(db_session, user.username, COURSE)
    due = _knowledge(db_session, user.username, code="snooze_due", title="暂缓知识点",
                     due_at=AS_OF - timedelta(days=1))
    item = review_recommendations.build_recommendations(db_session, user, as_of=AS_OF)["items"][0]
    key = item["recommendation_key"]

    until = snoozes.snooze(db_session, user, key, until=AS_OF + timedelta(hours=24), as_of=AS_OF)
    assert until == AS_OF + timedelta(hours=24)
    assert snoozes.active_keys(db_session, user, as_of=AS_OF) == {key}
    assert snoozes.active_keys(db_session, user,
                               as_of=AS_OF + timedelta(hours=24)) == set()
    snoozes.snooze(db_session, user, key, until=AS_OF + timedelta(hours=48), as_of=AS_OF)
    assert len(db_session.query(snoozes.ReviewRecommendationSnooze).filter_by(
        user_id=user.id, recommendation_key=key).all()) == 1

    other = User(username="recommendation_snooze_other", hashed_password="test-only")
    db_session.add(other)
    db_session.commit()
    assert snoozes.active_keys(db_session, other, as_of=AS_OF) == set()
    assert review_recommendations.build_recommendations(
        db_session, other, as_of=AS_OF)["items"] == []
    assert snoozes.active_keys(db_session, user, as_of=AS_OF + timedelta(hours=49)) == set()
    db_session.refresh(due)
    assert due.review_due_at == AS_OF - timedelta(days=1)


def test_recommendation_http_projection_and_snooze_are_current_user_scoped(client, db_session):
    snoozes.ReviewRecommendationSnooze.__table__.create(
        bind=db_session.get_bind(), checkfirst=True)
    register_and_login(client, "recommendation_http_owner")
    user = _user(db_session, "recommendation_http_owner")
    _own_course(db_session, user.username, COURSE)
    due_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
    due = _knowledge(db_session, user.username, code="http_due", title="HTTP 到期知识点",
                     due_at=due_at)
    db_session.commit()
    events_before = db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id).count()

    response = client.get("/review/recommendations")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "HTTP 到期知识点"
    key = payload["items"][0]["recommendation_key"]
    assert db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id).count() == events_before

    snoozed = client.post(f"/review/recommendations/{key}/snooze")
    assert snoozed.status_code == 200, snoozed.text
    assert client.get("/review/recommendations").json()["total"] == 0
    db_session.refresh(due)
    assert due.review_due_at == due_at
    assert client.post("/review/recommendations/" + "0" * 64 + "/snooze").status_code == 404
