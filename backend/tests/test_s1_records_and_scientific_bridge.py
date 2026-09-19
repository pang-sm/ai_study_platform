"""ACCEL SPRINT S1 — Learning Record closure + Scientific Runtime product bridge.

Doubles are placed BELOW the HTTP/runtime boundary only:

  * the runtime-side double stubs ``runtime_bridge.replay_state`` (inside the runtime
    service), so the REAL FastAPI runtime application still validates and serializes;
  * the product-side double is an ``httpx.MockTransport`` (the transport layer), so the
    real request building, timeout, status handling and response parsing all run.

No paid provider is called, and the StudentTwin scientific formula is never reimplemented.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from conftest import register_and_login
from fastapi.testclient import TestClient

import database
from core import timeutil
from core.learning_context import ServiceNamespace
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import producers, service as records_service, taxonomy
from learning.wrong_answers import service as wrong_service
from models import ExamQuestionBank, User
from science import client as sci_client
from science import misconception, student_twin, tutor_policy

EXAM = ServiceNamespace.EXAM_PREP.value
COURSE = ServiceNamespace.COURSE_LEARNING.value

# The academic moment every producer in the drift test is asked to record.
MOMENT = datetime(2026, 9, 19, 3, 4, 5, 250000)          # naive UTC wall-clock
MOMENT_EPOCH = MOMENT.replace(tzinfo=timezone.utc).timestamp()


# ---------------------------------------------------------------- helpers

def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def events_for(db, user_id, event_type=None):
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


def runtime_app():
    """The REAL scientific runtime application, imported from its own package."""
    root = Path(__file__).resolve().parents[2]
    path = str(root / "scientific_runtime_service")
    if path not in sys.path:
        sys.path.insert(0, path)
    from app.main import app  # noqa: PLC0415 — deliberate late import
    return app


def runtime_transport(replay_state=None):
    """A MockTransport that forwards to the real runtime app.

    ``replay_state`` doubles the scientific component INSIDE the runtime; everything
    between the product client and that function is the real code path.
    """
    test_client = TestClient(runtime_app())
    from app import runtime_bridge  # noqa: PLC0415

    original = runtime_bridge.replay_state
    if replay_state is not None:
        runtime_bridge.replay_state = replay_state

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(
            request.method, request.url.path, content=request.content,
            headers={"content-type": "application/json"})
        return httpx.Response(response.status_code, content=response.content,
                              headers={"content-type": "application/json"})

    def restore():
        runtime_bridge.replay_state = original

    return httpx.MockTransport(handler), restore


def fake_twin_state(user_ref: str, events) -> dict:
    """A deterministic stand-in for the scientific replay result."""
    concepts = {}
    for event in events:
        key = event.concept_ref or "unmapped"
        entry = concepts.setdefault(key, {"exposure_count": 0, "correct_count": 0})
        entry["exposure_count"] += 1
        entry["correct_count"] += 1 if event.correct else 0
    return {"user_id": user_ref, "concepts": concepts,
            "global_ability": 0.0, "events_seen": len(events)}


def product_client(transport):
    return sci_client.ScientificClient(base_url="http://runtime.test",
                                       timeout=5.0, transport=transport)


def with_client(monkeypatch, module, client):
    monkeypatch.setattr(module, "get_client", lambda: client)


# ================================================================ 1. UTC

def test_same_real_moment_has_no_cross_producer_drift(db_session):
    """SAME_REAL_MOMENT_EVENT_TIME_DRIFT <= 1 second across every producer family.

    The naive ``submitted_at`` reaching SQLite is UTC wall-clock; interpreting it as local
    time shifted practice rows by the host offset (8h on UTC+8). All four producers are
    given the SAME moment and must agree.
    """
    u = make_user(db_session, "s1_drift")

    # knowledge (aware datetime). The source id is unique to this test: event identity is
    # (source_type, source_attempt_id, item_key) and is user-INDEPENDENT, so reusing
    # another test's source id would be deduped instead of emitted.
    producers.emit_knowledge_status_changed(
        user_id=u.id, knowledge_point_id="kp-1", new_status="learning",
        occurred_at=MOMENT.replace(tzinfo=timezone.utc), source_type="knowledge_progress",
        source_id="s1-drift-1", service_namespace=COURSE)

    # AI / audit accounting
    producers.emit_ai_called(user_id=u.id, ai_request_id="drift-ai",
                             capability="tutor.chat", status="succeeded",
                             occurred_at=MOMENT.replace(tzinfo=timezone.utc))

    # practice + past paper, through the canonical attempt bridge
    _attempt(db_session, u, "drift-q1", source_type="exam_practice_attempt",
             source_id="900", submitted_at=MOMENT)
    _attempt(db_session, u, "drift-q2", source_type="past_paper_attempt",
             source_id="901", submitted_at=MOMENT)

    times = {e.event_type: float(e.occurred_at) for e in events_for(db_session, u.id)}
    assert set(times) == {"knowledge_status_changed", "ai_called", "question_answered"}
    assert times["knowledge_status_changed"] == pytest.approx(MOMENT_EPOCH, abs=1)
    assert times["ai_called"] == pytest.approx(MOMENT_EPOCH, abs=1)
    drift = abs(times["question_answered"] - MOMENT_EPOCH)
    assert drift <= 1.0, f"practice events drifted {drift}s from the same real moment"

    spread = max(times.values()) - min(times.values())
    assert spread <= 1.0, f"cross-family spread {spread}s"


def _exam_context(user, *, knowledge_point_id=None):
    from learning.spaces.exam_prep.context import cs408_context
    return cs408_context(user, module_key="operating_system",
                         knowledge_point_id=knowledge_point_id)


def _attempt(db, user, qid, *, source_type, source_id, submitted_at,
             knowledge_point_id=None, answer="A", correct=True, score=None):
    context = _exam_context(user, knowledge_point_id=knowledge_point_id)
    session, _created = practice_service.ensure_legacy_session(
        db, user, ServiceNamespace.EXAM_PREP, source_type=source_type,
        source_session_key=int(source_id), started_at=submitted_at, context=context)
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id=qid, service_namespace=ServiceNamespace.EXAM_PREP,
                      context={"subject_key": "operating_system",
                               "exam_module_id": "operating_system",
                               "knowledge_point_id": knowledge_point_id})
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=correct, score=score,
        submitted_at=submitted_at, context=context,
        source=practice_service.SourceIdentity(source_type, source_id, f"{qid}:0"))


def test_naive_persisted_timestamp_is_read_as_utc(db_session):
    """The shared conversion never infers server-local time."""
    naive = datetime(2026, 9, 19, 3, 4, 5)
    assert timeutil.to_epoch(naive) == naive.replace(tzinfo=timezone.utc).timestamp()
    aware = datetime(2026, 9, 19, 11, 4, 5, tzinfo=timezone.utc)
    assert timeutil.to_epoch(aware) == timeutil.to_epoch(naive) + 8 * 3600


# ================================================================ 2-3. visibility & routes

def test_ai_audit_never_reaches_the_user_timeline(client, db_session):
    """AI_AUDIT_EVENT_USER_FACING = NO, enforced server-side."""
    user = register_and_login(client, "s1_audit")
    u = db_session.query(User).filter(User.username == "s1_audit").first()
    producers.emit_ai_called(user_id=u.id, ai_request_id="s1-hidden",
                             capability="tutor.chat", status="succeeded",
                             occurred_at=None)
    producers.emit_material_opened(user_id=u.id, material_id=77, occurred_at=None)

    body = client.get("/learning-records").json()
    assert [r["event_type"] for r in body["records"]] == ["material_opened"]
    assert all(r["record_category"] != taxonomy.CAT_AI for r in body["records"])

    # the fact is preserved, not deleted: it is still in the database and still queryable
    assert len(events_for(db_session, u.id, "ai_called")) == 1
    audit = client.get("/learning-records", params={"include_audit": True}).json()
    assert "ai_called" in [r["event_type"] for r in audit["records"]]
    assert user["id"] == u.id


def test_canonical_record_route_does_not_shadow_literal_paths(client):
    """CANONICAL_RECORD_ROUTE_AMBIGUITY = 0."""
    register_and_login(client, "s1_routes")
    assert client.get("/learning-records/stats").status_code == 200
    assert client.get("/learning-records/taxonomy").status_code == 200
    assert client.get("/learning-records/summary").status_code == 200

    listed = client.get("/learning-records").json()
    for record in listed["records"]:
        assert client.get(f"/learning-records/{record['event_id']}").status_code == 200


def test_exam_scoped_timeline_is_module_filterable(client, db_session):
    """The canonical CS408 surface filters by module in SQL, and rejects a bad module."""
    register_and_login(client, "s1_exam_records")
    u = db_session.query(User).filter(User.username == "s1_exam_records").first()
    _attempt(db_session, u, "mod-q1", source_type="exam_practice_attempt",
             source_id="710", submitted_at=MOMENT)
    producers.emit_ai_called(user_id=u.id, ai_request_id="s1-exam-hidden",
                             capability="question.explain", status="succeeded",
                             occurred_at=None, service_namespace=EXAM)

    body = client.get("/exam/prep/records").json()
    assert [r["event_type"] for r in body["records"]] == ["question_answered"]
    assert body["records"][0]["context"]["exam_module_id"] == "operating_system"

    scoped = client.get("/exam/prep/records",
                        params={"exam_module_id": "operating_system"}).json()
    assert len(scoped["records"]) == 1
    empty = client.get("/exam/prep/records",
                       params={"exam_module_id": "computer_network"}).json()
    assert empty["records"] == []
    bad = client.get("/exam/prep/records", params={"exam_module_id": "not_a_module"})
    assert bad.status_code == 400


# ================================================================ 4-7. contract

def test_unanswered_item_carries_no_score(db_session):
    """UNANSWERED_SCORE_ZERO = 0 — a blank has no verdict and no score."""
    u = make_user(db_session, "s1_unanswered")
    _blank_attempt(db_session, u, "blank-q1")

    record = records_service.list_records(db_session, u.id)["records"][0]
    assert record["summary"]["correct"] is None
    assert "score" not in record["summary"]
    assert record["summary"]["score"] if "score" in record["summary"] else None is None
    assert records_service.summarize_records(db_session, u.id)["ungraded_attempts"] == 1

    # a REAL graded zero still passes through untouched
    _scored_attempt(db_session, u, "zero-q1", score=0.0)
    scored = [r for r in records_service.list_records(db_session, u.id)["records"]
              if r["summary"].get("question_source_id") == "zero-q1"]
    assert scored and scored[0]["summary"]["score"] == 0.0


def test_unanswered_score_is_not_zeroed_at_the_attempt_boundary(db_session):
    """The legacy writer's `score: 0` for a blank never becomes a canonical fact."""
    u = make_user(db_session, "s1_unanswered_row")
    attempt = _mirror_blank_past_paper(db_session, u, "blank-pp-1")
    assert attempt is not None
    assert attempt.correct is None
    assert attempt.score is None
    assert attempt.max_score is None


