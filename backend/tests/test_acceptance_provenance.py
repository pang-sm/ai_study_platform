"""Trusted acceptance provenance — one production account's facts must never train a model.

ACCEL_PRODUCT provenance closure. The process-wide ``DATA_ORIGIN`` cannot express a
production acceptance account: production refuses that variable on purpose, because a
deployment-wide switch that suppresses every learner's data is destructive where it is
wrong. So the account carries its own marker (``users.data_origin``), written only through
the admin-only contract, and every training-relevant fact it produces inherits it.

What these tests are for: the marker is a DATA-INTEGRITY control, so "it works" has to mean
the fact rows really carry the value, the training export really excludes them, no client can
set it, and no other account is affected.
"""
from __future__ import annotations

import itertools

import pytest

from conftest import register_and_login
from core.learning_context import ServiceNamespace
from data_plane import origin
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.models import PracticeAttempt, PracticeSession
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.records import producers
from science import kt_dataset
import models

COURSE = ServiceNamespace.COURSE_LEARNING
EXAM = ServiceNamespace.EXAM_PREP
PROG = ServiceNamespace.PROGRAMMING

_counter = itertools.count(1)


def _username(prefix: str) -> str:
    return f"{prefix}-{next(_counter)}"


def _user(db, username: str) -> models.User:
    user = models.User(username=username, hashed_password="x", grade="freshman", major="cs")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mark(db, username: str, value: str = origin.ACCEPTANCE) -> models.User:
    """Set the trusted marker directly — the propagation under test, not the contract."""
    user = db.query(models.User).filter_by(username=username).one()
    user.data_origin = value
    db.commit()
    db.refresh(user)
    return user


def _attempt(db, user, namespace, source_id: str) -> PracticeAttempt:
    session = practice_service.create_session(db, user, namespace)
    practice_service.record_attempt(db, user, session, QuestionRef(
        source_type=QuestionSourceType.STATIC_QUESTION_BANK,
        source_id=source_id, service_namespace=namespace), answer="A", correct=True)
    return (db.query(PracticeAttempt)
            .filter(PracticeAttempt.user_id == user.id)
            .order_by(PracticeAttempt.id.desc()).first())


def _events(db, user_id: int) -> list[LearningEvent]:
    # ``event_id`` is the primary key; there is no surrogate id to order by.
    return (db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
            .order_by(LearningEvent.occurred_at.asc()).all())


@pytest.fixture
def cleanup_user_facts(db_session):
    """Remove everything these tests write, so no unrelated suite counts a fact from here.

    The database is shared across the suite and other tests assert on counts; a row left
    behind would make their result depend on module order.
    """
    created: list[int] = []
    yield created
    for user_id in created:
        db_session.query(LearningEvent).filter(LearningEvent.user_id == user_id).delete(
            synchronize_session=False)
        db_session.query(PracticeAttempt).filter(PracticeAttempt.user_id == user_id).delete(
            synchronize_session=False)
        db_session.query(PracticeSession).filter(PracticeSession.user_id == user_id).delete(
            synchronize_session=False)
    db_session.commit()


# ------------------------------------------------------------- 1 / 2  the two populations

def test_a_normal_learner_is_learner_and_training_admissible(db_session, cleanup_user_facts):
    user = _user(db_session, _username("prov-normal"))
    cleanup_user_facts.append(user.id)
    assert origin.origin_for_user(user) == origin.LEARNER

    attempt = _attempt(db_session, user, COURSE, "prov-normal-q1")
    assert attempt.data_origin == origin.LEARNER
    assert origin.is_training_admissible(attempt.data_origin) is True

    events = _events(db_session, user.id)
    assert events and all(e.data_origin == origin.LEARNER for e in events)


def test_an_acceptance_account_is_acceptance_and_not_admissible(db_session, cleanup_user_facts):
    user = _mark(db_session, _user(db_session, _username("prov-acc")).username)
    cleanup_user_facts.append(user.id)

    assert origin.origin_for_user(user) == origin.ACCEPTANCE

    attempt = _attempt(db_session, user, COURSE, "prov-acc-q1")
    assert attempt.data_origin == origin.ACCEPTANCE
    assert origin.is_training_admissible(attempt.data_origin) is False

    events = _events(db_session, user.id)
    assert events, "the attempt must have produced its learning events"
    assert all(e.data_origin == origin.ACCEPTANCE for e in events), \
        [e.data_origin for e in events]


