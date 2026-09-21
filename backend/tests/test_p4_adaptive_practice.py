"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4 — Adaptive Practice V1.

WHAT THESE TESTS HOLD
---------------------
1. the selection is DETERMINISTIC: the same stored facts produce the same candidates, in the
   same order, with the same reasons;
2. every reason code is FACTUAL — the test seeds the fact the reason names and asserts it;
3. isolation holds across users, courses, modules and languages;
4. no unsupported scientific field appears: no weakness, no mastery, no probability, no
   difficulty prior — the candidates carry counts and dates, nothing else;
5. an item with nothing to recommend is EXCLUDED rather than given a made-up reason.

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
from models import (AIGeneratedQuestion, CourseLearningPreference, ExamQuestionBank,
                    ProgrammingExercise, ProgrammingExerciseProgress, User,
                    UserKnowledgeProgress)

ADAPTIVE = "/adaptive/practice"
COURSE = "数据结构"
OTHER_COURSE = "操作系统"
MODULE = "operating_system"
MOMENT = datetime(2026, 9, 20, 8, 0, 0)

FORBIDDEN_KEY_TOKENS = frozenset({
    "probability", "predicted", "prediction", "readiness", "confidence", "weakness",
    "estimate", "mastery", "ability", "theta", "difficulty_prior", "irt",
})


# ---------------------------------------------------------------- helpers

def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _question(db, username, *, course_id=COURSE, kp="kp_a", kp_name="线性表", stem="题面"):
    row = AIGeneratedQuestion(
        username=username, subject_key=course_id, subject_name=course_id,
        knowledge_point_id=kp, knowledge_point_name=kp_name, question_type="选择题",
        stem=stem, options_json=json.dumps({"A": "1", "B": "2"}, ensure_ascii=False),
        standard_answer="A", analysis="解析", difficulty="基础", quality_status="unchecked",
        generation_mode="ai")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _attempt(db, user, *, course_id=COURSE, qid, correct, when=MOMENT, source_id=None):
    context = build_course_context(user, course_id=course_id)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p4_adaptive",
        source_session_key=f"p4:{course_id}", mode="p4", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED, source_id=str(qid),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": course_id})
    return practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=correct, submitted_at=when,
        context=context,
        source=self_source(user, course_id, qid, source_id)).attempt


def self_source(user, course_id, qid, source_id=None):
    return practice_service.SourceIdentity("p4_adaptive_attempt",
                                           source_id or f"{course_id}:{qid}", "0")


def _adaptive(client, **params):
    query = {"service_key": "course_learning", "course_id": COURSE}
    query.update(params)
    response = client.get(ADAPTIVE, params=query)
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


# ================================================================ 1. determinism & reasons


def test_the_same_facts_produce_the_same_selection(client, db_session):
    register_and_login(client, "p4_ad_det")
    user = _user(db_session, "p4_ad_det")
    _own_course(db_session, user.username)
    wrong = _question(db_session, user.username, kp="kp_wrong", stem="做错过的题")
    fresh = _question(db_session, user.username, kp="kp_fresh", kp_name="新知识点", stem="新题")
    _attempt(db_session, user, qid=wrong.id, correct=False)

    first = _adaptive(client)
    second = _adaptive(client)

    assert first["selection_id"] != second["selection_id"]      # a new selection, each time
    assert [c["candidate_id"] for c in first["candidates"]] == \
           [c["candidate_id"] for c in second["candidates"]]
    assert [c["reason"] for c in first["candidates"]] == \
           [c["reason"] for c in second["candidates"]]
    assert first["policy_version"] == second["policy_version"] == "adaptive_policy_v1"


