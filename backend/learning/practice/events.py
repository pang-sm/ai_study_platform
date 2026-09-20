"""Practice Core → LearningEvent bridge.

OWNERSHIP (frozen, STEP 7D)
---------------------------
``course_practice`` events have exactly ONE authoritative owner: the existing
``data_plane.emitter`` on the course-learning submit path. The Practice Core must never
emit a second event for those attempts — that would double-count the learner's history
for StudentTwin. ``emit_for_attempt`` therefore refuses ``course_learning`` outright.

For attempts whose domain has no emitter today (exam_prep, programming) the Practice
Core IS the owner. Those events:

  * are derived from the durable ``PracticeAttempt`` — never from client payload;
  * use the frozen deterministic id function (``data_plane.identity.event_id``) over the
    same (source_type, source_attempt_id, item_key) triple, so replay/backfill agree;
  * use event types that are NOT ``course_practice`` (``question_answered`` /
    ``code_submitted``), which is what keeps them out of the StudentTwin producer: the
    worker selects ``LearningEvent.event_type == "course_practice"`` only.

EVENT RECOVERY: because a canonical attempt is durable and its event id is
deterministic, a failed emission is recoverable by replaying ``recover_events`` — a
historical fact can never be permanently absent from the data plane.
"""
from __future__ import annotations

import json
import logging
import time

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core.learning_context import ServiceNamespace, resolve_event_subject_key
from core import timeutil
from data_plane import identity, origin
from data_plane.models import LearningEvent

from ..records.envelope import domain_context_json

from .models import PracticeAttempt

logger = logging.getLogger("learning.practice")

EVENT_SCHEMA_VERSION = 2
EVENT_GRANULARITY = "ITEM_LEVEL"

# learning space → practice-owned event type.
EVENT_TYPE_BY_NAMESPACE = {
    ServiceNamespace.COURSE_LEARNING.value: "question_answered",
    ServiceNamespace.EXAM_PREP.value: "question_answered",
    ServiceNamespace.PROGRAMMING.value: "code_submitted",
}

# Sources whose events are already owned by ANOTHER producer. A course AIQuestionAttempt
# produces the frozen ``course_practice`` event through ``data_plane.emitter``; emitting
# ``question_answered`` for the same attempt as well would double-count one answer.
FOREIGN_OWNED_SOURCES = {
    (ServiceNamespace.COURSE_LEARNING.value, "ai_question_attempt"),
}

# The practice-owned event families, used to keep recovery scoped.
PRACTICE_EVENT_TYPES = tuple(EVENT_TYPE_BY_NAMESPACE.values())


def event_type_for(service_namespace: str) -> str | None:
    return EVENT_TYPE_BY_NAMESPACE.get(service_namespace)


def _source_triple(attempt: PracticeAttempt) -> tuple[str, str, str]:
    """The (source_type, source_attempt_id, item_key) triple for event identity."""
    if attempt.source_attempt_type and attempt.source_attempt_id:
        item_key = attempt.source_item_key or attempt.source_attempt_id
        return attempt.source_attempt_type, str(attempt.source_attempt_id), str(item_key)
    # born in the Practice Core: its own deterministic uid is the source identity
    return "practice_attempt", str(attempt.attempt_uid), str(attempt.attempt_uid)


def _item_index(item_key: str) -> int:
    tail = str(item_key).rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _result_field(attempt: PracticeAttempt, key: str):
    """One factual field from the attempt's persisted result blob, or None."""
    try:
        data = json.loads(attempt.result_json or "{}")
    except (TypeError, ValueError):
        return None
    return data.get(key) if isinstance(data, dict) else None


