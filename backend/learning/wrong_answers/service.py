"""Canonical Wrong Answer service — the only way wrong-answer state is read or changed.

Everything is scoped by ``user_id`` AND ``service_namespace``. Display data is READ
from the attempt facts rather than duplicated into the state row (§7.1): the question
pointer, the learner's answer, the correct answer, the context and any error analysis
all come from ``practice_attempts`` + the domain source.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from core.learning_context import (
    ServiceNamespace,
    normalize_service_namespace,
)
from sqlalchemy.orm import Session as DbSession

from ..practice.models import PracticeAttempt
from .models import STATUS_ACTIVE, STATUS_RESOLVED, WrongAnswerState
from .project import attempts_for_question, course_scope, rebuild, scope_key

logger = logging.getLogger("learning.wrong_answers")


class WrongAnswerError(Exception):
    """Base class for wrong-answer refusals."""


class StateNotFound(WrongAnswerError):
    pass


class CrossUserAccess(WrongAnswerError):
    pass


def _namespace_value(service_namespace) -> str:
    """Canonical namespace via the shared boundary helper (legacy aliases accepted)."""
    try:
        return normalize_service_namespace(service_namespace)
    except ValueError as exc:
        raise WrongAnswerError(str(exc)) from exc


def course_scope_key(course_id) -> str:
    """The scope discriminator that isolates ONE course's wrong-answer states.

    Built by the SAME function the writer used (``project.course_scope``), so the read
    filter and the write discriminator can never disagree about the format.
    """
    return course_scope(course_id)


def _filtered(db: DbSession, user_id: int, *, service_namespace: str | None = None,
              status: str | None = None, module_key: str | None = None,
              course_id: str | None = None):
    q = db.query(WrongAnswerState).filter(WrongAnswerState.user_id == user_id)
    if service_namespace:
        q = q.filter(WrongAnswerState.service_namespace == _namespace_value(service_namespace))
    if status:
        q = q.filter(WrongAnswerState.status == status)
    if module_key:
        # An indexed column, so a module-scoped read is a WHERE and never a parse of a scope
        # string or a context blob. A module the caller does not own any state in simply
        # yields nothing — it is a filter, not an authorization boundary.
        q = q.filter(WrongAnswerState.module_key == str(module_key).strip())
    if course_id:
        # Applied in SQL, BEFORE any limit: filtering after pagination would return short
        # pages and let another course's states consume the page the caller asked for.
        # A state whose question carries no course scope is NOT matched here — an unscoped
        # row is of unknown provenance, and reporting it under a specific course would be
        # the cross-course leak this filter exists to prevent.
        q = q.filter(WrongAnswerState.question_scope_key == course_scope_key(course_id))
    return q


def list_states(db: DbSession, user_id: int, *, service_namespace: str | None = None,
                status: str | None = None, module_key: str | None = None,
                course_id: str | None = None,
                limit: int = 100, offset: int = 0) -> list[WrongAnswerState]:
    return (_filtered(db, user_id, service_namespace=service_namespace, status=status,
                      module_key=module_key, course_id=course_id)
            .order_by(WrongAnswerState.last_wrong_at.desc().nullslast(),
                      WrongAnswerState.id.desc())
            .offset(offset).limit(limit).all())


def count_states(db: DbSession, user_id: int, *, service_namespace: str | None = None,
                 status: str | None = None, module_key: str | None = None,
                 course_id: str | None = None) -> int:
    """Total rows the same filters match — the pagination contract needs it server-side."""
    return _filtered(db, user_id, service_namespace=service_namespace, status=status,
                     module_key=module_key, course_id=course_id).count()


def get_state(db: DbSession, user_id: int, state_id: int,
              service_namespace: str | None = None) -> WrongAnswerState:
    q = db.query(WrongAnswerState).filter(WrongAnswerState.id == state_id,
                                          WrongAnswerState.user_id == user_id)
    if service_namespace:
        q = q.filter(WrongAnswerState.service_namespace == _namespace_value(service_namespace))
    row = q.first()
    if row is None:
        raise StateNotFound(f"wrong answer state {state_id} not found for this user")
    return row


def set_status(db: DbSession, user_id: int, state_id: int, *, resolved: bool) -> WrongAnswerState:
    """Manual lifecycle change, mirroring the legacy mastered toggle.

    This is a compatibility action, not learning evidence: it records what the learner
    asserted. A later factual incorrect attempt reopens the state regardless (§29).
    """
    row = get_state(db, user_id, state_id)
    if row.origin == "practice":
        # a fact-derived state is not hand-editable into a different factual status
        logger.info("practice.wrong_answer_manual_override state_id=%s user_id=%s",
                    row.id, user_id)
    row.status = STATUS_RESOLVED if resolved else STATUS_ACTIVE
    row.resolved_at = datetime.utcnow() if resolved else None
    row.legacy_mastered = bool(resolved)
    if resolved and row.legacy_reviewed_at is None:
        row.legacy_reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def state_detail(db: DbSession, user_id: int, state_id: int) -> dict:
    """State + the display data the frozen product needs, read from the facts."""
    row = get_state(db, user_id, state_id)
    attempts = attempts_for_question(
        db, user_id=row.user_id, service_namespace=row.service_namespace,
        question_source_type=row.question_source_type,
        question_source_id=row.question_source_id,
        question_scope_key=row.question_scope_key)

    history = [_attempt_view(a) for a in attempts]
    latest = history[-1] if history else None
    return {
        "state": _state_view(row),
        # Question / UserAnswer / Context come from the canonical facts,
        # not from a duplicated snapshot
        "question": latest["question"] if latest else None,
        "user_answer": latest["answer"] if latest else None,
        "correct_answer": latest["correct_answer"] if latest else None,
        "context": json.loads(row.context_json) if row.context_json else None,
        # ErrorAnalysis is whatever the domain already produced — null when there is
        # none, never an LLM guess
        "error_analysis": latest["error_analysis"] if latest else None,
        "review_status": row.status,
        "attempt_history": history,
    }


def _attempt_view(attempt: PracticeAttempt) -> dict:
    result = {}
    try:
        parsed = json.loads(attempt.result_json or "{}")
        result = parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        result = {}
    return {
        "attempt_id": attempt.id,
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "answer": attempt.answer,
        "correct": attempt.correct,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "question": json.loads(attempt.question_ref_json or "{}"),
        "correct_answer": result.get("standard_answer"),
        "error_analysis": result.get("feedback") or result.get("analysis"),
        "source_attempt_type": attempt.source_attempt_type,
    }


def _state_view(row: WrongAnswerState) -> dict:
    return {
        "id": row.id,
        "service_namespace": row.service_namespace,
        "question_source_type": row.question_source_type,
        "question_source_id": row.question_source_id,
        "question_scope_key": row.question_scope_key,
        "status": row.status,
        "origin": row.origin,
        "wrong_count": row.wrong_count,
        "first_wrong_at": row.first_wrong_at.isoformat() if row.first_wrong_at else None,
        "last_wrong_at": row.last_wrong_at.isoformat() if row.last_wrong_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "latest_attempt_id": row.latest_attempt_id,
        "latest_wrong_attempt_id": row.latest_wrong_attempt_id,
        "resolved_attempt_id": row.resolved_attempt_id,
        "legacy": {
            "source_type": row.legacy_source_type,
            "source_id": row.legacy_source_id,
            "mastered": row.legacy_mastered,
            "review_count": row.legacy_review_count,
            "reviewed_at": row.legacy_reviewed_at.isoformat() if row.legacy_reviewed_at else None,
        } if row.legacy_source_type else None,
        "schema_version": row.schema_version,
    }


def rebuild_states(db: DbSession, *, user_id: int | None = None,
                   service_namespace: str | None = None, dry_run: bool = False) -> dict:
    """Reconcile canonical states from practice attempts. Idempotent, non-destructive."""
    return rebuild(db, user_id=user_id, service_namespace=service_namespace, dry_run=dry_run)


_ = scope_key
