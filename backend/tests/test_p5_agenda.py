"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5 — Daily Learning Orchestrator.

WHAT THESE TESTS HOLD
---------------------
1. the agenda is DETERMINISTIC: the same stored facts produce the same items in the same order;
2. every item's priority reason is FACTUAL — the fact it names is seeded and asserted;
3. the three learning spaces coexist in one agenda, and each item carries the domain of ITS OWN
   row: a filter can only NARROW, and no item is ever attributed to another space's context;
4. the agenda holds NO state: completing the real action (a review, a plan task) removes or
   demotes the item on the next read, with no second "completed" flag anywhere;
5. the same question reached from two sources appears ONCE;
6. no prediction-shaped field is exposed.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import json
from datetime import datetime, timedelta

from conftest import register_and_login

from core.learning_context import LearningContext, ServiceNamespace
from learning.agenda import (
    AGENDA_POLICY_VERSION,
    REASON_CURRENT_PLAN_TASK,
    REASON_DUE_REVIEW,
    REASON_NEEDS_WORK,
    REASON_OVERDUE_PLAN_TASK,
    REASON_REPEATED_WRONG,
)
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import producers
from learning.spaces.course_learning.context import build_course_context
from models import (AIGeneratedQuestion, CourseLearningPreference, ExamStudyPlanTask,
                    ProgrammingExercise, ProgrammingExerciseProgress, User,
                    UserKnowledgeProgress)

AGENDA = "/learning/agenda"
COURSE = "数据结构"
MODULE = "operating_system"
MOMENT = datetime(2026, 9, 20, 9, 30, 0)

FORBIDDEN_KEY_TOKENS = frozenset({
    "probability", "predicted", "prediction", "readiness", "confidence", "weakness",
    "mastery", "ability", "theta", "difficulty_prior",
})


# ---------------------------------------------------------------- helpers

def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _plan_task(db, username, *, subject_key, title, due_date, status="not_started"):
    row = ExamStudyPlanTask(username=username, subject_key=subject_key, title=title,
                            task_type="knowledge", status=status, due_date=due_date)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _course_key(course_id=COURSE) -> str:
    import main
    return main._course_learning_task_subject_key(course_id)


def _question(db, username, *, stem="错题"):
    row = AIGeneratedQuestion(
        username=username, subject_key=COURSE, subject_name=COURSE,
        knowledge_point_id="kp_agenda", knowledge_point_name="议程知识点",
        question_type="选择题", stem=stem, standard_answer="A", analysis="解析",
        quality_status="unchecked", generation_mode="ai")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _wrong_state(db, user):
    question = _question(db, user.username)
    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p5_agenda",
        source_session_key="p5:agenda", mode="p5", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p5_agenda_attempt", f"q{question.id}", "0"))
    from learning.wrong_answers import service as wrong_service
    return wrong_service.list_states(db, user.id, service_namespace="course_learning")[0]


def _due_review_item(db, user, state) -> str:
    """Make the wrong-answer item genuinely DUE by recording a real, past schedule."""
    item_id = f"wrong:course_learning:{state.id}"
    past = (datetime.utcnow() - timedelta(days=2)).isoformat()
    producers.emit_review_scheduled(
        user_id=user.id, item_id=item_id, due_at=past,
        policy_version="review_policy_v1", service_namespace="course_learning",
        interval_days=3, reason="first_schedule",
        scheduled_at=(datetime.utcnow() - timedelta(days=5)).isoformat(),
        facts={"last_review_result": None}, occurred_at=None,
        source_user_ref=user.username)
    return item_id