def _context(attempt: PracticeAttempt) -> dict:
    try:
        data = json.loads(attempt.context_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def build_event(attempt: PracticeAttempt) -> dict | None:
    """Build the LearningEvent payload for one canonical attempt, or None if not ours."""
    event_type = event_type_for(attempt.service_namespace)
    if event_type is None:
        return None

    source_type, source_attempt_id, item_key = _source_triple(attempt)
    if (attempt.service_namespace, source_type) in FOREIGN_OWNED_SOURCES:
        # the existing emitter owns this fact; a second event would double-count it
        return None

    ctx = _context(attempt)

    # The Practice Core references questions rather than copying them, so the snapshot
    # is explicitly PARTIAL: content is NOT duplicated out of the static assets.
    #
    # `judge` is carried because it is a FACT about the verdict, and the StudentTwin input
    # rule (data_plane.eligibility) must be decidable from the event alone: an
    # authoritative binary correctness fact requires that the item was not self-reviewed.
    # It is a marker, not content, so the snapshot stays PARTIAL and leaks nothing.
    snapshot = {
        "question_source_type": attempt.question_source_type,
        "question_source_id": attempt.question_source_id,
        "service_namespace": attempt.service_namespace,
        "judge": _result_field(attempt, "judge"),
        "context": ctx,
    }
    missing = ["item_content"]

    occurred = timeutil.to_epoch_or_now(attempt.submitted_at)

    # UNANSWERED != INCORRECT and UNANSWERED != SCORED-ZERO. A blank submission has no
    # factual verdict and no authoritative score; both cross the event boundary as null so
    # no reader can render "0 分" for a question the learner never answered.
    if not str(attempt.answer or "").strip():
        correct, score = None, None
    else:
        correct, score = attempt.correct, attempt.score

    return {
        "event_id": identity.event_id(source_type, source_attempt_id, item_key),
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "event_type": event_type,
        "event_granularity": EVENT_GRANULARITY,
        "source_type": source_type,
        "source_attempt_id": str(source_attempt_id),
        "source_item_key": str(item_key),
        "source_item_index": _item_index(item_key),
        "user_id": attempt.user_id,
        "source_user_ref": attempt.username,
        "service_key": attempt.service_namespace,
        # carried from the attempt's LearningContext so course-scoped records can be
        # filtered by course identity (§428 pipeline); never a display name
        "course_id": ctx.get("course_id"),
        "subject_key": resolve_event_subject_key(ctx),
        "question_id": attempt.question_source_id,
        "knowledge_point_ref_json": identity.canonical_json(
            domain_context_json(ctx)),
        "item_snapshot_json": identity.canonical_json(snapshot),
        "item_content_hash": identity.item_content_hash(snapshot),
        "answer": attempt.answer,
        "correct": correct,                  # tri-state preserved through the bridge
        "score": score,
        "response_time_ms": attempt.response_time_ms,
        "attempt_no": attempt.attempt_no,
        # ACCEL_SPRINT_S5: the duration's provenance and the per-(user, question) attempt
        # ordinal travel WITH the duration. A downstream scientific reader must be able to
        # tell a measured duration from a number of unknown origin without opening the
        # practice row — and both are NULL whenever the source did not observe them.
        "response_time_source": attempt.response_time_source,
        "attempt_index": attempt.attempt_index,
        "occurred_at": occurred,
        "ingested_at": time.time(),
        "source_payload_version": 1,
        "idempotency_key": identity.idempotency_key(source_type, source_attempt_id, item_key),
        "snapshot_capture_mode": "PRACTICE_CORE",
        "snapshot_completeness": "PARTIAL",
        "snapshot_missing_fields_json": identity.canonical_json(missing),
    }


def emit_for_attempt(db, attempt: PracticeAttempt) -> dict:
    """Best-effort emit for one durable attempt. Never raises.

    The emitted event inherits the ATTEMPT's recorded origin, not the emitting process's:
    the fact was created when the attempt was created, and a later re-emit (a repair run, a
    different process) must not be able to relabel it.
    """
    event = build_event(attempt)
    if event is None:
        return {"emitted": 0, "reason": "not_practice_owned"}
    event["data_origin"] = attempt.data_origin or origin.active_origin()

    # The caller's practice transaction is already committed; a distinct session keeps a
    # data-plane failure from rolling the attempt back.
    try:
        from database import SessionLocal
        session = SessionLocal()
    except Exception as exc:  # noqa: BLE001
        logger.warning("practice.event_emit_failed attempt_id=%s error=%s",
                       attempt.id, type(exc).__name__)
        return {"emitted": 0, "reason": "session_unavailable"}

    try:
        stmt = sqlite_insert(LearningEvent).values(**event).on_conflict_do_nothing(
            index_elements=["event_id"])
        result = session.execute(stmt)
        session.commit()
        return {"emitted": result.rowcount or 0, "reason": "ok"}
    except Exception as exc:  # noqa: BLE001 — data plane must never break practice
        session.rollback()
        logger.warning("practice.event_emit_failed attempt_id=%s namespace=%s error=%s",
                       attempt.id, attempt.service_namespace, type(exc).__name__)
        return {"emitted": 0, "reason": "emit_failed"}
    finally:
        session.close()
        _ = db  # the caller's session is intentionally untouched


def emit_for_attempts(db, attempts) -> dict:
    emitted = dup = skipped = 0
    for attempt in attempts:
        res = emit_for_attempt(db, attempt)
        if res["reason"] == "not_practice_owned":
            skipped += 1
        elif res["emitted"]:
            emitted += 1
        else:
            dup += 1
    return {"emitted": emitted, "already_present_or_failed": dup, "not_owned": skipped}


def recover_events(db, *, limit: int = 1000) -> dict:
    """Re-emit events for durable attempts whose event never landed.

    Recovery is possible precisely because the event id is deterministic: re-running
    this cannot create a duplicate, only fill a real gap.
    """
    from sqlalchemy import func, select

    from database import SessionLocal

    session = SessionLocal()
    try:
        known = select(LearningEvent.source_type, LearningEvent.source_attempt_id,
                       LearningEvent.source_item_key)
        known_pairs = {(r[0], str(r[1]), str(r[2])) for r in session.execute(known)}
    finally:
        session.close()

    candidates = (db.query(PracticeAttempt)
                  .filter(PracticeAttempt.service_namespace.in_(
                      list(EVENT_TYPE_BY_NAMESPACE.keys())))
                  .order_by(PracticeAttempt.id.asc())
                  .limit(limit * 5).all())

    emitted = 0
    for attempt in candidates:
        source_type, source_attempt_id, item_key = _source_triple(attempt)
        if (source_type, source_attempt_id, item_key) in known_pairs:
            continue
        if emit_for_attempt(db, attempt)["emitted"]:
            emitted += 1
        if emitted >= limit:
            break
    _ = func
    return {"recovered": emitted, "scanned": len(candidates)}
