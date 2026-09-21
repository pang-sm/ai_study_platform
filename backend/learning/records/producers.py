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
                   model: str | None = None,
                   reason_code: str | None = None,
                   candidate_count: int | None = None,
                   quality_class: str | None = None,
                   latency_class: str | None = None,
                   router_version: str | None = None,
                   entitlement_grant: str | None = None,
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
    # Router V1 observability (P4 §D/§E): WHICH model was chosen, WHY, and how big the
    # candidate pool was. Refs + classes only — never a prompt, a response or a candidate's
    # pricing internals.
    for key, value in (("model", model), ("router_reason_code", reason_code),
                       ("quality_class", quality_class), ("latency_class", latency_class),
                       ("router_version", router_version),
                       # P6: the MODE of an ops flag that granted this call's entitlement step
                       # (ALL / INTERNAL). Absent on every ordinary call — the learner's own
                       # tier is what opened those, and it is already recorded.
                       ("entitlement_grant", entitlement_grant)):
        if value:
            payload[key] = str(value)
    if candidate_count is not None:
        payload["candidate_count"] = int(candidate_count)
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


# ---------------------------------------------------------------- Deep Study (P3A)

def emit_strong_reasoning_requested(*, user_id: int, run_id: str, capability: str,
                                    service_namespace: str, question_len: int | None = None,
                                    material_ids: list | None = None,
                                    learning_context: LearningContext | None = None,
                                    occurred_at, source_user_ref: str | None = None) -> dict:
    """The learner started a Deep Study session.

    References and counts only: the question text stays in the request, and the materials are
    named by id. ``run_id`` ties this fact to the completed one and to nothing else.
    """
    payload = {"run_id": str(run_id), "capability": capability}
    if question_len is not None:
        payload["question_len"] = int(question_len)
    if material_ids:
        payload["material_ids"] = [str(m) for m in material_ids][:20]
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="strong_reasoning_requested", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="strong_reasoning_run", source_id=run_id,
        source_item_key="requested", payload=payload, context=event_context,
        source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["question_text", "answer"],
    ))


def emit_strong_reasoning_completed(*, user_id: int, run_id: str, request_id: str,
                                    status: str, capability: str, service_namespace: str,
                                    chunk_count: int | None = None,
                                    learning_context: LearningContext | None = None,
                                    occurred_at, source_user_ref: str | None = None) -> dict:
    """The Deep Study session produced an answer, with the request that answered it."""
    payload = {"run_id": str(run_id), "request_id": str(request_id), "status": status,
               "capability": capability}
    if chunk_count is not None:
        payload["chunk_count"] = int(chunk_count)
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="strong_reasoning_completed", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="strong_reasoning_run", source_id=run_id,
        source_item_key="completed", payload=payload, context=event_context,
        source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["answer"],
    ))


# ---------------------------------------------------------------- Programming agent (P3A)

def emit_programming_agent_started(*, user_id: int, agent_run_id: str, exercise_id,
                                   language: str | None, max_iterations: int,
                                   max_executions: int, learning_context=None,
                                   occurred_at, source_user_ref: str | None = None) -> dict:
    """A bounded debug workflow began. The bounds travel WITH the fact that they applied."""
    payload = {"agent_run_id": str(agent_run_id),
               "max_iterations": int(max_iterations),
               "max_executions": int(max_executions)}
    if exercise_id is not None:
        payload["exercise_id"] = int(exercise_id)
    if language:
        payload["language"] = language
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else {"programming_language": language})
    return emit(lambda: build_event(
        event_type="programming_agent_started", user_id=user_id,
        service_namespace=ServiceNamespace.PROGRAMMING.value,
        occurred_at=_epoch(occurred_at), source_type="programming_agent_run",
        source_id=agent_run_id, source_item_key="started", payload=payload,
        context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["code", "prompt"],
    ))


def _agent_trace_payload(*, agent_run_id: str, status: str, steps: list | None,
                         error_category: str | None = None,
                         tests_before: dict | None = None,
                         tests_after: dict | None = None,
                         reason: str | None = None) -> dict:
    payload = {"agent_run_id": str(agent_run_id), "status": status,
               "step_count": len(steps or [])}
    if steps:
        payload["steps"] = steps
    if error_category:
        payload["error_category"] = str(error_category)
    if reason:
        payload["reason"] = str(reason)
    if tests_before:
        payload["tests_before"] = tests_before
    if tests_after:
        payload["tests_after"] = tests_after
    return payload


