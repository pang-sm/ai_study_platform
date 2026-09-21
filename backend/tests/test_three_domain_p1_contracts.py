"""THREE_DOMAIN_PRODUCTIZATION_P1 — backend contracts for course / exam / programming.

WHAT THESE TESTS HOLD
---------------------
1. The three Learning Spaces are isolated in the canonical infrastructure: a course read
   cannot see exam or programming facts, a programming read cannot see course or exam
   facts, and two courses of the same learner cannot see each other.
2. The programming space records which LANGUAGE each fact belongs to, and never reports
   another language's context.
3. The study plan is gated by the unified subscription tier through ONE
   ``FEATURE_CAPABILITY`` entry, in every direction.
4. The state projections report recorded facts and nothing else — no mastery probability,
   no readiness score, no model output.
5. Dataset provenance stays fail-closed: DEMO and TEST facts never satisfy the readiness
   gate, whatever surface wrote them.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported. Nothing here can reach ``backend/app.db``.
"""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from conftest import grant_unified_tier, register_and_login

from core.learning_context import LearningContext, ServiceNamespace
from data_plane.models import LearningEvent
from data_plane.origin import DEMO, LEARNER, TEST as TEST_ORIGIN
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import taxonomy
from learning.spaces.course_learning.context import build_course_context
from learning.spaces.programming import context as programming_context
from learning.spaces.programming import events as programming_events
from models import AIGeneratedQuestion, CourseLearningPreference, User

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

MOMENT = datetime(2026, 9, 20, 3, 0, 0)

# A field whose NAME says "this is a prediction / an estimate of the learner" must never
# appear in a state projection. Matched on key TOKENS (split on "." and "_") rather than as
# substrings, so `capability` — the legitimate AI capability label — is not read as
# `ability`. Only keys are inspected: a `semantics` sentence stating that no probability is
# produced is text, not a field.
FORBIDDEN_STATE_KEY_TOKENS = frozenset({
    "probability", "probabilities", "prob", "predicted", "prediction", "predictions",
    "readiness", "confidence", "weakness", "weaknesses", "estimate", "estimated",
    "forecast", "mastery", "ability", "theta",
})


# ---------------------------------------------------------------- helpers

def _key_paths(payload, prefix=""):
    out: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            out.append(f"{prefix}{key}")
            out.extend(_key_paths(value, f"{prefix}{key}."))
    elif isinstance(payload, list):
        for item in payload:
            out.extend(_key_paths(item, prefix))
    return out


def assert_no_prediction_fields(payload):
    hits = []
    for path in _key_paths(payload):
        tokens = {t for chunk in path.lower().split(".") for t in chunk.split("_") if t}
        offenders = tokens & FORBIDDEN_STATE_KEY_TOKENS
        if offenders:
            hits.append((path, sorted(offenders)))
    assert not hits, f"state exposes a prediction-shaped field: {hits}"


def _user(db, username) -> User:
    user = User(username=username, hashed_password="x", grade="freshman", major="cs")
    db.add(user)
    db.commit()
    return user


def _own_course(db, username, course_id):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _course_context(user, course_id):
    return build_course_context(user, course_id=course_id)


def _exam_context(user, module):
    return LearningContext(user_id=user.id, service_namespace=ServiceNamespace.EXAM_PREP,
                           subject_key=module, exam_subject_id="cs_408",
                           exam_module_id=module)


def _record(db, user, *, namespace, qid, correct, source_type, context, submitted_at,
            answer="A", source_id=None):
    """Record ONE factual attempt through the canonical Practice Core.

    This exercises the real write path (including the wrong-answer projection and the
    LearningEvent emitter), so the isolation these tests assert is the isolation the
    product actually produces — not a property of a test double.

    The source identity is derived from the CONTEXT, exactly as a real adapter does: two
    courses reusing one question id are two different attempts, and a source identity that
    ignored the course would be refused as a conflicting overwrite of history.
    """
    scope = (context.course_id or context.subject_key
             or context.programming_language or "-")
    ref = QuestionRef(
        source_type=source_type, source_id=str(qid),
        service_namespace=ServiceNamespace(namespace),
        context=dict(context.to_dict()),
        raw_source={"table": "p1_test", "qid": qid})
    session, _ = practice_service.ensure_legacy_session(
        db, user, namespace, source_type="p1_test",
        source_session_key=f"{namespace}:{scope}", mode="p1", context=context,
        started_at=None)
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=correct, submitted_at=submitted_at,
        context=context,
        source=practice_service.SourceIdentity("p1_test_attempt",
                                               source_id or f"{namespace}:{scope}:{qid}",
                                               f"{qid}:0"))


