"""Programming Space API — /programming/records, /programming/state, /programming/plan.

The canonical PROGRAMMING-SCOPED reads over the Shared Learning Core. The workspace routes
(exercises, projects, files, execution, AI coach) already exist in ``main.py`` under
``/programming/*`` and ``/code/*`` and are untouched; this module adds the unified
contracts they never had: the study history, the deterministic state, and the study plan.

THREE THINGS THIS MODULE ENFORCES
---------------------------------
1. **One namespace.** Every record read is filtered on ``service_key = 'programming'`` in
   SQL, so a course or exam fact can never appear in a programming timeline.
2. **One membership.** The study plan is gated by ``learning_plan`` through the UNIFIED
   subscription tier — the same ``FEATURE_CAPABILITY`` entry the other two directions use.
   There is no programming membership, no programming tier and no programming quota here.
3. **Facts only.** The state projection reports stored facts and counts over stored facts.
   It computes no mastery probability, no readiness score, no weakness ranking, and it
   reads nothing out of ``code_challenge_attempts`` (whose status is keyword-matched from
   the AI's prose reply, so it is not a learner fact).

Every handler is scoped to the caller's identity from the session cookie.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning.records import service as records_service
from learning.records.contract import RecordPage, RecordsSummaryResponse, RecordView
from learning.spaces.programming import context as programming_context
from learning.spaces.programming import service as programming_service

router = APIRouter(prefix="/programming", tags=["programming"])

# The task kinds a programming plan may contain. A closed set, because an open string
# would let a client file an exam task type into a programming plan.
PROGRAMMING_TASK_TYPES = ("knowledge", "exercise", "project", "review")

# Task statuses the shared task row accepts. Same vocabulary the course and exam
# directions use — the plan page renders them identically.
PROGRAMMING_TASK_STATUSES = ("not_started", "in_progress", "completed")


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


def _plan_subject_key(language: str | None) -> str:
    """The programming context a plan task is filed under.

    ``programming:<language>`` mirrors the course direction's ``course_learning:<course>``
    key: the SAME shared task table, addressed by direction, with the direction's own
    identity embedded so two languages' plans cannot merge.
    """
    return f"{programming_context.PROGRAMMING_NAMESPACE}:{programming_context.normalize_language(language)}"


def _require_plan_entitlement(current_user, db: Session):
    """The ONE gate for the study plan — the unified tier, through the shared capability.

    Raises the standard ``FEATURE_REQUIRES_UPGRADE`` 403 so the upgrade path is identical in
    all three directions.
    """
    from main import require_feature_entitlement
    return require_feature_entitlement(current_user, db, programming_context.PROGRAMMING_NAMESPACE,
                                       "learning_plan")


# ---------------------------------------------------------------- response models


class FeatureEntitlement(BaseModel):
    """The unified-tier verdict for one product feature.

    Declared rather than left as a bare ``dict`` so the generated client can read
    ``allowed`` without a cast. ``current_tier`` is the tier the learner holds;
    ``required_tier`` is the lowest tier that opens the feature.
    """

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    feature: str
    current_tier: str
    required_tier: str
    required_capability: str | None = None
    service_key: str


class ProgrammingPlanTask(BaseModel):
    """One programming study task. ``subject_key`` states which plan it belongs to."""

    model_config = ConfigDict(extra="forbid")

    id: int
    subject_key: str
    language: str | None = None
    title: str
    task_type: str
    status: str
    knowledge_point_name: str | None = None
    due_date: str | None = None
    note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProgrammingPlanResponse(BaseModel):
    service_namespace: str
    subject_key: str
    language: str | None = None
    entitlement: FeatureEntitlement
    total: int
    open: int
    by_status: dict[str, int]
    tasks: list[ProgrammingPlanTask]

    model_config = ConfigDict(extra="forbid")


class ProgrammingExerciseState(BaseModel):
    """One exercise's recorded product status. NOT an error classification."""

    model_config = ConfigDict(extra="forbid")

    exercise_id: int
    personal_status: str
    last_action: str | None = None
    last_submit_passed: bool
    last_public_passed_count: int
    last_public_total_count: int
    last_run_at: str | None = None
    last_test_at: str | None = None
    last_submit_at: str | None = None


class ProgrammingExerciseProgressBlock(BaseModel):
    """Per-exercise progress aggregated from the durable progress rows."""

    model_config = ConfigDict(extra="forbid")

    tracked_exercises: int
    passed: int
    in_progress: int
    by_status: dict[str, int]
    status_semantics: str
    recent_exercises: list[ProgrammingExerciseState]


