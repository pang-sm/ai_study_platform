"""Learning Records API (STEP 7F / F1C6) — read-only over the canonical event stream.

There is deliberately NO write endpoint: events come from server-side trusted business
facts, and letting a client post an arbitrary event would let it write its own history.

The SSOT freezes no exact paths for this module (only the records disposition), so the
canonical ``/learning-records`` style is used. Every handler is scoped to the caller.

TWO RULES THIS SURFACE ENFORCES
-------------------------------
1. **Study history only.** The default scope is the USER_FACING taxonomy; audit facts
   (``ai_called``) are excluded SERVER-SIDE so no client filters ops telemetry out of a
   learner's timeline. They are never deleted — ``include_audit=true`` queries them.
2. **Unambiguous identity.** The detail route matches a canonical UUID only
   (``{event_id:uuid}``), so it can no longer swallow sibling literal paths such as
   ``/learning-records/stats`` — a legacy route that was unreachable before.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from learning.records import service, taxonomy
from learning.records.contract import (
    RecordDetail,
    RecordPage,
    RecordsSummaryResponse,
    RecordsTaxonomyResponse,
)

router = APIRouter(prefix="/learning-records", tags=["learning-records"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid circular import
    return get_current_user(request, db)


@router.get("/summary", response_model=RecordsSummaryResponse)
def records_summary(start_at: str = "", end_at: str = "", service_namespace: str = "",
                    exam_module_id: str = "",
                    db: Session = Depends(get_db), current_user=Depends(_require_user)):
    try:
        return service.summarize_records(db, current_user.id,
                                         start_at=start_at or None,
                                         end_at=end_at or None,
                                         service_namespace=service_namespace or None,
                                         exam_module_id=exam_module_id or None)
    except service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/taxonomy", response_model=RecordsTaxonomyResponse)
def records_taxonomy(current_user=Depends(_require_user)):
    """The frozen event taxonomy + ownership registry (read-only reference)."""
    return {
        "event_schema_version": taxonomy.EVENT_SCHEMA_VERSION,
        "active_event_types": list(taxonomy.active_event_types()),
        "deferred_event_types": list(taxonomy.deferred_event_types()),
        "user_facing_event_types": list(taxonomy.user_facing_event_types()),
        "audit_only_event_types": list(taxonomy.audit_only_event_types()),
        "categories": list(taxonomy.all_categories()),
        "student_twin_eligible_types": list(taxonomy.student_twin_eligible_types()),
        "ownership_matrix": taxonomy.ownership_matrix(),
    }


@router.get("", response_model=RecordPage)
def list_records(start_at: str = "", end_at: str = "", service_namespace: str = "",
                 category: str = "", event_type: str = "", exam_module_id: str = "",
                 include_audit: bool = Query(
                     default=False,
                     description="Include audit-only facts (e.g. ai_called). Never "
                                 "study history; defaults to false."),
                 limit: int = Query(default=50, ge=1, le=200), cursor: str = "",
                 db: Session = Depends(get_db), current_user=Depends(_require_user)):
    try:
        return service.list_records(db, current_user.id,
                                    start_at=start_at or None, end_at=end_at or None,
                                    service_namespace=service_namespace or None,
                                    category=category or None,
                                    event_type=event_type or None,
                                    exam_module_id=exam_module_id or None,
                                    limit=limit, cursor=cursor or None,
                                    include_audit=include_audit)
    except service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{event_id:uuid}", response_model=RecordDetail)
def get_record(event_id: uuid.UUID, include_audit: bool = False,
               db: Session = Depends(get_db), current_user=Depends(_require_user)):
    try:
        return service.get_record(db, current_user.id, str(event_id),
                                  include_audit=include_audit)
    except service.RecordNotFound:
        raise HTTPException(status_code=404, detail="record not found")
