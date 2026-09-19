"""STEP 7F: canonical envelope, taxonomy, producers, records read model, backfill."""
import json
from datetime import datetime

import database
import main
import pytest
from core.learning_context import ServiceNamespace
from data_plane import identity, worker
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import backfill, envelope, producers, service, taxonomy
from models import KnowledgePoint, KnowledgeProgressEvent, LearningRecord, User
from models import UserKnowledgeProgress

COURSE = ServiceNamespace.COURSE_LEARNING
EXAM = ServiceNamespace.EXAM_PREP
PROG = ServiceNamespace.PROGRAMMING


def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def events_of(db, event_type=None) -> list[LearningEvent]:
    q = db.query(LearningEvent)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


def events_for(db, user_id: int, event_type=None) -> list[LearningEvent]:
    """Every test shares one SQLite file, so event assertions must be user-scoped."""
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


# ---------------------------------------------------------------- taxonomy

def test_taxonomy_registry_shape():
    assert taxonomy.EVENT_SCHEMA_VERSION == 2          # not bumped by STEP 7F
    assert "course_practice" in taxonomy.active_event_types()
    for event_type in ("question_answered", "code_submitted", "ai_called",
                       "knowledge_status_changed", "material_opened", "material_asked"):
        assert taxonomy.is_active(event_type), event_type
        spec = taxonomy.spec_for(event_type)
        assert spec.owner and spec.durable_source


def test_deferred_types_have_no_producer():
    """Reserved names must not be emittable while no durable source exists."""
    for event_type in taxonomy.deferred_event_types():
        assert not taxonomy.is_active(event_type)
        with pytest.raises(envelope.EventValidationError):
            envelope.build_event(
                event_type=event_type, user_id=1, service_namespace=COURSE.value,
                occurred_at=1.0, source_type="x", source_id="1", source_item_key="k",
                payload={}, snapshot_capture_mode="LIVE_EMITTER")


def test_ownership_matrix_has_one_owner_per_event():
    matrix = taxonomy.ownership_matrix()
    owners = {row["event_type"]: row["authoritative_producer"] for row in matrix}
    assert len(owners) == len(matrix)                  # no duplicate event_type entries
    assert owners["course_practice"] == "data_plane.emitter.build_course_practice_events"
    assert owners["question_answered"] == "learning.practice.events.emit_for_attempt"


def test_student_twin_eligible_families_are_the_two_practice_families():
    """ACCEL_SPRINT_S2: `question_answered` joined the eligible set by explicit product
    decision. The flag is TYPE-level and necessary-not-sufficient — the per-event input
    rule in data_plane.eligibility decides each event."""
    assert taxonomy.student_twin_eligible_types() == ("course_practice",
                                                      "question_answered")
    for other in ("code_submitted", "ai_called", "knowledge_status_changed",
                  "material_opened", "material_asked"):
        assert taxonomy.spec_for(other).student_twin_eligible is False


def test_categories_are_read_model_only():
    assert taxonomy.category_for("course_practice") == taxonomy.CAT_PRACTICE
    assert taxonomy.category_for("code_submitted") == taxonomy.CAT_PROGRAMMING
    assert taxonomy.category_for("nope") is None


# ---------------------------------------------------------------- envelope

def _valid_event(**overrides):
    kwargs = dict(event_type="ai_called", user_id=1, service_namespace=COURSE.value,
                  occurred_at=1_700_000_000.0, source_type="ai_request", source_id="r1",
                  source_item_key="tutor.chat",
                  payload={"ai_request_id": "r1", "status": "succeeded"},
                  snapshot_capture_mode="LIVE_EMITTER")
    kwargs.update(overrides)
    return envelope.build_event(**kwargs)


def test_envelope_has_every_frozen_field():
    event = _valid_event()
    for field in ("event_id", "user_id", "event_type", "service_key", "occurred_at",
                  "source_type", "source_attempt_id", "source_item_key",
                  "item_snapshot_json", "event_schema_version"):
        assert field in event, field
    assert event["event_schema_version"] == 2


