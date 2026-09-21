"""THREE_DOMAIN_PRODUCTIZATION_P1_2 — course wrong-answer source identity + isolation.

WHAT THESE TESTS HOLD
---------------------
A course AI question lives in ``ai_generated_questions``. Until P1.2 the practice mirror
declared it as ``material_generated`` — the static ``questions`` table — so:

  * a real question resolved to no row at all (empty stem and reference answer), and
  * where the two tables' ids overlapped, the id resolved to ANOTHER ROW in a table the
    question was never in (another learner's question, or another course's).

Both are closed here, and the properties that keep them closed are asserted rather than
assumed:

1. a new course AI attempt is mirrored with its TRUE source identity
   (``AI_generated`` / ``ai_generated_questions``);
2. the wrong-answer record resolves the stem, the reference answer and the question
   identity from the table that owns the id — and only when the row is provably this
   learner's question in THIS course;
3. the same numeric id in ``questions`` and ``ai_generated_questions`` cannot collide:
   each declared source reads its own table and is never tested against the other;
4. a state whose id points at another learner's question resolves NOTHING;
5. a state whose id points at another course's question resolves NOTHING;
6. a wrong / unmapped declared source type resolves NOTHING;
7. a legacy ``material_generated`` course row (the pre-P1.2 declaration) resolves as the AI
   question it provably is, and an AMBIGUOUS one (mixed, unknown or absent lineage) resolves
   nothing rather than being tested against both tables;
8. the whole loop holds end to end: submit a wrong answer → wrong state → wrong detail,
   with the returned question id usable by the course redo contract.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported. Nothing here can reach ``backend/app.db``.
"""
import json
from datetime import datetime, timedelta

from conftest import register_and_login

from core.learning_context import ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.course_learning.context import build_course_context
from models import AIGeneratedQuestion, AIQuestionAttempt, CourseLearningPreference, Question, User

COURSE = ServiceNamespace.COURSE_LEARNING.value
DATA_STRUCTURE = "数据结构"
OPERATING_SYSTEM = "操作系统"
MOMENT = datetime(2026, 9, 20, 5, 0, 0)

COURSE_WRONG = "/course-learning/courses/{course}/wrong-answers"
COURSE_WRONG_DETAIL = "/course-learning/courses/{course}/wrong-answers/{record}"
COURSE_NEW_ATTEMPT = "/course-learning/courses/{course}/practice/questions/{question}/attempts"
COURSE_SUBMIT = "/course-learning/courses/{course}/practice/{attempt}/submit"

AI_LINEAGE = "ai_question_attempt"        # learning.practice.adapters.course.SOURCE_ATTEMPT_TYPE
QUESTION_LINEAGE = "question_attempt"     # the ordinary course practice flow over `questions`

# High, collision-free ids: the two tables have INDEPENDENT id spaces, and these tests need
# to place the same number in both of them deliberately.
COLLIDE_ID = 990101
STRANGER_ID = 990201


# ---------------------------------------------------------------- helpers

def _user(db, username) -> User:
    user = db.query(User).filter(User.username == username).one()
    return user


def _register(db, client, username) -> User:
    profile = register_and_login(client, username)
    return db.query(User).filter(User.id == profile["id"]).one()


def _own_course(db, username, course_id):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _onboard(client, username, courses):
    """The REAL course onboarding: it writes the preference rows the course routes require."""
    register_and_login(client, username)
    response = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": list(courses), "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text


def _seed_ai_question(db, username, course_key, *, stem, answer="A", qid=None):
    """A persisted course workbook question, in the shape the generator writes."""
    question = AIGeneratedQuestion(
        id=qid, username=username, subject_key=course_key, subject_name=course_key,
        knowledge_point_id="kp_list", knowledge_point_name="线性表",
        knowledge_point_path="线性结构", question_type="选择题", stem=stem,
        options_json=json.dumps({"A": "随机访问", "B": "顺序访问", "C": "无法访问",
                                 "D": "只读访问"}, ensure_ascii=False),
        standard_answer=answer, analysis=f"{stem} 的解析",
        difficulty="基础", requirement="课程章节练习", generation_mode="ai",
        quality_status="unchecked")
    db.add(question)
    db.commit()
    return question


