"""StudentTwin product integration (PART C) — a read-only learning-state PREVIEW.

WHAT STUDENT TWIN IS
--------------------
A deterministic, rule-based state engine written in Python. It is NOT a neural network,
NOT an AI prediction model, and its output is NOT a mastery score. It replays an ordered
history of factual practice events and returns the resulting state. Every number it emits
is reproducible from the same input, and none of it may gate a product decision
(``controls_product_decision = False``).

WHAT THIS MODULE DOES
---------------------
Reads the caller's REAL canonical events (the ``learning_events`` stream — no LLM output,
no re-derivation, no fabricated fields), maps them to the runtime's event schema, and asks
the Scientific Runtime Service for the state. It writes nothing: no knowledge status, no
mastery, no wrong-answer state, no plan, no grade.
"""
from __future__ import annotations

import hashlib
import json
import logging

from data_plane import eligibility
from data_plane.models import LearningEvent
from sqlalchemy.orm import Session as DbSession

from . import metadata
from .client import (
    ScientificClient,
    ScientificRejected,
    ScientificUnavailable,
    get_client,
    new_request_id,
)

logger = logging.getLogger("science.student_twin")

COMPONENT = "student_twin"
CONTRACT_VERSION = 1
RUNTIME_PATH = "/v1/inference/student-twin"

# A preview is bounded: the most recent N events in scope, never the whole history.
MAX_EVENTS = 2000

# Product event type -> the runtime's activity class. Only families that carry a factual
# correctness measurement are mapped: StudentTwin consumes measured practice, and an
# ungraded item carries no evidence.
ACTIVITY_BY_EVENT_TYPE = {
    "course_practice": "PRACTICE",
    "question_answered": "PRACTICE",
}

# Reported when the caller's real events exist but none of them carry an authoritative
# binary correctness fact. It names the actual reason, never a blanket family refusal.
BLOCKER_INPUT_EXCLUDED = "STUDENT_TWIN_INPUT_EXCLUDED"


def user_ref_for(user_id: int) -> str:
    """An opaque, stable reference. The runtime needs an identity, not a person."""
    return "u_" + hashlib.sha256(f"student-twin:{user_id}".encode()).hexdigest()[:32]


def _context_of(event: LearningEvent) -> dict:
    try:
        parsed = json.loads(event.knowledge_point_ref_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def to_runtime_event(event: LearningEvent, user_ref: str) -> dict | None:
    """Map one ELIGIBLE canonical event to the runtime's event schema.

    Called only after :func:`data_plane.eligibility.student_twin_event_eligibility` has
    accepted the event, so ``correct`` is guaranteed to be a real boolean. Nothing is
    invented: an absent field stays absent.
    """
    activity = ACTIVITY_BY_EVENT_TYPE.get(event.event_type)
    if activity is None or not isinstance(event.correct, bool):
        return None
    context = _context_of(event)
    return {
        "event_id": event.event_id,
        "occurred_at": float(event.occurred_at),
        "activity_type": activity,
        # the runtime schema requires a bool; events without a factual verdict are skipped
        "correct": bool(event.correct),
        "source": event.event_type,
        "item_id": event.question_id,
        "concept_ref": context.get("knowledge_point_id"),
        "response_time_ms": event.response_time_ms,
        "attempt_no": event.attempt_no,
        "hints": None,
    }


def load_input(db: DbSession, user_id: int, *, service_namespace: str | None = None,
               exam_module_id: str | None = None, limit: int = MAX_EVENTS) -> dict:
    """The caller's real ELIGIBLE practice history in scope, oldest-first.

    The family filter is deliberately broader than the verdict: every capable-family event
    in the window is examined, and the ones the S2 input rule rejects are counted with
    their reason, so the caller is told exactly why their evidence was not used instead of
    seeing an unexplained empty state.
    """
    from sqlalchemy import func

    q = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id,
        LearningEvent.event_type.in_(eligibility.STUDENT_TWIN_INPUT_EVENT_TYPES))
    if service_namespace:
        q = q.filter(LearningEvent.service_key == service_namespace)
    if exam_module_id:
        q = q.filter(func.json_extract(LearningEvent.knowledge_point_ref_json,
                                       "$.exam_module_id") == exam_module_id)

    # bounded: newest `limit` rows, then flipped to the runtime's oldest-first order
    rows = (q.order_by(LearningEvent.occurred_at.desc(), LearningEvent.event_id.desc())
            .limit(max(1, int(limit))).all())
    rows.reverse()

    user_ref = user_ref_for(user_id)
    events: list[dict] = []
    excluded: dict[str, int] = {}
    for row in rows:
        verdict = eligibility.student_twin_event_eligibility(row)
        if not verdict.eligible:
            excluded[verdict.reason] = excluded.get(verdict.reason, 0) + 1
            continue
        mapped = to_runtime_event(row, user_ref)
        if mapped is not None:
            events.append(mapped)

    types: dict[str, int] = {}
    for event in events:
        types[event["source"]] = types.get(event["source"], 0) + 1

    return {"events": events, "user_ref": user_ref, "event_types": types,
            "scanned": len(rows), "excluded_reasons": excluded}


