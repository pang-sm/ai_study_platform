"""Records backfill / reconciliation.

Every source is classified honestly (FULL / PARTIAL / INELIGIBLE) with the reason
stated. Backfilled events reuse the SAME identity strategy as the live producers, so a
fact that was recorded live and then replayed by the backfill collapses onto one event
instead of two (§30).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from core import timeutil
from core.learning_context import ServiceNamespace

from . import producers

logger = logging.getLogger("learning.records")

FULL = "FULL"
PARTIAL = "PARTIAL"
INELIGIBLE = "INELIGIBLE"

SOURCE_CLASSIFICATION = (
    {"source": "learning_records", "record_kind": "practice",
     "classification": INELIGIBLE,
     "reason": "the underlying practice fact is already owned by the practice spine / "
               "course_practice emitter; mirroring it would double-count one answer"},
    {"source": "learning_records", "record_kind": "review (material-linked)",
     "classification": PARTIAL,
     "reason": "maps to material_asked via the SAME identity as the live producer "
               "(source_id=message_id, item_key=material:message_id); question text is "
               "not copied, and missing material references cannot be mapped"},
    {"source": "learning_records", "record_kind": "other record_type",
     "classification": INELIGIBLE,
     "reason": "no canonical event type corresponds to it; the durable row remains the "
               "source of truth for its own feature"},
    {"source": "knowledge_progress_events", "record_kind": "delta-driven causes",
     "classification": PARTIAL,
     "reason": "records a mastery-score delta and its cause, NOT a status transition. "
               "old/new status is recovered by replaying the product's own documented "
               "clamp+threshold rule in chronological order (derived_from=delta_replay_v1); "
               "status changes made outside this path are not visible here"},
    {"source": "ai_requests", "record_kind": "terminal requests",
     "classification": PARTIAL,
     "reason": "FULL for identity/status/credits; a later reconcile_credits would move a "
               "reconciliation_pending request without rewriting its already-written event"},
)

_TERMINAL_REQUEST_STATUS = {
    "settled": "succeeded",
    "released": "failed",
    "reconciliation_pending": "pending",
}

# The product's own status derivation (main.apply_knowledge_progress_event).
_STATUS_THRESHOLDS = ((80, "mastered"), (40, "reviewing"), (1, "learning"))
_INITIAL_STATUS = "not_started"


def classification_matrix() -> list[dict]:
    return [dict(row) for row in SOURCE_CLASSIFICATION]


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def _status_for(score: int) -> str:
    for threshold, status in _STATUS_THRESHOLDS:
        if score >= threshold:
            return status
    return _INITIAL_STATUS


def _users_by_name(db) -> dict:
    from models import User
    return {u.username: u for u in db.query(User).all()}


def _epoch(value) -> float:
    """One shared conversion: a naive persisted datetime is UTC, never server-local."""
    return timeutil.to_epoch_or_now(value)


# ---------------------------------------------------------------- knowledge

def backfill_knowledge_progress_events(db, report: dict, *, limit: int | None = None) -> None:
    from models import KnowledgeProgressEvent

    users = _users_by_name(db)
    q = db.query(KnowledgeProgressEvent).order_by(
        KnowledgeProgressEvent.created_at.asc(), KnowledgeProgressEvent.id.asc())
    if limit:
        q = q.limit(limit)

    state: dict[tuple, tuple[int, str, bool]] = {}   # key → (score, status, seeded)
    for row in q.all():
        user = users.get(row.username)
        if user is None:
            report["skipped"] += 1
            continue
        key = (row.username, row.course_id, row.knowledge_point_id)
        score, status, seeded = state.get(key, (0, _INITIAL_STATUS, False))
        if not seeded:
            # the durable progress row carries the starting point when it exists
            seeded_score, seeded_status = _seed_from_progress(db, row)
            if seeded_score is not None:
                score, status = seeded_score, seeded_status
        new_score = _clamp(score + (row.delta or 0))
        new_status = _status_for(new_score)
        state[key] = (new_score, new_status, True)

        if new_status == status:
            report["skipped"] += 1          # a score nudge is not a status change
            continue

        result = producers.emit_knowledge_status_changed(
            user_id=user.id, knowledge_point_id=row.knowledge_point_id,
            new_status=new_status, old_status=status,
            occurred_at=_epoch(row.created_at),
            source_type="knowledge_progress_event", source_id=row.id,
            service_namespace=ServiceNamespace.COURSE_LEARNING.value,
            course_id=row.course_id, source_user_ref=row.username,
            extra_payload={"change_event_type": row.event_type, "delta": row.delta,
                           "derived_from": "delta_replay_v1"})
        _count(report, result)


def _seed_from_progress(db, row):
    """Initial score/status for a knowledge point before its first recorded delta.

    Uses the durable progress row only when it is consistent with a fresh start
    (score 0 / not_started); otherwise the replay base is unknown and we stay with the
    documented initial state rather than inventing a different starting point.
    """
    from models import UserKnowledgeProgress
    progress = (db.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.username == row.username,
                        UserKnowledgeProgress.course_id == row.course_id,
                        UserKnowledgeProgress.knowledge_point_id == row.knowledge_point_id)
                .first())
    if progress is None:
        return 0, _INITIAL_STATUS
    return None, None       # a pre-existing score means the replay base is unknown


# ---------------------------------------------------------------- legacy records

def backfill_learning_records(db, report: dict, *, limit: int | None = None) -> None:
    """Legacy ``learning_records`` → canonical events.

    Only material-linked review records are mappable, and they map onto the SAME event
    identity the live producer uses, so a live ask and its historical row collapse into
    one event. ``practice`` records are deliberately NOT mapped: the practice spine
    already owns that fact.
    """
    from models import LearningRecord

    users = {u.id: u for u in db.query(_user_model()).all()}
    q = db.query(LearningRecord).order_by(LearningRecord.id.asc())
    if limit:
        q = q.limit(limit)

    for row in q.all():
        if row.record_type != "review" or not row.message_id:
            report["skipped"] += 1
            continue
        user = users.get(row.user_id)
        if user is None:
            report["skipped"] += 1
            continue
        material_ids = _material_ids(row)
        if not material_ids:
            report["skipped"] += 1
            continue
        for material_id in material_ids:
            result = producers.emit_material_asked(
                user_id=user.id, material_id=material_id,
                occurred_at=_epoch(row.created_at), source_id=row.message_id,
                capability="material.qa",
                service_namespace=ServiceNamespace.COURSE_LEARNING.value,
                source_user_ref=user.username,
                # identical to the live producer's identity for the same ask
                source_item_key=f"{material_id}:{row.message_id}")
            _count(report, result)


def _user_model():
    from models import User
    return User


def _material_ids(row) -> list[int]:
    try:
        payload = json.loads(row.references_json or "[]")
    except (TypeError, ValueError):
        return []
    out: list[int] = []
    items = payload if isinstance(payload, list) else payload.get("materials", [])
    for item in items or []:
        value = item.get("id") if isinstance(item, dict) else item
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in out:
            out.append(value)
    return out


# ---------------------------------------------------------------- AI

def rebuild_ai_events(db, report: dict, *, limit: int | None = None) -> None:
    """``ai_requests`` → ``ai_called``. Same identity the live producer uses."""
    from models import User
    from usage.models import AIRequest

    users = {u.id: u for u in db.query(User).all()}
    q = db.query(AIRequest).order_by(AIRequest.id.asc())
    if limit:
        q = q.limit(limit)

    for row in q.all():
        status = _TERMINAL_REQUEST_STATUS.get(row.status or "")
        if status is None:
            report["skipped"] += 1
            continue
        user = users.get(row.user_id)
        if user is None:
            report["skipped"] += 1
            continue
        result = producers.emit_ai_called(
            user_id=user.id, ai_request_id=row.request_id,
            capability=row.capability or "unknown", status=status,
            occurred_at=_epoch(row.finished_at or row.created_at),
            provider=row.provider, credits=row.actual_credits,
            error_category=(row.error_category if status == "failed" else None),
            source_user_ref=user.username)
        _count(report, result)


def _count(report: dict, result: dict) -> None:
    if result.get("emitted"):
        report["inserted"] += 1
    elif result.get("reason"):
        report["failed"] += 1
    else:
        report["deduped"] += 1


BACKFILLERS = (
    ("learning_records", backfill_learning_records),
    ("knowledge_progress_events", backfill_knowledge_progress_events),
    ("ai_requests", rebuild_ai_events),
)


def run_records_backfill(db, *, sources=None, limit: int | None = None,
                         dry_run: bool = False) -> dict:
    """Reconcile the canonical event stream from durable sources. Idempotent."""
    report = {"inserted": 0, "deduped": 0, "skipped": 0, "failed": 0}
    if dry_run:
        # dry-run counts what WOULD be considered, without writing anything
        for name, fn in BACKFILLERS:
            if sources and name not in sources:
                continue
            probe = {"inserted": 0, "deduped": 0, "skipped": 0, "failed": 0}
            if name == "ai_requests":
                _count_candidates(db, probe, limit)
            else:
                probe["skipped"] = _count_rows(db, name, limit)
            for key in report:
                report[key] += probe[key]
        report["dry_run"] = True
        report["classification"] = classification_matrix()
        return report

    for name, fn in BACKFILLERS:
        if sources and name not in sources:
            continue
        fn(db, report, limit=limit)
    report["dry_run"] = False
    report["classification"] = classification_matrix()
    logger.info("records.backfill_inserted=%s skipped=%s failed=%s",
                report["inserted"], report["skipped"], report["failed"])
    return report


def _count_rows(db, name: str, limit) -> int:
    from models import KnowledgeProgressEvent, LearningRecord
    model = {"learning_records": LearningRecord,
             "knowledge_progress_events": KnowledgeProgressEvent}.get(name)
    return db.query(model).count() if model is not None else 0


def _count_candidates(db, probe: dict, limit) -> None:
    from usage.models import AIRequest
    probe["skipped"] = db.query(AIRequest).count()