def _blank_attempt(db, user, qid):
    return _attempt(db, user, qid, source_type="exam_practice_attempt",
                    source_id=str(abs(hash(qid)) % 100000), submitted_at=MOMENT,
                    answer="", correct=None)


def _scored_attempt(db, user, qid, score):
    return _attempt(db, user, qid, source_type="exam_practice_attempt",
                    source_id=str(abs(hash(qid)) % 100000), submitted_at=MOMENT,
                    answer="A", correct=True, score=score)


def _mirror_blank_past_paper(db, user, qid):
    """Drive the REAL past-paper mirror with a legacy `score: 0` blank row."""
    from learning.practice.adapters import exam as exam_adapter
    from models import PastPaperAttempt

    attempt = PastPaperAttempt(
        username=user.username, subject_key="operating_system",
        subject_name="操作系统", mode="past_paper",
        year=2024, attempt_no=1, status="submitted", total_questions=1, total_score=0,
        max_score=2, started_at=MOMENT, submitted_at=MOMENT,
        result_json=json.dumps({"results": [
            {"question_id": qid, "user_answer": "", "correct": False, "score": 0,
             "full_score": 2, "judge": "auto"}]}),
    )
    db.add(attempt)
    db.commit()
    exam_adapter.mirror_past_paper_attempt(db, user, attempt, submitted_at=MOMENT)
    from learning.practice.models import PracticeAttempt
    return (db.query(PracticeAttempt)
            .filter(PracticeAttempt.user_id == user.id,
                    PracticeAttempt.source_attempt_type == "past_paper_attempt")
            .first())


