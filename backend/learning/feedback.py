"""Unified AI response feedback — one contract for every AI surface.

WHAT THIS IS FOR
----------------
Not a thumbs-up decoration. A rating is recorded against the REQUEST that produced the
response, together with everything an offline decision would need to interpret it: which
capability, which model served it, which router reason picked it, how long it took and what it
cost. A rating without that context is uninterpretable later, and a rating that is not tied to
the caller is a security hole.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does NOT train, adjust or re-rank the router — not on one dislike, and not on a thousand.
Feedback is stored as an audit fact so a FUTURE, offline decision can use it (with its own
validation); the live router keeps selecting from the Qualified Model Pool by the same
deterministic rules, and no learner signal ever enters a selection.

REUSE, NOT A NEW TABLE
----------------------
The request identity, model, provider, capability, cost and timing already live in
``ai_requests``; the rating and its classification are recorded as a canonical AUDIT event
(``ai_feedback_submitted``) whose payload carries references and closed-vocabulary codes only.
No schema change is needed, and no free text is stored — a detail box belongs in a support
flow, not in a telemetry stream.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

logger = logging.getLogger("learning.feedback")

RATING_UP = "up"
RATING_DOWN = "down"
RATINGS = (RATING_UP, RATING_DOWN)

# FROZEN taxonomy for negative feedback. Extending it is a product decision, not a code change.
REASON_TAXONOMY = ("incorrect", "too_shallow", "too_complex", "too_verbose", "too_brief",
                   "bad_code", "slow", "poor_image", "other")


class FeedbackRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _router_reason(db: DbSession, request_id: str) -> str | None:
    """The router's reason code for this request, from its own audit fact (if it has one)."""
    from data_plane.models import LearningEvent
    import json

    row = (db.query(LearningEvent)
           .filter(LearningEvent.event_type == "ai_called",
                   LearningEvent.source_type == "ai_request",
                   LearningEvent.source_attempt_id == str(request_id))
           .order_by(LearningEvent.occurred_at.desc()).first())
    if row is None:
        return None
    try:
        payload = json.loads(row.item_snapshot_json or "{}")
    except (TypeError, ValueError):
        return None
    value = payload.get("router_reason_code")
    return str(value) if value else None


def submit_feedback(db: DbSession, user, *, request_id: str, rating: str,
                    reason: str | None = None, regenerated: bool = False,
                    switched_model: bool = False, workflow_id: str | None = None) -> dict:
    """Record ONE rating of ONE of the caller's OWN AI responses."""
    from usage.models import AIRequest

    normalized_rating = str(rating or "").strip().lower()
    if normalized_rating not in RATINGS:
        raise FeedbackRefusal("invalid_rating", f"rating 必须是 {list(RATINGS)} 之一")
    normalized_reason = str(reason or "").strip().lower() or None
    if normalized_reason is not None and normalized_reason not in REASON_TAXONOMY:
        raise FeedbackRefusal("invalid_reason",
                              f"reason 必须是 {list(REASON_TAXONOMY)} 之一")
    if normalized_rating == RATING_DOWN and normalized_reason is None:
        raise FeedbackRefusal("reason_required", "负反馈必须给出原因分类")

    request = (db.query(AIRequest)
               .filter(AIRequest.request_id == str(request_id),
                       AIRequest.user_id == user.id).first())
    if request is None:
        raise FeedbackRefusal("request_not_found", "AI 请求不存在")

    latency_ms = None
    if request.started_at and request.finished_at:
        latency_ms = int((request.finished_at - request.started_at).total_seconds() * 1000)

    router_reason = _router_reason(db, str(request_id))
    record = {
        "request_id": request.request_id,
        "rating": normalized_rating,
        "reason": normalized_reason,
        "regenerated": bool(regenerated),
        "switched_model": bool(switched_model),
        "workflow_id": workflow_id or None,
        "capability": request.capability,
        "service_namespace": request.service_namespace,
        "model": request.model,
        "provider": request.provider,
        "tier": request.tier,
        "status": request.status,
        "latency_ms": latency_ms,
        "estimated_credits": request.estimated_credits,
        "actual_credits": request.actual_credits,
        "router_reason": router_reason,
        "context": request.context_json,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "submitted_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "trains_router_online": False,
        "reason_taxonomy": list(REASON_TAXONOMY),
    }

    try:
        from learning.records import producers
        producers.emit_ai_feedback_submitted(
            user_id=user.id, request_id=request.request_id, rating=normalized_rating,
            service_namespace=request.service_namespace, capability=request.capability,
            reason=normalized_reason, model=request.model, provider=request.provider,
            latency_ms=latency_ms, estimated_credits=request.estimated_credits,
            actual_credits=request.actual_credits, regenerated=bool(regenerated),
            switched_model=bool(switched_model), workflow_id=workflow_id,
            router_reason=router_reason, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001 — a records problem never fails the rating
        logger.warning("feedback.event_failed error=%s", type(exc).__name__)
    return record
