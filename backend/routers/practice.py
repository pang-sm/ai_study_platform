"""Practice Core API (STEP 7D) — GET/POST /practice/...

Minimal canonical surface over the shared practice spine: create/list/read a session,
record an attempt, read attempt history, close a session. The legacy domain endpoints
(course / exam / programming) keep working unchanged and feed this core through their
adapters.

The SSOT STEP5 API matrix does not freeze paths for session-level practice APIs, so
these use the canonical ``/practice/`` style. Every handler is user-scoped: the caller's
identity comes from the session cookie, never from a query parameter.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.learning_context import LearningContext, ServiceNamespace
from database import get_db
from learning.practice import service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.practice.telemetry import AttemptTelemetry

router = APIRouter(prefix="/practice", tags=["practice"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid circular import
    return get_current_user(request, db)


class SessionCreate(BaseModel):
    service_namespace: str
    mode: str | None = None
    context: dict | None = None


class AttemptTelemetryPayload(BaseModel):
    """ACCEL_SPRINT_S5: the caller's factual per-attempt observations, with provenance.

    ``duration_source`` is required whenever a duration is supplied — a number without a
    measured boundary is refused rather than stored. ``hint_source`` defaults to the value
    that matches every CS408 surface today (there is no hint mechanism), and a count may
    only accompany ``COUNTED``.
    """

    duration_ms: int | None = None
    duration_source: str = "UNAVAILABLE"
    hint_count: int | None = None
    hint_source: str = "NO_HINT_MECHANISM"
    attempt_index: int | None = None


class AttemptCreate(BaseModel):
    question_source_type: str
    question_source_id: str
    answer: str | None = None
    correct: bool | None = None
    score: float | None = None
    max_score: float | None = None
    result: dict | None = None
    submitted_at: str | None = None
    response_time_ms: int | None = None
    attempt_no: int | None = None
    telemetry: AttemptTelemetryPayload | None = None
    question_context: dict | None = Field(default=None)


def _session_dict(session) -> dict:
    return {
        "id": session.id,
        "session_uid": session.session_uid,
        "service_namespace": session.service_namespace,
        "mode": session.mode,
        "status": session.status,
        "session_origin": session.session_origin,
        "source_type": session.source_type,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "schema_version": session.schema_version,
    }


def _attempt_dict(attempt) -> dict:
    return {
        "id": attempt.id,
        "attempt_uid": attempt.attempt_uid,
        "session_id": attempt.session_id,
        "service_namespace": attempt.service_namespace,
        "question_source_type": attempt.question_source_type,
        "question_source_id": attempt.question_source_id,
        "answer": attempt.answer,
        "correct": attempt.correct,          # tri-state: null means "source did not say"
        "score": attempt.score,
        "max_score": attempt.max_score,
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "response_time_ms": attempt.response_time_ms,
        "response_time_source": attempt.response_time_source,
        "attempt_no": attempt.attempt_no,
        "attempt_index": attempt.attempt_index,
        "source_attempt_type": attempt.source_attempt_type,
        "schema_version": attempt.schema_version,
    }


@router.post("/sessions")
def create_session(payload: SessionCreate, db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    context = LearningContext(**payload.context) if payload.context else None
    try:
        session = service.create_session(db, current_user, payload.service_namespace,
                                         mode=payload.mode, context=context)
    except service.PracticeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_dict(session)


@router.get("/sessions")
def list_sessions(service_namespace: str = "", status: str = "", limit: int = 50,
                  offset: int = 0, db: Session = Depends(get_db),
                  current_user=Depends(_require_user)):
    rows = service.list_sessions(db, current_user.id,
                                 service_namespace=service_namespace or None,
                                 status=status or None, limit=min(limit, 200),
                                 offset=max(offset, 0))
    return {"sessions": [_session_dict(s) for s in rows]}


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db),
                current_user=Depends(_require_user)):
    try:
        session = service.get_session(db, current_user.id, session_id)
    except service.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_dict(session)


@router.get("/sessions/{session_id}/summary")
def session_summary(session_id: int, db: Session = Depends(get_db),
                    current_user=Depends(_require_user)):
    try:
        return service.session_summary(db, current_user.id, session_id)
    except service.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")


@router.post("/sessions/{session_id}/attempts")
def record_attempt(session_id: int, payload: AttemptCreate, db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    try:
        session = service.get_session(db, current_user.id, session_id)
    except service.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        ref = QuestionRef(
            source_type=QuestionSourceType(payload.question_source_type),
            source_id=payload.question_source_id,
            service_namespace=ServiceNamespace(session.service_namespace),
            context=payload.question_context or {},
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="unknown question_source_type")

    submitted = None
    if payload.submitted_at:
        from datetime import datetime
        try:
            submitted = datetime.fromisoformat(payload.submitted_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid submitted_at")

    telemetry = None
    if payload.telemetry is not None:
        if payload.response_time_ms is not None:
            raise HTTPException(
                status_code=400,
                detail="pass either telemetry or response_time_ms, not both — the "
                       "telemetry envelope already carries the duration and its source")
        try:
            telemetry = AttemptTelemetry(
                duration_ms=payload.telemetry.duration_ms,
                duration_source=payload.telemetry.duration_source,
                hint_count=payload.telemetry.hint_count,
                hint_source=payload.telemetry.hint_source,
                attempt_index=payload.telemetry.attempt_index,
            )
        except ValueError as exc:
            # An uninterpretable observation is refused, never coerced into a valid one.
            raise HTTPException(status_code=400, detail=str(exc))

    try:
        result = service.record_attempt(
            db, current_user, session, ref,
            answer=payload.answer, correct=payload.correct, score=payload.score,
            max_score=payload.max_score, result=payload.result,
            submitted_at=submitted, response_time_ms=payload.response_time_ms,
            attempt_no=payload.attempt_no, telemetry=telemetry,
        )
    except service.SessionClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except service.NamespaceMismatch as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except service.AttemptConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # the practice service already emitted the learning event for a created attempt
    return {"created": result.created, "attempt": _attempt_dict(result.attempt)}


@router.get("/sessions/{session_id}/attempts")
def list_session_attempts(session_id: int, limit: int = 100, offset: int = 0,
                          db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    try:
        service.get_session(db, current_user.id, session_id)
    except service.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")
    rows = service.list_attempts(db, current_user.id, session_id=session_id,
                                 limit=min(limit, 500), offset=max(offset, 0))
    return {"attempts": [_attempt_dict(a) for a in rows]}


@router.get("/history")
def practice_history(service_namespace: str = "", limit: int = 100, offset: int = 0,
                     db: Session = Depends(get_db), current_user=Depends(_require_user)):
    rows = service.list_attempts(db, current_user.id,
                                 service_namespace=service_namespace or None,
                                 limit=min(limit, 500), offset=max(offset, 0))
    return {"attempts": [_attempt_dict(a) for a in rows]}


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: int, db: Session = Depends(get_db),
                     current_user=Depends(_require_user)):
    try:
        session = service.complete_session(db, current_user.id, session_id)
    except service.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except service.SessionClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _session_dict(session)


@router.post("/sessions/{session_id}/abandon")
def abandon_session(session_id: int, db: Session = Depends(get_db),
                    current_user=Depends(_require_user)):
    try:
        session = service.abandon_session(db, current_user.id, session_id)
    except service.SessionNotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except service.SessionClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _session_dict(session)