def test_summary_is_bounded_by_sql_aggregates(db_session):
    """The summary never materializes the user's history — it aggregates in SQL."""
    u = make_user(db_session, "s1_summary")
    for i in range(25):
        producers.emit_material_opened(user_id=u.id, material_id=1000 + i,
                                       occurred_at=1_700_000_000.0 + i)
    summary = records_service.summarize_records(db_session, u.id)
    assert summary["total_events"] == 25
    assert summary["material_interactions"] == 25
    assert summary["by_event_type"] == {"material_opened": 25}

    # structurally bounded: no row materialization remains — the old implementation held
    # `events = q.all()` and derived every figure from that list in Python
    source = Path(records_service.__file__).read_text(encoding="utf-8")
    summary_body = source.split("def summarize_records", 1)[1].split("\ndef ", 1)[0]
    assert "events = " not in summary_body
    assert "for event in" not in summary_body
    assert "func.count()" in summary_body
    assert summary_body.count("group_by") >= 2


def test_cursor_pagination_is_stable_and_module_scoped(db_session):
    u = make_user(db_session, "s1_paging")
    ids = [_attempt(db_session, u, f"page-q{i}", source_type="exam_practice_attempt",
                    source_id=str(800 + i), submitted_at=MOMENT).attempt.id
           for i in range(7)]

    seen, cursor, pages = [], None, 0
    while True:
        page = records_service.list_records(db_session, u.id, limit=3, cursor=cursor)
        seen.extend(r["event_id"] for r in page["records"])
        pages += 1
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
        assert pages < 10
    assert len(seen) == len(set(seen)) == len(ids)
    assert pages == 3


