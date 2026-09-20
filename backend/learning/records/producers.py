"""Trusted LearningEvent producers.

Every producer here is called from SERVER-SIDE business facts only, after the durable
domain row has committed. There is deliberately no HTTP entry point that lets a client
post an arbitrary event (§25).

Each producer is failure-isolated: a data-plane problem must never roll back or fail the
business fact that already committed. Failures are logged and counted, so they are
observable and, where the durable source allows it, recoverable by backfill.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from data_plane.models import LearningEvent
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core import timeutil
from core.learning_context import LearningContext, ServiceNamespace

from .envelope import EventValidationError, build_event

logger = logging.getLogger("learning.records")

# observability counters (§45) — process-local, same style as the existing emitter
COUNTERS = {
    "events_emitted": 0,
    "events_deduped": 0,
    "events_failed": 0,
    "events_validation_failed": 0,
}


def counters() -> dict:
    return dict(COUNTERS)


def reset_counters() -> None:
    for key in COUNTERS:
        COUNTERS[key] = 0


def _bump(key: str, n: int = 1) -> None:
    COUNTERS[key] = COUNTERS.get(key, 0) + n


def write_event(event: dict) -> dict:
    """Insert one validated event idempotently (INSERT OR IGNORE on event_id).

    EVERY failure is absorbed, including failing to obtain a session at all: the
    business fact behind this event has already committed and must not be disturbed by
    a data-plane problem, however early it strikes.

    The dataset origin is stamped HERE rather than by each producer: this is the single
    insert every produced event passes through, so no producer can forget to declare why
    its fact exists (``data_plane.origin``).
    """
    session = None
    try:
        from data_plane import origin
        event = origin.stamp(event)
        from database import SessionLocal
        session = SessionLocal()
        stmt = sqlite_insert(LearningEvent).values(**event).on_conflict_do_nothing(
            index_elements=["event_id"])
        result = session.execute(stmt)
        session.commit()
        inserted = result.rowcount or 0
        _bump("events_emitted" if inserted else "events_deduped")
        return {"emitted": inserted, "event_id": event["event_id"]}
    except Exception as exc:  # noqa: BLE001 — never fail the business fact
        if session is not None:
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
        _bump("events_failed")
        logger.warning("records.event_write_failed event_type=%s error=%s",
                       event.get("event_type"), type(exc).__name__)
        return {"emitted": 0, "event_id": event.get("event_id"), "reason": "write_failed"}
    finally:
        if session is not None:
            session.close()


def emit(event_factory) -> dict:
    """Build + validate + write, absorbing every failure into counters."""
    try:
        event = event_factory()
    except EventValidationError as exc:
        _bump("events_validation_failed")
        logger.warning("records.event_validation_failed error=%s", str(exc)[:200])
        return {"emitted": 0, "reason": "validation_failed"}
    except Exception as exc:  # noqa: BLE001
        _bump("events_failed")
        logger.warning("records.event_build_failed error=%s", type(exc).__name__)
        return {"emitted": 0, "reason": "build_failed"}
    return write_event(event)


def _epoch(value) -> float:
    """One shared conversion: a naive persisted datetime is UTC, never server-local."""
    return timeutil.to_epoch_or_now(value)


# ---------------------------------------------------------------- AI

def emit_ai_called(*, user_id: int, ai_request_id: str, capability: str, status: str,
                   occurred_at, service_namespace: str = ServiceNamespace.COURSE_LEARNING.value,
                   provider: str | None = None, credits=None,
                   error_category: str | None = None,
                   source_user_ref: str | None = None,
                   learning_context: LearningContext | None = None) -> dict:
    """One terminal AI request. References and a coarse class only — no prompt/response.

    A provider failure is recorded as a coarse status plus the NORMALIZED error category
    (authentication / rate_limited / timeout / ...). Vendor stack traces, error bodies
    and retry internals stay in ops telemetry and never reach a learning record (§16).
    """
    payload = {
        "ai_request_id": str(ai_request_id),
        "capability": capability,
        "status": status,
    }
    if provider:
        payload["provider"] = provider          # provider name is not sensitive
    if credits is not None:
        payload["credit_class"] = int(credits)
    if error_category:
        payload["error_category"] = str(error_category)
    if learning_context is not None:
        service_namespace = learning_context.service_namespace.value
        event_context = learning_context.to_event_context()
    else:
        event_context = None
    return emit(lambda: build_event(
        event_type="ai_called", user_id=user_id, service_namespace=service_namespace,
        occurred_at=_epoch(occurred_at), source_type="ai_request",
        source_id=ai_request_id, source_item_key=str(capability or "unknown"),
        payload=payload, context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["prompt", "response"],
    ))


# ---------------------------------------------------------------- knowledge

def emit_knowledge_status_changed(*, user_id: int, knowledge_point_id, new_status: str,
                                  occurred_at, source_type: str, source_id,
                                  service_namespace: str,
                                  old_status: str | None = None,
                                  subject_key: str | None = None,
                                  course_id: str | None = None,
                                  source_user_ref: str | None = None,
                                  source_item_key: str = "status",
                                  exam_module_id: str | None = None,
                                  extra_payload: dict | None = None) -> dict:
    """A real user knowledge-status transition — never an inferred mastery claim."""
    payload = {"new_status": new_status}
    if old_status is not None:
        payload["old_status"] = old_status
    if extra_payload:
        payload.update(extra_payload)
    return emit(lambda: build_event(
        event_type="knowledge_status_changed", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type=source_type, source_id=source_id, source_item_key=source_item_key,
        payload=payload,
        context={"knowledge_point_id": (str(knowledge_point_id)
                                        if knowledge_point_id is not None else None),
                 "exam_module_id": exam_module_id,
                 "subject_key": subject_key, "course_id": course_id},
        source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["mastery_semantics"],
    ))


# ---------------------------------------------------------------- material

def emit_material_asked(*, user_id: int, material_id, occurred_at, source_id,
                        capability: str | None = None, ai_request_id: str | None = None,
                        service_namespace: str = ServiceNamespace.COURSE_LEARNING.value,
                        source_user_ref: str | None = None,
                        source_item_key: str | None = None) -> dict:
    """The learner asked something about a material. Question text stays in chat_messages."""
    payload = {"material_id": str(material_id)}
    if capability:
        payload["capability"] = capability
    if ai_request_id:
        payload["ai_request_id"] = str(ai_request_id)
    return emit(lambda: build_event(
        event_type="material_asked", user_id=user_id, service_namespace=service_namespace,
        occurred_at=_epoch(occurred_at), source_type="material_ask", source_id=source_id,
        source_item_key=source_item_key or str(material_id), payload=payload,
        source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["question_text"],
    ))


def emit_material_opened(*, user_id: int, material_id, occurred_at,
                         service_namespace: str = ServiceNamespace.COURSE_LEARNING.value,
                         source_user_ref: str | None = None) -> dict:
    """A material was opened.

    DEDUP: a page refresh must not become an event, so the identity is
    (user, material, UTC day) — the deterministic event_id makes repeat opens on the
    same day collapse into the one event that actually happened.
    """
    occurred = _epoch(occurred_at)
    day = datetime.utcfromtimestamp(occurred).strftime("%Y-%m-%d")
    payload = {"material_id": str(material_id), "day": day}
    return emit(lambda: build_event(
        event_type="material_opened", user_id=user_id,
        service_namespace=service_namespace, occurred_at=occurred,
        source_type="material_open", source_id=f"{user_id}:{material_id}",
        source_item_key=day, payload=payload, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["read_duration"],
    ))