def preview(db: DbSession, user_id: int, *, service_namespace: str | None = None,
            exam_module_id: str | None = None,
            client: ScientificClient | None = None) -> dict:
    """Compute a StudentTwin state preview. Never raises for a runtime outage."""
    payload = load_input(db, user_id, service_namespace=service_namespace,
                         exam_module_id=exam_module_id)
    events = payload["events"]

    # S2: no blanket family refusal. A blocker is reported only for the events the input
    # rule actually rejected, and it names the reason, so valid CS408 evidence produces no
    # blocker at all.
    blockers = [f"{BLOCKER_INPUT_EXCLUDED}: {reason} ({count})"
                for reason, count in sorted(payload["excluded_reasons"].items())]

    input_summary = {
        "event_count": len(events),
        "event_types": payload["event_types"],
        "excluded_event_count": sum(payload["excluded_reasons"].values()),
        "excluded_reasons": payload["excluded_reasons"] or None,
        "scanned_events": payload["scanned"],
        "bounded_to": MAX_EVENTS,
        "scope": {"service_namespace": service_namespace,
                  "exam_module_id": exam_module_id},
        "eligibility_rule": eligibility.RULE_STATEMENT,
        "semantics": "real canonical practice facts; no LLM output, no derived learner state",
    }

    if not events:
        return {
            "metadata": metadata.metadata(
                component=COMPONENT, mode=metadata.MODE_UNAVAILABLE,
                runtime_release_id=None, source_class=None,
                blockers=blockers + ["NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE"],
                semantics="deterministic replay of factual practice events; "
                          "NOT a neural model and NOT a mastery score"),
            "input_summary": input_summary,
            "state": None,
        }

    request_id = new_request_id(COMPONENT)
    runtime_request = {
        "contract_version": CONTRACT_VERSION,
        "request_id": request_id,
        "user_ref": payload["user_ref"],
        "target_event_id": events[-1]["event_id"],
        "events": events,
    }

    client = client or get_client()
    try:
        body = client.infer(RUNTIME_PATH, runtime_request, component=COMPONENT)
    except (ScientificUnavailable, ScientificRejected) as exc:
        # PART F: a scientific outage — or a request the runtime refused — is a bounded
        # "temporarily unavailable", never a failure of the learning flow and never a 500.
        # The preview is a convenience; the learner's real practice data is unaffected.
        logger.warning("student_twin preview unavailable request_id=%s detail=%s",
                       request_id, getattr(exc, "detail", None))
        return {
            "metadata": metadata.metadata(
                component=COMPONENT, mode=metadata.MODE_UNAVAILABLE,
                request_id=request_id, blockers=blockers + ["SCIENTIFIC_RUNTIME_UNAVAILABLE"],
                semantics="deterministic replay of factual practice events; "
                          "NOT a neural model and NOT a mastery score"),
            "input_summary": input_summary,
            "state": None,
        }

    return {
        "metadata": metadata.from_runtime_response(
            COMPONENT, metadata.MODE_PREVIEW, body, blockers=blockers,
            semantics="deterministic rule-based state replay; NOT a neural model, "
                      "NOT a mastery probability, and it controls no product decision"),
        "input_summary": input_summary,
        "state": body.get("state"),
    }
