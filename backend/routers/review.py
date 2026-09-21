"""Unified Review API — GET /review and GET /review/summary.

The learner's outstanding review work across every learning space, read from the facts each
space already stores. Read-only: these routes create no task, write no state, and schedule
nothing. A due date appears ONLY when a space has stored one.

Scope is always the session user; the filters narrow the caller's OWN projection and can never
widen it.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import review as review_service
from ops import feature_flags


router = APIRouter(prefix="/review", tags=["review"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


# ---------------------------------------------------------------- response models


class ReviewQuestionIdentity(BaseModel):
    """WHICH question this item is about. Content is rendered by the domain page."""

    question_source_type: str
    question_source_id: str
    question_scope_key: str = ""


class ReviewItemView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    service_namespace: str
    domain_context: dict
    source_type: str
    source_id: str
    question_identity: ReviewQuestionIdentity | None = None

    title: str
    summary: str

    review_status: str          # due | needs_attention | scheduled
    due_at: str | None = None   # ONLY from a stored date; null means "no stored schedule"
    due_source: str | None = None
    last_attempt_at: str | None = None
    reason: str
    metrics: dict = Field(default_factory=dict)
    deep_link: str


class ReviewListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[ReviewItemView]
    total: int
    limit: int
    offset: int
    buckets: dict[str, int]
    semantics: str


class ReviewSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    service_namespace: str | None = None
    total: int
    by_namespace: dict[str, int]
    by_status: dict[str, int]
    by_source: dict[str, int]
    has_stored_due_dates: bool
    semantics: str


# ---------------------------------------------------------------- endpoints


@router.get("", response_model=ReviewListResponse)
def list_review_items(service_namespace: str = Query("", description="course_learning | exam_11408 | programming"),
                      status: str = Query("", description="due | needs_attention | scheduled"),
                      course_id: str = "", exam_module_id: str = "", language: str = "",
                      limit: int = Query(review_service.DEFAULT_LIMIT, ge=1,
                                         le=review_service.MAX_LIMIT),
                      offset: int = Query(0, ge=0),
                      db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """The caller's outstanding review work, newest facts first within each bucket.

    ``status=due`` is the ONLY bucket backed by a stored date. ``needs_attention`` items have
    no stored date, so they are never presented as scheduled — and a domain with no real
    schedule contributes nothing to it rather than a fabricated interval.
    """
    feature_flags.ensure_feature_allowed(db, current_user, "intelligent_review")
    try:
        return review_service.collect_review_items(
            db, current_user, service_namespace=service_namespace or None,
            course_id=course_id or None, exam_module_id=exam_module_id or None,
            language=language or None, bucket=status or None,
            limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/summary", response_model=ReviewSummaryResponse)
def review_summary(service_namespace: str = "", db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    """Deterministic counts over the SAME projection the list serves.

    There is no second aggregation path: a summary that counted differently from the page
    would be a bug the learner would see immediately.
    """
    feature_flags.ensure_feature_allowed(db, current_user, "intelligent_review")
    return review_service.review_summary(db, current_user,
                                         service_namespace=service_namespace or None)


# ---------------------------------------------------------------- P4: scheduling


class ReviewScheduleItem(BaseModel):
    """ONE computed due date, WITH the policy and the facts that produced it."""

    model_config = ConfigDict(extra="allow")

    item_id: str
    policy_version: str
    reason: str
    interval_days: int
    scheduled_at: str
    due_at: str
    facts: dict = Field(default_factory=dict)
    last_reviewed_at: str | None = None


class ReviewScheduleRequest(BaseModel):
    """Which items to (re)schedule. An empty list schedules the ones not yet scheduled."""

    model_config = ConfigDict(extra="forbid")

    item_ids: list[str] = Field(default_factory=list, max_length=50)
    include_all: bool = False


class ReviewScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    policy_version: str
    scheduled: list[ReviewScheduleItem] = Field(default_factory=list)
    count: int = 0
    semantics: str
    generated_at: str | None = None


class ReviewCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["correct", "incorrect"]


class ReviewCompleteResponse(BaseModel):
    """A completed review and the schedule it produced — never one without the other."""

    model_config = ConfigDict(extra="allow")

    item_id: str
    result: str
    previous_review_result: str | None = None
    policy_version: str
    scheduled_at: str
    due_at: str
    interval_days: int
    reason: str
    source_facts: dict = Field(default_factory=dict)
    semantics: str


def _schedule_error(exc) -> HTTPException:
    status = 404 if exc.reason == "item_not_found" else 400
    return HTTPException(status_code=status, detail={"code": exc.reason,
                                                     "message": exc.message})


@router.post("/schedule", response_model=ReviewScheduleResponse)
def schedule_reviews(payload: ReviewScheduleRequest, db: Session = Depends(get_db),
                     current_user=Depends(_require_user)):
    """Compute and RECORD the next review date for the caller's items.

    The date comes from the deterministic policy over stored facts — never from a memory
    model, because there is no real interval/rating/lapse history to feed one. Everything the
    policy used is returned with the date, so it can be re-derived and checked.
    """
    from learning import review_schedule

    feature_flags.ensure_feature_allowed(db, current_user, "intelligent_review")
    try:
        return review_schedule.schedule_items(db, current_user,
                                              item_ids=payload.item_ids or None,
                                              include_all=payload.include_all)
    except review_schedule.ReviewScheduleRefusal as exc:
        raise _schedule_error(exc)


@router.post("/{item_id}/complete", response_model=ReviewCompleteResponse)
def complete_review(item_id: str, payload: ReviewCompleteRequest,
                    db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """Record the learner's OWN review result and reschedule from it.

    The result is mandatory: an unreported review cannot move a schedule. The completion and
    its next due date are emitted together as canonical facts.
    """
    from learning import review_schedule

    feature_flags.ensure_feature_allowed(db, current_user, "intelligent_review")
    try:
        return review_schedule.complete_review(db, current_user, item_id=item_id,
                                              result=payload.result)
    except review_schedule.ReviewScheduleRefusal as exc:
        raise _schedule_error(exc)