def emit_programming_agent_completed(*, user_id: int, agent_run_id: str, status: str,
                                     language: str | None, steps: list | None = None,
                                     tests_before: dict | None = None,
                                     tests_after: dict | None = None,
                                     reason: str | None = None, occurred_at,
                                     source_user_ref: str | None = None) -> dict:
    """The workflow finished, whether the tests passed, and every step it took.

    ``steps`` is the CODE-FREE trace built by ``agent.step_trace``: a step that carried
    source code would be rejected here by ``envelope.assert_payload_is_safe``.
    """
    payload = _agent_trace_payload(agent_run_id=agent_run_id, status=status, steps=steps,
                                   tests_before=tests_before, tests_after=tests_after,
                                   reason=reason)
    if language:
        payload["language"] = language
    return emit(lambda: build_event(
        event_type="programming_agent_completed", user_id=user_id,
        service_namespace=ServiceNamespace.PROGRAMMING.value,
        occurred_at=_epoch(occurred_at), source_type="programming_agent_run",
        source_id=agent_run_id, source_item_key="completed", payload=payload,
        context={"programming_language": language}, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["code", "prompt", "response"],
    ))


def emit_programming_agent_failed(*, user_id: int, agent_run_id: str, error_category: str,
                                  language: str | None, steps: list | None = None,
                                  occurred_at, source_user_ref: str | None = None) -> dict:
    """The workflow stopped before it could finish, with the steps that DID happen."""
    payload = _agent_trace_payload(agent_run_id=agent_run_id, status="failed", steps=steps,
                                   error_category=error_category)
    if language:
        payload["language"] = language
    return emit(lambda: build_event(
        event_type="programming_agent_failed", user_id=user_id,
        service_namespace=ServiceNamespace.PROGRAMMING.value,
        occurred_at=_epoch(occurred_at), source_type="programming_agent_run",
        source_id=agent_run_id, source_item_key="failed", payload=payload,
        context={"programming_language": language}, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["code", "prompt", "response"],
    ))


# ---------------------------------------------------------------- P3B

def emit_report_generated(*, user_id: int, report_id: str, period_days: int,
                          service_namespace: str, metric_blocks: list | None = None,
                          narrative: bool = False, request_id: str | None = None,
                          learning_context: LearningContext | None = None,
                          occurred_at, source_user_ref: str | None = None) -> dict:
    """A structured learning report was produced for one learner and one period."""
    payload = {"report_id": str(report_id), "period_days": int(period_days),
               "narrative": bool(narrative)}
    if metric_blocks:
        payload["metric_blocks"] = [str(block) for block in metric_blocks][:16]
    if request_id:
        payload["request_id"] = str(request_id)
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="report_generated", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="learning_report", source_id=report_id, source_item_key="generated",
        payload=payload, context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["narrative_text"]))


def emit_wrong_analysis_generated(*, user_id: int, state_id, question_source_type: str,
                                  question_source_id: str, request_id: str,
                                  service_namespace: str,
                                  learning_context: LearningContext | None = None,
                                  occurred_at, source_user_ref: str | None = None) -> dict:
    """A wrong-answer state was analysed. References only — the analysis text is AI output."""
    payload = {"state_id": str(state_id),
               "question_source_type": str(question_source_type),
               "question_source_id": str(question_source_id),
               "request_id": str(request_id)}
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="wrong_analysis_generated", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="wrong_analysis", source_id=str(state_id),
        source_item_key=str(request_id), payload=payload, context=event_context,
        source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["analysis_text"]))


def emit_plan_adjustment_proposed(*, user_id: int, proposal_id: str, change_count: int,
                                  plan_identity: str, service_namespace: str,
                                  request_id: str | None = None,
                                  learning_context: LearningContext | None = None,
                                  occurred_at, source_user_ref: str | None = None) -> dict:
    """An adjustment was PROPOSED. Nothing was written to the plan by this fact."""
    payload = {"proposal_id": str(proposal_id), "change_count": int(change_count),
               "plan_identity": str(plan_identity)}
    if request_id:
        payload["request_id"] = str(request_id)
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="plan_adjustment_proposed", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="plan_adjustment", source_id=proposal_id, source_item_key="proposed",
        payload=payload, context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["proposal_text"]))


def emit_plan_adjustment_applied(*, user_id: int, proposal_id: str, applied_count: int,
                                 plan_identity: str, service_namespace: str,
                                 learning_context: LearningContext | None = None,
                                 occurred_at, source_user_ref: str | None = None) -> dict:
    """The learner accepted a proposal and the plan changed."""
    payload = {"proposal_id": str(proposal_id), "applied_count": int(applied_count),
               "plan_identity": str(plan_identity)}
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="plan_adjustment_applied", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="plan_adjustment", source_id=proposal_id, source_item_key="applied",
        payload=payload, context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["applied_text"]))


