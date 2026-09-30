"""Initial plan API — POST /ai/plan-initial.

ONE endpoint, one question: "I have no plan for this subject, draw one up." It is a separate
route from ``/ai/plan-adjustment`` on purpose. That route's semantics are "change the plan I
already have", and pointing an empty plan at it is what produced an answer about a plan that did
not exist — the learner read "nothing needs adjusting" while looking at nothing.

This endpoint WRITES NOTHING. What it returns is a draft the learner edits and then saves
through the ordinary per-space task endpoints, so a task the assistant imagined and a task the
learner typed are stored by exactly the same code.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import plan_adjustment as planning
from ops import feature_flags

router = APIRouter(prefix="/ai/plan-initial", tags=["ai-workflows"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


class InitialPlanScope(BaseModel):
    """Which subject to draw a plan for. WHO is the session."""

    model_config = ConfigDict(extra="forbid")

    service_key: Literal["course_learning", "exam_11408", "programming"] = "course_learning"
    course_id: str = ""
    exam_module_id: str = ""
    language: str = ""
    goal: str = Field(default="", max_length=300)


class InitialPlanTask(BaseModel):
    """One line of the DRAFT. A task with no day is carried, not dropped — the learner supplies
    the day before anything is saved, and the client cannot save while one is missing."""

    model_config = ConfigDict(extra="allow")

    title: str
    task_type: str
    due_date: str | None = None
    needs_due_date: bool = False


class InitialPlanProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    proposal_id: str
    capability: str
    request_id: str
    service_namespace: str
    subject_key: str
    tasks: list[InitialPlanTask] = Field(default_factory=list)
    dropped_tasks: list[dict] = Field(default_factory=list)
    # `proposed` when there is a draft, otherwise why there is not — with the one line the learner
    # reads. A model answer with nothing usable in it is not an error status.
    outcome: str = "proposed"
    message: str = ""
    rationale: str = ""
    # True when at least one drafted task still needs the learner to choose its day.
    needs_days: bool = False
    usage: dict = Field(default_factory=dict)
    applies_to: str
    generated_at: str


@router.post("", response_model=InitialPlanProposal)
def propose_initial_plan(payload: InitialPlanScope, db: Session = Depends(get_db),
                         current_user=Depends(_require_user)):
    """Draw up a first plan for ONE of the caller's subjects. WRITES NOTHING."""
    feature_flags.ensure_feature_allowed(db, current_user, "dynamic_planning")
    try:
        return planning.propose_initial_plan(
            db, current_user, service_key=payload.service_key, goal=payload.goal,
            course_id=payload.course_id or None,
            exam_module_id=payload.exam_module_id or None,
            language=payload.language or None)
    except planning.PlanAdjustmentRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})