def test_records_are_isolated_per_user(client, db_session):
    register_and_login(client, "s1_iso_a", password="secret123")
    a = db_session.query(User).filter(User.username == "s1_iso_a").first()
    _attempt(db_session, a, "iso-q1", source_type="exam_practice_attempt",
             source_id="950", submitted_at=MOMENT)

    client.cookies.clear()
    register_and_login(client, "s1_iso_b", password="secret123")
    assert client.get("/learning-records").json()["records"] == []
    assert client.get("/exam/prep/records").json()["records"] == []


# ================================================================ 8-10. Student Twin

def test_student_twin_speaks_the_real_runtime_http_contract(client, db_session,
                                                            monkeypatch):
    """The product request is accepted by the REAL runtime FastAPI application."""
    register_and_login(client, "s1_twin")
    u = db_session.query(User).filter(User.username == "s1_twin").first()
    _attempt(db_session, u, "twin-q1", source_type="exam_practice_attempt",
             source_id="960", submitted_at=MOMENT)

    transport, restore = runtime_transport(replay_state=fake_twin_state)
    try:
        with_client(monkeypatch, student_twin, product_client(transport))
        body = client.get("/exam/prep/scientific/student-twin").json()
    finally:
        restore()

    assert body["metadata"]["mode"] == "PREVIEW"
    assert body["metadata"]["component"] == "student_twin"
    assert body["metadata"]["runtime_release_id"]
    assert body["metadata"]["controls_product_decision"] is False
    assert body["metadata"]["writes_learner_fact"] is False
    assert body["input_summary"]["event_count"] == 1
    assert body["state"]["global_ability"] == 0.0
    assert body["state"]["user_id"] != u.username          # opaque ref, not an identity


def test_student_twin_request_satisfies_runtime_validation(db_session, monkeypatch):
    """Ordering / identity rules: the runtime would 400 a wrong request, so it must not."""
    u = make_user(db_session, "s1_twin_contract")
    for i in range(4):
        _attempt(db_session, u, f"order-q{i}", source_type="exam_practice_attempt",
                 source_id=str(970 + i),
                 submitted_at=datetime(2026, 9, 19, 3, 0, i))

    captured = {}

    def _capture(user_ref, events):
        captured["user_ref"] = user_ref
        captured["events"] = list(events)
        return fake_twin_state(user_ref, events)

    transport, restore = runtime_transport(replay_state=_capture)
    try:
        with_client(monkeypatch, student_twin, product_client(transport))
        result = student_twin.preview(db_session, u.id, service_namespace=EXAM)
    finally:
        restore()

    assert result["metadata"]["mode"] == "PREVIEW"
    occurred = [e.occurred_at for e in captured["events"]]
    assert occurred == sorted(occurred)
    assert len({e.event_id for e in captured["events"]}) == len(captured["events"])
    assert captured["events"][-1].event_id