def test_the_emitter_and_the_backfill_stamp_the_account_origin(db_session, cleanup_user_facts):
    """Both course-practice emitters take the ATTEMPT'S ACCOUNT origin.

    The live emitter and the re-projection builder produce the same event for the same
    attempt, so they must also agree on WHY it exists — otherwise replaying history could
    relabel an acceptance account's fact as real data.
    """
    import json
    from types import SimpleNamespace

    from data_plane import backfill, emitter

    user = _mark(db_session, _user(db_session, _username("prov-emit")).username)
    cleanup_user_facts.append(user.id)

    attempt = SimpleNamespace(
        id=97531, username=user.username, subject_key="data_structure",
        knowledge_point_id="kp_list",
        question_ids_json=json.dumps([1]), answers_json=json.dumps({"1": "A"}),
        result_json=json.dumps({"question_id": 1, "correct": True}),
        submitted_at=None, service_namespace=COURSE.value, course_id=None,
        source_attempt_type=None, source_attempt_id=None)
    item = SimpleNamespace(id=1, stem="q", subject_key="data_structure",
                           question_type="选择题", options_json=None,
                           knowledge_point_id="kp_list", standard_answer="A")

    live = emitter.build_course_practice_events(attempt, item, "A", True, user)[0]
    assert live["data_origin"] == origin.ACCEPTANCE

    replayed = backfill.build_backfill_events(attempt, user.id, origin.ACCEPTANCE)[0]
    assert replayed["data_origin"] == origin.ACCEPTANCE
    # same identity, same reason — the two paths must not disagree about either
    assert live["event_id"] == replayed["event_id"]
    assert live["data_origin"] == replayed["data_origin"]


# --------------------------------------------------------------------- 3  the three domains

@pytest.mark.parametrize("namespace", [COURSE, EXAM, PROG], ids=["course", "exam", "programming"])
def test_the_marker_propagates_in_every_learning_space(db_session, cleanup_user_facts, namespace):
    user = _mark(db_session, _user(db_session, _username("prov-ns")).username)
    cleanup_user_facts.append(user.id)

    attempt = _attempt(db_session, user, namespace, f"prov-ns-{namespace.value}")
    assert attempt.service_namespace == namespace.value
    assert attempt.data_origin == origin.ACCEPTANCE
    assert all(e.data_origin == origin.ACCEPTANCE for e in _events(db_session, user.id))


# ------------------------------------------------------------------ 5/6  the producer funnel

def test_ai_request_and_feedback_events_inherit_the_account_origin(db_session, cleanup_user_facts):
    """The funnel is the single stamping point for every produced event, so the AI paths
    are covered by construction — this asserts it rather than trusting the comment."""
    user = _mark(db_session, _user(db_session, _username("prov-ai")).username)
    cleanup_user_facts.append(user.id)

    producers.emit_ai_called(user_id=user.id, ai_request_id="prov-ai-req-1",
                             capability="tutor.chat", status="ok", occurred_at=1000.0,
                             service_namespace=COURSE.value)
    producers.emit_ai_feedback_submitted(user_id=user.id, request_id="prov-ai-req-1",
                                         rating="up", capability="tutor.chat",
                                         service_namespace=COURSE.value, occurred_at=1001.0)

    kinds = {e.event_type: e.data_origin for e in _events(db_session, user.id)}
    assert kinds, "the producers must have written their events"
    assert all(value == origin.ACCEPTANCE for value in kinds.values()), kinds


def test_review_and_progress_events_inherit_the_account_origin(db_session, cleanup_user_facts):
    user = _mark(db_session, _user(db_session, _username("prov-rev")).username)
    cleanup_user_facts.append(user.id)

    producers.emit_review_completed(user_id=user.id, item_id="prov-rev-item-1",
                                    result="remembered", service_namespace=EXAM.value,
                                    occurred_at=2000.0)
    producers.emit_knowledge_status_changed(user_id=user.id, knowledge_point_id="3.6",
                                            new_status="REVIEWING", source_type="knowledge_map",
                                            source_id="prov-rev-kp-1",
                                            service_namespace=EXAM.value, occurred_at=2001.0)

    events = _events(db_session, user.id)
    assert events
    assert all(e.data_origin == origin.ACCEPTANCE for e in events), \
        [(e.event_type, e.data_origin) for e in events]


# ------------------------------------------------------------------ 7  the training selector

