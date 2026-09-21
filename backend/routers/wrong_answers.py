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
from core.learning_context import ServiceNamespace
from learning.spaces.course_learning import wrong_answers as course_wrong
from learning.spaces.exam_prep import wrong_answers as exam_wrong
from learning.wrong_answers import service
from learning.wrong_answers.models import STATUSES
from ops import feature_flags

router = APIRouter(prefix="/wrong-answers", tags=["wrong-answers"])

WrongAnswerStatus = Literal["active", "resolved"]
# P1.3: ``course_material`` joins the vocabulary because a course state now renders through
# the COURSE resolver on this surface too, and that resolver reports what its row provably is.
WrongAnswerSourceKind = Literal["chapter_practice", "past_paper", "ai_generated",
                                "course_material", "other"]

COURSE_NAMESPACE = ServiceNamespace.COURSE_LEARNING.value


def _render_records(db: Session, states: list) -> list[dict]:
    """ONE record per state, rendered by the resolver that OWNS that state's learning space.

    The global surface is a UNION of two spaces, and each space's content has its own identity
    rules. Rendering a course state through the exam resolver (the previous behaviour) applied
    the exam space's resolution rules to a course question — the exact cross-space mixing this
    dispatch removes. Order is the caller's: the page order never depends on which resolver a
    row went to.
    """
    groups: dict[str, list] = {}
    for state in states:
        groups.setdefault(state.service_namespace, []).append(state)
    by_id: dict[int, dict] = {}
    for namespace, group in groups.items():
        resolver = (course_wrong if namespace == COURSE_NAMESPACE else exam_wrong)
        is_course = namespace == COURSE_NAMESPACE
        for record in resolver.build_records(db, group):
            by_id[record["wrong_record_id"]] = (
                _union_shape(record) if is_course else record)
    return [by_id[state.id] for state in states]


def _union_shape(record: dict) -> dict:
    """A COURSE record in this surface's union shape: it states no exam module.

    The module fields are required here (BC7 froze them as always-present), and a course
    question has no module — so they are filled with the honest empty value rather than the
    field being dropped or the record being reshaped.
    """
    return {"module_key": "", "module_name": "", **record}


def _render_one(db: Session, state) -> dict:
    resolver = (course_wrong if state.service_namespace == COURSE_NAMESPACE else exam_wrong)
    record = resolver.build_record(db, state)
    if state.service_namespace == COURSE_NAMESPACE:
        return _union_shape(record)
    return record


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
    # An exam record names its module; a course record states NO module (both stay required
    # and are honest empty strings for a space that has no module, so no client has to branch
    # on which space a row came from). ``course_id`` is the course counterpart: present and
    # null for an exam row.
    module_key: str
    module_name: str
    course_id: str | None = None

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
    # course context: the AI 题册 id the COURSE redo contract takes (a different id space
    # from the exam bank — see the course resolver). Only a course record fills it.
    question_id: int | None = None
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


# ---------------------------------------------------------------- deep wrong-cause (P3B)


class WrongAnalysisFacts(BaseModel):
    """The FACT half: what was asked, what the learner answered, what the records show."""

    model_config = ConfigDict(extra="allow")

    question: dict
    user_answer: str = ""
    wrong_count: int = 0
    state_status: str | None = None
    first_wrong_at: str | None = None
    last_wrong_at: str | None = None
    attempt_history: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    source: dict = Field(default_factory=dict)


class WrongAnalysisResult(BaseModel):
    """The AI half: a hypothesis about the mistake. Never a measured learner property."""

    model_config = ConfigDict(extra="allow")

    error_category: str = ""
    reasoning_gap: str = ""
    correct_reasoning: str = ""
    next_action: str = ""
    review_recommendation: str = ""


class WrongAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    state_id: int
    service_namespace: str
    capability: str
    request_id: str

    facts: WrongAnalysisFacts
    fact_origin: str
    analysis: WrongAnalysisResult
    analysis_origin: str
    analysis_semantics: str

    usage: dict = Field(default_factory=dict)
    persistence: dict = Field(default_factory=dict)
    generated_at: str


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
    return {"items": _render_records(db, rows),
            "total": total, "limit": limit, "offset": offset}


@router.get("/{state_id}", response_model=WrongAnswerDetailResponse)
def get_wrong_answer(state_id: int, db: Session = Depends(database.get_db),
                     current_user=Depends(_require_user)):
    try:
        state = service.get_state(db, current_user.id, state_id)
    except service.StateNotFound:
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    resolver = (course_wrong if state.service_namespace == COURSE_NAMESPACE else exam_wrong)
    record = _render_one(db, state)
    record["attempt_history"] = resolver.attempt_history(db, state)
    record["error_analysis"] = resolver.error_analysis(db, state)
    return record


@router.post("/{state_id}/analysis", response_model=WrongAnalysisResponse)
def analyze_wrong_answer(state_id: int, db: Session = Depends(database.get_db),
                         current_user=Depends(_require_user)):
    """Deep wrong-cause analysis for ONE of the caller's own wrong-answer states.

    The state is resolved through the SAME ownership check every read here uses, and its
    question is resolved through the space's hardened resolver — so a state whose content
    cannot be proven is not analysed (409), rather than analysed from an empty stem.
    """
    from learning import wrong_analysis

    feature_flags.ensure_feature_allowed(db, current_user, "wrong_analysis")
    try:
        state = service.get_state(db, current_user.id, state_id)
    except service.StateNotFound:
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    try:
        return wrong_analysis.analyze_wrong_answer(db, current_user, state=state)
    except wrong_analysis.WrongAnalysisRefusal as exc:
        status = 409 if exc.reason == "question_content_unavailable" else 400
        raise HTTPException(status_code=status,
                            detail={"code": exc.reason, "message": exc.message})
    except wrong_analysis.WrongAnalysisOutputError:
        raise HTTPException(status_code=502,
                            detail={"code": "unusable_analysis",
                                    "message": "模型未返回可用的错因分析"})


@router.patch("/{state_id}", response_model=WrongAnswerRecord)
def update_wrong_answer(state_id: int, payload: StateUpdate,
                        db: Session = Depends(database.get_db),
                        current_user=Depends(_require_user)):
    try:
        state = service.set_status(db, current_user.id, state_id, resolved=payload.resolved)
    except service.StateNotFound:
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    return _render_one(db, state)