def _record(db, user, *, course_id, qid, source_type, lineage, correct=False,
            source_id=None, answer="A", when=MOMENT):
    """Record ONE canonical course attempt with a CHOSEN provenance.

    The lineage is stated explicitly because it is what the resolver reads to prove which id
    space a stored ``material_generated`` row belongs to; a real adapter always writes it.
    """
    context = build_course_context(user, course_id=course_id)
    session, _ = practice_service.ensure_legacy_session(
        db, user, COURSE, source_type=lineage or "p12_unstated",
        source_session_key=f"p12:{course_id}", mode="p12", context=context, started_at=None)
    ref = QuestionRef(source_type=source_type, source_id=str(qid),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": course_id})
    source = (practice_service.SourceIdentity(
        lineage, source_id or f"{course_id}:{qid}:{lineage}", f"{qid}:0")
        if lineage else None)
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=correct, submitted_at=when,
        source=source, context=context).attempt


def _listed(client, course) -> list[dict]:
    response = client.get(COURSE_WRONG.format(course=course))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _only_record(client, course, *, wrong_record_id=None) -> dict:
    items = _listed(client, course)
    if wrong_record_id is not None:
        assert [item["wrong_record_id"] for item in items] == [wrong_record_id]
    assert len(items) == 1, items
    return items[0]


# ================================================================ 1. the emitted identity


def test_a_new_course_ai_attempt_is_mirrored_as_ai_generated(client, db_session):
    """The declared source states the table the question id really is in."""
    _onboard(client, "p12_identity", [DATA_STRUCTURE])
    question = _seed_ai_question(db_session, "p12_identity", DATA_STRUCTURE, stem="身份题")

    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    assert started.status_code == 200, started.text
    attempt_id = started.json()["attempt_id"]
    submitted = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                            json={"answer": "B"})
    assert submitted.status_code == 200, submitted.text

    from learning.practice.models import PracticeAttempt
    mirrored = (db_session.query(PracticeAttempt)
                .filter(PracticeAttempt.source_attempt_type == AI_LINEAGE,
                        PracticeAttempt.source_attempt_id == str(attempt_id)).all())
    assert len(mirrored) == 1
    assert mirrored[0].question_source_type == "AI_generated"
    assert mirrored[0].service_namespace == "course_learning"
    ref = json.loads(mirrored[0].question_ref_json)
    # the raw provenance is preserved verbatim AND names the real table
    assert ref["raw_source"]["table"] == "ai_generated_questions"
    assert ref["raw_source"]["mode"] == "course_learning"
    assert ref["context"]["course_id"] == DATA_STRUCTURE

    record = _only_record(client, DATA_STRUCTURE)
    assert record["source_kind"] == "ai_generated"


def test_the_exam_mode_keeps_its_ai_generated_identity(db_session):
    """The 11408 row was already right; the course correction must not disturb it."""
    from learning.practice.adapters import course as course_adapter

    user = User(username="p12_exam_mode", hashed_password="x", grade="freshman", major="cs")
    db_session.add(user)
    db_session.commit()
    row = AIQuestionAttempt(
        username=user.username, mode="11408", subject_key="ds", subject_name="数据结构",
        question_ids_json=json.dumps([11]), status="submitted", total_questions=1,
        submitted_at=MOMENT, answers_json=json.dumps({"11": "A"}),
        result_json=json.dumps({"results": [
            {"question_id": 11, "correct": True, "user_answer": "A",
             "question_type": "选择题"}]}))
    db_session.add(row)
    db_session.commit()

    course_adapter.mirror_ai_question_attempt(db_session, user, row)
    attempt = practice_service.list_attempts(db_session, user.id,
                                             service_namespace="exam_prep")[0]
    assert attempt.question_source_type == "AI_generated"
    ref = json.loads(attempt.question_ref_json)
    assert ref["raw_source"]["table"] == "ai_generated_questions"


def test_an_unknown_attempt_mode_records_no_provenance():
    """A row whose mode names no known space states no identity — and none is invented.

    The behavioural half of this lives in ``test_practice_adapters``; what is asserted here
    is the mapping itself: BOTH known modes state the AI table, and neither states the static
    ``questions`` table.
    """
    from learning.practice.adapters import course as course_adapter

    assert "some_future_mode" not in course_adapter._MODE_MAP
    assert course_adapter._MODE_MAP["course_learning"][1] == "ai_generated_questions"
    assert course_adapter._MODE_MAP["11408"][1] == "ai_generated_questions"


# ================================================================ 2. content resolution