def test_event_id_is_deterministic_and_reused_from_the_frozen_identity():
    a = _valid_event()
    b = _valid_event()
    assert a["event_id"] == b["event_id"]
    assert a["event_id"] == identity.event_id("ai_request", "r1", "tutor.chat")
    assert a["idempotency_key"] == identity.idempotency_key("ai_request", "r1", "tutor.chat")


def test_unregistered_event_type_is_rejected():
    with pytest.raises(envelope.EventValidationError):
        _valid_event(event_type="made_up")


@pytest.mark.parametrize("override,fragment", [
    ({"user_id": None}, "user_id"),
    ({"service_key": "not_a_space"}, "service_namespace"),
    ({"occurred_at": 0}, "occurred_at"),
    ({"occurred_at": "2024-01-01"}, "occurred_at"),
    ({"source_attempt_id": ""}, "source identity"),
    ({"event_schema_version": 99}, "event_schema_version"),
    ({"event_type": "made_up"}, "unregistered"),
    ({"idempotency_key": ""}, "idempotency_key"),
])
def test_invalid_events_are_rejected_not_repaired(override, fragment):
    """An invalid row must be rejected outright — never quietly corrected."""
    event = _valid_event()
    event.update(override)
    errors = envelope.validate_event(event)
    assert any(fragment in e for e in errors), errors


def test_namespace_restriction_is_enforced():
    with pytest.raises(envelope.EventValidationError):
        _valid_event(event_type="code_submitted", service_namespace=EXAM.value,
                     payload={"correct": True})


def test_required_payload_fields_are_enforced():
    with pytest.raises(envelope.EventValidationError):
        _valid_event(payload={"capability": "tutor.chat"})     # no ai_request_id/status


def test_correctness_must_stay_tri_state():
    event = _valid_event(event_type="question_answered", service_namespace=EXAM.value,
                         payload={"correct": None})
    assert envelope.validate_event(event) == []
    broken = _valid_event(event_type="question_answered", service_namespace=EXAM.value,
                          payload={"correct": None})
    broken["correct"] = "yes"
    assert any("correct" in e for e in envelope.validate_event(broken))


def test_privacy_guard_rejects_bulk_user_content():
    for forbidden in ({"code": "print(1)"}, {"prompt": "..."}, {"raw_response": "..."},
                      {"full_answer": "A"}, {"api_key": "x"}):
        with pytest.raises(envelope.EventValidationError):
            _valid_event(payload={"ai_request_id": "r1", "status": "ok", **forbidden})


def test_privacy_guard_allows_references_and_metrics():
    envelope.assert_payload_is_safe({"ai_request_id": "r1", "capability": "tutor.chat",
                                     "credit_class": 3, "material_id": "9"})


# ---------------------------------------------------------------- producers

def test_ai_called_event_is_written_once(db_session):
    u = make_user(db_session, "rec_ai")
    first = producers.emit_ai_called(user_id=u.id, ai_request_id="req-1",
                                     capability="tutor.chat", status="succeeded",
                                     occurred_at=None, source_user_ref="rec_ai")
    second = producers.emit_ai_called(user_id=u.id, ai_request_id="req-1",
                                      capability="tutor.chat", status="succeeded",
                                      occurred_at=None, source_user_ref="rec_ai")
    assert first["emitted"] == 1 and second["emitted"] == 0
    rows = events_for(db_session, u.id, "ai_called")
    assert len([r for r in rows if r.source_attempt_id == "req-1"]) == 1


def test_material_opened_is_deduped_per_day(db_session):
    u = make_user(db_session, "rec_mat")
    a = producers.emit_material_opened(user_id=u.id, material_id=7, occurred_at=None)
    b = producers.emit_material_opened(user_id=u.id, material_id=7, occurred_at=None)
    assert a["emitted"] == 1 and b["emitted"] == 0     # page refresh is not a new event


