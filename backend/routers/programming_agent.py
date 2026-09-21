"""Programming Debug Agent API — POST /programming/agent/debug.

The bounded multi-step workflow: diagnose → propose a patch → RUN the exercise's own tests →
inspect → optional second repair → explanation. It is NOT the workbench: ``/code/analyze``,
``/code/diagnose``, ``/programming/exercises/{id}/run|test|submit`` are untouched and keep
their single-step semantics.

SCOPE, DECIDED HERE
-------------------
WHO: the session, never the body. WHICH CODE: the caller's OWN project for this exercise, or
the caller's own submitted files — never a path, never another project's file, never another
learner's row. The execution backend receives a copy; the learner's stored files are only ever
read.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning.spaces.programming import agent as debug_agent
from ops import feature_flags

router = APIRouter(prefix="/programming/agent", tags=["programming"])

MAX_FILES = 8
MAX_FILE_CHARS = debug_agent.MAX_CONTENT_CHARS


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


# ---------------------------------------------------------------- request / response


class AgentDebugFile(BaseModel):
    """One file of the caller's own working copy. A name only — never a path."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=MAX_FILE_CHARS)


class AgentDebugRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: int
    project_id: int | None = None
    files: list[AgentDebugFile] = Field(default_factory=list, max_length=MAX_FILES)
    goal: str = Field(default="", max_length=500)


class AgentStepView(BaseModel):
    """ONE step of the trace. ``action`` is a closed vocabulary; every figure is observed."""

    model_config = ConfigDict(extra="allow")

    step_index: int
    action: str
    status: str
    ai_request_id: str | None = None
    capability: str | None = None
    latency_ms: int | None = None
    credits: int | None = None
    estimated_credits: int | None = None
    tests: dict | None = None
    file: str | None = None
    patch: str | None = None
    reason: str | None = None


class AgentUsageView(BaseModel):
    model_steps: int = 0
    execution_steps: int = 0
    actual_credits: int = 0
    estimated_credits: int = 0


class AgentDebugResponse(BaseModel):
    """The bounded run: its status, its trace, its artifacts and what it cost."""

    model_config = ConfigDict(extra="allow")

    agent_run_id: str
    status: Literal["completed", "failed", "no_repair_needed"]
    reason: str | None = None
    stop_reason: str | None = None
    exercise_id: int | None = None
    language: str = ""
    steps: list[AgentStepView] = Field(default_factory=list)
    iterations_used: int = 0
    executions_used: int = 0
    tests_before: dict | None = None
    tests_after: dict | None = None
    proposed_patch: str | None = None
    patch_file: str | None = None
    final_code: str | None = None
    diagnosis: str = ""
    patch_summary: str = ""
    explanation: str = ""
    usage: AgentUsageView = Field(default_factory=AgentUsageView)
    error_category: str | None = None
    message: str | None = None


# ---------------------------------------------------------------- endpoint


def _own_project(db: Session, user, exercise_id: int, project_id: int | None):
    """The caller's own project for THIS exercise, or None when they have none yet."""
    from main import get_code_project_or_404
    from models import CodeProject

    if project_id is not None:
        project = get_code_project_or_404(project_id, user.username, db)
        if project.programming_exercise_id != exercise_id:
            raise HTTPException(status_code=404, detail="题目项目不存在")
        return project
    return (db.query(CodeProject)
            .filter(CodeProject.user_id == user.id,
                    CodeProject.username == user.username,
                    CodeProject.course_id == "programming",
                    CodeProject.programming_exercise_id == exercise_id,
                    CodeProject.is_deleted.is_(False))
            .order_by(CodeProject.updated_at.desc()).first())


def _working_files(db: Session, user, payload: AgentDebugRequest, project,
                   exercise) -> list[dict]:
    """The copy the agent may read: the caller's own files, and nothing else."""
    if payload.files:
        return [{"filename": item.filename, "content": item.content}
                for item in payload.files]
    if project is None:
        return []
    from main import list_project_files
    return [{"filename": row.relative_path, "content": row.content or ""}
            for row in list_project_files(project.id, db)]


@router.post("/debug", response_model=AgentDebugResponse)
def run_programming_agent(payload: AgentDebugRequest, db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    """Run ONE bounded debug workflow over the caller's own exercise code.

    A capability the tier does not permit is a 403 and an exhausted budget is a 429 BEFORE
    any work starts. A workflow that fails after real steps have run returns 200 with
    ``status="failed"`` plus its trace: the facts that happened are not hidden behind an
    error, and the steps that did run were settled individually.
    """
    from models import ProgrammingExercise

    feature_flags.ensure_feature_allowed(db, current_user, "programming_agent")
    exercise = (db.query(ProgrammingExercise)
                .filter(ProgrammingExercise.id == payload.exercise_id).first())
    if exercise is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    project = _own_project(db, current_user, exercise.id, payload.project_id)
    files = _working_files(db, current_user, payload, project, exercise)

    from main import _is_standard_oj_exercise
    if project is None and _is_standard_oj_exercise(exercise):
        # Standard-I/O exercises are judged against a project's entry file, so the run has
        # nothing to execute without one. Saying so is better than guessing a scaffold.
        raise HTTPException(status_code=409,
                            detail={"code": "project_required",
                                    "message": "请先在练习页开始该题目以创建项目"})

    try:
        return debug_agent.run_debug_agent(
            db, current_user, exercise=exercise, project=project, files=files)
    except debug_agent.AgentRefusal as exc:
        status = 404 if exc.reason == "exercise_not_found" else 400
        raise HTTPException(status_code=status,
                            detail={"code": exc.reason, "message": exc.message})