def test_the_wrong_answer_record_resolves_stem_answer_and_question_identity(client, db_session):
    """A real submission resolves its own question: stem, reference answer, redo id."""
    _onboard(client, "p12_resolve", [DATA_STRUCTURE])
    question = _seed_ai_question(db_session, "p12_resolve", DATA_STRUCTURE,
                                 stem="顺序表的插入平均复杂度是多少？", answer="C")

    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    attempt_id = started.json()["attempt_id"]
    client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                json={"answer": "B"})

    record = _only_record(client, DATA_STRUCTURE)
    assert record["stem"] == question.stem
    assert record["reference_answer"] == "C"
    assert record["user_answer"] == "B"
    assert record["question_id"] == question.id
    assert record["status"] == "active"
    assert record["repeat_wrong_count"] == 1
    assert record["knowledge_point_name"] == "线性表"
    assert record["options"]["A"] == "随机访问"

    detail = client.get(COURSE_WRONG_DETAIL.format(
        course=DATA_STRUCTURE, record=record["wrong_record_id"])).json()
    assert detail["stem"] == question.stem
    assert detail["reference_answer"] == "C"
    assert detail["attempt_history"][0]["answer"] == "B"
    assert detail["attempt_history"][0]["correct"] is False


def test_the_same_id_in_both_question_tables_cannot_collide(client, db_session):
    """``questions`` and ``ai_generated_questions`` have independent id spaces.

    The same number is placed in BOTH tables, for the same learner and the same course, and
    each declared source must read its own table — never the other, and never "whichever one
    has a row".
    """
    user = _register(db_session, client, "p12_collide")
    _own_course(db_session, user.username, DATA_STRUCTURE)

    ai_question = _seed_ai_question(db_session, user.username, DATA_STRUCTURE,
                                    stem="AI STEM", answer="B", qid=COLLIDE_ID)
    material = Question(id=COLLIDE_ID, username=user.username, course_id=DATA_STRUCTURE,
                        type="choice", title="MATERIAL TITLE", content="MATERIAL STEM",
                        options=json.dumps({"A": "1", "B": "2"}, ensure_ascii=False),
                        answer="C")
    db_session.add(material)
    db_session.commit()

    _record(db_session, user, course_id=DATA_STRUCTURE, qid=COLLIDE_ID,
            source_type=QuestionSourceType.AI_GENERATED, lineage=AI_LINEAGE)
    _record(db_session, user, course_id=DATA_STRUCTURE, qid=COLLIDE_ID,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=QUESTION_LINEAGE)

    items = _listed(client, DATA_STRUCTURE)
    by_kind = {item["source_kind"]: item for item in items}
    assert set(by_kind) == {"ai_generated", "course_material"}

    assert by_kind["ai_generated"]["stem"] == ai_question.stem
    assert by_kind["ai_generated"]["reference_answer"] == "B"
    assert by_kind["ai_generated"]["question_id"] == COLLIDE_ID

    material_record = by_kind["course_material"]
    assert material_record["stem"] == "MATERIAL STEM"
    assert material_record["reference_answer"] == "C"
    # the redo contract takes an AI 题册 id and nothing else, so a `questions` row has none
    assert material_record["question_id"] is None


def test_another_learners_question_is_never_resolved(client, db_session):
    """The owner is checked, not assumed from the id.

    A state whose stored id points at another learner's question (the shape a mis-pointed
    legacy row has) resolves NOTHING: no stem, no reference answer, no question id.
    """
    stranger = _register(db_session, client, "p12_stranger")
    stranger_question = _seed_ai_question(db_session, stranger.username, DATA_STRUCTURE,
                                          stem="STRANGER PRIVATE STEM", answer="D",
                                          qid=STRANGER_ID)

    user = _register(db_session, client, "p12_owner")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    _record(db_session, user, course_id=DATA_STRUCTURE, qid=stranger_question.id,
            source_type=QuestionSourceType.AI_GENERATED, lineage=AI_LINEAGE)

    record = _only_record(client, DATA_STRUCTURE)
    assert record["stem"] == ""
    assert record["reference_answer"] == ""
    assert record["question_id"] is None
    assert record["source_kind"] == "ai_generated"     # the declared identity is still stated
    assert record["user_answer"] == "A"                # the FACT survives; only content is withheld

    detail = client.get(COURSE_WRONG_DETAIL.format(
        course=DATA_STRUCTURE, record=record["wrong_record_id"])).json()
    assert "STRANGER PRIVATE STEM" not in json.dumps(detail, ensure_ascii=False)

    # and the row really is there and really is someone else's — the id was not simply missing
    row = (db_session.query(AIGeneratedQuestion)
           .filter(AIGeneratedQuestion.id == STRANGER_ID).one())
    assert row.username == stranger.username
    assert row.stem == "STRANGER PRIVATE STEM"


