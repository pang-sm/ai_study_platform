"""THREE_DOMAIN_PRODUCTIZATION_P1_1 — Course Learning backend closure.

WHAT THESE TESTS HOLD
---------------------
The course workspace can now run its whole loop against ONE identity — the course the URL
names — and these are the properties that make that safe to expose:

1. an upload's WHO and WHICH COURSE come from the session and the path; the client supplies
   neither, and a course the caller does not have is not writable through it;
2. a material is filed under the course's own identity, and the course's library lists that
   course and nothing else (not an exam scope, not a programming course that shares a
   spelling);
3. a submission is checked against the course BEFORE it is graded, so a course-A attempt
   cannot be answered into course B;
4. a submission still writes the canonical fact — the practice attempt AND the learning
   event both carry the course, which is what makes the course's own timeline show it;
5. today's plan is attributable per course, and a task that cannot be attributed is left
   out rather than guessed into the course.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported. Nothing here can reach ``backend/app.db``.

The two courses used are REAL catalog courses (``数据结构`` / ``操作系统``), because the
identity rules under test are the product's own identity map — a synthetic pair would
prove the filter works on strings, not that it works on the catalog.
"""
import json
from datetime import datetime

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from data_plane.models import LearningEvent
from learning.practice.models import PracticeAttempt
from models import (AIGeneratedQuestion, AIQuestionAttempt, CourseLearningPreference,
                    ExamStudyPlanTask, LearningRecord, LearningTask, StudyMaterial, User)

DATA_STRUCTURE = "数据结构"          # display name — the canonical preference key
OPERATING_SYSTEM = "操作系统"
MOMENT = datetime(2026, 9, 20, 4, 0, 0)

COURSE_RECORDS = "/course-learning/courses/{course}/records"
COURSE_STATE = "/course-learning/courses/{course}/state"
COURSE_MATERIALS = "/course-learning/courses/{course}/materials"
COURSE_WORKBOOK = "/course-learning/courses/{course}/practice/workbook"
COURSE_HISTORY = "/course-learning/courses/{course}/practice/history"
COURSE_SUBMIT = "/course-learning/courses/{course}/practice/{attempt}/submit"
COURSE_NEW_ATTEMPT = "/course-learning/courses/{course}/practice/questions/{question}/attempts"
COURSE_GENERATE = "/course-learning/courses/{course}/practice/generate"
COURSE_TODAY = "/course-learning/courses/{course}/today-plan"


# ---------------------------------------------------------------- helpers

