"""Learning Records read model — a projection over ``learning_events``.

There is no second record table: records ARE the event stream, read back under a
user-facing shape with a safe serializer. Everything is user-scoped.

Time semantics are UTC throughout: ``occurred_at`` is stored as a UTC epoch number and
query bounds are converted to UTC explicitly (a naive input is read as UTC, never as
server local time).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from core import timeutil
from core.learning_context import (
    ServiceNamespace,
    normalize_service_namespace,
)
from data_plane.models import LearningEvent
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from . import envelope, taxonomy

logger = logging.getLogger("learning.records")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class RecordsError(Exception):
    pass


class RecordNotFound(RecordsError):
    pass


def _to_epoch(value) -> float | None:
    """ISO-8601 or epoch → UTC epoch seconds.

    Delegates to the ONE shared conversion (:mod:`core.timeutil`) so the read side and
    every write-side producer agree: a naive value is UTC, never server-local time.
    """
    try:
        return timeutil.to_epoch(value)
    except ValueError as exc:
        raise RecordsError(f"invalid datetime {value!r}") from exc


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()


def _encode_cursor(event: LearningEvent) -> str:
    # repr round-trips the float exactly; formatting to a fixed number of decimals would
    # round the boundary and make the next page repeat the last row.
    return f"{float(event.occurred_at)!r}|{event.event_id}"


def _decode_cursor(cursor: str) -> tuple[float, str]:
    try:
        occurred, event_id = str(cursor).split("|", 1)
        return float(occurred), event_id
    except (ValueError, AttributeError) as exc:
        raise RecordsError("invalid cursor") from exc


def _safe_view(event: LearningEvent) -> dict:
    """Public shape. Never dumps raw payload or private content (§19)."""
    payload = {}
    try:
        parsed = json.loads(event.item_snapshot_json or "{}")
        payload = parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        payload = {}
    context = {}
    try:
        parsed_ctx = json.loads(event.knowledge_point_ref_json or "{}")
        if isinstance(parsed_ctx, dict):
            # The domain-context JSON carries the exam module alongside the knowledge
            # point; both are references, neither is learner state.
            for key in ("knowledge_point_id", "exam_module_id"):
                if parsed_ctx.get(key):
                    context[key] = parsed_ctx[key]
    except (TypeError, ValueError):
        pass
    for key in ("course_id", "subject_key"):
        value = getattr(event, key, None)
        if value:
            context[key] = value

    # PROGRAMMING facts carry their language and exercise identity in the snapshot's own
    # context, not in a column (``learning_events`` has none for either — see
    # ``native_concept.PROGRAMMING_CONTEXT_KEYS``, which is the same declaration the
    # producers write against). Without this a programming record could not say which
    # language it belongs to, and the caller would have to parse an implementation blob.
    if event.service_key == ServiceNamespace.PROGRAMMING.value:
        program_context = payload.get("context")
        program_context = program_context if isinstance(program_context, dict) else {}
        language = str(program_context.get("programming_language") or "").strip()
        if language:
            context["programming_language"] = language
        if program_context.get("exercise_id") is not None:
            context["exercise_id"] = program_context["exercise_id"]
        if payload.get("project_id") is not None:
            context["project_id"] = payload["project_id"]

    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "record_category": taxonomy.category_for(event.event_type),
        "service_namespace": event.service_key,
        "occurred_at": _iso(event.occurred_at),
        "schema_version": event.event_schema_version,
        "context": context or None,
        # source REFERENCE, not the fact itself — the domain table stays authoritative
        "source": {
            "type": event.source_type,
            "id": event.source_attempt_id,
            "item_key": event.source_item_key,
        },
        "summary": _summary_of(event, payload),
    }


def _summary_of(event: LearningEvent, payload: dict) -> dict:
    """Small display metadata. References and factual metrics only."""
    summary: dict = {}
    if event.event_type in ("question_answered", "code_submitted", "course_practice"):
        summary["correct"] = event.correct          # tri-state, carried as-is
        # UNANSWERED != SCORED-ZERO. Mirrors the write boundary: a blank submission has no
        # authoritative score, so a zero here would be an invented "0 分".
        blank = not str(getattr(event, "answer", None) or "").strip()
        if event.score is not None and not blank:
            summary["score"] = event.score
        question_ref = payload.get("question_source_type")
        if question_ref:
            summary["question_source_type"] = question_ref
            summary["question_source_id"] = payload.get("question_source_id")
        if event.question_id:
            summary["question_source_id"] = event.question_id
    elif event.event_type in ("code_run", "code_tested"):
        # EXECUTION facts only. A run produces no verdict and a check against the
        # exercise's own tests is not a submission, so neither carries `correct` — that
        # belongs to `code_submitted`, the one graded fact in the programming loop.
        for key in ("passed_count", "total_count", "exit_code", "timed_out"):
            if payload.get(key) is not None:
                summary[key] = payload[key]
    elif event.event_type == "ai_called":
        summary["capability"] = payload.get("capability")
        summary["status"] = payload.get("status")
    elif event.event_type == "knowledge_status_changed":
        summary["new_status"] = payload.get("new_status")
        if payload.get("old_status") is not None:
            summary["old_status"] = payload.get("old_status")
    elif event.event_type in ("material_opened", "material_asked"):
        summary["material_id"] = payload.get("material_id")
        if payload.get("capability"):
            summary["capability"] = payload["capability"]
    return summary


def _base_query(db: DbSession, user_id: int, *, start_at, end_at, service_namespace,
                exam_module_id: str | None = None, course_id: str | None = None):
    """User-scoped event query with the shared window / namespace / scope filters."""
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)

    start_epoch = _to_epoch(start_at)
    end_epoch = _to_epoch(end_at)
    if start_epoch is not None:
        q = q.filter(LearningEvent.occurred_at >= start_epoch)
    if end_epoch is not None:
        q = q.filter(LearningEvent.occurred_at <= end_epoch)

    if service_namespace:
        q = q.filter(LearningEvent.service_key == _namespace_value(service_namespace))

    if exam_module_id:
        # exam_module_id lives in the domain-context JSON, applied in SQL (before
        # pagination) so a module-scoped page is correct AND pages stay full.
        q = q.filter(func.json_extract(LearningEvent.knowledge_point_ref_json,
                                       "$.exam_module_id") == exam_module_id)

    if course_id:
        # course_id is a real column on the event. Filtering it AFTER pagination would
        # return short pages and skip matching rows on the next cursor.
        q = q.filter(LearningEvent.course_id == course_id)
    return q


def _visibility_filter(q, *, event_type: str | None, category: str | None,
                       include_audit: bool):
    """Apply the study-history scope SERVER-SIDE (A2).

    ``include_audit=False`` (the default for every user-facing route) restricts the query
    to USER_FACING event types. Audit-only facts (``ai_called``) stay in the database and
    remain queryable by asking for them explicitly — they are never deleted, only kept out
    of the learner's study history.
    """
    if event_type:
        if not taxonomy.is_registered(event_type):
            raise RecordsError(f"unknown event_type {event_type!r}")
        if taxonomy.is_user_facing(event_type) or include_audit:
            return q.filter(LearningEvent.event_type == event_type)
        raise RecordsError(
            f"event_type {event_type!r} is an audit-only fact, not study history; "
            "pass include_audit=true to query it")

    if category:
        if category not in taxonomy.all_categories():
            raise RecordsError(f"unknown record category {category!r}")
        active = [t for t in taxonomy.active_event_types()
                  if taxonomy.category_for(t) == category]
        types = [t for t in active if include_audit or taxonomy.is_user_facing(t)]
        if not types:
            raise RecordsError(
                f"record category {category!r} is audit-only; pass include_audit=true")
        return q.filter(LearningEvent.event_type.in_(types))

    if include_audit:
        return q
    return q.filter(LearningEvent.event_type.in_(taxonomy.user_facing_event_types()))


def list_records(db: DbSession, user_id: int, *, start_at=None, end_at=None,
                 service_namespace: str | None = None, category: str | None = None,
                 event_type: str | None = None, exam_module_id: str | None = None,
                 course_id: str | None = None, limit: int = DEFAULT_LIMIT,
                 cursor: str | None = None, include_audit: bool = False) -> dict:
    """Newest-first page of records. Cursor pagination, deterministic tie-break."""
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    q = _base_query(db, user_id, start_at=start_at, end_at=end_at,
                    service_namespace=service_namespace, exam_module_id=exam_module_id,
                    course_id=course_id)
    q = _visibility_filter(q, event_type=event_type, category=category,
                           include_audit=include_audit)

    if cursor:
        c_occurred, c_id = _decode_cursor(cursor)
        q = q.filter(
            (LearningEvent.occurred_at < c_occurred) |
            ((LearningEvent.occurred_at == c_occurred) & (LearningEvent.event_id < c_id)))

    rows = (q.order_by(LearningEvent.occurred_at.desc(), LearningEvent.event_id.desc())
            .limit(limit + 1).all())
    has_more = len(rows) > limit
    page = rows[:limit]
    return {
        "records": [_safe_view(r) for r in page],
        "next_cursor": _encode_cursor(page[-1]) if (has_more and page) else None,
        "has_more": has_more,
    }


def get_record(db: DbSession, user_id: int, event_id: str,
               include_audit: bool = False) -> dict:
    event = (db.query(LearningEvent)
             .filter(LearningEvent.event_id == event_id,
                     LearningEvent.user_id == user_id)
             .first())
    if event is None:
        raise RecordNotFound(f"record {event_id} not found for this user")
    if not include_audit and not taxonomy.is_user_facing(event.event_type):
        raise RecordNotFound(
            f"record {event_id} is an audit-only fact, not study history")
    view = _safe_view(event)
    view["recovery"] = recovery_capability(event.event_type)
    return view


def summarize_records(db: DbSession, user_id: int, *, start_at=None, end_at=None,
                      service_namespace: str | None = None,
                      exam_module_id: str | None = None,
                      course_id: str | None = None) -> dict:
    """Deterministic records metrics over the study-history scope.

    BOUNDED BY CONSTRUCTION: every figure is a SQL aggregate (COUNT / SUM over
    ``event_type``, ``correct``), so the summary cost is a database scan+aggregate and
    never materializes the user's history in memory. Explicitly NOT mastery / ability.
    """
    start_epoch = _to_epoch(start_at)
    end_epoch = _to_epoch(end_at)
    base = _base_query(db, user_id, start_at=start_at, end_at=end_at,
                       service_namespace=service_namespace,
                       exam_module_id=exam_module_id, course_id=course_id)

    by_type = dict(
        base.with_entities(LearningEvent.event_type, func.count())
        .group_by(LearningEvent.event_type).all())

    # factual tri-state split, computed in SQL
    graded = (base.with_entities(LearningEvent.correct, func.count())
              .filter(LearningEvent.event_type.in_(("question_answered", "course_practice")))
              .filter(LearningEvent.correct.isnot(None))
              .group_by(LearningEvent.correct).all())
    correct_true = next((c for v, c in graded if v is True), 0)
    correct_false = next((c for v, c in graded if v is False), 0)

    practice_attempts = sum(by_type.get(t, 0)
                            for t in ("question_answered", "course_practice"))
    graded_attempts = correct_true + correct_false

    by_category: dict[str, int] = {}
    for event_type, count in by_type.items():
        category = taxonomy.category_for(event_type) or "UnknownEvent"
        by_category[category] = by_category.get(category, 0) + count

    return {
        "window": {"start_at": _iso(start_epoch), "end_at": _iso(end_epoch),
                   "timezone": "UTC"},
        "service_namespace": service_namespace or None,
        "exam_module_id": exam_module_id or None,
        "course_id": course_id or None,
        "total_events": sum(by_type.values()),
        "practice_attempts": practice_attempts,
        "graded_attempts": graded_attempts,
        "factual_correct": correct_true,
        "factual_incorrect": correct_false,
        "ungraded_attempts": practice_attempts - graded_attempts,
        "programming_submissions": by_type.get("code_submitted", 0),
        "material_interactions": (by_type.get("material_opened", 0)
                                  + by_type.get("material_asked", 0)),
        "knowledge_status_changes": by_type.get("knowledge_status_changed", 0),
        "by_category": by_category,
        "by_event_type": by_type,
        "metrics_semantics": "deterministic records counts over study history; NOT "
                             "mastery, ability, or learner-state estimates",
    }


# ---------------------------------------------------------------- recovery

RECOVERY_MATRIX = {
    "course_practice": "FULL（ai_question_attempts → data_plane 既有 backfill）",
    "question_answered": "FULL（practice_attempts → learning.practice.events）",
    "code_submitted": "FULL（practice_attempts → learning.practice.events）",
    "ai_called": "FULL（ai_requests → learning.records.backfill）",
    "knowledge_status_changed": "PARTIAL（knowledge_progress_events）",
    "material_asked": "PARTIAL（chat_messages / ai_requests 可重建引用，问题文本不复原）",
    "material_opened": "EVENT_ONLY（无独立 durable source；事件本身即事实）",
}


def recovery_capability(event_type: str) -> str:
    return RECOVERY_MATRIX.get(event_type, "UNKNOWN")


def recovery_matrix() -> list[dict]:
    return [{"event_type": k, "recovery": v} for k, v in RECOVERY_MATRIX.items()]


def _namespace_value(service_namespace) -> str:
    """Canonical namespace via the shared boundary helper (legacy aliases accepted)."""
    try:
        return normalize_service_namespace(service_namespace)
    except ValueError as exc:
        raise RecordsError(str(exc)) from exc


_ = envelope
