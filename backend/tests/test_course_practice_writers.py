"""STEP 7G PART A: the three course practice writers → shared Practice Core.

Semantics established BEFORE migrating (not guessed from endpoint names):

    POST /practice/questions/{id}/attempts  → a real answer with a server-derived
                                              judgement; its own legacy row
    POST /practice/questions/{id}/feedback  → asks for AI feedback on an answer;
                                              self_result is "unknown" (no judgement);
                                              its own legacy row
    POST /practice/submit-result            → a completed practice BATCH whose durable
                                              write is ONE summary row; the per-question
                                              correctness is client-asserted and never
                                              persisted

Each legacy row is mirrored 1:1 on its own id, so one real submission yields exactly one
canonical attempt — the same identity the STEP7D backfill uses.
"""
import json

import main
from conftest import register_and_login
from data_plane.models import LearningEvent
from learning.practice import backfill, service as practice_service
from learning.practice.adapters import course as course_adapter
from learning.practice.adapters.base import safe_mirror
from learning.wrong_answers import service as wrong_service
from models import Question, QuestionAttempt, UserKnowledgeProgress


def _make_question(db, username, *, course_id="ds", kp_id=77, qtype="choice",
                   answer="A") -> Question:
    q = Question(username=username, course_id=course_id, knowledge_point_id=kp_id,
                 type=qtype, title="进程与线程", content="题干",
                 options=json.dumps([{"label": "A", "text": "资源分配单位"}]),
                 answer=answer, explanation="解析")
    db.add(q)
    db.commit()
    return q


def _attempt(client, question_id, username, user_answer="A"):
    return client.post(f"/practice/questions/{question_id}/attempts",
                       json={"username": username, "question_id": question_id,
                             "user_answer": user_answer})


def _feedback(client, question_id, username, user_answer="A"):
    return client.post(f"/practice/questions/{question_id}/feedback",
                       json={"username": username, "user_answer": user_answer})


def _canonical(db, user_id):
    return practice_service.list_attempts(db, user_id, service_namespace="course_learning")


def _events(db, user_id, event_type=None):
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


# ---------------------------------------------------------------- A1 semantics

def test_attempts_endpoint_creates_exactly_one_canonical_attempt(client, db_session):
    user = register_and_login(client, "cpw1")
    q = _make_question(db_session, "cpw1")

    r = _attempt(client, q.id, "cpw1")
    assert r.status_code == 200, r.text
    assert r.json()["attempt"]["self_result"] == "correct"

    attempts = _canonical(db_session, user["id"])
    assert len(attempts) == 1
    a = attempts[0]
    assert a.correct is True
    assert a.question_source_id == str(q.id)
    assert a.service_namespace == "course_learning"
    assert a.source_attempt_type == "question_attempt"
    assert a.source_attempt_id == str(r.json()["attempt"]["id"])
    context = json.loads(a.context_json)
    assert context["course_id"] == "ds"
    assert context["service_namespace"] == "course_learning"


def test_incorrect_answer_maps_to_false_not_none(client, db_session):
    user = register_and_login(client, "cpw2")
    q = _make_question(db_session, "cpw2")
    assert _attempt(client, q.id, "cpw2", "B").status_code == 200
    assert _canonical(db_session, user["id"])[0].correct is False


def test_two_real_submissions_yield_two_canonical_attempts(client, db_session):
    """Two distinct answers are two distinct facts — never collapsed, never tripled."""
    user = register_and_login(client, "cpw3")
    q = _make_question(db_session, "cpw3")
    _attempt(client, q.id, "cpw3", "B")
    _attempt(client, q.id, "cpw3", "A")
    attempts = _canonical(db_session, user["id"])
    assert len(attempts) == 2
    assert {a.correct for a in attempts} == {False, True}


