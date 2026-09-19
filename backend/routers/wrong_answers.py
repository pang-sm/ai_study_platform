"""Wrong Answer Core API — the canonical wrong-answer surface.

BC7. This is the ONE contract the F1C4 wrong-answer workspace consumes. The shape it
returns is a product record, not a database row: the state's identity, its factual status
(``active`` / ``resolved``), where the question came from, the factual answer the learner
gave, the reference answer, and — for a past paper — the BC6 public identity.

What is deliberately NOT in the contract:
  * ``question_source_type`` / ``question_source_id`` / ``question_scope_key``
    (implementation identity — the frontend must not reason about them);
  * document-source internal ids and OCR cache ids;
  * the legacy wrong-answer tables, which are no longer part of any read path.

Both ``GET`` endpoints are side-effect free; the projection never resolves, reopens or
recomputes a state. Manual lifecycle change stays available through ``PATCH`` and is still
a compatibility action, not learning evidence.

Every handler is scoped to the caller's identity from the session cookie.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

import database
from learning.spaces.exam_prep import wrong_answers as exam_wrong
from learning.wrong_answers import service
from learning.wrong_answers.models import STATUSES

router = APIRouter(prefix="/wrong-answers", tags=["wrong-answers"])

WrongAnswerStatus = Literal["active", "resolved"]
WrongAnswerSourceKind = Literal["chapter_practice", "past_paper", "ai_generated", "other"]


def _require_user(request: Request, db: Session = Depends(database.get_db)):
    from main import get_current_user  # lazy import to avoid circular import
    return get_current_user(request, db)


class WrongAnswerResource(BaseModel):
    """A figure reference, relative to the API base URL — the same contract BC6 uses.

    ``resolveApiResourceUrl()`` on the frontend already resolves this form; the
    wrong-answer workspace must not invent a second one.
    """

    model_config = ConfigDict(extra="forbid")

    url: str


class WrongAnswerRecord(BaseModel):
    """ONE canonical wrong-answer record.

    Fields that only one source can fill are nullable rather than absent, so the frontend
    never has to branch on which legacy table a row came from. ``repeat_wrong_count`` is
    the number of distinct FACTUAL incorrect attempts for this question — it is not a view
    count, not a retry count, and not a review count.
    """

    model_config = ConfigDict(extra="forbid")

    wrong_record_id: int
    status: WrongAnswerStatus

    service_namespace: str
    module_key: str
    module_name: str

    source_kind: WrongAnswerSourceKind
    source_label: str

    question_type: str | None = None
    stem: str = ""
    options: dict[str, str] = Field(default_factory=dict)

    user_answer: str = ""
    reference_answer: str = ""
    analysis: str | None = None

    # past-paper public identity (BC6 frozen: subject_key + year + question_number)
    year: int | None = None
    question_number: int | None = None

    # chapter-practice context: the authoritative bank question id the redo contract takes
    question_bank_id: int | None = None
    knowledge_point_id: str | None = None
    knowledge_point_name: str | None = None
    knowledge_point_path: str | None = None

    resources: list[WrongAnswerResource] = Field(default_factory=list)

    first_wrong_at: str | None = None
    last_wrong_at: str | None = None
    resolved_at: str | None = None
    repeat_wrong_count: int = 0


class WrongAnswerAttemptView(BaseModel):
    """One factual attempt behind a state. Read from ``practice_attempts`` only."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: int
    submitted_at: str | None = None
    answer: str | None = None
    correct: bool | None = None
    score: float | None = None
    max_score: float | None = None
    source_attempt_type: str | None = None


class WrongAnswerListResponse(BaseModel):
    items: list[WrongAnswerRecord]
    total: int
    limit: int
    offset: int


class WrongAnswerDetailResponse(WrongAnswerRecord):
    """The record plus the factual history the record was derived from."""

    attempt_history: list[WrongAnswerAttemptView] = Field(default_factory=list)
    error_analysis: str | None = None


class StateUpdate(BaseModel):
    resolved: bool


def _validate_filters(service_namespace: str, status: str, module: str) -> None:
    if status and status not in STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"status must be one of {list(STATUSES)}")


@router.get("", response_model=WrongAnswerListResponse)
def list_wrong_answers(
    service_namespace: str = Query("", description="canonical learning space; legacy aliases accepted"),
    status: str = Query("", description="active | resolved | empty for all"),
    module: str = Query("", description="exam module filter, e.g. operating_system"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(database.get_db),
    current_user=Depends(_require_user),
):
    _validate_filters(service_namespace, status, module)
    try:
        rows = service.list_states(db, current_user.id,
                                   service_namespace=service_namespace or None,
                                   status=status or None,
                                   module_key=module or None,
                                   limit=limit, offset=offset)
        total = service.count_states(db, current_user.id,
                                     service_namespace=service_namespace or None,
                                     status=status or None,
                                     module_key=module or None)
    except service.WrongAnswerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"items": exam_wrong.build_records(db, rows),
            "total": total, "limit": limit, "offset": offset}


@router.get("/{state_id}", response_model=WrongAnswerDetailResponse)
def get_wrong_answer(state_id: int, db: Session = Depends(database.get_db),
                     current_user=Depends(_require_user)):
    try:
        state = service.get_state(db, current_user.id, state_id)
    except service.StateNotFound:
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    record = exam_wrong.build_record(db, state)
    record["attempt_history"] = exam_wrong.attempt_history(db, state)
    record["error_analysis"] = exam_wrong.error_analysis(db, state)
    return record


@router.patch("/{state_id}", response_model=WrongAnswerRecord)
def update_wrong_answer(state_id: int, payload: StateUpdate,
                        db: Session = Depends(database.get_db),
                        current_user=Depends(_require_user)):
    try:
        state = service.set_status(db, current_user.id, state_id, resolved=payload.resolved)
    except service.StateNotFound:
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    return exam_wrong.build_record(db, state)