def _due_knowledge(db, user):
    row = UserKnowledgeProgress(
        username=user.username, course_id=COURSE, knowledge_point_id=8801,
        knowledge_point_code="kp_agenda", knowledge_point_title="议程知识点", status="learning",
        practice_count=1, review_interval_days=7,
        review_due_at=datetime.utcnow() - timedelta(days=1))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _exercise_needing_work(db, user):
    import uuid
    exercise = ProgrammingExercise(
        slug=f"p5-agenda-exercise-{uuid.uuid4().hex[:8]}", title="议程练习", language="Python",
        difficulty="easy",
        description="d", tags_json="[]", starter_files_json="[]", reference_files_json="[]",
        public_tests_json="[]", hidden_tests_json="[]", official_test_files_json="[]",
        source_repo="fixture", source_path="solution.py", source_commit="0" * 40, license="MIT",
        license_text="MIT", attribution="test", audit_report_json="{}", is_active=True,
        quality_status="approved")
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    db.add(ProgrammingExerciseProgress(
        user_id=user.id, username=user.username, exercise_id=exercise.id,
        personal_status="needs_work", last_submit_passed=False, last_submit_at=MOMENT,
        last_public_passed_count=1, last_public_total_count=3))
    db.commit()
    return exercise


def _agenda(client, **params):
    response = client.get(AGENDA, params=params)
    assert response.status_code == 200, response.text
    return response.json()


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


# ================================================================ 1. determinism & priority