def test_material_asked_carries_references_not_text(db_session):
    u = make_user(db_session, "rec_ask")
    producers.emit_material_asked(user_id=u.id, material_id=5, occurred_at=None,
                                  source_id=42, capability="material.qa",
                                  source_item_key="5:42")
    row = events_for(db_session, u.id, "material_asked")[0]
    payload = json.loads(row.item_snapshot_json)
    assert payload["material_id"] == "5"
    assert payload.get("ai_request_id") is None
    # the question text itself stays in chat_messages
    assert "question" not in payload and "answer" not in payload and "content" not in payload


def test_knowledge_transition_skips_non_transitions(db_session):
    """A score nudge that does not cross a threshold is not a status change."""
    u = make_user(db_session, "rec_kp")
    main._emit_knowledge_transition({"username": "rec_kp", "course_id": "c",
                                     "knowledge_point_id": 1, "old_status": "learning",
                                     "new_status": "learning", "occurred_at": None})
    main._emit_knowledge_transition(None)
    assert events_for(db_session, u.id, "knowledge_status_changed") == []


def test_knowledge_transition_emits_on_real_change(db_session):
    u = make_user(db_session, "rec_kp2")
    main._emit_knowledge_transition({
        "username": "rec_kp2", "course_id": "c", "knowledge_point_id": 1,
        "old_status": "not_started", "new_status": "learning",
        "occurred_at": None, "source_type": "question_attempt", "source_id": 3})
    rows = events_for(db_session, u.id, "knowledge_status_changed")
    assert len(rows) == 1
    payload = json.loads(rows[0].item_snapshot_json)
    assert payload["new_status"] == "learning" and payload["old_status"] == "not_started"


def test_producer_failure_is_absorbed_and_counted(db_session, monkeypatch):
    producers.reset_counters()

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(database, "SessionLocal", _boom)
    result = producers.emit_material_opened(user_id=999, material_id=1, occurred_at=None)
    assert result["emitted"] == 0                         # never raises
    assert producers.counters()["events_failed"] >= 1
    producers.reset_counters()


# ---------------------------------------------------------------- practice spine

def _record(db, user, ns, *, qid, correct, source_type=QuestionSourceType.STATIC_QUESTION_BANK,
            when=None, tag=None):
    session = practice_service.create_session(db, user, ns)
    ref = QuestionRef(source_type=source_type, source_id=qid, service_namespace=ns)
    src = (practice_service.SourceIdentity(tag, f"{qid}-{when}-{correct}", None)
           if tag else None)
    return practice_service.record_attempt(db, user, session, ref, answer="A",
                                           correct=correct, submitted_at=when,
                                           source=src).attempt


def test_practice_attempt_produces_question_answered(db_session):
    """The event is owned by the practice spine, so it fires on the SERVICE path —
    not only when an HTTP handler happens to call the emitter."""
    u = make_user(db_session, "rec_p1")
    _record(db_session, u, EXAM, qid="7001", correct=False, when=datetime(2024, 3, 1))
    rows = events_for(db_session, u.id, "question_answered")
    assert len(rows) == 1
    assert rows[0].correct is False
    assert rows[0].service_key == "exam_prep"
    assert rows[0].question_id == "7001"


def test_practice_null_correctness_survives_the_event(db_session):
    u = make_user(db_session, "rec_p2")
    _record(db_session, u, EXAM, qid="7002", correct=None, when=datetime(2024, 3, 1))
    rows = events_for(db_session, u.id, "question_answered")
    assert len(rows) == 1
    assert rows[0].correct is None                # never coerced to False


def test_programming_attempt_produces_code_submitted(db_session):
    u = make_user(db_session, "rec_p3")
    _record(db_session, u, PROG, qid="501", correct=True,
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
            when=datetime(2024, 3, 1), tag="progsubmit")
    rows = events_for(db_session, u.id, "code_submitted")
    assert rows and rows[0].service_key == "programming"
    assert rows[0].correct is True


