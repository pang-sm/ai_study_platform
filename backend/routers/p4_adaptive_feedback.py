"""P4 API — adaptive practice selection and unified AI feedback.

Two surfaces, both thin: the logic lives in ``learning.adaptive`` / ``learning.feedback``.

    GET  /adaptive/practice   what to practise next, with a factual reason per candidate
    POST /ai/feedback         rate ONE AI response, against the request that produced it
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import adaptive as adaptive_service
from learning import feedback as feedback_service
from ops import feature_flags

router = APIRouter(tags=["ai-workflows"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


# ---------------------------------------------------------------- adaptive practice


class AdaptiveCandidateView(BaseModel):
    """ONE candidate, with the FACTUAL rule that selected it."""

    model_config = ConfigDict(extra="allow")

    candidate_id: str
    source_type: str
    question_source_id: str
    label: str = ""
    question_type: str | None = None
    difficulty: str | None = None
    knowledge_point_id: str | None = None
    knowledge_point_name: str | None = None
    reason: str
    facts: dict = Field(default_factory=dict)


class AdaptivePracticeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    selection_id: str
    service_namespace: str
    context: dict
    policy_version: str
    candidates: list[AdaptiveCandidateView] = Field(default_factory=list)
    total_candidates: int = 0
    excluded_count: int = 0
    counts_by_reason: dict[str, int] = Field(default_factory=dict)
    reasons: dict[str, str] = Field(default_factory=dict)
    semantics: str
    generated_at: str


@router.get("/adaptive/practice", response_model=AdaptivePracticeResponse)
def adaptive_practice(service_key: str = Query("course_learning"),
                      course_id: str = "", exam_module_id: str = "", language: str = "",
                      limit: int = Query(adaptive_service.DEFAULT_LIMIT, ge=1,
                                         le=adaptive_service.MAX_LIMIT),
                      db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """What to practise next in ONE learning space, ranked by stored facts.

    Every candidate carries a reason code (``due_review`` / ``recent_wrong`` / ``needs_work`` /
    ``coverage_gap`` / ``unseen_topic``) and the facts behind it. No scientific component is
    consulted and no weakness or mastery claim is made — see the response's ``semantics``.
    """
    feature_flags.ensure_feature_allowed(db, current_user, "adaptive_practice")
    try:
        return adaptive_service.select_candidates(
            db, current_user, service_key=service_key, course_id=course_id or None,
            exam_module_id=exam_module_id or None, language=language or None, limit=limit)
    except adaptive_service.AdaptiveRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})


# ---------------------------------------------------------------- AI feedback


class AIFeedbackRequest(BaseModel):
    """One rating. The request id is the identity; ``reason`` follows the frozen taxonomy."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=6, max_length=64)
    rating: Literal["up", "down"]
    reason: Literal["incorrect", "too_shallow", "too_complex", "too_verbose", "too_brief",
                    "bad_code", "slow", "poor_image", "other"] | None = None
    regenerated: bool = False
    switched_model: bool = False
    workflow_id: str = Field(default="", max_length=64)


class AIFeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    rating: str
    reason: str | None = None
    regenerated: bool = False
    switched_model: bool = False
    workflow_id: str | None = None
    capability: str
    service_namespace: str | None = None
    model: str | None = None
    provider: str | None = None
    tier: str | None = None
    status: str | None = None
    latency_ms: int | None = None
    estimated_credits: int | None = None
    actual_credits: int | None = None
    router_reason: str | None = None
    context: dict | None = None
    created_at: str | None = None
    submitted_at: str
    trains_router_online: bool = False
    reason_taxonomy: list[str] = Field(default_factory=list)


class FeedbackAnalyticsResponse(BaseModel):
    """Read-only aggregates. Platform scope is admin-only and aggregated only."""

    model_config = ConfigDict(extra="allow")

    scope: str
    window_days: int
    generated_at: str
    totals: dict
    by_reason: dict[str, int] = Field(default_factory=dict)
    by_workflow: dict = Field(default_factory=dict)
    by_capability: dict = Field(default_factory=dict)
    by_model: dict = Field(default_factory=dict)
    by_provider: dict = Field(default_factory=dict)
    per_capability_model: dict = Field(default_factory=dict)
    semantics: str
    router_mutation: bool = False


@router.get("/ai/feedback/analytics", response_model=FeedbackAnalyticsResponse)
def feedback_analytics(scope: Literal["mine", "platform"] = Query("mine"),
                       window_days: int = Query(30, ge=1, le=365),
                       db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """Aggregated ratings, for Champion/Challenger work later — read-only, no tuning.

    ``scope=mine`` (default) is the caller's own ratings. ``scope=platform`` is the
    admin-only, AGGREGATED view: it returns counts and rates, never a user id, a request id or
    a per-learner row. Neither scope changes the router.
    """
    from learning import feedback_analytics as analytics_service

    if scope == "platform":
        from main import is_admin_user        # the ONE admin gate the product already uses
        if not is_admin_user(current_user):
            raise HTTPException(status_code=403, detail="admin only")
        return analytics_service.build_analytics(db, user_id=None, window_days=window_days)
    return analytics_service.build_analytics(db, user_id=current_user.id,
                                             window_days=window_days)


@router.get("/ai/feedback/availability", response_model=dict)
def model_availability(current_user=Depends(_require_user)):
    """Router V1 availability, WITH its scope stated — admin-facing ops view.

    The state is process-local, which is correct for a single-process deployment (the current
    topology) and would need a shared store to be exact across workers. Exposing it makes that
    requirement visible instead of implicit.
    """
    from main import is_admin_user
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    from ai.health import registry
    return registry().describe()


@router.post("/ai/feedback", response_model=AIFeedbackResponse)
def submit_ai_feedback(payload: AIFeedbackRequest, db: Session = Depends(get_db),
                       current_user=Depends(_require_user)):
    """Rate ONE of the caller's OWN AI responses.

    The rating is stored against the request's full context (capability, model, router reason,
    latency, cost) as an audit fact. It does NOT adjust the router: ``trains_router_online``
    is false and stays false — a single dislike must never re-route anyone's next request.
    """
    try:
        return feedback_service.submit_feedback(
            db, current_user, request_id=payload.request_id, rating=payload.rating,
            reason=payload.reason, regenerated=payload.regenerated,
            switched_model=payload.switched_model,
            workflow_id=payload.workflow_id or None)
    except feedback_service.FeedbackRefusal as exc:
        status = 404 if exc.reason == "request_not_found" else 400
        raise HTTPException(status_code=status, detail={"code": exc.reason,
                                                       "message": exc.message})