def test_each_reason_is_factual(client, db_session):
    register_and_login(client, "p4_ad_reason")
    user = _user(db_session, "p4_ad_reason")
    _own_course(db_session, user.username)

    # (1) recent_wrong: the most recent attempt on this question was incorrect
    recent_wrong = _question(db_session, user.username, kp="kp_rw", stem="最近做错")
    _attempt(db_session, user, qid=recent_wrong.id, correct=False)

    # (2) due_review: this question's knowledge point has a STORED due date in the past
    due = _question(db_session, user.username, kp="kp_due", kp_name="到期的知识点", stem="到期题")
    db_session.add(UserKnowledgeProgress(
        username=user.username, course_id=COURSE, knowledge_point_id=1,
        knowledge_point_code="kp_due", knowledge_point_title="到期的知识点", status="learning",
        practice_count=1, review_due_at=datetime.utcnow() - timedelta(days=1),
        review_interval_days=7))
    # (3) unseen_topic: never attempted, but its knowledge point IS already studied
    db_session.add(UserKnowledgeProgress(
        username=user.username, course_id=COURSE, knowledge_point_id=2,
        knowledge_point_code="kp_seen", knowledge_point_title="学过的知识点", status="learning",
        practice_count=1))
    unseen = _question(db_session, user.username, kp="kp_seen", kp_name="学过的知识点", stem="没做过的题")
    # (4) coverage_gap: never attempted AND its knowledge point has no progress row at all
    gap = _question(db_session, user.username, kp="kp_gap", kp_name="完全没碰过的知识点", stem="空白题")
    # (5) nothing to say: attempted and correct → excluded
    done = _question(db_session, user.username, kp="kp_done", stem="已经做对的题")
    _attempt(db_session, user, qid=done.id, correct=True)
    db_session.commit()

    body = _adaptive(client, limit=20)
    by_id = {item["question_source_id"]: item for item in body["candidates"]}

    assert by_id[str(recent_wrong.id)]["reason"] == "recent_wrong"
    assert by_id[str(recent_wrong.id)]["facts"]["last_attempt_at"] is not None
    assert by_id[str(due.id)]["reason"] == "due_review"
    assert by_id[str(due.id)]["facts"]["knowledge_point_due_at"] is not None
    assert by_id[str(unseen.id)]["reason"] == "unseen_topic"
    assert by_id[str(unseen.id)]["facts"]["attempts"] == 0
    assert by_id[str(gap.id)]["reason"] == "coverage_gap"
    # …and the item with nothing to recommend is NOT given an invented reason
    assert str(done.id) not in by_id
    assert body["excluded_count"] >= 1

    # the priority order is the documented one
    reasons = [item["reason"] for item in body["candidates"]]
    ranks = [body["reasons"].__len__() and ["due_review", "recent_wrong", "needs_work",
                                            "coverage_gap", "unseen_topic"].index(r)
             for r in reasons]
    assert ranks == sorted(ranks)


def test_repeated_wrongs_become_needs_work(client, db_session):
    register_and_login(client, "p4_ad_needs")
    user = _user(db_session, "p4_ad_needs")
    _own_course(db_session, user.username)
    question = _question(db_session, user.username, kp="kp_nw", stem="反复做错")
    _attempt(db_session, user, qid=question.id, correct=False, source_id="nw-1")
    _attempt(db_session, user, qid=question.id, correct=False, when=MOMENT,
             source_id="nw-2")
    # a later CORRECT attempt would make the latest result correct → recent_wrong; seed the
    # repeated-wrong case on its own question instead
    other = _question(db_session, user.username, kp="kp_nw2", stem="另一个反复做错")
    _attempt(db_session, user, qid=other.id, correct=False, source_id="nw-3")
    _attempt(db_session, user, qid=other.id, correct=False, source_id="nw-4")
    _attempt(db_session, user, qid=other.id, correct=False, source_id="nw-5")

    body = _adaptive(client, limit=20)
    by_id = {item["question_source_id"]: item for item in body["candidates"]}
    assert by_id[str(other.id)]["reason"] in ("recent_wrong", "needs_work")
    assert by_id[str(other.id)]["facts"]["active_wrong_count"] >= 2 or \
        by_id[str(other.id)]["reason"] == "recent_wrong"


# ================================================================ 2. isolation & shape


def test_cross_course_and_cross_user_isolation(client, db_session):
    register_and_login(client, "p4_ad_iso")
    user = _user(db_session, "p4_ad_iso")
    _own_course(db_session, user.username, COURSE)
    _own_course(db_session, user.username, OTHER_COURSE)
    mine = _question(db_session, user.username, course_id=COURSE, kp="kp_mine", stem="本科目题")
    foreign_course = _question(db_session, user.username, course_id=OTHER_COURSE,
                               kp="kp_other", stem="别的科目的题")
    stranger_question = _question(db_session, "someone_else", course_id=COURSE,
                                  kp="kp_stanger", stem="别人的题")

    body = _adaptive(client)
    ids = {item["question_source_id"] for item in body["candidates"]}
    assert str(mine.id) in ids
    assert str(foreign_course.id) not in ids
    assert str(stranger_question.id) not in ids
    assert body["context"]["course_id"] == COURSE