def test_another_courses_question_is_never_resolved(client, db_session):
    """A course is part of the question's identity, and it is checked against the row."""
    user = _register(db_session, client, "p12_course_scope")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    _own_course(db_session, user.username, OPERATING_SYSTEM)
    os_question = _seed_ai_question(db_session, user.username, OPERATING_SYSTEM,
                                    stem="进程调度练习", answer="B")

    # the SAME learner, the SAME question id — but recorded under the OTHER course
    _record(db_session, user, course_id=DATA_STRUCTURE, qid=os_question.id,
            source_type=QuestionSourceType.AI_GENERATED, lineage=AI_LINEAGE,
            source_id="cross-course")
    # …and legitimately under its own course
    _record(db_session, user, course_id=OPERATING_SYSTEM, qid=os_question.id,
            source_type=QuestionSourceType.AI_GENERATED, lineage=AI_LINEAGE,
            source_id="own-course", when=MOMENT + timedelta(minutes=1))

    wrong_course = _only_record(client, DATA_STRUCTURE)
    assert wrong_course["stem"] == ""
    assert wrong_course["question_id"] is None
    assert "进程调度练习" not in json.dumps(wrong_course, ensure_ascii=False)

    own_course = _only_record(client, OPERATING_SYSTEM)
    assert own_course["stem"] == os_question.stem
    assert own_course["reference_answer"] == "B"
    assert own_course["course_id"] == OPERATING_SYSTEM


def test_a_wrong_source_type_fails_closed(client, db_session):
    """A declared source that names no course table resolves nothing — no fallback exists.

    ``adaptive`` is a canonical source type with no course content table. It is scoped to the
    course like any other course state (so this really does reach the resolver), and the id it
    carries DOES exist in ``ai_generated_questions`` — which is exactly why it may not be read
    there: the declaration names no table, so nothing is resolved and nothing is guessed.
    """
    user = _register(db_session, client, "p12_wrong_type")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    question = _seed_ai_question(db_session, user.username, DATA_STRUCTURE,
                                 stem="不应被解析", answer="A")

    _record(db_session, user, course_id=DATA_STRUCTURE, qid=question.id,
            source_type=QuestionSourceType.ADAPTIVE, lineage=AI_LINEAGE)

    record = _only_record(client, DATA_STRUCTURE)
    assert record["stem"] == ""
    assert record["reference_answer"] == ""
    assert record["question_id"] is None
    assert record["source_kind"] == "other"      # unmapped provenance says so
    assert "不应被解析" not in json.dumps(record, ensure_ascii=False)


# ================================================================ 3. legacy compatibility


def test_a_proven_legacy_ai_row_resolves_as_the_ai_question_it_is(client, db_session):
    """The pre-P1.2 declaration, read through the attempt lineage.

    A stored course ``material_generated`` state whose attempts are ALL from the
    ``ai_question_attempt`` lineage provably points at ``ai_generated_questions`` (that
    lineage is the only thing that ever wrote it). It resolves there — under the same owner
    and course checks — and is REPORTED as what it is.
    """
    user = _register(db_session, client, "p12_legacy")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    question = _seed_ai_question(db_session, user.username, DATA_STRUCTURE,
                                 stem="历史 AI 题", answer="C")

    _record(db_session, user, course_id=DATA_STRUCTURE, qid=question.id,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=AI_LINEAGE)

    record = _only_record(client, DATA_STRUCTURE)
    assert record["source_kind"] == "ai_generated"
    assert record["stem"] == question.stem
    assert record["reference_answer"] == "C"
    assert record["question_id"] == question.id


