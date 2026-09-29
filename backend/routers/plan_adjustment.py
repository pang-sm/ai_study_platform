"""Dynamic Planning API — POST /ai/plan-adjustment and POST /ai/plan-adjustment/apply.

TWO endpoints, on purpose. The first asks for a proposal and touches NOTHING; the second
applies an accepted proposal and re-verifies, at that moment, both ownership and the plan
identity the proposal was built from. A plan is only ever changed by the second one.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import plan_adjustment as planning
from ops import feature_flags

router = APIRouter(prefix="/ai/plan-adjustment", tags=["ai-workflows"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


class PlanScope(BaseModel):
    """The plan to work on. WHO is the session; the rest names the space's plan."""

    model_config = ConfigDict(extra="forbid")

    service_key: Literal["course_learning", "exam_11408", "programming"] = "course_learning"
    course_id: str = ""
    exam_module_id: str = ""
    language: str = ""
    goal: str = Field(default="", max_length=300)


class ProposedChange(BaseModel):
    """One change, carried as BOTH the mutation to apply and the diff to display.

    ``op`` / ``task_id`` / ``due_date`` / ``title`` are what ``apply`` executes. ``type`` /
    ``field`` / ``before`` / ``after`` are derived by the server from the plan itself. They travel
    in the same object so a screen cannot show one change while the write performs another, and so
    ``before`` is never a value the client asserted — it is read from the plan.
    """

    model_config = ConfigDict(extra="allow")

    op: str
    task_id: int | None = None
    title: str | None = None
    task_type: str | None = None
    due_date: str | None = None
    type: str = ""
    task_title: str = ""
    field: str = ""
    before: str | None = None
    after: str | None = None
    direction: str | None = None


class PlanEvidence(BaseModel):
    """One reason, stated as the stored number behind it."""

    code: str
    text: str
    metric: int


class PlanImpact(BaseModel):
    """What changes, counted. No estimate of effort, time or future performance."""

    inserted: int
    rescheduled: int
    moved_earlier: int
    moved_later: int
    replaced: int
    task_count_before: int
    task_count_after: int
    overdue_before: int
    overdue_after: int
    text: str


class PlanAdjustmentProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    proposal_id: str
    capability: str
    request_id: str
    service_namespace: str
    subject_key: str
    plan_identity: str
    summary: str
    rationale: str
    # `proposed` when there is something to apply, otherwise why there is not — with the one line
    # the learner reads. A proposal that holds no change is a 200, not an error: the assistant
    # answered, and its answer was "nothing to adjust".
    outcome: str = "proposed"
    message: str = ""
    adjustment_types: list[str] = Field(default_factory=list)
    evidence: list[PlanEvidence] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    impact: PlanImpact
    # False when nothing survived validation. The client must not offer to apply such a proposal.
    can_apply: bool = False
    affected_tasks: list[int] = Field(default_factory=list)
    dropped_changes: list[dict] = Field(default_factory=list)
    plan_snapshot: dict
    usage: dict = Field(default_factory=dict)
    applies_to: str
    generated_at: str


class PlanApplyRequest(BaseModel):
    """What the client accepted. ``plan_identity`` is MANDATORY: without it, a stale proposal
    could overwrite a plan that changed in between, and that is exactly what it prevents."""

    model_config = ConfigDict(extra="forbid")

    service_key: Literal["course_learning", "exam_11408", "programming"] = "course_learning"
    course_id: str = ""
    exam_module_id: str = ""
    language: str = ""
    plan_identity: str = Field(min_length=8, max_length=64)
    proposed_changes: list[ProposedChange] = Field(min_length=1,
                                                   max_length=planning.MAX_CHANGES)
    proposal_id: str = ""


class PlanApplyResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    service_namespace: str
    subject_key: str
    applied_count: int
    dropped_changes: list[dict] = Field(default_factory=list)
    plan_identity: str
    plan_identity_before: str
    applied_at: str


@router.post("", response_model=PlanAdjustmentProposal)
def propose_plan_adjustment(payload: PlanScope, db: Session = Depends(get_db),
                            current_user=Depends(_require_user)):
    """Propose a bounded adjustment to ONE of the caller's plans. WRITES NOTHING."""
    feature_flags.ensure_feature_allowed(db, current_user, "dynamic_planning")
    try:
        return planning.propose_adjustment(
            db, current_user, service_key=payload.service_key, goal=payload.goal,
            course_id=payload.course_id or None,
            exam_module_id=payload.exam_module_id or None,
            language=payload.language or None)
    except planning.PlanAdjustmentRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})


@router.post("/apply", response_model=PlanApplyResponse)
def apply_plan_adjustment(payload: PlanApplyRequest, db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    """Apply an ACCEPTED proposal — the only action that changes a plan.

    409 ``stale_proposal`` when the plan is no longer the one the proposal was built from:
    the learner's newer edits always win over an old suggestion.
    """
    feature_flags.ensure_feature_allowed(db, current_user, "dynamic_planning")
    try:
        return planning.apply_adjustment(
            db, current_user, service_key=payload.service_key,
            plan_identity_value=payload.plan_identity,
            changes=[change.model_dump() for change in payload.proposed_changes],
            proposal_id=payload.proposal_id or None,
            course_id=payload.course_id or None,
            exam_module_id=payload.exam_module_id or None,
            language=payload.language or None)
    except planning.StaleProposal as exc:
        raise HTTPException(status_code=409, detail={"code": exc.reason,
                                                     "message": exc.message})
    except planning.PlanAdjustmentRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})