def _onboard(client, username, courses, major="计算机科学与技术", grade="大二"):
    """Register a learner and put them through the REAL course onboarding.

    The onboarding is what writes ``selected_courses`` AND creates one
    ``course_learning_preferences`` row per course, so this is the same pair of facts a
    real learner's account has. Setting them by hand would let a test pass with an account
    the product never produces.
    """
    profile = register_and_login(client, username)
    response = client.post("/course-learning/onboarding", json={
        "major": major, "grade": grade, "semester": "上学期",
        "selected_courses": list(courses), "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text
    return profile


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _seed_question(db, username, course_key, stem="线性表练习", answer="A") -> AIGeneratedQuestion:
    """A persisted course workbook question, in the exact shape the generator writes."""
    question = AIGeneratedQuestion(
        username=username, subject_key=course_key, subject_name=course_key,
        knowledge_point_id="kp_list", knowledge_point_name="线性表",
        knowledge_point_path="线性结构", question_type="选择题", stem=stem,
        options_json=json.dumps({"A": "随机访问", "B": "顺序访问", "C": "无法访问",
                                 "D": "只读访问"}, ensure_ascii=False),
        standard_answer=answer, analysis="顺序存储按下标计算地址。",
        difficulty="基础", requirement="课程章节练习", generation_mode="ai",
        quality_status="unchecked")
    db.add(question)
    db.commit()
    return question


def _plan_subject_key(course_id) -> str:
    import main
    return main._course_learning_task_subject_key(course_id)


def _mirrored(db, attempt_id) -> list[PracticeAttempt]:
    """The canonical attempts THIS course-AI attempt was mirrored into.

    Filtered by the full source identity, not by the id alone: ``source_attempt_id`` is
    only unique WITHIN its source table (``data_plane.identity``), so an unrelated row
    mirrored from the legacy ``question_attempts`` table may carry the same number. The
    triple ``(source_type, source_attempt_id, item_key)`` is what identifies one fact.
    """
    return (db.query(PracticeAttempt)
            .filter(PracticeAttempt.source_attempt_type == "ai_question_attempt",
                    PracticeAttempt.source_attempt_id == str(attempt_id))
            .all())


def _upload(client, course, filename="notes.txt", body=b"linear list notes"):
    return client.post(COURSE_MATERIALS.format(course=course),
                       files={"file": (filename, body, "text/plain")})


# ================================================================ 1. materials


def test_material_upload_derives_identity_from_the_session_and_the_path(client, db_session):
    """WHO uploads and INTO WHICH COURSE are both facts of the request's context.

    The body carries a file and nothing else: no ``username`` the server would have to
    trust, no ``subject_key`` for the client to invent, no course to reconcile against the
    URL. If this test were passing because of a submitted field, removing that field would
    break it — which is exactly what it does not do.
    """
    _onboard(client, "p11_material_owner", [DATA_STRUCTURE])

    uploaded = _upload(client, DATA_STRUCTURE)
    assert uploaded.status_code == 200, uploaded.text
    payload = uploaded.json()

    assert payload["course_id"] == DATA_STRUCTURE
    assert payload["success"] is True
    assert payload["material_id"]

    row = db_session.query(StudyMaterial).filter(StudyMaterial.id == payload["material_id"]).one()
    # the identity was derived, not received: the session decided the owner, the path
    # decided the course, and the course IS its own subject_key (no fabricated 学科).
    assert row.username == "p11_material_owner"
    assert row.course_id == DATA_STRUCTURE
    assert row.subject_key == DATA_STRUCTURE
    assert row.subject == DATA_STRUCTURE
    assert row.is_deleted is False

    # the pipeline really ran: the file was stored and parsed, not merely recorded
    assert (row.original_filename or "").endswith("notes.txt")
    assert row.parse_status in {"success", "pending", "parsing", "partial"}


def test_a_learner_cannot_upload_into_another_learners_course(client, db_session):
    _onboard(client, "p11_upload_owner", [DATA_STRUCTURE])

    # a different learner, who does NOT have this course
    register_and_login(client, "p11_upload_stranger")
    refused = _upload(client, DATA_STRUCTURE)
    assert refused.status_code == 404, refused.text

    # …and the refused upload left nothing behind for the stranger
    assert db_session.query(StudyMaterial).filter(
        StudyMaterial.username == "p11_upload_stranger").count() == 0

    # a course that exists in the catalog but is not this learner's is refused too
    assert client.get(COURSE_RECORDS.format(course=OPERATING_SYSTEM)).status_code == 404
    assert _upload(client, OPERATING_SYSTEM).status_code == 404


def test_course_materials_list_is_scoped_to_the_course(client, db_session):
    _onboard(client, "p11_material_scope", [DATA_STRUCTURE, OPERATING_SYSTEM])

    mine = _upload(client, DATA_STRUCTURE, "mine.txt", b"course notes for data structure")
    assert mine.status_code == 200, mine.text

    # a material of the learner's OTHER course, an 11408 exam scope, and a programming
    # course that shares a spelling with a catalog course — none of them is this course's
    for course_id, subject_key, name in (
        (OPERATING_SYSTEM, OPERATING_SYSTEM, "other-course.txt"),
        ("data_structure_11408", "data_structure", "exam-scope.txt"),
        ("python_programming", "programming", "programming.txt"),
    ):
        db_session.add(StudyMaterial(
            username="p11_material_scope", course_id=course_id, subject_key=subject_key,
            subject=subject_key, file_type="text", original_filename=name,
            file_hash=f"hash-{name}", file_path=f"test/{name}", file_size=10,
            extracted_text="", summary="", parse_status="success", is_deleted=False))
    db_session.commit()

    listed = client.get(COURSE_MATERIALS.format(course=DATA_STRUCTURE))
    assert listed.status_code == 200, listed.text
    body = listed.json()

    assert body["course_id"] == DATA_STRUCTURE
    assert body["total"] == 1
    assert [item["original_filename"] for item in body["items"]] == ["mine.txt"]
    assert body["items"][0]["course_id"] == DATA_STRUCTURE

    # the same library read through the OTHER course's path shows its own material only
    other = client.get(COURSE_MATERIALS.format(course=OPERATING_SYSTEM)).json()
    assert [item["original_filename"] for item in other["items"]] == ["other-course.txt"]

    # a course the learner does not have is a 404, not an empty library
    assert client.get(COURSE_MATERIALS.format(course="离散数学")).status_code == 404


# ================================================================ 2. practice


def test_a_course_attempt_cannot_be_submitted_through_another_course(client, db_session):
    """The cross-course hole this closes: an attempt id is not an authority.

    Course A's attempt, submitted through course B's path, must be refused — and refused
    BEFORE anything is graded, which is asserted by the attempt still being open afterwards.
    """
    _onboard(client, "p11_cross_submit", [DATA_STRUCTURE, OPERATING_SYSTEM])
    question = _seed_question(db_session, "p11_cross_submit", DATA_STRUCTURE)

    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    assert started.status_code == 200, started.text
    attempt_id = started.json()["attempt_id"]
    assert started.json()["course_id"] == DATA_STRUCTURE

    foreign = client.post(COURSE_SUBMIT.format(course=OPERATING_SYSTEM, attempt=attempt_id),
                          json={"answer": "A"})
    assert foreign.status_code == 404, foreign.text

    attempt = db_session.query(AIQuestionAttempt).filter(
        AIQuestionAttempt.id == attempt_id).one()
    assert attempt.status == "in_progress", "a refused submit must not grade anything"
    assert _mirrored(db_session, attempt_id) == [], "a refused submit must not mirror"

    # the course that DOES own it accepts the very same answer
    accepted = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                           json={"answer": "A"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["course_id"] == DATA_STRUCTURE
    assert accepted.json()["result"]["correct"] is True


def test_a_question_from_another_course_cannot_open_an_attempt(client, db_session):
    _onboard(client, "p11_cross_question", [DATA_STRUCTURE, OPERATING_SYSTEM])
    foreign_question = _seed_question(db_session, "p11_cross_question", OPERATING_SYSTEM,
                                      stem="进程调度练习", answer="B")

    refused = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=foreign_question.id))
    assert refused.status_code == 404, refused.text
    assert db_session.query(AIQuestionAttempt).filter(
        AIQuestionAttempt.username == "p11_cross_question").count() == 0


def test_submit_writes_the_course_into_the_canonical_facts(client, db_session, monkeypatch):
    """A submission is not only a verdict — it is a FACT about this course.

    The legacy emitter used to leave ``course_id`` NULL on the event, which made a real
    submission invisible to the course's own timeline. Both halves of the canonical record
    (the durable practice attempt and the learning event) are asserted here, because a
    course-scoped page reads them from different places and only one of them being right
    would look like "the learner never practised".
    """
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "true")
    _onboard(client, "p11_submit_facts", [DATA_STRUCTURE, OPERATING_SYSTEM])
    question = _seed_question(db_session, "p11_submit_facts", DATA_STRUCTURE)

    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    attempt_id = started.json()["attempt_id"]
    submitted = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                            json={"answer": "A"})
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()["result"]
    assert result["correct"] is True
    assert result["standard_answer"] == "A"
    assert result["analysis"]

    # ── the canonical practice attempt carries the course on its question reference
    mirrored = _mirrored(db_session, attempt_id)
    assert len(mirrored) == 1
    ref = json.loads(mirrored[0].question_ref_json)
    assert ref["context"]["course_id"] == DATA_STRUCTURE
    assert mirrored[0].service_namespace == "course_learning"

    # ── the canonical learning event carries it too
    events = db_session.query(LearningEvent).filter(
        LearningEvent.event_type == "course_practice",
        LearningEvent.user_id == _user(db_session, "p11_submit_facts").id).all()
    assert len(events) == 1, "one submit is one course_practice fact"
    assert events[0].course_id == DATA_STRUCTURE
    assert events[0].subject_key == DATA_STRUCTURE
    assert events[0].service_key == "course_learning"
    assert events[0].correct is True

    # ── and the course-scoped surfaces can therefore SEE it
    timeline = client.get(COURSE_RECORDS.format(course=DATA_STRUCTURE)).json()
    assert [record["event_type"] for record in timeline["records"]] == ["course_practice"]
    assert timeline["records"][0]["context"]["course_id"] == DATA_STRUCTURE

    summary = client.get(COURSE_RECORDS.format(
        course=DATA_STRUCTURE) + "/summary").json()
    assert summary["course_id"] == DATA_STRUCTURE
    assert summary["total_events"] == 1
    assert summary["practice_attempts"] == 1

    state = client.get(COURSE_STATE.format(course=DATA_STRUCTURE)).json()
    assert state["practice"]["attempts"] == 1
    assert state["practice"]["factual_correct"] == 1

    # ── the OTHER course sees none of it
    other_state = client.get(COURSE_STATE.format(course=OPERATING_SYSTEM)).json()
    assert other_state["practice"]["attempts"] == 0
    other_timeline = client.get(COURSE_RECORDS.format(course=OPERATING_SYSTEM)).json()
    assert other_timeline["records"] == []


