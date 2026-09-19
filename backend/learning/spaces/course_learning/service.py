"""Course Space service — a domain view over the shared Learning Core.

This module COORDINATES; it does not re-implement. Practice reads come from
``learning.practice``, wrong answers from ``learning.wrong_answers``, records from
``learning.records``. Nothing here talks to an AI provider or duplicates a shared
service.

Every read is scoped by user AND course: a course-A view can never include course-B
rows, and matching chapter/knowledge *titles* never stand in for identity.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from learning.practice import service as practice_service
from learning.records import service as records_service
from learning.wrong_answers import service as wrong_service

from .context import COURSE_NAMESPACE, CourseContextError, normalize_course_id, resolve_course_context

logger = logging.getLogger("learning.spaces.course_learning")


def list_user_courses(db: DbSession, user) -> list[dict]:
    """The course contexts attached to this user (identity = the stored course key)."""
    from models import CourseLearningPreference

    rows = (db.query(CourseLearningPreference)
            .filter(CourseLearningPreference.username == user.username)
            .order_by(CourseLearningPreference.course_id.asc()).all())
    return [{
        "course_id": r.course_id,
        "display_name": r.display_name or r.course_id,
        "mastery_level": r.mastery_level,
        "learning_goal": r.learning_goal,
        "is_started": bool(r.is_started),
    } for r in rows]


def course_context(db: DbSession, user, course_id) -> dict:
    """Resolve the canonical course context, or raise if the user does not have it."""
    ref, context = resolve_course_context(db, user, course_id)
    return {"ref": ref.to_dict(), "context": context.to_dict()}


def course_knowledge_state(db: DbSession, user, course_id) -> dict:
    """Deterministic knowledge state for ONE course.

    ``mastery_score`` is the legacy product field name for a deterministic point
    counter; nothing here reinterprets it as a probability or a scientific estimate.
    """
    from models import UserKnowledgeProgress

    key = normalize_course_id(course_id)
    rows = (db.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == user.username,
                    UserKnowledgeProgress.course_id == key)
            .order_by(UserKnowledgeProgress.knowledge_point_code.asc()).all())
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
    return {
        "course_id": key,
        "service_namespace": COURSE_NAMESPACE,
        "points": [{
            "knowledge_point_id": r.knowledge_point_id,
            "knowledge_point_code": r.knowledge_point_code,
            "title": r.knowledge_point_title,
            "status": r.status,
            "system_suggested_status": r.system_suggested_status,
            "user_confirmed_status": r.user_confirmed_status,
            "mastery_score": r.mastery_score,      # deterministic counter, legacy name
            "practice_count": r.practice_count,
            "task_count": r.task_count,
            "review_due_at": r.review_due_at.isoformat() if r.review_due_at else None,
        } for r in rows],
        "by_status": by_status,
        "total_points": len(rows),
        "semantics": "deterministic product state; not a mastery probability",
    }


def course_practice_view(db: DbSession, user, course_id, *, limit: int = 50) -> dict:
    """Course-scoped practice read, delegated to the shared Practice Core."""
    key = normalize_course_id(course_id)
    sessions = practice_service.list_sessions(
        db, user.id, service_namespace=COURSE_NAMESPACE, limit=limit)
    scoped = [s for s in sessions if _session_course_id(s) == key]
    attempts = practice_service.list_attempts(
        db, user.id, service_namespace=COURSE_NAMESPACE, limit=limit * 4)
    scoped_ids = {s.id for s in scoped}
    scoped_attempts = [a for a in attempts if a.session_id in scoped_ids]
    return {
        "course_id": key,
        "sessions": [{"id": s.id, "mode": s.mode, "status": s.status} for s in scoped],
        "attempts": [{"id": a.id, "question_source_type": a.question_source_type,
                      "question_source_id": a.question_source_id,
                      "correct": a.correct, "submitted_at": (
                          a.submitted_at.isoformat() if a.submitted_at else None)}
                     for a in scoped_attempts],
        "attempt_count": len(scoped_attempts),
    }


def course_wrong_view(db: DbSession, user, course_id, *, limit: int = 100) -> dict:
    """Course-scoped wrong-answer read, delegated to the shared Wrong Answer Core."""
    key = normalize_course_id(course_id)
    states = wrong_service.list_states(
        db, user.id, service_namespace=COURSE_NAMESPACE, limit=limit)
    scoped = [s for s in states if _state_course_id(s) == key]
    return {
        "course_id": key,
        "states": [wrong_service._state_view(s) for s in scoped],
        "active_count": sum(1 for s in scoped if s.status == "active"),
    }


def course_records(db: DbSession, user, course_id, *, limit: int = 50,
                   cursor: str | None = None) -> dict:
    """Course-scoped learning records, delegated to the shared Records read model.

    The shared model pages over the event stream; the course filter is applied in SQL on
    the event's own ``course_id`` column, never on a display name, and before pagination —
    so a page is always full and the next cursor never skips a matching row.
    """
    key = normalize_course_id(course_id)
    page = records_service.list_records(
        db, user.id, service_namespace=COURSE_NAMESPACE, course_id=key,
        limit=limit, cursor=cursor)
    return {"course_id": key, "records": page["records"],
            "next_cursor": page["next_cursor"], "has_more": page["has_more"]}


def assert_owned_course(db: DbSession, user, course_id) -> str:
    """Raise unless the user actually has this course — the cross-course entry guard."""
    key = normalize_course_id(course_id)
    from models import CourseLearningPreference

    exists = (db.query(CourseLearningPreference)
              .filter(CourseLearningPreference.username == user.username,
                      CourseLearningPreference.course_id == key).first())
    if exists is None:
        raise CourseContextError(f"course {key!r} is not attached to this user")
    return key


# ---------------------------------------------------------------- helpers

def _session_course_id(session) -> str | None:
    import json
    try:
        data = json.loads(session.context_json or "{}")
    except (TypeError, ValueError):
        return None
    return data.get("course_id") if isinstance(data, dict) else None


def _state_course_id(state) -> str | None:
    import json
    try:
        data = json.loads(state.context_json or "{}")
    except (TypeError, ValueError):
        return None
    return data.get("course_id") if isinstance(data, dict) else None


def _record_course_id(record: dict) -> str | None:
    context = record.get("context") or {}
    return context.get("course_id")
