"""Daily Learning Agenda API — GET /learning/agenda and /learning/agenda/explain.

"What should I do next?", answered from the facts the product already stores. The endpoint
writes nothing and emits no event: the agenda is a projection over plan tasks, review items
and practice candidates, and the ONE fact behind each item keeps its ONE owner.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import agenda as agenda_service

router = APIRouter(prefix="/learning/agenda", tags=["learning"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


class AgendaItemView(BaseModel):
    """ONE next action. Its domain is the domain of ITS OWN row — never the caller's filter."""

    model_config = ConfigDict(extra="allow")

    action_type: str
    service_namespace: str
    domain_context: dict
    source_type: str
    source_id: str
    title: str
    summary: str
    priority_reason: str
    deep_link: str
    due_at: str | None = None
    facts: dict = Field(default_factory=dict)
    status: str = "open"
    resolved_by: str | None = None


class AgendaSourceSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    plan_tasks: int = 0
    review_items: int = 0
    adaptive_candidates: int = 0
    unattributable_plan_tasks: int = 0
    deduplicated: int = 0


class AgendaResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    policy_version: str
    generated_at: str
    items: list[AgendaItemView] = Field(default_factory=list)
    total_items: int = 0
    source_summary: AgendaSourceSummary
    by_namespace: dict[str, int] = Field(default_factory=dict)
    by_reason: dict[str, int] = Field(default_factory=dict)
    priority_order: list[str] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)
    semantics: str


def _scope(service_key, course_id, exam_module_id, language):
    return {"service_key": service_key or None, "course_id": course_id or None,
            "exam_module_id": exam_module_id or None, "language": language or None}


def _with_resolved_by(agenda: dict) -> dict:
    for item in agenda["items"]:
        item["resolved_by"] = agenda_service.RESOLVED_BY.get(item["priority_reason"])
    return agenda


@router.get("", response_model=AgendaResponse)
def get_learning_agenda(service_key: str = Query("", description="course_learning | exam_11408 | programming"),
                        course_id: str = "", exam_module_id: str = "", language: str = "",
                        limit: int = Query(agenda_service.DEFAULT_LIMIT, ge=1,
                                           le=agenda_service.MAX_LIMIT),
                        db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """The caller's next actions across every learning space, in policy order.

    READ-ONLY and state-free: each item names an object that already exists and links to the
    surface that owns it. Complete the real action there and the next read simply recomputes —
    there is no second "completed" state for anything to drift out of sync with.
    """
    try:
        agenda = agenda_service.build_agenda(
            db, current_user, limit=limit,
            **_scope(service_key, course_id, exam_module_id, language))
    except agenda_service.AgendaRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})
    return _with_resolved_by(agenda)


@router.get("/explain", response_model=dict)
def explain_learning_agenda(
        service_key: str = "", course_id: str = "", exam_module_id: str = "",
        language: str = "",
        limit: int = Query(agenda_service.DEFAULT_LIMIT, ge=1,
                           le=agenda_service.MAX_LIMIT),
        db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """Why this item, why now, and what will change the next read.

    Competition/explainability surface: the policy ladder, the rule behind every reason code,
    what makes each item disappear, and the same agenda with its facts.
    """
    try:
        payload = agenda_service.explain_agenda(
            db, current_user, limit=limit,
            **_scope(service_key, course_id, exam_module_id, language))
    except agenda_service.AgendaRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})
    payload["agenda"] = _with_resolved_by(payload["agenda"])
    return payload