def test_the_course_practice_loop_reads_workbook_history_and_next(client, db_session):
    """question → answer → feedback → next, entirely under one course identity."""
    _onboard(client, "p11_loop", [DATA_STRUCTURE])
    question = _seed_question(db_session, "p11_loop", DATA_STRUCTURE)

    workbook = client.get(COURSE_WORKBOOK.format(course=DATA_STRUCTURE)).json()
    assert workbook["course_id"] == DATA_STRUCTURE
    assert [item["id"] for item in workbook["items"]] == [question.id]
    assert workbook["items"][0]["workbook_status"] == "unanswered"
    # a question the learner has not answered must not arrive with its answer attached
    assert "standard_answer" not in workbook["items"][0]
    assert "analysis" not in workbook["items"][0]

    attempt_id = client.post(COURSE_NEW_ATTEMPT.format(
        course=DATA_STRUCTURE, question=question.id)).json()["attempt_id"]
    wrong = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                        json={"answer": "C"})
    assert wrong.json()["result"]["correct"] is False

    # the verdict is readable back, and the workbook reports the derived status
    workbook = client.get(COURSE_WORKBOOK.format(course=DATA_STRUCTURE)).json()
    assert workbook["items"][0]["workbook_status"] == "wrong"
    assert workbook["items"][0]["attempt_count"] == 1

    history = client.get(COURSE_HISTORY.format(course=DATA_STRUCTURE)).json()
    assert history["course_id"] == DATA_STRUCTURE
    assert [row["id"] for row in history["items"]] == [attempt_id]

    # "next": a NEW attempt on the same question, then a correct answer resolves it
    nxt = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE, question=question.id))
    assert nxt.status_code == 200, nxt.text
    assert nxt.json()["attempt_id"] != attempt_id
    right = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE,
                                             attempt=nxt.json()["attempt_id"]),
                        json={"answer": "A"})
    assert right.json()["result"]["correct"] is True

    workbook = client.get(COURSE_WORKBOOK.format(course=DATA_STRUCTURE)).json()
    assert workbook["items"][0]["workbook_status"] == "correct"
    assert workbook["items"][0]["attempt_count"] == 2

    # the learner's own practice history stays on the course it happened in
    assert client.get(COURSE_WORKBOOK.format(course=OPERATING_SYSTEM)).status_code == 404

    # one canonical LearningRecord row per submission — the legacy factual trail
    assert db_session.query(LearningRecord).filter(
        LearningRecord.user_id == _user(db_session, "p11_loop").id,
        LearningRecord.record_type == "practice").count() == 2