def test_course_practice_events_are_never_renamed_or_duplicated(db_session):
    """The STEP6/7A exception: one stored event, original identity, no second event.

    The AIQuestionAttempt lineage is owned by the existing course_practice emitter, so
    the practice spine must stay silent for it. Other course practice sources (STEP 7G)
    ARE covered by the practice spine — they have no other emitter.
    """
    u = make_user(db_session, "rec_p4")
    _record(db_session, u, COURSE, qid="c1", correct=True,
            source_type=QuestionSourceType.MATERIAL_GENERATED,
            when=datetime(2024, 3, 1), tag="ai_question_attempt")
    assert [r for r in events_for(db_session, u.id, "question_answered")
            if r.service_key == "course_learning"] == []
    assert taxonomy.spec_for("course_practice").status == "ACTIVE"
    assert ("course_learning", "ai_question_attempt") in         __import__("learning.practice.events", fromlist=["x"]).FOREIGN_OWNED_SOURCES


# ---------------------------------------------------------------- worker safety

def test_data_producer_ignores_non_eligible_event_types(db_session, monkeypatch):
    """Only the two capable families are ever TARGETS.

    Asserted per-event rather than by counting the shared test database: a non-capable
    event addressed by id must not be scanned at all.
    """
    u = make_user(db_session, "rec_w1")
    producers.emit_material_opened(user_id=u.id, material_id=1, occurred_at=None)
    producers.emit_ai_called(user_id=u.id, ai_request_id="w-1", capability="tutor.chat",
                             status="succeeded", occurred_at=None)

    from core import config
    monkeypatch.setattr(config, "data_producer_execution_enabled", lambda: True)

    for event in events_for(db_session, u.id):
        assert event.event_type in ("material_opened", "ai_called")
        report = worker.run_once(database.SessionLocal, event_id=event.event_id)
        assert report["events_scanned"] == 0, event.event_type
        assert report["events_inferred"] == 0
        assert report["inference_runs_created"] == 0


def test_student_twin_type_eligibility_is_not_sufficient(db_session):
    """A capable family is still not automatically eligible: a blank, ungraded or
    self-reviewed event must be refused by the per-event rule."""
    from data_plane import eligibility

    assert taxonomy.student_twin_eligible_types() == ("course_practice",
                                                      "question_answered")
    for event_type in ("code_submitted", "ai_called", "knowledge_status_changed",
                       "material_opened", "material_asked"):
        assert taxonomy.spec_for(event_type).student_twin_eligible is False

    capable = eligibility.student_twin_input_eligibility(
        answer="A", correct=True, event_type="question_answered")
    assert capable.eligible is True
    for bad in ({"answer": "", "correct": True},
                {"answer": "A", "correct": None},
                {"answer": "A", "correct": True, "judge": "self_review"},
                {"answer": "A", "correct": True, "event_type": "material_opened"}):
        kw = {"event_type": "question_answered", **bad}
        assert eligibility.student_twin_input_eligibility(**kw).eligible is False, bad


# ---------------------------------------------------------------- read model

def test_list_records_is_user_scoped_and_newest_first(db_session):
    u = make_user(db_session, "rec_r1")
    other = make_user(db_session, "rec_r1b")
    producers.emit_material_opened(user_id=u.id, material_id=1, occurred_at=None)
    producers.emit_ai_called(user_id=u.id, ai_request_id="a1", capability="tutor.chat",
                             status="succeeded", occurred_at=1_700_000_000.0)
    producers.emit_ai_called(user_id=other.id, ai_request_id="a2", capability="tutor.chat",
                             status="succeeded", occurred_at=1_700_000_000.0)
    page = service.list_records(db_session, u.id, include_audit=True)
    ids = [r["source"]["id"] for r in page["records"]]
    assert "a2" not in ids and "a1" in ids