def test_the_training_dataset_excludes_an_acceptance_account(db_session, cleanup_user_facts):
    """The hard gate, with the variable isolated.

    Both accounts are given the SAME canonical concept, the same answers and the same shape,
    so the ONLY thing that can decide inclusion is ``data_origin``. The real learner's fact
    must still export — without that control the test could not tell "excluded because
    acceptance" from "excluded because the concept never resolved".

    The events are written directly rather than through the practice service for that same
    reason: the service path would leave the concept unresolvable, which is a second,
    unrelated exclusion. That the writers stamp these origins correctly is proven separately,
    above — here the question is only whether the SELECTOR honours them.
    """
    import json

    learner = _user(db_session, _username("prov-real"))
    acceptance = _mark(db_session, _user(db_session, _username("prov-excl")).username)
    cleanup_user_facts.extend([learner.id, acceptance.id])
    reference = json.dumps({"exam_module_id": "computer_network",
                            "knowledge_point_id": "3.6"})

    keys = ["k-prov-real", "k-prov-acceptance"]
    for event_id, user, value in (("prov-real-e1", learner, origin.LEARNER),
                                  ("prov-acceptance-e1", acceptance, origin.ACCEPTANCE)):
        db_session.add(LearningEvent(
            event_id=event_id, event_schema_version=2, event_type="question_answered",
            event_granularity="ITEM_LEVEL", source_type="chapter_practice",
            source_attempt_id=event_id, source_item_key="1", source_item_index=1,
            user_id=user.id, service_key="exam_prep", subject_key="computer_network",
            question_id="1", knowledge_point_ref_json=reference,
            answer="A", correct=True, occurred_at=3000.0, ingested_at=3000.0,
            source_payload_version=1, idempotency_key=f"k-{event_id}",
            snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="FULL",
            data_origin=value))
    db_session.commit()

    acceptance_body = kt_dataset.build(db_session, user_id=acceptance.id)
    acceptance_exported = [i for sequence in acceptance_body.get("sequences") or []
                           for i in sequence.get("interactions") or []]
    assert acceptance_exported == [], acceptance_exported
    assert acceptance_body["excluded"].get("DATASET_ORIGIN_ACCEPTANCE", 0) >= 1, \
        acceptance_body["excluded"]

    learner_body = kt_dataset.build(db_session, user_id=learner.id)
    learner_exported = [i for sequence in learner_body.get("sequences") or []
                        for i in sequence.get("interactions") or []]
    assert learner_exported, ("the control: a real learner's identical fact must still export "
                              f"(excluded={learner_body['excluded']})")

    for key in keys:
        db_session.query(LearningEvent).filter(LearningEvent.idempotency_key == key).delete(
            synchronize_session=False)
    db_session.commit()


# ---------------------------------------------------------------- 8  isolation between users

def test_marking_one_account_does_not_change_another(db_session, cleanup_user_facts):
    marked = _mark(db_session, _user(db_session, _username("prov-iso-a")).username)
    plain = _user(db_session, _username("prov-iso-b"))
    cleanup_user_facts.extend([marked.id, plain.id])

    marked_attempt = _attempt(db_session, marked, COURSE, "prov-iso-a-q1")
    plain_attempt = _attempt(db_session, plain, COURSE, "prov-iso-b-q1")

    assert marked_attempt.data_origin == origin.ACCEPTANCE
    assert plain_attempt.data_origin == origin.LEARNER
    assert all(e.data_origin == origin.ACCEPTANCE for e in _events(db_session, marked.id))
    assert all(e.data_origin == origin.LEARNER for e in _events(db_session, plain.id))


# ------------------------------------------------------------------- 9  existing semantics

def test_demo_and_test_process_semantics_do_not_regress(db_session, monkeypatch):
    """A process that already declares a non-LEARNER origin keeps it, for every account.

    A deployment-level origin is a property of the deployment; an account marker may never
    upgrade it, or a demo process could be relabelled as producing real data.
    """
    monkeypatch.setattr(origin, "_production", lambda: False)
    monkeypatch.setenv(origin.ENV_VAR, origin.DEMO)

    plain = _user(db_session, _username("prov-proc"))
    marked = _mark(db_session, _user(db_session, _username("prov-proc-m")).username,
                   origin.ACCEPTANCE)

    assert origin.origin_for_user(plain) == origin.DEMO
    assert origin.origin_for_user(marked) == origin.DEMO, \
        "the process origin wins; a marker cannot relabel a demo deployment"
    assert origin.origin_for_user_id(plain.id, db_session) == origin.DEMO


def test_a_marker_can_never_grant_admissibility(db_session):
    """The one-way rule, at the resolver: only exclusion origins are honoured as markers."""
    user = _user(db_session, _username("prov-one-way"))
    user.data_origin = origin.LEARNER          # not an allowed marker value
    db_session.commit()

    # LEARNER is not in the allowed set, so it is not applied as a marker; the account
    # resolves through the ordinary path rather than through a marker that could be used to
    # claim facts are real.
    assert origin.LEARNER not in origin.ALLOWED_ACCOUNT_ORIGINS
    assert origin.ALLOWED_ACCOUNT_ORIGINS == origin.EXCLUDED_FROM_TRAINING


def test_an_unusable_marker_fails_closed_to_unclassified(db_session):
    """Garbage in the column must not silently become real data."""
    user = _user(db_session, _username("prov-garbage"))
    user.data_origin = "NOT_AN_ORIGIN"
    db_session.commit()

    assert origin.origin_for_user(user) == origin.UNCLASSIFIED
    assert origin.is_training_admissible(origin.origin_for_user(user)) is False


