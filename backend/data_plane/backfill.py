"""Deterministic idempotent historical backfill for course_practice LearningEvents.

Historical AIQuestionAttempt records are NOT self-contained (result_json lacks
stem/options/question_type), so backfill produces PARTIAL snapshots and records the
missing fields.  It never fabricates history from the mutable AIGeneratedQuestion row.
"""
import json
import logging
import time

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from . import identity, snapshots
from .emitter import SOURCE_TYPE, SERVICE_KEY, EVENT_TYPE
from .models import LearningEvent

logger = logging.getLogger("data_plane.backfill")


def build_backfill_events(attempt, user_id) -> list:
    """Build PARTIAL LearningEvent payloads from a durable attempt record alone."""
    qids = json.loads(attempt.question_ids_json or "[]")
    answers = json.loads(attempt.answers_json or "{}")
    result_items = {}
    try:
        res = json.loads(attempt.result_json or "{}")
    except Exception:
        res = {}
    # result_items keyed by question_id (course_learning single-item result has question_id)
    for r in res.get("results", []):
        result_items[str(r.get("question_id"))] = r
    if "question_id" in res and not result_items:
        result_items[str(res["question_id"])] = res

    occurred = (attempt.submitted_at.timestamp() if getattr(attempt, "submitted_at", None) else time.time())
    events = []
    for idx, qid in enumerate(qids):
        qid_str = str(qid)
        item_key = identity.source_item_key(qid_str, idx)
        ri = result_items.get(qid_str, {})
        answer = answers.get(qid_str)
        correct = ri.get("correct")
        snapshot, missing = snapshots.build_backfill_item_snapshot(attempt, ri)
        events.append({
            "event_id": identity.event_id(SOURCE_TYPE, str(attempt.id), item_key),
            "event_schema_version": 2,
            "event_type": EVENT_TYPE,
            "event_granularity": "ITEM_LEVEL",
            "source_type": SOURCE_TYPE,
            "source_attempt_id": str(attempt.id),
            "source_item_key": item_key,
            "source_item_index": idx,
            "user_id": user_id,
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
            "snapshot_capture_mode": "SOURCE_BACKFILL",
            "snapshot_completeness": "PARTIAL" if missing else "FULL",
            "snapshot_missing_fields_json": identity.canonical_json(missing),
        })
    return events


def backfill(attempts, SessionLocal, user_map, apply=False) -> dict:
    """Scan attempts, build events, insert idempotently.  Returns a report dict."""
    report = {
        "attempts_scanned": 0, "attempts_eligible": 0, "items_seen": 0,
        "events_existing": 0, "events_created": 0, "events_partial": 0,
        "events_full": 0, "events_failed": 0, "duplicate_prevented": 0,
    }
    session = SessionLocal() if apply else None
    try:
        for attempt in attempts:
            report["attempts_scanned"] += 1
            if attempt.status != "submitted":
                continue
            user_id = user_map.get(attempt.username)
            if user_id is None:
                continue
            report["attempts_eligible"] += 1
            events = build_backfill_events(attempt, user_id)
            for ev in events:
                report["items_seen"] += 1
                if ev["snapshot_completeness"] == "PARTIAL":
                    report["events_partial"] += 1
                else:
                    report["events_full"] += 1
                if apply:
                    try:
                        stmt = (sqlite_insert(LearningEvent).values(**ev)
                                .on_conflict_do_nothing(index_elements=["event_id"]))
                        r = session.execute(stmt)
                        if r.rowcount:
                            report["events_created"] += 1
                        else:
                            report["events_existing"] += 1
                            report["duplicate_prevented"] += 1
                    except Exception as exc:  # noqa: BLE001
                        report["events_failed"] += 1
                        logger.warning("backfill insert failed: %s", type(exc).__name__)
        if apply:
            session.commit()
    finally:
        if session is not None:
            session.close()
    return report