def test_feedback_endpoint_mirrors_without_inventing_a_judgement(client, db_session,
                                                                 monkeypatch):
    """feedback creates its own legacy row but carries NO factual correctness."""
    user = register_and_login(client, "cpw4")
    q = _make_question(db_session, "cpw4")
    monkeypatch.setattr(main, "_course_ai_content",
                        lambda *a, **k: "思路基本正确，注意区分资源与调度。")

    r = _feedback(client, q.id, "cpw4", "A")
    assert r.status_code == 200, r.text

    attempts = _canonical(db_session, user["id"])
    assert len(attempts) == 1
    assert attempts[0].correct is None            # never coerced to False
    assert json.loads(attempts[0].result_json)["feedback_present"] is True


def test_endpoints_do_not_double_count_each_others_facts(client, db_session, monkeypatch):
    """attempts + feedback = two distinct legacy rows = two canonical attempts."""
    user = register_and_login(client, "cpw5")
    q = _make_question(db_session, "cpw5")
    monkeypatch.setattr(main, "_course_ai_content", lambda *a, **k: "反馈内容")
    _attempt(client, q.id, "cpw5", "A")
    _feedback(client, q.id, "cpw5", "A")

    rows = (db_session.query(QuestionAttempt)
            .filter(QuestionAttempt.username == "cpw5").all())
    assert len(rows) == 2
    assert len(_canonical(db_session, user["id"])) == 2


def test_submit_result_mirrors_a_session_not_client_asserted_attempts(client, db_session):
    user = register_and_login(client, "cpw6")
    _make_question(db_session, "cpw6")
    r = client.post("/practice/submit-result", json={
        "username": "cpw6", "course_id": "ds", "duration_seconds": 300,
        "question_results": [{"question_id": 1, "is_correct": True},
                             {"question_id": 2, "is_correct": False}]})
    assert r.status_code == 200, r.text

    # a session-level fact — and deliberately NO per-question attempts built from
    # client-asserted correctness
    assert _canonical(db_session, user["id"]) == []
    sessions = practice_service.list_sessions(db_session, user["id"],
                                              service_namespace="course_learning")
    assert len(sessions) == 1
    assert sessions[0].status == "completed"
    assert sessions[0].source_type == "practice_batch_result"


def test_two_batches_are_two_sessions(client, db_session):
    user = register_and_login(client, "cpw7")
    payload = {"username": "cpw7", "course_id": "ds", "duration_seconds": 60,
               "question_results": [{"question_id": 1, "is_correct": True}]}
    client.post("/practice/submit-result", json=payload)
    client.post("/practice/submit-result", json=payload)
    sessions = practice_service.list_sessions(db_session, user["id"],
                                              service_namespace="course_learning")
    assert len(sessions) == 2


# ---------------------------------------------------------------- A6/A7 effects

def test_wrong_then_correct_resolves_without_wrong_count_inflation(client, db_session):
    user = register_and_login(client, "cpw8")
    q = _make_question(db_session, "cpw8")
    _attempt(client, q.id, "cpw8", "B")                        # wrong
    states = wrong_service.list_states(db_session, user["id"],
                                       service_namespace="course_learning")
    assert len(states) == 1 and states[0].status == "active"
    assert states[0].wrong_count == 1

    _attempt(client, q.id, "cpw8", "A")                        # correct
    # the endpoint wrote through its OWN session, so drop this session's identity map
    # before re-reading the state
    db_session.expire_all()
    states = wrong_service.list_states(db_session, user["id"],
                                       service_namespace="course_learning")
    assert len(states) == 1 and states[0].status == "resolved"
    assert states[0].wrong_count == 1                          # not inflated


def test_feedback_row_never_creates_a_wrong_state(client, db_session, monkeypatch):
    """correct=None must not create an error state (A3)."""
    user = register_and_login(client, "cpw9")
    q = _make_question(db_session, "cpw9")
    monkeypatch.setattr(main, "_course_ai_content", lambda *a, **k: "反馈")
    assert _feedback(client, q.id, "cpw9", "B").status_code == 200
    assert wrong_service.list_states(db_session, user["id"],
                                     service_namespace="course_learning") == []