def test_a_submit_body_cannot_name_its_own_course(client, db_session):
    """The request schema refuses the fields that would make the body an authority."""
    _onboard(client, "p11_body_authority", [DATA_STRUCTURE])
    question = _seed_question(db_session, "p11_body_authority", DATA_STRUCTURE)
    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    attempt_id = started.json()["attempt_id"]

    smuggled = client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE, attempt=attempt_id),
                           json={"answer": "A", "course_id": OPERATING_SYSTEM})
    assert smuggled.status_code == 422, smuggled.text
    # the attempt is untouched: the request never reached the grader
    assert db_session.query(AIQuestionAttempt).filter(
        AIQuestionAttempt.id == attempt_id).one().status == "in_progress"


def test_generation_is_gated_by_the_tier_and_filed_under_the_path_course(client, monkeypatch,
                                                                        db_session):
    """A denied capability is an ANSWER; an allowed one really uses the model.

    The Free refusal is asserted first because "generate a question for me" is exactly the
    request a fabricated local question would satisfy most cheaply — the product's rule is
    that a tier denial must come back as a denial instead.
    """
    _onboard(client, "p11_generate", [DATA_STRUCTURE])
    body = {"knowledge_point_title": "线性表", "chapter": "线性结构"}

    denied = client.post(COURSE_GENERATE.format(course=DATA_STRUCTURE), json=body)
    assert denied.status_code == 403, denied.text
    assert db_session.query(AIGeneratedQuestion).filter(
        AIGeneratedQuestion.username == "p11_generate").count() == 0

    grant_unified_tier(db_session, "p11_generate", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _fake_provider_factory())

    generated = client.post(COURSE_GENERATE.format(course=DATA_STRUCTURE), json=body)
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    assert payload["course_id"] == DATA_STRUCTURE
    assert payload["generation_mode"] == "ai"
    assert payload["attempt_id"]

    item = db_session.query(AIGeneratedQuestion).filter(
        AIGeneratedQuestion.id == payload["question"]["id"]).one()
    # filed under the CANONICAL course identity, not the English alias the client may hold
    assert item.subject_key == DATA_STRUCTURE
    assert item.requirement == "课程章节练习"

    attempt = db_session.query(AIQuestionAttempt).filter(
        AIQuestionAttempt.id == payload["attempt_id"]).one()
    assert attempt.subject_key == DATA_STRUCTURE
    assert attempt.mode == "course_learning"

    # a course the caller does not have is refused before any model call
    assert client.post(COURSE_GENERATE.format(course=OPERATING_SYSTEM),
                       json=body).status_code == 404