def test_audit_facts_are_not_study_history(db_session):
    """A2: ``ai_called`` stays a real backend fact but never enters the learner timeline."""
    u = make_user(db_session, "rec_r1a")
    producers.emit_material_opened(user_id=u.id, material_id=9, occurred_at=None)
    producers.emit_ai_called(user_id=u.id, ai_request_id="a9", capability="tutor.chat",
                             status="succeeded", occurred_at=None)

    default_page = service.list_records(db_session, u.id)
    assert [r["event_type"] for r in default_page["records"]] == ["material_opened"]

    audit_page = service.list_records(db_session, u.id, include_audit=True)
    assert sorted(r["event_type"] for r in audit_page["records"]) == [
        "ai_called", "material_opened"]

    # asking for the audit type without opting in is an explicit error, not a silent
    # empty page — the contract says so rather than letting a caller guess
    with pytest.raises(service.RecordsError):
        service.list_records(db_session, u.id, event_type="ai_called")
    explicit = service.list_records(db_session, u.id, event_type="ai_called",
                                    include_audit=True)
    assert len(explicit["records"]) == 1
    summary = service.summarize_records(db_session, u.id)
    assert "ai_calls" not in summary
    assert summary["material_interactions"] == 1


def test_record_view_never_leaks_raw_payload(db_session):
    u = make_user(db_session, "rec_r2")
    producers.emit_ai_called(user_id=u.id, ai_request_id="a3", capability="tutor.chat",
                             status="succeeded", occurred_at=None, credits=3)
    record = service.list_records(db_session, u.id, include_audit=True)["records"][0]
    assert "item_snapshot_json" not in record
    assert "payload" not in record
    assert record["record_category"] == taxonomy.CAT_AI
    assert record["summary"]["capability"] == "tutor.chat"
    assert record["service_namespace"] == "course_learning"


def test_records_pagination_is_stable(db_session):
    u = make_user(db_session, "rec_r3")
    for i in range(5):
        producers.emit_ai_called(user_id=u.id, ai_request_id=f"page-{i}",
                                 capability="tutor.chat", status="succeeded",
                                 occurred_at=1_700_000_000.0 + i)
    first = service.list_records(db_session, u.id, limit=2, include_audit=True)
    assert len(first["records"]) == 2 and first["has_more"] is True
    second = service.list_records(db_session, u.id, limit=2, cursor=first["next_cursor"],
                                  include_audit=True)
    first_ids = {r["event_id"] for r in first["records"]}
    assert first_ids.isdisjoint({r["event_id"] for r in second["records"]})


def test_records_time_and_namespace_filters(db_session):
    u = make_user(db_session, "rec_r4")
    producers.emit_ai_called(user_id=u.id, ai_request_id="t-old",
                             capability="tutor.chat", status="succeeded",
                             occurred_at=1_600_000_000.0)
    producers.emit_ai_called(user_id=u.id, ai_request_id="t-new",
                             capability="tutor.chat", status="succeeded",
                             occurred_at=1_700_000_000.0)
    window = service.list_records(db_session, u.id, start_at=1_650_000_000.0,
                                  include_audit=True)
    assert [r["source"]["id"] for r in window["records"]] == ["t-new"]
    assert service.list_records(db_session, u.id,
                                service_namespace="programming")["records"] == []


def test_record_detail_and_recovery_capability(db_session):
    u = make_user(db_session, "rec_r5")
    producers.emit_material_opened(user_id=u.id, material_id=2, occurred_at=None)
    event_id = service.list_records(db_session, u.id)["records"][0]["event_id"]
    detail = service.get_record(db_session, u.id, event_id)
    assert detail["recovery"].startswith("EVENT_ONLY")
    assert service.recovery_capability("question_answered").startswith("FULL")


def test_record_detail_is_user_scoped(db_session):
    u = make_user(db_session, "rec_r6")
    other = make_user(db_session, "rec_r7")
    producers.emit_material_opened(user_id=u.id, material_id=3, occurred_at=None)
    event_id = events_for(db_session, u.id, "material_opened")[0].event_id
    with pytest.raises(service.RecordNotFound):
        service.get_record(db_session, other.id, event_id)


def test_summary_metrics_are_deterministic_and_not_mastery(db_session):
    u = make_user(db_session, "rec_r8")
    _record(db_session, u, EXAM, qid="s1", correct=True, when=datetime(2024, 3, 1),
            tag="sum1")
    _record(db_session, u, EXAM, qid="s2", correct=False, when=datetime(2024, 3, 2),
            tag="sum2")
    _record(db_session, u, EXAM, qid="s3", correct=None, when=datetime(2024, 3, 3),
            tag="sum3")
    summary = service.summarize_records(db_session, u.id, service_namespace="exam_prep")
    assert summary["practice_attempts"] == 3
    assert summary["factual_correct"] == 1
    assert summary["factual_incorrect"] == 1
    assert summary["ungraded_attempts"] == 1
    assert "mastery" in summary["metrics_semantics"]