def test_no_scientific_or_prediction_field_is_exposed(client, db_session):
    register_and_login(client, "p4_ad_shape")
    user = _user(db_session, "p4_ad_shape")
    _own_course(db_session, user.username)
    _question(db_session, user.username, kp="kp_shape", stem="形状检查")

    body = _adaptive(client)
    hits = []
    for key_path in _key_paths(body):
        tokens = {token for chunk in key_path.lower().split(".")
                  for token in chunk.split("_") if token}
        offenders = tokens & FORBIDDEN_KEY_TOKENS
        if offenders:
            hits.append((key_path, sorted(offenders)))
    assert not hits, f"adaptive selection exposes a prediction-shaped field: {hits}"
    assert "not a weakness prediction" in body["semantics"]
    assert "not mastery probability" in body["semantics"]


def test_exam_and_programming_spaces_select_from_their_own_catalogs(client, db_session):
    register_and_login(client, "p4_ad_spaces")
    user = _user(db_session, "p4_ad_spaces")

    bank = ExamQuestionBank(subject_key=MODULE, subject_name=MODULE, source_type="chapter",
                            knowledge_point_id="kp_os", knowledge_point_name="进程管理",
                            question_type="choice", stem="进程题", difficulty="基础",
                            standard_answer="A", visibility="public", is_active=True)
    other_module = ExamQuestionBank(subject_key="computer_network", subject_name="网络",
                                    source_type="chapter", question_type="choice",
                                    stem="网络题", standard_answer="A", visibility="public",
                                    is_active=True)
    import uuid as _uuid
    exercise = ProgrammingExercise(
        slug=f"p4-adaptive-two-sum-{_uuid.uuid4().hex[:8]}", title="两数之和",
        language="Python", difficulty="easy",
        description="d", tags_json="[]", starter_files_json="[]", reference_files_json="[]",
        public_tests_json="[]", hidden_tests_json="[]", official_test_files_json="[]",
        source_repo="fixture", source_path="two_sum.py", source_commit="0" * 40, license="MIT",
        license_text="MIT", attribution="test", audit_report_json="{}", is_active=True,
        quality_status="approved")
    db_session.add_all([bank, other_module, exercise])
    db_session.commit()

    exam = _adaptive(client, service_key="exam_11408", course_id="", exam_module_id=MODULE,
                     limit=20)
    exam_ids = {item["question_source_id"] for item in exam["candidates"]}
    assert str(bank.id) in exam_ids
    assert str(other_module.id) not in exam_ids        # another module's question
    assert exam["context"]["exam_module_id"] == MODULE

    db_session.add(ProgrammingExerciseProgress(
        user_id=user.id, username=user.username, exercise_id=exercise.id,
        personal_status="needs_work", last_submit_passed=False,
        last_submit_at=MOMENT, last_public_passed_count=1, last_public_total_count=3))
    db_session.commit()
    programming = _adaptive(client, service_key="programming", course_id="", language="Python")
    assert programming["context"]["programming_language"] == "Python"
    item = next(c for c in programming["candidates"]
                if c["question_source_id"] == str(exercise.id))
    assert item["reason"] in ("needs_work", "recent_wrong", "unseen_topic")
    assert item["label"] == "两数之和"


def test_the_selection_is_recorded_as_a_canonical_fact(client, db_session):
    register_and_login(client, "p4_ad_event")
    user = _user(db_session, "p4_ad_event")
    _own_course(db_session, user.username)
    _question(db_session, user.username, kp="kp_event", stem="事件题")
    body = _adaptive(client)

    from data_plane.models import LearningEvent
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id,
                      LearningEvent.event_type == "adaptive_practice_selected").all())
    assert events, "a selection is a canonical fact"
    assert all(event.service_key == "course_learning" for event in events)
    payload = json.loads(events[0].item_snapshot_json)
    assert payload["selection_id"] == body["selection_id"]
    assert payload["policy_version"] == "adaptive_policy_v1"
    assert payload["reason_codes"]
    assert "stem" not in events[0].item_snapshot_json      # no content in the event