# ---------------------------------------------------------------- AI double

class _ScriptedProvider(FakeProvider):
    """FakeProvider whose completion is the course question payload under test.

    The base fake answers with fixed prose, which a question generator would correctly
    reject — so the content is replaced while the rest of the adapter (usage reporting,
    provider name, finish reason) stays the real double's.
    """

    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self._content = content

    def complete(self, spec):
        import dataclasses
        return dataclasses.replace(super().complete(spec), content=self._content)


def _fake_provider_factory():
    """Patch the ONE seam — how the orchestrator obtains a provider adapter.

    The whole lifecycle (capability permission → router → estimate → reserve → gateway →
    settle) still runs; only the outbound call is replaced. That is the difference between
    proving the course route reaches the model boundary and proving it fabricated a
    question.
    """
    content = json.dumps({
        "stem": "顺序表按下标定位元素的时间复杂度是多少？",
        "options": {"A": "O(1)", "B": "O(log n)", "C": "O(n)", "D": "O(n log n)"},
        "standard_answer": "A",
        "analysis": "顺序存储可以直接由基址与下标计算出地址。",
    }, ensure_ascii=False)

    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, provider=name, input_tokens=50,
                                 output_tokens=50)

    return _make


# ================================================================ 3. today plan


def test_today_plan_lists_only_this_courses_tasks(client, db_session):
    _onboard(client, "p11_today_scope", [DATA_STRUCTURE, OPERATING_SYSTEM])

    db_session.add(ExamStudyPlanTask(
        username="p11_today_scope", subject_key=_plan_subject_key(DATA_STRUCTURE),
        title="复习线性表", task_type="review", status="not_started",
        due_date="2026-09-21"))
    db_session.add(ExamStudyPlanTask(
        username="p11_today_scope", subject_key=_plan_subject_key(OPERATING_SYSTEM),
        title="复习进程调度", task_type="review", status="not_started",
        due_date="2026-09-21"))
    db_session.add(LearningTask(
        username="p11_today_scope", course_id=DATA_STRUCTURE, title="做课后题",
        task_type="custom", status="todo", due_date=MOMENT))
    db_session.add(LearningTask(
        username="p11_today_scope", course_id=OPERATING_SYSTEM, title="看进程视频",
        task_type="custom", status="todo", due_date=MOMENT))
    db_session.commit()

    body = client.get(COURSE_TODAY.format(course=DATA_STRUCTURE)).json()
    assert body["course_id"] == DATA_STRUCTURE
    assert body["service_namespace"] == "course_learning"
    assert {item["title"] for item in body["items"]} == {"复习线性表", "做课后题"}
    # EVERY item is attributable to the course it was served under
    assert {item["course_id"] for item in body["items"]} == {DATA_STRUCTURE}
    assert {item["source"] for item in body["items"]} == {"course_study_plan", "learning_tasks"}

    other = client.get(COURSE_TODAY.format(course=OPERATING_SYSTEM)).json()
    assert {item["title"] for item in other["items"]} == {"复习进程调度", "看进程视频"}

    # a course the learner does not have is a 404, never another course's list
    assert client.get(COURSE_TODAY.format(course="数据结构与算法")).status_code == 404