def test_summary_time_window_is_utc(db_session):
    u = make_user(db_session, "rec_r9")
    producers.emit_material_opened(user_id=u.id, material_id=5,
                                   occurred_at=1_700_000_000.0)
    inside = service.summarize_records(db_session, u.id, start_at="2023-11-14T00:00:00")
    assert inside["material_interactions"] == 1
    after = service.summarize_records(db_session, u.id, start_at="2024-01-01T00:00:00")
    assert after["material_interactions"] == 0
    assert inside["window"]["timezone"] == "UTC"

    # a naive bound is read as UTC, never as server-local time: 2023-11-14T22:13:20Z is
    # exactly the event, so a bound one second later must exclude it on any host
    boundary = service.summarize_records(db_session, u.id,
                                         start_at="2023-11-14T22:13:21")
    assert boundary["material_interactions"] == 0


# ---------------------------------------------------------------- backfill

def _kp_event(session, username, kp_id, event_type, delta, when):
    session.add(KnowledgeProgressEvent(username=username, course_id="c1",
                                       knowledge_point_id=kp_id, event_type=event_type,
                                       delta=delta, created_at=when))
    session.commit()


def test_knowledge_backfill_replays_deltas_into_transitions(db_session):
    u = make_user(db_session, "bf_kp")
    _kp_event(db_session, "bf_kp", 11, "question_correct", 8, datetime(2024, 1, 1))
    _kp_event(db_session, "bf_kp", 11, "question_incorrect", -3, datetime(2024, 1, 2))
    backfill.run_records_backfill(db_session,
                                  sources=["knowledge_progress_events"])
    # scoped to this user: the shared test database also holds other users' knowledge
    # events, so a global insert count would not describe this test
    mine = events_for(db_session, u.id, "knowledge_status_changed")
    assert len(mine) == 1
    row = mine[0]
    payload = json.loads(row.item_snapshot_json)
    assert payload["new_status"] == "learning" and payload["old_status"] == "not_started"
    assert payload["derived_from"] == "delta_replay_v1"


def test_knowledge_backfill_crosses_thresholds(db_session):
    u = make_user(db_session, "bf_kp2")
    for i in range(10):
        _kp_event(db_session, "bf_kp2", 12, "question_correct", 8,
                  datetime(2024, 1, 1 + i))
    backfill.run_records_backfill(db_session, sources=["knowledge_progress_events"])
    ids = {str(e.id) for e in db_session.query(KnowledgeProgressEvent)
           .filter(KnowledgeProgressEvent.username == "bf_kp2").all()}
    statuses = [json.loads(r.item_snapshot_json)["new_status"]
                for r in events_for(db_session, u.id, "knowledge_status_changed")
                if r.source_attempt_id in ids]
    assert "reviewing" in statuses and "mastered" in statuses


def test_knowledge_backfill_skips_unknown_users(db_session):
    _kp_event(db_session, "ghost_kp", 13, "question_correct", 8, datetime(2024, 1, 1))
    report = backfill.run_records_backfill(db_session,
                                           sources=["knowledge_progress_events"])
    assert report["inserted"] == 0 and report["skipped"] >= 1


def test_legacy_learning_records_practice_is_ineligible(db_session):
    u = make_user(db_session, "bf_lr")
    db_session.add(LearningRecord(user_id=u.id, subject="c1", record_type="practice",
                                  question="q", answer="a", review_status="pending"))
    db_session.commit()
    report = backfill.run_records_backfill(db_session, sources=["learning_records"])
    assert report["inserted"] == 0 and report["skipped"] >= 1