def _stub_exercise(exercise_id, language):
    """The minimal exercise shape the programming emitters read (id + language)."""
    return SimpleNamespace(id=exercise_id, language=language)


# ================================================================ 1. course records


def test_course_records_never_leak_exam_or_programming(client, db_session):
    profile = register_and_login(client, "p1_course_isolation")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    _own_course(db_session, user.username, "data_structures")

    course_ctx = _course_context(user, "data_structures")
    exam_ctx = _exam_context(user, "operating_system")
    prog_ctx = programming_context.build_programming_context(user, language="Python",
                                                             exercise_id=101)

    _record(db_session, user, namespace=COURSE, qid=1, correct=True,
            source_type=QuestionSourceType.AI_GENERATED, context=course_ctx,
            submitted_at=MOMENT)
    _record(db_session, user, namespace=EXAM, qid=2, correct=True,
            source_type=QuestionSourceType.STATIC_QUESTION_BANK, context=exam_ctx,
            submitted_at=MOMENT + timedelta(minutes=1))
    _record(db_session, user, namespace=PROG, qid=3, correct=True,
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE, context=prog_ctx,
            submitted_at=MOMENT + timedelta(minutes=2))

    page = client.get("/course-learning/courses/data_structures/records").json()
    namespaces = {record["service_namespace"] for record in page["records"]}
    assert namespaces == {COURSE}, namespaces
    assert all(record["context"].get("course_id") == "data_structures"
               for record in page["records"])

    summary = client.get("/course-learning/courses/data_structures/records/summary").json()
    assert summary["service_namespace"] == COURSE
    assert summary["course_id"] == "data_structures"
    # the exam and programming facts exist for this learner — they are simply not HIS
    # course's history, and must not be counted here
    assert summary["by_event_type"].get("code_submitted") is None
    assert summary["total_events"] == len(page["records"])


def test_two_courses_of_one_learner_do_not_cross(client, db_session):
    profile = register_and_login(client, "p1_two_courses")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    _own_course(db_session, user.username, "course_alpha")
    _own_course(db_session, user.username, "course_beta")

    # the SAME question id in both courses: identity must include the course
    for index, course in enumerate(("course_alpha", "course_beta")):
        _record(db_session, user, namespace=COURSE, qid=77, correct=False,
                source_type=QuestionSourceType.AI_GENERATED,
                context=_course_context(user, course),
                submitted_at=MOMENT + timedelta(minutes=index))

    alpha = client.get("/course-learning/courses/course_alpha/records").json()
    beta = client.get("/course-learning/courses/course_beta/records").json()
    assert {r["context"]["course_id"] for r in alpha["records"]} == {"course_alpha"}
    assert {r["context"]["course_id"] for r in beta["records"]} == {"course_beta"}

    alpha_state = client.get("/course-learning/courses/course_alpha/state").json()
    beta_state = client.get("/course-learning/courses/course_beta/state").json()
    assert alpha_state["wrong_answers"]["active"] == 1
    assert beta_state["wrong_answers"]["active"] == 1

    # the two wrong-answer states are DISTINCT rows, not one shared state
    alpha_wrong = client.get(
        "/course-learning/courses/course_alpha/wrong-answers").json()
    beta_wrong = client.get("/course-learning/courses/course_beta/wrong-answers").json()
    assert alpha_wrong["total"] == 1 and beta_wrong["total"] == 1
    assert (alpha_wrong["items"][0]["wrong_record_id"]
            != beta_wrong["items"][0]["wrong_record_id"])

    # a course the learner does not have is a 404, not an empty page
    assert client.get("/course-learning/courses/course_gamma/records").status_code == 404
    assert client.get("/course-learning/courses/course_gamma/state").status_code == 404