def test_an_ambiguous_legacy_row_fails_closed(client, db_session):
    """Lineage that cannot establish the id space resolves NOTHING.

    One state holds BOTH lineages plus an attempt that states none — the shape a colliding id
    produces. Its id WOULD resolve if it were tested against ``ai_generated_questions``, which
    is exactly why it may not be: the table cannot be established, so no table is consulted.
    """
    user = _register(db_session, client, "p12_ambiguous")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    question = _seed_ai_question(db_session, user.username, DATA_STRUCTURE,
                                 stem="有歧义的题", answer="A")

    # one identity: material_generated / <id> / course:<course> — three attempts on it
    _record(db_session, user, course_id=DATA_STRUCTURE, qid=question.id,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=AI_LINEAGE,
            source_id="mixed-ai")
    _record(db_session, user, course_id=DATA_STRUCTURE, qid=question.id,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=QUESTION_LINEAGE,
            source_id="mixed-questions", when=MOMENT + timedelta(minutes=1))
    _record(db_session, user, course_id=DATA_STRUCTURE, qid=question.id,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=None,
            when=MOMENT + timedelta(minutes=2))

    record = _only_record(client, DATA_STRUCTURE)
    assert record["stem"] == ""
    assert record["reference_answer"] == ""
    assert record["question_id"] is None
    # the declared kind is kept as stored, and the FACTS are untouched
    assert record["source_kind"] == "course_material"
    assert record["repeat_wrong_count"] == 3
    assert "有歧义的题" not in json.dumps(record, ensure_ascii=False)


def test_an_ordinary_question_attempt_row_still_resolves_from_the_questions_table(
        client, db_session):
    """The ordinary practice flow over ``questions`` keeps working exactly as before.

    Its lineage is unambiguous, so requiring the proof costs it nothing — and its content
    still comes from the table it was always in.
    """
    user = _register(db_session, client, "p12_material")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    row = Question(username=user.username, course_id=DATA_STRUCTURE, type="choice",
                   title="普通练习题", content="普通练习题的题干", answer="D",
                   knowledge_point_id=None)
    db_session.add(row)
    db_session.commit()

    _record(db_session, user, course_id=DATA_STRUCTURE, qid=row.id,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=QUESTION_LINEAGE)

    record = _only_record(client, DATA_STRUCTURE)
    assert record["source_kind"] == "course_material"
    assert record["stem"] == "普通练习题的题干"
    assert record["reference_answer"] == "D"
    assert record["question_id"] is None


def test_a_question_of_another_course_never_leaks_through_a_legacy_row(client, db_session):
    """The legacy path is not a way around the course check."""
    user = _register(db_session, client, "p12_legacy_scope")
    _own_course(db_session, user.username, DATA_STRUCTURE)
    _own_course(db_session, user.username, OPERATING_SYSTEM)
    os_question = _seed_ai_question(db_session, user.username, OPERATING_SYSTEM,
                                    stem="操作系统私有题干", answer="B")

    _record(db_session, user, course_id=DATA_STRUCTURE, qid=os_question.id,
            source_type=QuestionSourceType.MATERIAL_GENERATED, lineage=AI_LINEAGE)

    record = _only_record(client, DATA_STRUCTURE)
    assert record["stem"] == ""
    assert record["question_id"] is None
    assert "操作系统私有题干" not in json.dumps(record, ensure_ascii=False)


# ================================================================ 4. the whole loop


def test_submit_wrong_answer_wrong_state_wrong_detail_full_loop(client, db_session):
    """question → wrong answer → wrong state → wrong detail → redo, under one identity."""
    _onboard(client, "p12_loop", [DATA_STRUCTURE])
    question = _seed_ai_question(db_session, "p12_loop", DATA_STRUCTURE,
                                 stem="循环验证题干", answer="A")

    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    attempt_id = started.json()["attempt_id"]
    submitted = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                            json={"answer": "D"})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["result"]["correct"] is False

    record = _only_record(client, DATA_STRUCTURE)
    assert record["status"] == "active"
    assert record["stem"] == question.stem
    assert record["user_answer"] == "D"
    assert record["reference_answer"] == "A"
    assert record["question_id"] == question.id

    # the id the record hands out is usable by the course redo contract
    redo = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                 question=record["question_id"]))
    assert redo.status_code == 200, redo.text
    assert redo.json()["question"]["id"] == question.id

    # a correct redo resolves the state through the same identity
    again = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE,
                                             attempt=redo.json()["attempt_id"]),
                        json={"answer": "A"})
    assert again.status_code == 200, again.text
    resolved = client.get(COURSE_WRONG.format(course=DATA_STRUCTURE)).json()
    assert resolved["items"][0]["status"] == "resolved"
    assert resolved["items"][0]["stem"] == question.stem

    # and the two submissions are two distinct canonical attempts on ONE question identity
    from learning.practice.models import PracticeAttempt
    mirrored = (db_session.query(PracticeAttempt)
                .filter(PracticeAttempt.service_namespace == "course_learning",
                        PracticeAttempt.question_source_type == "AI_generated",
                        PracticeAttempt.question_source_id == str(question.id)).all())
    assert len(mirrored) == 2
    assert sorted(a.correct for a in mirrored) == [False, True]
