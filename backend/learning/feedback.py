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

# WHAT the rating is ABOUT. A rating of an ANSWER and a rating of a PLAN SUGGESTION are two
# different questions, and a single shared vocabulary would make them answerable with each
# other's words: "解释不清楚" cannot describe a plan, and "学习任务太多" cannot describe an
# answer. The target therefore selects which closed vocabulary a submission is validated
# against — and the frontend only mirrors that decision, it does not make it.
TARGET_ANSWER = "answer"
TARGET_PLAN_ADJUSTMENT = "plan_adjustment"
TARGETS = (TARGET_ANSWER, TARGET_PLAN_ADJUSTMENT)

# FROZEN taxonomy for negative ANSWER feedback. Its names, values and behaviour are unchanged by
# the plan-adjustment work: this is the set every existing rating was recorded against.
ANSWER_REASON_TAXONOMY = ("incorrect", "not_answered", "unclear", "too_shallow", "too_complex",
                          "too_verbose", "too_brief", "citation_issue", "bad_code", "slow",
                          "poor_image", "other")

# The PLAN-ADJUSTMENT vocabulary: a separate set, never merged into the answer one. Every entry
# is a judgement a learner can actually make about a proposed schedule change.
PLAN_ADJUSTMENT_REASON_TAXONOMY = ("adjustment_too_large", "adjustment_too_small",
                                    "unreasonable_timing", "too_much_work", "too_little_work",
                                    "wrong_priority", "ignored_goal_or_deadline",
                                    "insufficient_reason", "too_vague_to_execute", "other")

REASON_TAXONOMY_BY_TARGET = {
    TARGET_ANSWER: ANSWER_REASON_TAXONOMY,
    TARGET_PLAN_ADJUSTMENT: PLAN_ADJUSTMENT_REASON_TAXONOMY,
}

# Backwards-compatible alias: every existing caller, stored payload and analytics reader says
# `REASON_TAXONOMY` and means the answer set.
REASON_TAXONOMY = ANSWER_REASON_TAXONOMY

# The capability the rated request must actually have been produced by. Without this a client
# could relabel an answer as a plan suggestion and have plan reasons accepted against it — the
# frontend hiding an option is not a boundary.
TARGET_CAPABILITY = {TARGET_ANSWER: None, TARGET_PLAN_ADJUSTMENT: "planning.adjust"}


def normalize_target(value) -> str:
    """The target a submission is for. An unknown or absent value is an ANSWER rating."""
    text = str(value or "").strip().lower()
    return text if text in TARGETS else TARGET_ANSWER


def reason_taxonomy(target: str) -> tuple[str, ...]:
    """The closed vocabulary `target` is validated against."""
    return REASON_TAXONOMY_BY_TARGET.get(target, ANSWER_REASON_TAXONOMY)


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
                    switched_model: bool = False, workflow_id: str | None = None,
                    reasons: list[str] | None = None, comment: str = "",
                    target_type: str = TARGET_ANSWER) -> dict:
    """Record ONE rating of ONE of the caller's OWN AI responses."""
    from usage.models import AIRequest

    normalized_target = normalize_target(target_type)
    allowed_reasons = reason_taxonomy(normalized_target)

    normalized_rating = str(rating or "").strip().lower()
    if normalized_rating not in RATINGS:
        raise FeedbackRefusal("invalid_rating", f"rating 必须是 {list(RATINGS)} 之一")
    normalized_reasons: list[str] = []
    for value in ([reason] if reason else []) + list(reasons or []):
        normalized = str(value or "").strip().lower()
        if not normalized:
            continue
        # Validated against THIS target's vocabulary, so an answer reason on a plan suggestion
        # (or the reverse) is refused here rather than stored as an uninterpretable rating.
        if normalized not in allowed_reasons:
            raise FeedbackRefusal("invalid_reason",
                                  f"{normalized_target} 的 reason 必须是 "
                                  f"{list(allowed_reasons)} 之一")
        if normalized not in normalized_reasons:
            normalized_reasons.append(normalized)
    normalized_reason = normalized_reasons[0] if normalized_reasons else None
    if normalized_rating == RATING_DOWN and normalized_reason is None:
        raise FeedbackRefusal("reason_required", "负反馈必须给出原因分类")
    normalized_comment = str(comment or "").strip()
    if len(normalized_comment) > 1000:
        raise FeedbackRefusal("comment_too_long", "补充说明不能超过 1000 字")

    request = (db.query(AIRequest)
               .filter(AIRequest.request_id == str(request_id),
                       AIRequest.user_id == user.id).first())
    if request is None:
        raise FeedbackRefusal("request_not_found", "AI 请求不存在")

    # The target must match what the request actually was. A caller cannot turn an answer into a
    # plan suggestion (or back) by declaring it so — the request's own capability decides.
    required_capability = TARGET_CAPABILITY[normalized_target]
    if required_capability and request.capability != required_capability:
        raise FeedbackRefusal(
            "target_capability_mismatch",
            f"{normalized_target} 反馈只能针对 {required_capability} 的请求")

    latency_ms = None
    if request.started_at and request.finished_at:
        latency_ms = int((request.finished_at - request.started_at).total_seconds() * 1000)

    router_reason = _router_reason(db, str(request_id))
    record = {
        "request_id": request.request_id,
        "rating": normalized_rating,
        "reason": normalized_reason,
        "reasons": normalized_reasons,
        "comment": normalized_comment,
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
        "target_type": normalized_target,
        # The vocabulary this submission was validated against. Identical to the historical value
        # for every answer rating — which is every rating recorded before this field existed.
        "reason_taxonomy": list(allowed_reasons),
    }

    try:
        from learning.records import producers
        producers.emit_ai_feedback_submitted(
            user_id=user.id, request_id=request.request_id, rating=normalized_rating,
            service_namespace=request.service_namespace, capability=request.capability,
            reason=normalized_reason, model=request.model, provider=request.provider,
            reasons=normalized_reasons, comment=normalized_comment,
            target_type=normalized_target,
            latency_ms=latency_ms, estimated_credits=request.estimated_credits,
            actual_credits=request.actual_credits, regenerated=bool(regenerated),
            switched_model=bool(switched_model), workflow_id=workflow_id,
            router_reason=router_reason, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001 — a records problem never fails the rating
        logger.warning("feedback.event_failed error=%s", type(exc).__name__)
    return record