class ProgrammingPracticeBlock(BaseModel):
    """Factual judged-attempt counts. ``ungraded`` is a real third state."""

    model_config = ConfigDict(extra="forbid")

    attempts: int
    graded_attempts: int
    factual_correct: int
    factual_incorrect: int
    ungraded_attempts: int


class ProgrammingPlanBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    by_status: dict[str, int]
    open: int


class ProgrammingStateResponse(BaseModel):
    """The deterministic state of ONE learner in the programming space.

    There is no field for mastery probability, readiness, weakness ranking or any
    scientific model output, and none may be added: the product has no such capability for
    this space.
    """

    model_config = ConfigDict(extra="forbid")

    service_namespace: str
    languages: list[str]
    current_language: str | None = None
    onboarding_completed: bool
    exercise_progress: ProgrammingExerciseProgressBlock
    practice: ProgrammingPracticeBlock
    plan: ProgrammingPlanBlock
    recent_activity: list[RecordView]
    recent_activity_has_more: bool
    state_semantics: str


class ProgrammingPlanTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    task_type: str = Field(default="exercise")
    language: str | None = None
    knowledge_point_name: str | None = None
    due_date: str | None = None
    note: str | None = None


class ProgrammingPlanTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    task_type: str | None = None
    status: str | None = None
    knowledge_point_name: str | None = None
    due_date: str | None = None
    note: str | None = None


# ---------------------------------------------------------------- records


@router.get("/records", response_model=RecordPage)
def list_programming_records(event_type: str = "", start_at: str = "", end_at: str = "",
                             limit: int = Query(default=50, ge=1, le=200), cursor: str = "",
                             db: Session = Depends(get_db),
                             current_user=Depends(_require_user)):
    """Newest-first page of the caller's programming study history.

    The namespace filter is applied in SQL before pagination: this page can only ever
    contain ``service_key = 'programming'`` facts, and a course or exam event cannot reach
    it by any query parameter.

    Audit-only facts (AI accounting) are never part of a study timeline.
    """
    try:
        return programming_service.programming_records(
            db, current_user, limit=limit, cursor=cursor or None,
            event_type=event_type or None, start_at=start_at or None, end_at=end_at or None)
    except records_service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/records/summary", response_model=RecordsSummaryResponse)
def get_programming_records_summary(start_at: str = "", end_at: str = "",
                                    db: Session = Depends(get_db),
                                    current_user=Depends(_require_user)):
    """Deterministic programming study-history counts, namespace-scoped in SQL."""
    try:
        return programming_service.programming_records_summary(
            db, current_user, start_at=start_at or None, end_at=end_at or None)
    except records_service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------- state


@router.get("/state", response_model=ProgrammingStateResponse)
def get_programming_state(recent_limit: int = Query(default=10, ge=1, le=50),
                          db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    """The deterministic programming state for ONE learner. READ-ONLY; writes nothing.

    Every figure is a stored fact or a count over stored facts: per-exercise product status,
    real graded attempts, language, recorded study tasks, and the recent canonical events.
    There is deliberately NO mastery probability, NO readiness score, NO weakness ranking
    and NO scientific model output.
    """
    return programming_service.programming_state(db, current_user, recent_limit=recent_limit)


# ---------------------------------------------------------------- plan


def _serialize_task(task) -> dict:
    language = None
    subject_key = task.subject_key or ""
    prefix = f"{programming_context.PROGRAMMING_NAMESPACE}:"
    if subject_key.startswith(prefix):
        language = subject_key[len(prefix):] or None
    return {
        "id": task.id,
        "subject_key": subject_key,
        "language": language,
        "title": task.title,
        "task_type": task.task_type,
        "status": task.status,
        "knowledge_point_name": task.knowledge_point_name,
        "due_date": task.due_date,
        "note": task.note,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _plan_tasks(db: Session, user, subject_key: str) -> list:
    from models import ExamStudyPlanTask

    return (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username,
                    ExamStudyPlanTask.subject_key == subject_key)
            .order_by(ExamStudyPlanTask.id.asc()).all())


@router.get("/plan", response_model=ProgrammingPlanResponse)
def get_programming_plan(language: str = "", db: Session = Depends(get_db),
                         current_user=Depends(_require_user)):
    """The caller's programming study plan. GATED by the unified ``learning_plan`` feature.

    Free is denied with the standard upgrade contract; Standard and Advanced are allowed.
    The gate is the SAME ``FEATURE_CAPABILITY['learning_plan'] → planning.generate`` the
    course and exam directions use — this introduces no programming membership.
    """
    entitlement = _require_plan_entitlement(current_user, db)
    resolved = language or (programming_service.declared_languages(db, current_user) or
                            [None])[0]
    subject_key = _plan_subject_key(resolved)
    rows = _plan_tasks(db, current_user, subject_key)
    by_status: dict[str, int] = {}
    for row in rows:
        status = (row.status or "not_started").strip() or "not_started"
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "service_namespace": programming_context.PROGRAMMING_NAMESPACE,
        "subject_key": subject_key,
        "language": programming_context.normalize_language(resolved) if resolved else None,
        "entitlement": entitlement,
        "total": len(rows),
        "open": sum(count for status, count in by_status.items() if status != "completed"),
        "by_status": by_status,
        "tasks": [_serialize_task(row) for row in rows],
    }