def test_knowledge_delta_is_applied_once(client, db_session):
    """The mirror must NOT re-apply the domain's delta: +8 stays +8, not +16."""
    register_and_login(client, "cpw10")
    from models import KnowledgePoint
    db_session.add(KnowledgePoint(username="cpw10", course_id="ds", node_key="kp",
                                  title="进程", level=1))
    db_session.commit()
    kp = (db_session.query(KnowledgePoint)
          .filter(KnowledgePoint.username == "cpw10").first())
    q = _make_question(db_session, "cpw10", kp_id=kp.id)
    _attempt(client, q.id, "cpw10", "A")
    row = (db_session.query(UserKnowledgeProgress)
           .filter(UserKnowledgeProgress.username == "cpw10").first())
    assert row is not None
    assert row.mastery_score == 8
    assert row.practice_count == 1


def test_practice_event_is_not_duplicated(client, db_session):
    user = register_and_login(client, "cpw11")
    q = _make_question(db_session, "cpw11")
    _attempt(client, q.id, "cpw11", "A")
    events = [e for e in _events(db_session, user["id"], "question_answered")
              if e.source_type == "question_attempt"]
    assert len(events) == 1


# ---------------------------------------------------------------- A8 recovery

def test_mirror_failure_is_recoverable_from_the_legacy_row(client, db_session, monkeypatch):
    user = register_and_login(client, "cpw12")
    q = _make_question(db_session, "cpw12")

    def boom(*_a, **_kw):
        raise RuntimeError("mirror unavailable")

    legacy = (db_session.query(QuestionAttempt)
              .filter(QuestionAttempt.username == "cpw12").first())
    assert legacy is None                       # nothing written yet by this test
    # write the legacy row the way the endpoint does, then force the mirror to fail
    legacy = QuestionAttempt(username="cpw12", question_id=q.id, course_id="ds",
                             knowledge_point_id=77, user_answer="B",
                             self_result="incorrect")
    db_session.add(legacy)
    db_session.commit()

    fake_user = type("U", (), {"id": user["id"], "username": "cpw12"})()
    with monkeypatch.context() as patched:
        patched.setattr(practice_service, "ensure_legacy_session", boom)
        failed = safe_mirror(
            "course.question_attempt", "question_attempt", legacy.id,
            lambda: course_adapter.mirror_question_attempt(db_session, fake_user,
                                                           legacy, q),
            db=db_session)
    assert failed.failed == 1
    assert _canonical(db_session, user["id"]) == []

    # the legacy row is still the durable fact; backfill rebuilds the canonical attempt
    report = backfill.run_backfill(db_session, sources=["question_attempts"])
    assert report["per_source"].get("question_attempts", {}).get("mirrored", 0) >= 1
    rebuilt = _canonical(db_session, user["id"])
    assert len(rebuilt) == 1
    assert rebuilt[0].correct is False
    assert rebuilt[0].source_attempt_id == str(legacy.id)


def test_backfill_uses_the_same_identity_as_the_live_mirror(client, db_session):
    user = register_and_login(client, "cpw13")
    q = _make_question(db_session, "cpw13")
    _attempt(client, q.id, "cpw13", "B")
    assert len(_canonical(db_session, user["id"])) == 1

    report = backfill.run_backfill(db_session, sources=["question_attempts"])
    assert report["totals"]["mirrored"] == 0           # already canonical
    assert len(_canonical(db_session, user["id"])) == 1


def test_self_result_mapping_is_shared_with_the_backfill():
    for value, expected in (("correct", True), ("incorrect", False), ("wrong", False),
                            ("unknown", None), (None, None), ("", None),
                            ("CORRECT", True)):
        assert course_adapter.self_result_to_correct(value) is expected