def test_student_twin_preview_writes_no_learner_fact(client, db_session, monkeypatch):
    """C4: a preview may not change knowledge, mastery, wrong state, plan or grade."""
    register_and_login(client, "s1_twin_no_write")
    u = db_session.query(User).filter(User.username == "s1_twin_no_write").first()
    _attempt(db_session, u, "nw-q1", source_type="exam_practice_attempt",
             source_id="980", submitted_at=MOMENT)

    from models import UserKnowledgeProgress
    from learning.wrong_answers.models import WrongAnswerState

    def snapshot():
        return (
            db_session.query(LearningEvent).count(),
            db_session.query(WrongAnswerState).count(),
            db_session.query(UserKnowledgeProgress).count(),
        )

    before = snapshot()
    transport, restore = runtime_transport(replay_state=fake_twin_state)
    try:
        with_client(monkeypatch, student_twin, product_client(transport))
        body = client.get("/exam/prep/scientific/student-twin").json()
    finally:
        restore()
    db_session.expire_all()
    assert body["metadata"]["writes_learner_fact"] is False
    assert snapshot() == before


def test_scientific_outage_does_not_break_core_flows(client, db_session, monkeypatch):
    """PART F: a dead runtime is a bounded state, never a 500 and never a cascade."""
    register_and_login(client, "s1_outage")
    u = db_session.query(User).filter(User.username == "s1_outage").first()
    _attempt(db_session, u, "out-q1", source_type="exam_practice_attempt",
             source_id="990", submitted_at=MOMENT)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("runtime down", request=request)

    with_client(monkeypatch, student_twin, product_client(httpx.MockTransport(refuse)))
    with_client(monkeypatch, misconception, product_client(httpx.MockTransport(refuse)))

    twin = client.get("/exam/prep/scientific/student-twin")
    assert twin.status_code == 200
    assert twin.json()["metadata"]["mode"] == "UNAVAILABLE"
    assert "SCIENTIFIC_RUNTIME_UNAVAILABLE" in twin.json()["metadata"]["blockers"]

    # the core learning loop is untouched
    assert client.get("/learning-records").status_code == 200
    assert client.get("/exam/prep/records").status_code == 200
    assert client.get("/practice/sessions").status_code == 200
    assert client.get("/wrong-answers").status_code == 200
    assert client.post("/practice/sessions",
                       json={"service_namespace": EXAM}).status_code in (200, 201)


def test_scientific_base_url_and_timeout_are_configurable(monkeypatch):
    monkeypatch.setenv("SCIENTIFIC_RUNTIME_BASE_URL", "http://127.0.0.1:9999/")
    monkeypatch.setenv("SCIENTIFIC_RUNTIME_TIMEOUT", "2.5")
    built = sci_client.ScientificClient()
    assert built.base_url == "http://127.0.0.1:9999"
    assert built._timeout == 2.5

    # a timeout is a bounded failure, not an exception type that escapes the boundary
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(sci_client.ScientificUnavailable):
        sci_client.ScientificClient(
            base_url="http://x.test", transport=httpx.MockTransport(slow)
        ).infer("/v1/inference/student-twin", {"request_id": "r"}, component="student_twin")


# ================================================================ 11-15. advisory / shadow

def _wrong_state(db, client, username, *, question_id="mc-1", answer="A"):
    register_and_login(client, username)
    u = db.query(User).filter(User.username == username).first()
    bank = ExamQuestionBank(subject_key="operating_system", stem="什么是死锁？",
                            options_json=json.dumps({"A": "选项A", "B": "选项B"}),
                            standard_answer="B", is_active=True)
    db.add(bank)
    db.commit()
    _attempt_wrong(db, u, question_id, str(bank.id), answer=answer)
    wrong_service.rebuild_states(db, user_id=u.id)
    states = wrong_service.list_states(db, u.id)
    assert states, "the wrong-answer projection produced no state"
    return u, states[0].id


def _attempt_wrong(db, user, qid, source_id, *, answer):
    context = _exam_context(user)
    session, _ = practice_service.ensure_legacy_session(
        db, user, ServiceNamespace.EXAM_PREP, source_type="exam_practice_attempt",
        source_session_key=int(source_id), started_at=MOMENT, context=context)
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id=source_id, service_namespace=ServiceNamespace.EXAM_PREP,
                      context={"subject_key": "operating_system",
                               "exam_module_id": "operating_system"})
    return practice_service.record_attempt(
        db, user, session, ref, answer=answer, correct=False, submitted_at=MOMENT,
        context=context, result={"standard_answer": "B", "judge": "auto"},
        source=practice_service.SourceIdentity("exam_practice_attempt", source_id,
                                               f"{qid}:0"))