@router.post("/plan/tasks", response_model=ProgrammingPlanTask)
def create_programming_plan_task(payload: ProgrammingPlanTaskCreate,
                                 db: Session = Depends(get_db),
                                 current_user=Depends(_require_user)):
    """Add one task to the caller's programming plan. GATED by ``learning_plan``."""
    _require_plan_entitlement(current_user, db)

    task_type = (payload.task_type or "exercise").strip()
    if task_type not in PROGRAMMING_TASK_TYPES:
        raise HTTPException(status_code=400,
                            detail=f"task_type must be one of {list(PROGRAMMING_TASK_TYPES)}")

    from models import ExamStudyPlanTask
    from models import utc_now

    resolved = payload.language or (programming_service.declared_languages(db, current_user)
                                    or [None])[0]
    subject_key = _plan_subject_key(resolved)
    now = utc_now()
    task = ExamStudyPlanTask(
        username=current_user.username,
        subject_key=subject_key,
        title=payload.title.strip(),
        knowledge_point_name=(payload.knowledge_point_name or "").strip(),
        scope_type="single",
        task_type=task_type,
        status="not_started",
        due_date=(payload.due_date or "").strip(),
        note=(payload.note or "").strip(),
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


def _owned_plan_task(db: Session, user, task_id: int):
    """The task, or 404 — it must be this caller's AND a PROGRAMMING plan task.

    Membership is decided by the subject-key prefix, not by the language the learner
    currently has selected: changing the selected language must not orphan tasks that were
    legitimately created under the previous one. A course or exam task is not reachable
    through this path at all.
    """
    from models import ExamStudyPlanTask

    prefix = f"{programming_context.PROGRAMMING_NAMESPACE}:"
    task = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.id == task_id,
                    ExamStudyPlanTask.username == user.username,
                    ExamStudyPlanTask.subject_key.like(f"{prefix}%")).first())
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/plan/tasks/{task_id}", response_model=ProgrammingPlanTask)
def update_programming_plan_task(task_id: int, payload: ProgrammingPlanTaskUpdate,
                                 db: Session = Depends(get_db),
                                 current_user=Depends(_require_user)):
    """Update one programming plan task. GATED by ``learning_plan``."""
    _require_plan_entitlement(current_user, db)

    from models import utc_now

    task = _owned_plan_task(db, current_user, task_id)

    if payload.task_type is not None:
        if payload.task_type not in PROGRAMMING_TASK_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"task_type must be one of {list(PROGRAMMING_TASK_TYPES)}")
        task.task_type = payload.task_type
    if payload.status is not None:
        if payload.status not in PROGRAMMING_TASK_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of {list(PROGRAMMING_TASK_STATUSES)}")
        task.status = payload.status
    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.knowledge_point_name is not None:
        task.knowledge_point_name = payload.knowledge_point_name.strip()
    if payload.due_date is not None:
        task.due_date = payload.due_date.strip()
    if payload.note is not None:
        task.note = payload.note.strip()
    task.updated_at = utc_now()
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@router.delete("/plan/tasks/{task_id}")
def delete_programming_plan_task(task_id: int, db: Session = Depends(get_db),
                                 current_user=Depends(_require_user)):
    """Delete one programming plan task. GATED by ``learning_plan``."""
    _require_plan_entitlement(current_user, db)

    task = _owned_plan_task(db, current_user, task_id)
    db.delete(task)
    db.commit()
    return {"success": True, "task_id": task_id}