# ---------------------------------------------------------------- P4

def emit_adaptive_practice_selected(*, user_id: int, selection_id: str, candidate_count: int,
                                    service_namespace: str, reason_codes: list | None = None,
                                    policy_version: str, source_item_key: str = "selected",
                                    learning_context: LearningContext | None = None,
                                    occurred_at, source_user_ref: str | None = None) -> dict:
    """An adaptive selection was made. Reasons only — never a predicted weakness."""
    payload = {"selection_id": str(selection_id), "candidate_count": int(candidate_count),
               "policy_version": str(policy_version)}
    if reason_codes:
        payload["reason_codes"] = sorted({str(code) for code in reason_codes})[:12]
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="adaptive_practice_selected", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="adaptive_selection", source_id=selection_id,
        source_item_key=source_item_key, payload=payload, context=event_context,
        source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["candidate_content"]))


def emit_review_scheduled(*, user_id: int, item_id: str, due_at: str, policy_version: str,
                          service_namespace: str, interval_days=None, reason: str | None = None,
                          scheduled_at: str | None = None,
                          facts: dict | None = None, source_item_key: str | None = None,
                          learning_context: LearningContext | None = None,
                          occurred_at, source_user_ref: str | None = None) -> dict:
    """A next review date was computed. The policy and its inputs travel WITH the date."""
    payload = {"item_id": str(item_id), "due_at": str(due_at),
               "policy_version": str(policy_version)}
    if interval_days is not None:
        payload["interval_days"] = int(interval_days)
    if reason:
        payload["reason"] = str(reason)
    if scheduled_at:
        payload["scheduled_at"] = str(scheduled_at)
    if facts:
        payload["facts"] = {str(key): value for key, value in list(facts.items())[:12]}
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="review_scheduled", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="review_item", source_id=item_id,
        source_item_key=source_item_key or str(due_at), payload=payload,
        context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["interval_history"]))


def emit_review_completed(*, user_id: int, item_id: str, result: str,
                          service_namespace: str, policy_version: str | None = None,
                          next_due_at: str | None = None, attempt_id=None,
                          learning_context: LearningContext | None = None,
                          source_item_key: str | None = None,
                          occurred_at, source_user_ref: str | None = None) -> dict:
    """The learner finished one review, with the real result that was recorded."""
    payload = {"item_id": str(item_id), "result": str(result)}
    if policy_version:
        payload["policy_version"] = str(policy_version)
    if next_due_at:
        payload["next_due_at"] = str(next_due_at)
    if attempt_id is not None:
        payload["attempt_id"] = str(attempt_id)
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="review_completed", user_id=user_id,
        service_namespace=service_namespace, occurred_at=_epoch(occurred_at),
        source_type="review_item", source_id=item_id,
        source_item_key=source_item_key or f"completed:{result}", payload=payload,
        context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["review_notes"]))


def emit_ai_feedback_submitted(*, user_id: int, request_id: str, rating: str,
                               service_namespace: str | None = None,
                               capability: str | None = None, reason: str | None = None,
                               model: str | None = None, provider: str | None = None,
                               latency_ms: int | None = None,
                               estimated_credits: int | None = None,
                               actual_credits: int | None = None,
                               regenerated: bool = False, switched_model: bool = False,
                               workflow_id: str | None = None,
                               router_reason: str | None = None,
                               learning_context: LearningContext | None = None,
                               occurred_at, source_user_ref: str | None = None) -> dict:
    """One rating of one AI response — references and classifications, never free text."""
    payload = {"request_id": str(request_id), "rating": str(rating),
               "regenerated": bool(regenerated), "switched_model": bool(switched_model)}
    for key, value in (("capability", capability), ("reason", reason), ("model", model),
                       ("provider", provider), ("workflow_id", workflow_id),
                       ("router_reason", router_reason)):
        if value:
            payload[key] = str(value)
    for key, value in (("latency_ms", latency_ms), ("estimated_credits", estimated_credits),
                       ("actual_credits", actual_credits)):
        if value is not None:
            payload[key] = int(value)
    event_context = (learning_context.to_event_context()
                     if learning_context is not None else None)
    return emit(lambda: build_event(
        event_type="ai_feedback_submitted", user_id=user_id,
        service_namespace=service_namespace or ServiceNamespace.COURSE_LEARNING.value,
        occurred_at=_epoch(occurred_at), source_type="ai_feedback",
        source_id=request_id, source_item_key="rating", payload=payload,
        context=event_context, source_user_ref=source_user_ref,
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["feedback_text"]))


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