def _misconception_transport(scores=(0.71, 0.63, 0.55)):
    """The runtime's own HTTP contract, answered with a fixed retrieval result."""
    test_client = TestClient(runtime_app())
    from app import runtime_bridge

    original = runtime_bridge.misconception_matches
    runtime_bridge.misconception_matches = lambda q, a, k: {
        "results": [{"rank": i, "misconception_id": f"eedi-{i}",
                     "misconception_text": f"candidate {i}", "retrieval_score": s}
                    for i, s in enumerate(scores[:k])],
        "score_semantics": "cosine-like normalized inner product (NOT probability)",
        "weak_label": True, "ontology_size": 2587,
        "product_role": "DATA_PRODUCER", "controls_product_decision": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(request.method, request.url.path,
                                       content=request.content,
                                       headers={"content-type": "application/json"})
        return httpx.Response(response.status_code, content=response.content,
                              headers={"content-type": "application/json"})

    def restore():
        runtime_bridge.misconception_matches = original

    return httpx.MockTransport(handler), restore


def test_misconception_advisory_contract_and_shadow_mode(client, db_session, monkeypatch):
    _u, state_id = _wrong_state(db_session, client, "s1_mc")
    transport, restore = _misconception_transport()
    try:
        with_client(monkeypatch, misconception, product_client(transport))
        body = client.post("/science/misconception-advisory",
                           params={"state_id": state_id}).json()
    finally:
        restore()

    meta = body["metadata"]
    assert meta["component"] == "misconception_v2"
    assert meta["mode"] == misconception.PRODUCT_MODE == "SHADOW_NOT_USER_VISIBLE"
    assert meta["controls_product_decision"] is False
    assert meta["writes_learner_fact"] is False
    assert any(b.startswith("ONTOLOGY_MISMATCH") for b in meta["blockers"])
    assert body["available"] is True
    assert body["wrong_record"]["state_id"] == state_id
    assert body["weak_label"] is True


def test_misconception_exposes_similarity_only(client, db_session, monkeypatch):
    """No probability / confidence vocabulary may appear in the contract."""
    _u, state_id = _wrong_state(db_session, client, "s1_mc_sem")
    transport, restore = _misconception_transport()
    try:
        with_client(monkeypatch, misconception, product_client(transport))
        body = client.post("/science/misconception-advisory",
                           params={"state_id": state_id}).json()
    finally:
        restore()

    candidate = body["candidates"][0]
    assert set(candidate) == {"rank", "candidate_id", "candidate_label", "similarity"}
    assert candidate["similarity"] == 0.71

    # the word may only ever appear in a NEGATION ("NOT a probability"), never as a label
    for text in (body["score_semantics"], body["metadata"]["semantics"]):
        for sentence in text.replace(";", ".").split("."):
            if "probability" in sentence or "confidence" in sentence:
                assert "not" in sentence.lower()

    for forbidden in ("probability", "confidence", "diagnosis_certainty", "p_misconception"):
        assert forbidden not in candidate, forbidden

    spec = client.get("/openapi.json").json()
    schema = spec["components"]["schemas"]["MisconceptionCandidate"]["properties"]
    assert "similarity" in schema
    for forbidden in ("probability", "confidence", "score"):
        assert forbidden not in schema, forbidden


def test_misconception_advisory_writes_no_learner_fact(client, db_session, monkeypatch):
    """D4: MISCONCEPTION_ADVISORY_WRITES_LEARNER_FACT = 0."""
    from learning.wrong_answers.models import WrongAnswerState
    from models import UserKnowledgeProgress

    _u, state_id = _wrong_state(db_session, client, "s1_mc_write")

    def snapshot():
        return (
            db_session.query(LearningEvent).count(),
            [(s.id, s.status, s.wrong_count)
             for s in db_session.query(WrongAnswerState).order_by(WrongAnswerState.id)],
            db_session.query(UserKnowledgeProgress).count(),
        )

    before = snapshot()
    transport, restore = _misconception_transport()
    try:
        with_client(monkeypatch, misconception, product_client(transport))
        client.post("/science/misconception-advisory", params={"state_id": state_id})
    finally:
        restore()
    db_session.expire_all()
    assert snapshot() == before


def test_misconception_stays_shadow_when_the_runtime_is_unprovisioned(
        client, db_session, monkeypatch):
    """The real deployment cannot execute the component — that must be reported, not
    hidden behind an empty success."""
    _u, state_id = _wrong_state(db_session, client, "s1_mc_prov")
    monkeypatch.delenv("SCIENTIFIC_RUNTIME_BASE_URL", raising=False)
    sci_client.reset_client()
    try:
        body = client.post("/science/misconception-advisory",
                           params={"state_id": state_id}).json()
    finally:
        sci_client.reset_client()

    assert body["metadata"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    assert body["available"] is False
    blockers = " ".join(body["metadata"]["blockers"])
    assert "ONTOLOGY_MISMATCH" in blockers
    assert ("SCIENTIFIC_RUNTIME_UNAVAILABLE" in blockers
            or "RUNTIME_COMPONENT_NOT_PROVISIONED" in blockers)


def test_tutor_policy_shadow_cannot_control_a_response(client):
    register_and_login(client, "s1_tp")
    body = client.get("/science/tutor-policy").json()

    assert body["controls_response"] is False
    assert tutor_policy.TUTOR_POLICY_CONTROLS_RESPONSE is False
    assert body["suggested_action"] is None
    assert body["available"] is False
    assert body["action_ontology"] == ["focus", "generic", "probing", "telling"]
    blockers = " ".join(body["metadata"]["blockers"])
    assert "TURN_STATE_PREV_ACTIONS_UNAVAILABLE" in blockers
    assert body["metadata"]["mode"] == "SHADOW"


def test_tutor_policy_bridge_works_and_stays_shadow(monkeypatch):
    """The hook is REAL: an explicit turn state reaches the runtime and comes back
    SHADOW-labelled and non-controlling."""
    transport, restore = runtime_transport()
    try:
        from app import runtime_bridge
        original = runtime_bridge.tutor_policy_action
        runtime_bridge.tutor_policy_action = lambda *a, **k: {
            "requested_action": "probing",
            "action_probabilities": {"focus": 0.1, "generic": 0.2, "probing": 0.5,
                                     "telling": 0.2},
            "ranking": ["probing", "generic", "telling", "focus"],
            "action_ontology": ["focus", "generic", "probing", "telling"],
            "product_role": "DATA_PRODUCER", "controls_product_decision": False}
        try:
            result = tutor_policy.suggest_for_explicit_state(
                {"problem": "证明 DFA 与 NFA 等价", "wrong": "学生认为 NFA 更强",
                 "prev_actions": ["focus"]},
                client=product_client(transport))
        finally:
            runtime_bridge.tutor_policy_action = original
    finally:
        restore()

    assert result["available"] is True
    assert result["suggested_action"] == "probing"
    assert result["controls_response"] is False
    assert result["metadata"]["controls_product_decision"] is False
    assert result["metadata"]["mode"] == "SHADOW"


def test_tutor_policy_is_not_wired_into_any_response_path():
    """The hook exists but nothing consumes it: it cannot change a tutor reply."""
    root = Path(__file__).resolve().parents[1]
    for relative in ("ai/orchestrator.py", "routers/scientific.py"):
        text = (root / relative).read_text(encoding="utf-8")
        if relative.endswith("orchestrator.py"):
            assert "tutor_policy" not in text, relative
    text = (root / "routers" / "scientific.py").read_text(encoding="utf-8")
    # even the router only reports it; nothing feeds it into a chat/tutor response
    assert "_ = tutor_policy" not in text
    assert "shadow_suggest" in text


def test_scientific_endpoints_are_authenticated_and_user_scoped(client, db_session):
    """G: user B cannot read user A's state or wrong context."""
    a, state_id = _wrong_state(db_session, client, "s1_sec_a")
    assert client.post("/science/misconception-advisory",
                       params={"state_id": state_id}).status_code in (200, 503)

    client.cookies.clear()
    assert client.get("/exam/prep/scientific/student-twin").status_code in (401, 403)
    assert client.get("/science/tutor-policy").status_code in (401, 403)
    assert client.post("/science/misconception-advisory",
                       params={"state_id": state_id}).status_code in (401, 403)

    register_and_login(client, "s1_sec_b")
    assert client.post("/science/misconception-advisory",
                       params={"state_id": state_id}).status_code == 404
    other = client.get("/exam/prep/scientific/student-twin")
    assert other.status_code == 200
    assert other.json()["input_summary"]["event_count"] == 0


# ================================================================ 16. OpenAPI

def test_new_contracts_are_concrete_in_openapi(client):
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    for name in ("RecordView", "RecordPage", "RecordDetail", "RecordSourceRef",
                 "RecordContext", "RecordSummary", "RecordsSummaryResponse",
                 "RecordsTaxonomyResponse"):
        assert name in schemas and schemas[name].get("properties"), name

    for name in ("StudentTwinPreviewResponse", "ScientificAuthority",
                 "StudentTwinInputSummary", "MisconceptionAdvisoryResponse",
                 "MisconceptionCandidate", "TutorPolicyShadowResponse"):
        assert name in schemas and schemas[name].get("properties"), name

    paths = spec["paths"]
    for path, method in (("/learning-records", "get"),
                         ("/learning-records/summary", "get"),
                         ("/learning-records/taxonomy", "get"),
                         ("/exam/prep/records", "get"),
                         ("/exam/prep/scientific/student-twin", "get"),
                         ("/science/misconception-advisory", "post"),
                         ("/science/tutor-policy", "get")):
        operation = paths[path][method]
        ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in ref, f"{method.upper()} {path} 200 is untyped: {ref}"

    detail = paths["/learning-records/{event_id}"]["get"]
    assert "$ref" in detail["responses"]["200"]["content"]["application/json"]["schema"]


def test_declared_record_models_cover_every_emitted_summary_field(db_session):
    """A new factual summary field must break this test, not vanish from the contract."""
    from learning.records.contract import RecordSummary

    u = make_user(db_session, "s1_coverage")
    producers.emit_material_opened(user_id=u.id, material_id=1, occurred_at=None)
    producers.emit_material_asked(user_id=u.id, material_id=1, capability="material.qa",
                                  occurred_at=None, source_id="chat-1")
    producers.emit_knowledge_status_changed(
        user_id=u.id, knowledge_point_id="kp", new_status="learning",
        occurred_at=None, source_type="knowledge_progress", source_id="1",
        service_namespace=COURSE, old_status="not_started")
    producers.emit_ai_called(user_id=u.id, ai_request_id="cov-1",
                             capability="tutor.chat", status="succeeded",
                             occurred_at=None)
    _attempt(db_session, u, "cov-q1", source_type="exam_practice_attempt",
             source_id="777", submitted_at=MOMENT)

    declared = set(RecordSummary.model_fields)
    seen = set()
    for record in records_service.list_records(db_session, u.id,
                                               include_audit=True)["records"]:
        seen |= set(record["summary"])
    assert seen <= declared, f"undeclared summary fields: {sorted(seen - declared)}"


# ================================================================ B1 boundary

PRODUCT_BACKEND_HEAVY_MODULES = ("torch", "transformers", "faiss", "zhixue_runtime",
                                 "sentence_transformers", "sklearn")


def test_product_backend_imports_no_scientific_stack():
    """B1: the Product Backend must be importable and deployable without the scientific
    stack. A scientific capability is only ever reached over HTTP."""
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "tests" in path.parts or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for module in PRODUCT_BACKEND_HEAVY_MODULES:
            for pattern in (f"import {module}\n", f"import {module} ",
                            f"from {module} import", f"from {module}."):
                if pattern in text:
                    offenders.append(f"{path.relative_to(root)}: {pattern.strip()}")
    assert offenders == [], offenders


def test_the_product_backend_process_has_not_loaded_a_scientific_stack():
    """Runtime proof, not just source proof: importing the app must not pull them in."""
    import sys
    loaded = [m for m in PRODUCT_BACKEND_HEAVY_MODULES if m in sys.modules]
    assert loaded == [], f"heavy scientific modules loaded in-process: {loaded}"


def test_only_one_scientific_http_client_owns_transport():
    """ONE focused client: every scientific HTTP call goes through science.client."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "science" / "client.py").exists()
    for relative in ("science/student_twin.py", "science/misconception.py",
                     "science/tutor_policy.py"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "httpx.post" not in text and "httpx.get" not in text, relative
        assert "from .client import" in text, relative
    # the pre-existing evidence-pipeline client delegates transport too
    legacy = (root / "data_plane" / "runtime_client.py").read_text(encoding="utf-8")
    assert "httpx.post(" not in legacy
    assert "science import client" in legacy or "science.client" in legacy