def test_course_wrong_answer_detail_is_course_scoped(client, db_session):
    profile = register_and_login(client, "p1_course_wrong_detail")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    _own_course(db_session, user.username, "course_alpha")
    _own_course(db_session, user.username, "course_beta")

    alpha_question = AIGeneratedQuestion(
        username=user.username, subject_key="course_alpha", question_type="choice",
        stem="alpha stem", options_json=json.dumps({"A": "1", "B": "2"}),
        standard_answer="A", analysis="alpha analysis")
    beta_question = AIGeneratedQuestion(
        username=user.username, subject_key="course_beta", question_type="choice",
        stem="beta stem", options_json=json.dumps({"A": "1", "B": "2"}),
        standard_answer="B", analysis="beta analysis")
    db_session.add_all([alpha_question, beta_question])
    db_session.commit()

    _record(db_session, user, namespace=COURSE, qid=alpha_question.id, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=_course_context(user, "course_alpha"), submitted_at=MOMENT)
    _record(db_session, user, namespace=COURSE, qid=beta_question.id, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=_course_context(user, "course_beta"),
            submitted_at=MOMENT + timedelta(minutes=1))

    page = client.get("/course-learning/courses/course_alpha/wrong-answers").json()
    assert page["total"] == 1
    record = page["items"][0]
    assert record["course_id"] == "course_alpha"
    assert record["stem"] == "alpha stem"
    assert record["status"] == "active"
    assert record["repeat_wrong_count"] == 1

    detail = client.get(
        f"/course-learning/courses/course_alpha/wrong-answers/"
        f"{record['wrong_record_id']}").json()
    assert detail["attempt_history"][-1]["correct"] is False

    # the SAME record id read through the OTHER course's path must not resolve
    assert client.get(
        f"/course-learning/courses/course_beta/wrong-answers/"
        f"{record['wrong_record_id']}").status_code == 404


def test_course_state_reports_facts_and_no_prediction(client, db_session):
    profile = register_and_login(client, "p1_course_state")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    _own_course(db_session, user.username, "course_alpha")

    _record(db_session, user, namespace=COURSE, qid=11, correct=True,
            source_type=QuestionSourceType.AI_GENERATED,
            context=_course_context(user, "course_alpha"), submitted_at=MOMENT)
    _record(db_session, user, namespace=COURSE, qid=12, correct=False,
            source_type=QuestionSourceType.AI_GENERATED,
            context=_course_context(user, "course_alpha"),
            submitted_at=MOMENT + timedelta(minutes=1))

    state = client.get("/course-learning/courses/course_alpha/state").json()
    assert state["service_namespace"] == COURSE
    assert state["course"]["course_id"] == "course_alpha"
    assert state["practice"]["attempts"] == 2
    assert state["practice"]["factual_correct"] == 1
    assert state["practice"]["factual_incorrect"] == 1
    assert state["wrong_answers"]["active"] == 1
    assert "state_semantics" in state
    assert_no_prediction_fields(state)


# ================================================================ 2. programming


def test_programming_records_never_leak_course_or_exam(client, db_session):
    profile = register_and_login(client, "p1_prog_isolation")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    _own_course(db_session, user.username, "data_structures")

    _record(db_session, user, namespace=COURSE, qid=21, correct=True,
            source_type=QuestionSourceType.AI_GENERATED,
            context=_course_context(user, "data_structures"), submitted_at=MOMENT)
    _record(db_session, user, namespace=EXAM, qid=22, correct=True,
            source_type=QuestionSourceType.STATIC_QUESTION_BANK,
            context=_exam_context(user, "data_structure"),
            submitted_at=MOMENT + timedelta(minutes=1))
    _record(db_session, user, namespace=PROG, qid=23, correct=True,
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
            context=programming_context.build_programming_context(
                user, language="Python", exercise_id=55),
            submitted_at=MOMENT + timedelta(minutes=2))

    page = client.get("/programming/records").json()
    assert page["records"], "the programming submission must be visible"
    assert {r["service_namespace"] for r in page["records"]} == {PROG}

    summary = client.get("/programming/records/summary").json()
    assert summary["service_namespace"] == PROG
    assert summary["programming_submissions"] == 1
    # `practice_attempts` counts OBJECTIVE question attempts (question_answered /
    # course_practice). A judged submission is reported by `programming_submissions`, so
    # the two counters are disjoint by design — a programming scope legitimately reports 0
    # objective attempts. Asserted so the split is visible rather than mistaken for a gap.
    assert summary["practice_attempts"] == 0
    assert summary["by_event_type"] == {"code_submitted": 1}
    # the course and exam attempts exist for this learner and are simply not programming
    assert summary["total_events"] == 1


