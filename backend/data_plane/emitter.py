"""Post-commit best-effort LearningEvent emitter (course_practice).

The emitter is called AFTER the original business transaction has committed.  It opens a
NEW SQLAlchemy session/transaction and inserts idempotently (INSERT OR IGNORE on event_id).
Any Data Plane failure is logged and swallowed — it must NEVER fail the course submit.
"""
import logging
import os
import time

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core import timeutil

from . import identity, origin, snapshots
from .models import LearningEvent

logger = logging.getLogger("data_plane")

EVENT_TYPE = "course_practice"
SERVICE_KEY = "course_learning"
SOURCE_TYPE = "course_practice"


def write_enabled() -> bool:
    return os.getenv("DATA_PLANE_WRITE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def build_course_practice_events(attempt, item, answer, correct, user) -> list:
    """Build ITEM_LEVEL LearningEvent payloads (FULL live snapshot) for one attempt.

    Handles the general N-question case; course_learning mode is a single question.
    ``correct`` comes from the existing business submit computation, NOT re-derived here.
    """
    import json as _json
    qids = _json.loads(attempt.question_ids_json or "[]")
    occurred = timeutil.to_epoch_or_now(getattr(attempt, "submitted_at", None))
    events = []
    for idx, qid in enumerate(qids):
        qid_str = str(qid)
        item_key = identity.source_item_key(qid_str, idx)
        snapshot = snapshots.build_live_item_snapshot(item)
        events.append({
            "event_id": identity.event_id(SOURCE_TYPE, str(attempt.id), item_key),
            "event_schema_version": 2,
            "event_type": EVENT_TYPE,
            "event_granularity": "ITEM_LEVEL",
            "source_type": SOURCE_TYPE,
            "source_attempt_id": str(attempt.id),
            "source_item_key": item_key,
            "source_item_index": idx,
            "user_id": user.id,
            "source_user_ref": attempt.username,
            "service_key": SERVICE_KEY,
            "course_id": None,
            "subject_key": attempt.subject_key,
            "question_id": qid_str,
            "knowledge_point_ref_json": identity.canonical_json(snapshots.build_knowledge_point_ref(attempt)),
            "item_snapshot_json": identity.canonical_json(snapshot),
            "item_content_hash": identity.item_content_hash(snapshot),
            "answer": answer,
            "correct": correct,
            "score": None,
            "response_time_ms": None,
            "attempt_no": None,
            "occurred_at": occurred,
            "ingested_at": time.time(),
            "source_payload_version": 1,
            "idempotency_key": identity.idempotency_key(SOURCE_TYPE, str(attempt.id), item_key),
            "snapshot_capture_mode": "LIVE_EMITTER",
            "snapshot_completeness": "FULL",
            "snapshot_missing_fields_json": identity.canonical_json([]),
        })
        origin.stamp(events[-1])
    return events


def best_effort_emit(events, SessionLocal) -> int:
    """Insert LearningEvents in a NEW transaction.  Returns number inserted.  Never raises."""
    if not events:
        return 0
    if not write_enabled():
        return 0
    session = SessionLocal()
    inserted = 0
    try:
        for ev in events:
            stmt = sqlite_insert(LearningEvent).values(**ev).on_conflict_do_nothing(index_elements=["event_id"])
            result = session.execute(stmt)
            inserted += result.rowcount or 0
        session.commit()
    except Exception as exc:  # noqa: BLE001 — Data Plane failure must not fail submit
        session.rollback()
        logger.warning(
            "data_plane emit failed: type=%s source_type=%s attempt=%s item_keys=%s",
            type(exc).__name__, SOURCE_TYPE,
            events[0].get("source_attempt_id") if events else None,
            [e.get("source_item_key") for e in events],
        )
    finally:
        session.close()
    return inserted