def test_legacy_learning_records_material_ask_maps_onto_live_identity(db_session):
    u = make_user(db_session, "bf_lr2")
    db_session.add(LearningRecord(
        user_id=u.id, subject="c1", record_type="review", question="q", answer="a",
        message_id=4242, references_json=json.dumps([{"id": 9}]),
        review_status="pending"))
    db_session.commit()
    report = backfill.run_records_backfill(db_session, sources=["learning_records"])
    assert report["inserted"] == 1
    row = events_for(db_session, u.id, "material_asked")[0]
    assert row.source_attempt_id == "4242" and row.source_item_key == "9:4242"

    # and the LIVE producer for the same ask collapses onto the same event
    live = producers.emit_material_asked(user_id=u.id, material_id=9, occurred_at=None,
                                         source_id=4242, capability="material.qa",
                                         source_item_key="9:4242")
    assert live["emitted"] == 0


def test_ai_requests_rebuild_uses_the_live_identity(db_session):
    from usage.models import AIRequest

    u = make_user(db_session, "bf_ai")
    db_session.add(AIRequest(request_id="bf-req-1", user_id=u.id,
                             capability="tutor.chat", tier="free", status="settled",
                             created_at=datetime(2024, 1, 1),
                             finished_at=datetime(2024, 1, 1), actual_credits=2,
                             provider="deepseek"))
    db_session.commit()

    report = backfill.run_records_backfill(db_session, sources=["ai_requests"])
    assert report["inserted"] >= 1
    mine = events_for(db_session, u.id, "ai_called")
    assert [r.source_attempt_id for r in mine] == ["bf-req-1"]
    live = producers.emit_ai_called(user_id=u.id, ai_request_id="bf-req-1",
                                    capability="tutor.chat", status="succeeded",
                                    occurred_at=None)
    assert live["emitted"] == 0            # backfill and live agree on identity


def test_backfill_is_idempotent(db_session):
    u = make_user(db_session, "bf_idem")
    _kp_event(db_session, "bf_idem", 21, "question_correct", 8, datetime(2024, 1, 1))
    first = backfill.run_records_backfill(db_session)
    second = backfill.run_records_backfill(db_session)
    assert first["inserted"] >= 1
    assert second["inserted"] == 0         # nothing new on re-run
    assert len(events_for(db_session, u.id, "knowledge_status_changed")) == 1


def test_backfill_dry_run_writes_nothing(db_session):
    u = make_user(db_session, "bf_dry")
    _kp_event(db_session, "bf_dry", 22, "question_correct", 8, datetime(2024, 1, 1))
    before = len(events_for(db_session, u.id, "knowledge_status_changed"))
    report = backfill.run_records_backfill(db_session, dry_run=True)
    assert report["dry_run"] is True
    assert len(events_for(db_session, u.id, "knowledge_status_changed")) == before


def test_backfill_classification_is_explicit():
    matrix = {row["source"]: row for row in backfill.classification_matrix()}
    assert matrix["knowledge_progress_events"]["classification"] == "PARTIAL"
    assert matrix["ai_requests"]["classification"] == "PARTIAL"
    practice_rows = [r for r in backfill.classification_matrix()
                     if r["source"] == "learning_records"
                     and r["record_kind"] == "practice"]
    assert practice_rows[0]["classification"] == "INELIGIBLE"


# ---------------------------------------------------------------- tiers

@pytest.mark.parametrize("tier", ["free", "standard", "advanced"])
def test_event_persistence_is_independent_of_membership_tier(db_session, tier):
    """Free must record the same key learning events as a paid account (§17)."""
    from usage import service as usage_service

    u = make_user(db_session, f"tier_{tier}")
    if tier != "free":
        usage_service.activate_subscription(db_session, u.id, tier, 30)
    _record(db_session, u, EXAM, qid=f"tier-{tier}", correct=False,
            when=datetime(2024, 3, 1), tag=f"tier-{tier}")
    producers.emit_ai_called(user_id=u.id, ai_request_id=f"tier-req-{tier}",
                             capability="tutor.chat", status="succeeded",
                             occurred_at=None)
    mine = events_for(db_session, u.id)
    assert {r.event_type for r in mine} == {"question_answered", "ai_called"}