def test_programming_records_carry_their_own_language_only(client, db_session):
    profile = register_and_login(client, "p1_prog_language")
    user = db_session.query(User).filter(User.id == profile["id"]).one()

    # A submission per language, through the real judge-mirroring path.
    _record(db_session, user, namespace=PROG, qid=301, correct=True,
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
            context=programming_context.build_programming_context(
                user, language="Python", exercise_id=301),
            submitted_at=MOMENT)
    _record(db_session, user, namespace=PROG, qid=302, correct=True,
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
            context=programming_context.build_programming_context(
                user, language="C++", exercise_id=302),
            submitted_at=MOMENT + timedelta(minutes=1))

    # …and a run/test per language, through the canonical emitters.
    programming_events.emit_exercise_activity(
        user_id=user.id, exercise=_stub_exercise(301, "Python"), action="test",
        occurred_at=MOMENT + timedelta(minutes=2), observed={"passed_count": 3,
                                                             "total_count": 5})
    programming_events.emit_exercise_activity(
        user_id=user.id, exercise=_stub_exercise(302, "C++"), action="run",
        occurred_at=MOMENT + timedelta(minutes=3), observed={"exit_code": 0})

    page = client.get("/programming/records", params={"limit": 50}).json()
    by_type: dict[str, list[dict]] = {}
    for record in page["records"]:
        by_type.setdefault(record["event_type"], []).append(record)

    assert set(by_type) == {"code_submitted", "code_run", "code_tested"}
    for record in page["records"]:
        context = record["context"]
        exercise = context["exercise_id"]
        expected = "Python" if exercise == 301 else "C++"
        assert context["programming_language"] == expected, record
        # the language is a property of the EXERCISE, never of the reader's last action
        assert context.get("course_id") is None
        assert context.get("subject_key") is None

    tested = by_type["code_tested"][0]
    assert tested["summary"]["passed_count"] == 3
    assert tested["summary"]["total_count"] == 5
    # a run reports no verdict, and neither run nor test claims to be a submission
    assert tested["summary"].get("correct") is None
    assert by_type["code_run"][0]["summary"].get("correct") is None
    assert by_type["code_submitted"][0]["summary"]["correct"] is True


def test_programming_state_reports_facts_and_no_prediction(client, db_session):
    profile = register_and_login(client, "p1_prog_state")
    user = db_session.query(User).filter(User.id == profile["id"]).one()

    _record(db_session, user, namespace=PROG, qid=401, correct=False,
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
            context=programming_context.build_programming_context(
                user, language="Java", exercise_id=401),
            submitted_at=MOMENT)
    programming_events.emit_exercise_started(
        user_id=user.id, exercise=_stub_exercise(401, "Java"), occurred_at=MOMENT)

    state = client.get("/programming/state").json()
    assert state["service_namespace"] == PROG
    assert state["practice"]["attempts"] == 1
    assert state["practice"]["factual_incorrect"] == 1
    assert state["practice"]["factual_correct"] == 0
    assert any(record["event_type"] == "exercise_started"
               for record in state["recent_activity"])
    assert "state_semantics" in state
    assert_no_prediction_fields(state)


def test_exercise_events_are_per_learner_and_deduped_where_they_should_be(db_session):
    """Event identity is GLOBAL, so the learner must be part of the source id.

    Two learners performing the SAME action on the SAME exercise produce two facts. A
    source id that omitted the learner would make the second one collide with the first and
    vanish — silently, because the insert is INSERT OR IGNORE.
    """
    user = _user(db_session, "p1_start_dedupe")
    other = _user(db_session, "p1_start_other_learner")
    exercise = _stub_exercise(501, "Python")

    programming_events.emit_exercise_started(user_id=user.id, exercise=exercise,
                                             occurred_at=MOMENT)
    programming_events.emit_exercise_started(
        user_id=user.id, exercise=exercise, occurred_at=MOMENT + timedelta(hours=3))
    rows = (db_session.query(LearningEvent)
            .filter(LearningEvent.user_id == user.id,
                    LearningEvent.event_type == "exercise_started").all())
    assert len(rows) == 1, "opening the same exercise again is not a second start"

    programming_events.emit_exercise_started(user_id=other.id, exercise=exercise,
                                             occurred_at=MOMENT)
    rows = (db_session.query(LearningEvent)
            .filter(LearningEvent.event_type == "exercise_started",
                    LearningEvent.user_id.in_([user.id, other.id])).all())
    assert len(rows) == 2, "two learners starting one exercise are two facts"

    # the SAME instant for two learners must still be two runs, not one collapsed event
    for learner in (user, other):
        programming_events.emit_exercise_activity(
            user_id=learner.id, exercise=exercise, action="run", occurred_at=MOMENT,
            observed={"exit_code": 0})
    runs = (db_session.query(LearningEvent)
            .filter(LearningEvent.event_type == "code_run",
                    LearningEvent.user_id.in_([user.id, other.id])).all())
    assert len(runs) == 2, "a run belongs to ONE learner"
    assert len({run.event_id for run in runs}) == 2