def test_the_agenda_is_deterministic_and_policy_versioned(client, db_session):
    register_and_login(client, "p5_ag_det")
    user = _user(db_session, "p5_ag_det")
    _own_course(db_session, user.username)
    _plan_task(db_session, user.username, subject_key=_course_key(), title="逾期任务",
               due_date=(datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d"))
    _due_knowledge(db_session, user)
    state = _wrong_state(db_session, user)
    _due_review_item(db_session, user, state)

    first = _agenda(client)
    second = _agenda(client)
    assert first["policy_version"] == AGENDA_POLICY_VERSION
    assert [item["source_id"] + item["priority_reason"] for item in first["items"]] == \
           [item["source_id"] + item["priority_reason"] for item in second["items"]]
    assert first["priority_order"][0] == REASON_OVERDUE_PLAN_TASK


def test_the_priority_ladder_is_factual(client, db_session):
    register_and_login(client, "p5_ag_ladder")
    user = _user(db_session, "p5_ag_ladder")
    _own_course(db_session, user.username)
    overdue = _plan_task(db_session, user.username, subject_key=_course_key(),
                         title="逾期任务",
                         due_date=(datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d"))
    current = _plan_task(db_session, user.username, subject_key=_course_key(),
                         title="当前任务",
                         due_date=(datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d"))
    knowledge = _due_knowledge(db_session, user)
    exercise = _exercise_needing_work(db_session, user)

    body = _agenda(client, limit=30)
    by_source = {(item["source_type"], item["source_id"]): item for item in body["items"]}

    overdue_item = by_source[("plan_task", str(overdue.id))]
    assert overdue_item["priority_reason"] == REASON_OVERDUE_PLAN_TASK
    assert overdue_item["facts"]["overdue"] is True
    assert overdue_item["resolved_by"] == "plan_task_completion"

    current_item = by_source[("plan_task", str(current.id))]
    assert current_item["priority_reason"] == REASON_CURRENT_PLAN_TASK
    assert current_item["facts"]["overdue"] is False

    knowledge_item = by_source[("knowledge_review", str(knowledge.id))]
    assert knowledge_item["priority_reason"] == REASON_DUE_REVIEW
    assert knowledge_item["due_at"] is not None
    assert knowledge_item["facts"]["review_status"] == "due"
    assert knowledge_item["resolved_by"] == "review_completion"

    exercise_item = by_source[("programming_exercise", str(exercise.id))]
    assert exercise_item["priority_reason"] == REASON_NEEDS_WORK
    assert exercise_item["action_type"] == "programming"

    # the ORDER follows the ladder: overdue → due review → needs_work → current plan task
    reasons = [item["priority_reason"] for item in body["items"]]
    ladder = [REASON_OVERDUE_PLAN_TASK, REASON_DUE_REVIEW, REASON_NEEDS_WORK,
              REASON_CURRENT_PLAN_TASK]
    ranks = [ladder.index(reason) for reason in reasons if reason in ladder]
    assert ranks == sorted(ranks), reasons


def test_repeated_wrongs_rank_above_single_wrongs(client, db_session):
    register_and_login(client, "p5_ag_repeat")
    user = _user(db_session, "p5_ag_repeat")
    _own_course(db_session, user.username)
    state = _wrong_state(db_session, user)
    _due_review_item(db_session, user, state)
    # a second factual failure on the same question → repeated
    question_id = state.question_source_id
    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db_session, user, "course_learning", source_type="p5_agenda2",
        source_session_key="p5:agenda2", mode="p5", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question_id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db_session, user, session, ref, answer="B", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p5_agenda_attempt2", "repeat-2", "0"))

    body = _agenda(client)
    review_items = [item for item in body["items"]
                    if item["source_type"] == "wrong_answer"]
    assert review_items
    assert review_items[0]["priority_reason"] == REASON_REPEATED_WRONG
    assert review_items[0]["facts"]["wrong_count"] >= 2


# ================================================================ 2. three domains, isolated


def test_the_three_spaces_coexist_and_stay_isolated(client, db_session):
    register_and_login(client, "p5_ag_domains")
    user = _user(db_session, "p5_ag_domains")
    _own_course(db_session, user.username)
    _plan_task(db_session, user.username, subject_key=_course_key(), title="课程任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    _plan_task(db_session, user.username, subject_key=MODULE, title="考试任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    _plan_task(db_session, user.username, subject_key="programming:Python",
               title="编程任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    _exercise_needing_work(db_session, user)

    everything = _agenda(client, limit=30)
    namespaces = {item["service_namespace"] for item in everything["items"]}
    assert {"course_learning", "exam_prep", "programming"} <= namespaces

    # every item's DOMAIN comes from its own row
    for item in everything["items"]:
        if item["source_type"] == "plan_task":
            if item["service_namespace"] == "course_learning":
                assert item["domain_context"]["course_id"] == COURSE
                assert item["deep_link"].startswith(f"/course/{COURSE}/")
            elif item["service_namespace"] == "exam_prep":
                assert item["domain_context"]["exam_module_id"] == MODULE
                assert item["deep_link"].startswith("/exam/cs408/")
            else:
                assert item["domain_context"]["language"] == "Python"
                assert item["deep_link"].startswith("/programming/Python/")

    # a filter can only NARROW — never re-attribute
    for service_key, expected in (("course_learning", "course_learning"),
                                  ("exam_11408", "exam_prep"),
                                  ("programming", "programming")):
        filtered = _agenda(client, service_key=service_key, limit=30)
        assert filtered["items"], service_key
        assert {item["service_namespace"] for item in filtered["items"]} == {expected}

    # a programming needs_work item never appears under a course filter
    course_only = _agenda(client, service_key="course_learning",
                          course_id=COURSE, limit=30)
    assert all(item["service_namespace"] == "course_learning"
               for item in course_only["items"])
    assert all(item["action_type"] != "programming" for item in course_only["items"])


def test_a_learner_only_ever_sees_their_own_agenda(client, db_session):
    register_and_login(client, "p5_ag_owner")
    owner = _user(db_session, "p5_ag_owner")
    _own_course(db_session, owner.username)
    _plan_task(db_session, owner.username, subject_key=_course_key(), title="主人的任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    assert _agenda(client)["items"], "the owner has work to do"

    register_and_login(client, "p5_ag_other")
    other = _agenda(client)
    assert other["items"] == []
    assert other["total_items"] == 0


# ================================================================ 3. projection, not state


def test_completing_the_real_action_changes_the_next_read(client, db_session):
    register_and_login(client, "p5_ag_complete")
    user = _user(db_session, "p5_ag_complete")
    _own_course(db_session, user.username)
    task = _plan_task(db_session, user.username, subject_key=_course_key(), title="待办任务",
                      due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    state = _wrong_state(db_session, user)
    item_id = _due_review_item(db_session, user, state)

    before = _agenda(client, limit=30)
    before_keys = {(item["source_type"], item["source_id"]) for item in before["items"]}
    assert ("plan_task", str(task.id)) in before_keys
    assert ("wrong_answer", str(state.id)) in before_keys

    # the REAL actions happen on their own surfaces
    db_session.expire_all()
    row = db_session.query(ExamStudyPlanTask).filter(
        ExamStudyPlanTask.id == task.id).one()
    row.status = "completed"
    db_session.commit()
    completed = client.post(f"/review/{item_id}/complete", json={"result": "correct"})
    assert completed.status_code == 200, completed.text

    after = _agenda(client, limit=30)
    after_keys = {(item["source_type"], item["source_id"]) for item in after["items"]}
    # the completed plan task is GONE (its own fact changed) …
    assert ("plan_task", str(task.id)) not in after_keys
    # … and the review item is no longer DUE (its schedule moved into the future)
    assert ("wrong_answer", str(state.id)) not in after_keys

    # the agenda keeps no state of its own: the same computation gives the same answer
    assert _agenda(client, limit=30)["total_items"] == after["total_items"]


def test_one_question_is_never_listed_twice(client, db_session):
    register_and_login(client, "p5_ag_dedupe")
    user = _user(db_session, "p5_ag_dedupe")
    _own_course(db_session, user.username)
    state = _wrong_state(db_session, user)          # the question is now a wrong answer …
    _due_review_item(db_session, user, state)

    body = _agenda(client, service_key="course_learning", course_id=COURSE, limit=30)
    question_keys = [
        (item.get("question_identity") or {}).get("question_source_id")
        for item in body["items"] if item.get("question_identity")]
    question_keys = [key for key in question_keys if key]
    assert len(question_keys) == len(set(question_keys)), question_keys
    assert question_keys, "the wrong answer's question is on the agenda"
    assert body["source_summary"]["deduplicated"] >= 1


def test_no_prediction_shaped_field_is_exposed(client, db_session):
    register_and_login(client, "p5_ag_shape")
    user = _user(db_session, "p5_ag_shape")
    _own_course(db_session, user.username)
    _plan_task(db_session, user.username, subject_key=_course_key(), title="形状任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
    _due_knowledge(db_session, user)

    body = _agenda(client, limit=30)
    hits = []
    for key_path in _key_paths(body):
        tokens = {token for chunk in key_path.lower().split(".")
                  for token in chunk.split("_") if token}
        offenders = tokens & FORBIDDEN_KEY_TOKENS
        if offenders:
            hits.append((key_path, sorted(offenders)))
    assert not hits, f"agenda exposes a prediction-shaped field: {hits}"
    assert "no predicted weakness" in body["semantics"]


def test_the_explain_endpoint_answers_why(client, db_session):
    register_and_login(client, "p5_ag_explain")
    user = _user(db_session, "p5_ag_explain")
    _own_course(db_session, user.username)
    _plan_task(db_session, user.username, subject_key=_course_key(), title="解释任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))

    response = client.get(f"{AGENDA}/explain")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["policy_version"] == AGENDA_POLICY_VERSION
    assert body["priority_order"][0] == REASON_OVERDUE_PLAN_TASK
    assert body["priority_rules"][REASON_DUE_REVIEW]
    assert body["completion_paths"][REASON_OVERDUE_PLAN_TASK] == "plan_task_completion"
    assert "No model decides the order" in body["explanation_of_order"]
    assert body["why_the_next_read_changes"]
    assert body["agenda"]["items"], "the explanation carries the same agenda"
    assert body["agenda"]["items"][0]["facts"], "and the facts behind each item"


def test_the_agenda_writes_nothing(client, db_session):
    """A read is a read: no event, no row, no second state."""
    register_and_login(client, "p5_ag_readonly")
    user = _user(db_session, "p5_ag_readonly")
    _own_course(db_session, user.username)
    _plan_task(db_session, user.username, subject_key=_course_key(), title="只读任务",
               due_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))

    from data_plane.models import LearningEvent
    db_session.expire_all()
    before = db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id).count()
    _agenda(client)
    _agenda(client, limit=5)
    client.get(f"{AGENDA}/explain")
    db_session.expire_all()
    after = db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id).count()
    assert after == before, "an agenda read must not add a fact"