def test_an_unattributable_task_is_never_guessed_into_a_course(client, db_session):
    """A task whose course cannot be established is left OUT of every course.

    The alternatives — matching on the title, defaulting to the learner's first course, or
    showing it under whichever course was opened — would each put another course's work on
    this course's page. Not showing it is the only answer that is not a fabrication; the
    task is still the learner's, and still visible where it always was.
    """
    _onboard(client, "p11_today_unscoped", [DATA_STRUCTURE, OPERATING_SYSTEM])

    db_session.add(LearningTask(username="p11_today_unscoped", course_id="",
                                title="没有归属的任务", task_type="custom", status="todo"))
    db_session.add(LearningTask(username="p11_today_unscoped", course_id="某门不存在的课",
                                title="无法识别的课程任务", task_type="custom", status="todo"))
    db_session.add(LearningTask(username="p11_today_unscoped", course_id=DATA_STRUCTURE,
                                title="可归属的任务", task_type="custom", status="todo"))
    db_session.commit()

    for course in (DATA_STRUCTURE, OPERATING_SYSTEM):
        body = client.get(COURSE_TODAY.format(course=course)).json()
        titles = {item["title"] for item in body["items"]}
        assert "没有归属的任务" not in titles
        assert "无法识别的课程任务" not in titles

    mine = client.get(COURSE_TODAY.format(course=DATA_STRUCTURE)).json()
    assert {item["title"] for item in mine["items"]} == {"可归属的任务"}

    # the unscoped rows are real tasks and were not modified by being left out
    assert db_session.query(LearningTask).filter(
        LearningTask.course_id == "").count() == 1


def test_today_plan_never_reports_another_learners_tasks(client, db_session):
    """Two learners on the SAME course: the plan is scoped by owner as well as course."""
    _onboard(client, "p11_today_owner", [DATA_STRUCTURE])
    owner_task = ExamStudyPlanTask(
        username="p11_today_owner", subject_key=_plan_subject_key(DATA_STRUCTURE),
        title="我的任务", task_type="review", status="not_started")
    db_session.add(owner_task)
    db_session.commit()

    mine = client.get(COURSE_TODAY.format(course=DATA_STRUCTURE)).json()
    assert {item["title"] for item in mine["items"]} == {"我的任务"}

    # the other learner has the SAME course — and an empty plan
    register_and_login(client, "p11_today_other")
    _own_course(db_session, "p11_today_other", DATA_STRUCTURE)
    other = client.get(COURSE_TODAY.format(course=DATA_STRUCTURE)).json()
    assert other["items"] == []
    assert other["empty"] is True


# ================================================================ 4. identity forms


def test_a_course_is_addressable_by_any_form_the_product_itself_writes():
    """The identity set is the product's OWN alias resolution, and nothing looser.

    Everything asserted here is inherited from ``subjects.py`` — the module that decides
    what a course is called — rather than invented for the course-scoped routes: the two
    stored spellings are one course, a case variant of the English key is that same key,
    and a catalog alias resolves like every other surface resolves it. What the set does
    NOT do is recognize a string it has never seen: an unrecognized name resolves to
    itself alone, so a course-scoped read can never silently adopt a half-matched course.
    """
    from learning.spaces.course_learning.context import course_identity_forms

    forms = course_identity_forms(DATA_STRUCTURE)
    assert forms == frozenset({DATA_STRUCTURE, "data_structure"})
    assert course_identity_forms("data_structure") == forms
    assert course_identity_forms("  数据结构  ") == forms
    # a catalog alias resolves to the same course (it adds its own spelling, no 3rd course)
    assert course_identity_forms("数据结构与算法") >= forms
    # a case variant resolves to the same course too (the alias map's own rule); the raw
    # spelling is carried alongside rather than dropped, and adds nothing new
    assert course_identity_forms("Data_Structure") >= {"数据结构", "data_structure"}

    # a name the catalog does not know — including an exam scope that merely CONTAINS a
    # course key — resolves to itself alone and is therefore claimable by no course
    for unknown in ("data", "数据结构课", "某门不存在的课", "data_structure_11408"):
        assert course_identity_forms(unknown) == frozenset({unknown}), unknown


def test_the_suppressed_answer_never_leaves_the_server_before_a_submit(client, db_session):
    """The workbook, history and attempt-start payloads carry no reference answer."""
    _onboard(client, "p11_no_leak", [DATA_STRUCTURE])
    question = _seed_question(db_session, "p11_no_leak", DATA_STRUCTURE, stem="待答题")

    for payload in (
        client.get(COURSE_WORKBOOK.format(course=DATA_STRUCTURE)).json(),
        client.get(COURSE_HISTORY.format(course=DATA_STRUCTURE)).json(),
        client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                              question=question.id)).json(),
    ):
        blob = json.dumps(payload, ensure_ascii=False)
        assert "standard_answer" not in blob
        assert "顺序存储按下标计算地址" not in blob