# ================================================================ 3. service_key


def test_every_event_is_filed_under_its_canonical_service_key(db_session):
    user = _user(db_session, "p1_service_key")
    _own_course(db_session, user.username, "course_alpha")

    contexts = {
        COURSE: _course_context(user, "course_alpha"),
        EXAM: _exam_context(user, "operating_system"),
        PROG: programming_context.build_programming_context(
            user, language="Python", exercise_id=601),
    }
    source_types = {
        COURSE: QuestionSourceType.AI_GENERATED,
        EXAM: QuestionSourceType.STATIC_QUESTION_BANK,
        PROG: QuestionSourceType.PROGRAMMING_EXERCISE,
    }
    for index, namespace in enumerate((COURSE, EXAM, PROG)):
        _record(db_session, user, namespace=namespace, qid=600 + index, correct=True,
                source_type=source_types[namespace], context=contexts[namespace],
                submitted_at=MOMENT + timedelta(minutes=index))

    rows = (db_session.query(LearningEvent)
            .filter(LearningEvent.user_id == user.id).all())
    assert {row.service_key for row in rows} == {COURSE, EXAM, PROG}

    for row in rows:
        assert row.service_key in taxonomy.spec_for(row.event_type).namespaces, row.event_type
        # the namespace is the CANONICAL value, never a legacy alias
        assert row.service_key == row.service_key.strip().lower()
        assert row.service_key in (COURSE, EXAM, PROG)

    # a course fact carries the course; an exam or programming fact does not
    course_rows = [r for r in rows if r.service_key == COURSE]
    assert course_rows and all(r.course_id == "course_alpha" for r in course_rows)
    assert all(r.course_id is None for r in rows if r.service_key == PROG)


# ================================================================ 4. plan entitlement