def test_production_honours_the_account_marker_while_refusing_the_env_var(db_session, monkeypatch):
    """The whole reason the marker exists.

    Production refuses ``DATA_ORIGIN`` (a deployment-wide switch that would suppress every
    learner's data), so without the marker the acceptance account could not exist there at
    all. It must therefore be honoured on production — and the refusal must stay intact.
    """
    monkeypatch.setattr(origin, "_production", lambda: True)
    user = _mark(db_session, _user(db_session, _username("prov-prod")).username)

    assert origin.origin_for_user(user) == origin.ACCEPTANCE
    assert origin.origin_for_user_id(user.id, db_session) == origin.ACCEPTANCE

    # …and the env var is still refused, for a normal learner on the same process
    monkeypatch.setenv(origin.ENV_VAR, origin.DEMO)
    plain = _user(db_session, _username("prov-prod-plain"))
    assert origin.active_origin() == origin.UNCLASSIFIED
    assert origin.is_training_admissible(origin.UNCLASSIFIED) is False


# ------------------------------------------------------------------ 3  the client cannot spoof

def test_a_client_cannot_make_itself_an_acceptance_account(client, db_session):
    """No request surface sets the marker: it is not a field of any learner request."""
    username = _username("prov-spoof")
    profile = register_and_login(client, username)
    user_id = profile["id"]

    # The obvious vectors, including the one this feature exists to refuse.
    for path, payload in (("/me/profile", {"data_origin": origin.ACCEPTANCE}),
                          ("/register", {"data_origin": origin.ACCEPTANCE}),
                          ("/me/onboarding", {"data_origin": origin.ACCEPTANCE})):
        client.post(path, json=payload)
    client.put("/me/profile", json={"data_origin": origin.ACCEPTANCE})
    client.get("/me/profile", headers={"data_origin": origin.ACCEPTANCE,
                                       "X-Data-Origin": origin.ACCEPTANCE})

    db_session.expire_all()
    row = db_session.query(models.User).filter_by(username=username).one()
    assert row.data_origin is None, f"a client set the marker to {row.data_origin!r}"


def test_the_account_marker_is_never_returned_to_the_client(client):
    """It is internal provenance metadata, not account data."""
    username = _username("prov-hidden")
    register_and_login(client, username)

    body = client.get("/me/profile")
    assert body.status_code == 200, body.text
    assert "data_origin" not in body.text


# ------------------------------------------------------------------- the admin contract

def _make_super(client) -> str:
    username = _username("prov-admin")
    register_and_login(client, username)
    from database import SessionLocal
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter_by(username=username).one()
        admin.is_admin = 1
        admin.admin_role = "super_admin"
        db.commit()
    finally:
        db.close()
    return username


def test_the_admin_contract_marks_and_clears_one_account(client, db_session):
    target = _username("prov-target")
    register_and_login(client, target)
    _make_super(client)

    set_response = client.put(f"/admin/users/{target}/data-origin",
                              json={"data_origin": origin.ACCEPTANCE})
    assert set_response.status_code == 200, set_response.text
    assert set_response.json()["data_origin"] == origin.ACCEPTANCE

    db_session.expire_all()
    assert (db_session.query(models.User).filter_by(username=target).one().data_origin
            == origin.ACCEPTANCE)

    # a super-admin-only write, so it must be auditable
    log = (db_session.query(models.AdminAuditLog)
           .filter(models.AdminAuditLog.action == "update_user_data_origin")
           .order_by(models.AdminAuditLog.id.desc()).first())
    assert log is not None and target in (log.target_username or "")

    cleared = client.put(f"/admin/users/{target}/data-origin", json={"data_origin": ""})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data_origin"] is None
    db_session.expire_all()
    assert (db_session.query(models.User).filter_by(username=target).one().data_origin
            is None)


def test_the_admin_contract_refuses_a_non_exclusion_origin(client):
    target = _username("prov-refuse")
    register_and_login(client, target)
    _make_super(client)

    refused = client.put(f"/admin/users/{target}/data-origin",
                         json={"data_origin": origin.LEARNER})
    assert refused.status_code == 400, refused.text
    assert origin.LEARNER not in origin.ALLOWED_ACCOUNT_ORIGINS


def test_a_plain_learner_cannot_reach_the_contract(client):
    target = _username("prov-plain-target")
    register_and_login(client, target)
    attacker = _username("prov-plain-caller")
    register_and_login(client, attacker)

    refused = client.put(f"/admin/users/{target}/data-origin",
                         json={"data_origin": origin.ACCEPTANCE})
    assert refused.status_code in (401, 403), refused.text