def test_the_unified_plan_gate_still_decides_the_course_plan(client, db_session):
    """P1.1 changed no membership: the course plan gate is the SAME unified capability."""
    from membership import get_feature_entitlement
    from usage import capabilities

    assert capabilities.FEATURE_CAPABILITY["learning_plan"] == "planning.generate"
    _onboard(client, "p11_plan_gate", [DATA_STRUCTURE])
    user = _user(db_session, "p11_plan_gate")

    for service_key in ("course_learning", "exam_11408", "programming"):
        verdict = get_feature_entitlement(user, db_session, service_key, "learning_plan")
        assert verdict["allowed"] is False, service_key
        assert verdict["required_capability"] == "planning.generate"

    denied = client.get("/course-learning/study-plan", params={"course_id": DATA_STRUCTURE})
    assert denied.status_code == 403
    assert denied.json()["detail"]["required_capability"] == "planning.generate"

    grant_unified_tier(db_session, "p11_plan_gate", "standard")
    allowed = client.get("/course-learning/study-plan", params={"course_id": DATA_STRUCTURE})
    assert allowed.status_code == 200, allowed.text


# ================================================================ 5. emitter identity

def test_course_events_and_backfill_agree_on_the_course_identity(db_session):
    """Live emission and historical replay must file the same fact the same way.

    Asserted at the builder level because that is where the two agree or drift: if the
    backfill left ``course_id`` NULL while the live emitter filled it, the same submission
    would be visible or invisible to the learner's course timeline depending on whether it
    was recorded live or replayed.
    """
    from types import SimpleNamespace

    from data_plane import backfill, emitter

    user = User(username="p11_emitter", hashed_password="x", grade="freshman", major="cs")
    db_session.add(user)
    db_session.commit()

    attempt = SimpleNamespace(
        id=4242, username="p11_emitter", subject_key=DATA_STRUCTURE,
        knowledge_point_id="kp_list",
        question_ids_json=json.dumps([1]),
        answers_json=json.dumps({"1": "A"}),
        result_json=json.dumps({"question_id": 1, "correct": True}),
        submitted_at=MOMENT)
    item = SimpleNamespace(id=1, stem="q", subject_key=DATA_STRUCTURE,
                           question_type="选择题", options_json=None,
                           knowledge_point_id="kp_list", standard_answer="A")

    live = emitter.build_course_practice_events(attempt, item, "A", True, user)[0]
    replayed = backfill.build_backfill_events(attempt, user.id)[0]

    assert live["course_id"] == DATA_STRUCTURE
    assert replayed["course_id"] == DATA_STRUCTURE
    assert live["subject_key"] == replayed["subject_key"] == DATA_STRUCTURE
    # the frozen identity is untouched by carrying the course: same event, richer envelope
    assert live["event_id"] == replayed["event_id"]


# ================================================================ 6. regression guards

def test_p1_course_surfaces_still_answer_under_the_same_identity(client, db_session):
    """The P1 records / wrong-answers / state routes keep working — unchanged.

    The wrong-answer record is asserted on IDENTITY (which question, which course, which
    fact) rather than on display content: a real submission reaches the canonical store
    through the practice mirror, and what that mirror is allowed to say about a course AI
    question is P1's decision, not this change's.

    CONTRACT CORRECTION (P1.2): this test used to CHARACTERIZE the P1.1 blocker — a real
    submission was mirrored as ``material_generated`` and the record's content was therefore
    resolved from the static ``questions`` table while the question actually lives in
    ``ai_generated_questions``, giving an empty stem. The source identity is corrected (the
    mirror now declares ``AI_generated``), so the record reports what the row provably is and
    resolves its content from the table that owns the id.
    """
    _onboard(client, "p11_p1_regression", [DATA_STRUCTURE])
    question = _seed_question(db_session, "p11_p1_regression", DATA_STRUCTURE)
    started = client.post(COURSE_NEW_ATTEMPT.format(course=DATA_STRUCTURE,
                                                    question=question.id))
    client.post(COURSE_SUBMIT.format(course=DATA_STRUCTURE,
                                     attempt=started.json()["attempt_id"]),
                json={"answer": "D"})

    assert client.get(COURSE_RECORDS.format(course=DATA_STRUCTURE)).status_code == 200
    summary = client.get(COURSE_RECORDS.format(
        course=DATA_STRUCTURE) + "/summary").json()
    assert summary["course_id"] == DATA_STRUCTURE

    wrong = client.get("/course-learning/courses/数据结构/wrong-answers")
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["total"] == 1
    record = wrong.json()["items"][0]
    assert record["course_id"] == DATA_STRUCTURE
    assert record["status"] == "active"
    assert record["user_answer"] == "D"
    assert record["repeat_wrong_count"] == 1
    # CORRECTED BY P1.2 — the two lines this test promised would replace the P1.1
    # characterization. The mirrored provenance is ``AI_generated`` and the content is
    # resolved from ``ai_generated_questions``, with the owner and the course verified.
    assert record["source_kind"] == "ai_generated"
    assert record["stem"] == question.stem
    assert record["reference_answer"] == "A"
    # the id the course redo contract takes is the question's own id
    assert record["question_id"] == question.id
    detail = client.get(
        f"/course-learning/courses/数据结构/wrong-answers/{record['wrong_record_id']}").json()
    assert detail["attempt_history"][-1]["correct"] is False

    state = client.get(COURSE_STATE.format(course=DATA_STRUCTURE)).json()
    assert state["wrong_answers"]["active"] == 1
    # the workbook still carries the question itself, stems included
    workbook = client.get(COURSE_WORKBOOK.format(course=DATA_STRUCTURE)).json()
    assert workbook["items"][0]["stem"] == question.stem