def test_the_plan_gate_is_one_unified_capability_in_every_direction(client, db_session):
    from membership import get_feature_entitlement
    from usage import capabilities

    assert capabilities.FEATURE_CAPABILITY["learning_plan"] == "planning.generate"

    profile = register_and_login(client, "p1_plan_gate")
    user = db_session.query(User).filter(User.id == profile["id"]).one()

    # FREE: denied in every direction, with the standard upgrade contract
    for service_key in ("programming", "course_learning", "exam_11408"):
        verdict = get_feature_entitlement(user, db_session, service_key, "learning_plan")
        assert verdict["allowed"] is False, service_key
        assert verdict["required_tier"] == "standard"
        assert verdict["required_capability"] == "planning.generate"

    denied = client.get("/programming/plan")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "FEATURE_REQUIRES_UPGRADE"
    assert denied.json()["detail"]["required_capability"] == "planning.generate"

    # …and the WRITE routes are gated too, not just the read
    assert client.post("/programming/plan/tasks",
                       json={"title": "x"}).status_code == 403

    # STANDARD and ADVANCED: allowed, decided by the TIER alone
    for tier in ("standard", "advanced"):
        grant_unified_tier(db_session, user.username, tier)
        allowed = client.get("/programming/plan")
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["entitlement"]["current_tier"] == tier
        assert allowed.json()["entitlement"]["allowed"] is True

        created = client.post("/programming/plan/tasks",
                              json={"title": f"{tier} 练习", "task_type": "exercise"})
        assert created.status_code == 200, created.text
        assert created.json()["subject_key"].startswith("programming:")
        assert created.json()["task_type"] == "exercise"

        task_id = created.json()["id"]
        updated = client.patch(f"/programming/plan/tasks/{task_id}",
                               json={"status": "completed"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "completed"
        assert client.delete(f"/programming/plan/tasks/{task_id}").status_code == 200


def test_programming_plan_rejects_foreign_task_types_and_foreign_tasks(client, db_session):
    profile = register_and_login(client, "p1_plan_scope")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    grant_unified_tier(db_session, user.username, "standard")

    from models import ExamStudyPlanTask

    # a COURSE plan task must not be reachable through the programming plan path
    db_session.add(ExamStudyPlanTask(
        username=user.username, subject_key="course_learning:data_structures",
        title="课程任务", task_type="knowledge", status="not_started"))
    db_session.commit()
    foreign = (db_session.query(ExamStudyPlanTask)
               .filter(ExamStudyPlanTask.subject_key == "course_learning:data_structures")
               .one())

    assert client.patch(f"/programming/plan/tasks/{foreign.id}",
                        json={"status": "completed"}).status_code == 404
    assert client.delete(f"/programming/plan/tasks/{foreign.id}").status_code == 404

    assert client.post("/programming/plan/tasks",
                       json={"title": "bad", "task_type": "chapter_practice"}
                       ).status_code == 400


# ================================================================ 5. provenance


def test_demo_and_test_facts_never_satisfy_the_readiness_gate(db_session, monkeypatch):
    from science import kt_dataset

    user = _user(db_session, "p1_origin_gate")
    _own_course(db_session, user.username, "course_alpha")

    def emit(origin_value, minute):
        monkeypatch.setenv("DATA_ORIGIN", origin_value)
        # A knowledge point is carried so the fact is KT-ELIGIBLE on its own merits: the
        # exclusion under test must be the ORIGIN, not a missing concept reference.
        context = build_course_context(user, course_id="course_alpha",
                                       knowledge_point_id=f"kp-{900 + minute}")
        return _record(
            db_session, user, namespace=COURSE, qid=900 + minute, correct=True,
            source_type=QuestionSourceType.AI_GENERATED,
            context=context, submitted_at=MOMENT + timedelta(minutes=minute))

    real = emit(LEARNER, 0)
    demo = emit(DEMO, 1)
    tested = emit(TEST_ORIGIN, 2)
    monkeypatch.delenv("DATA_ORIGIN", raising=False)

    # the origin was stamped by the WRITER, from the process it ran in
    assert real.attempt.data_origin == LEARNER
    assert demo.attempt.data_origin == DEMO
    assert tested.attempt.data_origin == TEST_ORIGIN

    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id).all())
    assert {event.event_type for event in events} == {"question_answered"}
    assert {event.data_origin for event in events} == {LEARNER, DEMO, TEST_ORIGIN}

    body = kt_dataset.build(db_session, service_namespace=COURSE, user_id=user.id)
    exported = [i for s in body.get("sequences") or []
                for i in s.get("interactions") or []]
    assert len(exported) == 1, "only the LEARNER fact may reach the training export"
    assert body["excluded"]["DATASET_ORIGIN_DEMO"] == 1
    assert body["excluded"]["DATASET_ORIGIN_TEST"] == 1

    audit = kt_dataset.audit(db_session, service_namespace=COURSE, user_id=user.id)
    # three facts were written; exactly one may count toward readiness
    assert audit["readiness"]["interactions_collected"] == 1
    assert audit["readiness"]["native_concept_identity"] == "AVAILABLE"
    assert audit["excluded"]["DATASET_ORIGIN_DEMO"] == 1
    assert audit["excluded"]["DATASET_ORIGIN_TEST"] == 1


def test_a_learner_still_sees_their_own_demo_history_in_records(client, db_session,
                                                               monkeypatch):
    """Provenance decides TRAINING admissibility, not whether a fact is study history.

    Stated as a test because the two are easy to conflate: filtering a learner's own demo
    rehearsal out of their timeline would be a different product decision, and this change
    makes neither.
    """
    profile = register_and_login(client, "p1_origin_records")
    user = db_session.query(User).filter(User.id == profile["id"]).one()
    _own_course(db_session, user.username, "course_alpha")

    monkeypatch.setenv("DATA_ORIGIN", DEMO)
    _record(db_session, user, namespace=COURSE, qid=950, correct=True,
            source_type=QuestionSourceType.AI_GENERATED,
            context=_course_context(user, "course_alpha"), submitted_at=MOMENT)
    monkeypatch.delenv("DATA_ORIGIN", raising=False)

    page = client.get("/course-learning/courses/course_alpha/records").json()
    assert len(page["records"]) == 1