def test_the_legacy_material_route_still_takes_what_it_always_took(client, db_session):
    """The pre-existing /materials/upload contract is unchanged, and now converges.

    Nothing about the legacy shape was removed: the English course key, the explicit
    ``subject_key`` and the display ``subject`` are all still accepted exactly as before.
    What changed is that the two spellings of one course are recognized as one course
    everywhere — so a file uploaded the old way is listed in the course's own library
    rather than being invisible to it.
    """
    _onboard(client, "p11_legacy_materials", [DATA_STRUCTURE])

    uploaded = client.post("/materials/upload", data={
        "username": "p11_legacy_materials",
        "course_id": "data_structure",     # the English alias — still accepted
        "subject_key": "data_structure",
        "subject": DATA_STRUCTURE,
        "source_type": "user_upload",
    }, files={"file": ("legacy.txt", b"legacy path", "text/plain")})
    assert uploaded.status_code == 200, uploaded.text

    row = db_session.query(StudyMaterial).filter(
        StudyMaterial.id == uploaded.json()["material_id"]).one()
    assert row.course_id == "data_structure"
    assert row.course_id != row.subject
    assert row.subject == DATA_STRUCTURE
    # the SAME course, not a second one: the domain classifier agrees now
    import main
    assert main._material_domain(row.course_id, row.subject_key) == "course_learning"

    # the course-scoped library claims it, because the English key IS one of the course's
    # own identity forms — this is one course under two stored spellings, not a guess
    listed = client.get(COURSE_MATERIALS.format(course=DATA_STRUCTURE)).json()
    assert [item["id"] for item in listed["items"]] == [row.id]
    # The course-SCOPED path itself is addressed by the course's canonical key only — the
    # workspace lists courses by that key, and ownership is asserted against it exactly, so
    # the English spelling is a different (unowned) path rather than a second address for
    # the same course.
    assert client.get(COURSE_MATERIALS.format(course="data_structure")).status_code == 404

    # the legacy scoped LIST route now accepts the canonical spelling too (it used to 400),
    # and matches the spelling it was asked for exactly
    canonical_list = client.get("/materials", params={
        "username": "p11_legacy_materials",
        "course_id": "数据结构", "subject_key": "数据结构"})
    assert canonical_list.status_code == 200, canonical_list.text
    assert canonical_list.json()["materials"] == []   # nothing is stored under it yet

    # the legacy contract still REFUSES a course_id that is neither spelling
    refused = client.post("/materials/upload", data={
        "username": "p11_legacy_materials",
        "course_id": "某门不存在的课",
        "subject_key": "某门不存在的课",
        "subject": "某门不存在的课",
    }, files={"file": ("bad.txt", b"nope", "text/plain")})
    assert refused.status_code == 400, refused.text


def test_the_same_file_cannot_be_uploaded_twice_into_one_course(client, db_session):
    """Duplicate detection follows the COURSE, not the spelling used to reach it."""
    _onboard(client, "p11_duplicate", [DATA_STRUCTURE])

    first = _upload(client, DATA_STRUCTURE, "dup.txt", b"identical bytes here")
    assert first.status_code == 200, first.text

    again = _upload(client, DATA_STRUCTURE, "dup.txt", b"identical bytes here")
    assert again.status_code == 409, again.text
    assert again.json()["detail"]["code"] == "MATERIAL_DUPLICATE"
    assert again.json()["detail"]["existing_material_id"] == first.json()["material_id"]
