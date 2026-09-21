"""Programming Space service — a domain view over the shared Learning Core.

This module COORDINATES; it does not re-implement. Records come from
``learning.records``, practice facts from ``learning.practice``. Nothing here talks to an
AI provider, and nothing here reads ``code_challenge_attempts``: that table's ``status`` is
keyword-matched out of the AI's prose reply, so it is not a learner fact.

Every read is scoped by user AND by the programming service namespace in SQL. There is no
``programming_learning_records`` table and there must never be one: programming records ARE
the canonical event stream, read back under a namespace filter.

WHAT THIS MODULE REFUSES TO COMPUTE
-----------------------------------
The programming state is a DETERMINISTIC projection of recorded facts. It produces no
mastery probability, no readiness score, no weakness ranking and no scientific model
output — the product has no such capability for this space, and inventing one would be the
fabrication the SSOT forbids.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from learning.practice.models import PracticeAttempt
from learning.records import service as records_service

from .context import PROGRAMMING_NAMESPACE, normalize_language

logger = logging.getLogger("learning.spaces.programming")

DEFAULT_RECENT_LIMIT = 10

# The per-exercise product statuses the progress row actually stores. Declared here so the
# aggregation cannot silently grow a bucket the writer never writes.
EXERCISE_STATUSES = ("not_started", "needs_work", "passed")

STATE_SEMANTICS = (
    "deterministic projection of recorded programming facts (exercise progress, real "
    "attempts, canonical events). Not a mastery probability, not a readiness score, and "
    "not a weakness estimate."
)


# ---------------------------------------------------------------- records


def programming_records(db: DbSession, user, *, limit: int = 50, cursor: str | None = None,
                        event_type: str | None = None, start_at=None, end_at=None) -> dict:
    """Programming-scoped learning records, delegated to the shared Records read model.

    The namespace filter is applied in SQL on the event's own ``service_key`` column,
    before pagination, so a page is always full and the next cursor never skips a matching
    row. Course and exam events cannot appear here.
    """
    return records_service.list_records(
        db, user.id, service_namespace=PROGRAMMING_NAMESPACE,
        event_type=event_type, start_at=start_at, end_at=end_at,
        limit=limit, cursor=cursor)


def programming_records_summary(db: DbSession, user, *, start_at=None, end_at=None) -> dict:
    return records_service.summarize_records(
        db, user.id, service_namespace=PROGRAMMING_NAMESPACE,
        start_at=start_at, end_at=end_at)


# ---------------------------------------------------------------- identity


def onboarding_detail(db: DbSession, user) -> dict:
    """The learner's stored programming onboarding answers, verbatim. "" when absent."""
    from models import UserLearningTrack

    track = (db.query(UserLearningTrack)
             .filter(UserLearningTrack.user_id == user.id,
                     UserLearningTrack.track_type == "programming").first())
    if track is None or not track.onboarding_detail_json:
        return {}
    try:
        detail = json.loads(track.onboarding_detail_json)
    except (TypeError, ValueError):
        return {}
    return detail if isinstance(detail, dict) else {}


def declared_languages(db: DbSession, user) -> list[str]:
    """The languages the learner said they work in. Canonical order, no duplicates."""
    detail = onboarding_detail(db, user)
    raw = detail.get("selected_languages")
    values = [str(v) for v in raw if v] if isinstance(raw, list) else []
    if not values and detail.get("main_language"):
        values = [str(detail["main_language"])]
    out: list[str] = []
    for value in values:
        language = normalize_language(value)
        if language not in out:
            out.append(language)
    return out


# ---------------------------------------------------------------- state


def exercise_progress_state(db: DbSession, user, *, limit: int = DEFAULT_RECENT_LIMIT) -> dict:
    """Per-exercise progress, aggregated from the durable progress rows.

    ``by_status`` is a count over the ``personal_status`` column the submit path writes;
    it is a PRODUCT status ("passed" / "needs_work" / never started), not an error
    classification and not an ability estimate.
    """
    from models import ProgrammingExerciseProgress

    rows = (db.query(ProgrammingExerciseProgress)
            .filter(ProgrammingExerciseProgress.username == user.username)
            .all())
    by_status = {status: 0 for status in EXERCISE_STATUSES}
    for row in rows:
        status = (row.personal_status or "not_started").strip() or "not_started"
        by_status[status] = by_status.get(status, 0) + 1

    from datetime import datetime

    # total, deterministic order: newest activity first, surrogate id as the tie-break.
    # A row with no recorded activity sorts last rather than being dropped.
    ordered = sorted(rows, key=lambda r: (r.last_updated_at or datetime.min, r.id),
                     reverse=True)
    return {
        "tracked_exercises": len(rows),
        "passed": by_status.get("passed", 0),
        "in_progress": by_status.get("needs_work", 0),
        "by_status": by_status,
        "status_semantics": ("personal_status is the product's own per-exercise status "
                             "written by run/test/submit; it is not a mastery or "
                             "readiness estimate"),
        "recent_exercises": [{
            "exercise_id": row.exercise_id,
            "personal_status": row.personal_status,
            "last_action": row.last_action,
            "last_submit_passed": bool(row.last_submit_passed),
            "last_public_passed_count": row.last_public_passed_count or 0,
            "last_public_total_count": row.last_public_total_count or 0,
            "last_run_at": _iso(row.last_run_at),
            "last_test_at": _iso(row.last_test_at),
            "last_submit_at": _iso(row.last_submit_at),
        } for row in ordered[:limit]],
    }


def _iso(value):
    return value.isoformat() if value else None


def practice_state(db: DbSession, user) -> dict:
    """Factual attempt counts for this space. SQL aggregates, no rows materialized."""
    base = (db.query(PracticeAttempt)
            .filter(PracticeAttempt.user_id == user.id,
                    PracticeAttempt.service_namespace == PROGRAMMING_NAMESPACE))
    graded = (base.with_entities(PracticeAttempt.correct, func.count())
              .filter(PracticeAttempt.correct.isnot(None))
              .group_by(PracticeAttempt.correct).all())
    correct_true = next((c for v, c in graded if v is True), 0)
    correct_false = next((c for v, c in graded if v is False), 0)
    attempts = base.count()
    graded_total = correct_true + correct_false
    return {
        "attempts": attempts,
        "graded_attempts": graded_total,
        "factual_correct": correct_true,
        "factual_incorrect": correct_false,
        # a blank submission has no verdict and no score — it is counted, not scored
        "ungraded_attempts": attempts - graded_total,
    }


def plan_state(db: DbSession, user) -> dict:
    """The learner's programming study tasks, from the SHARED task table.

    Reused, not duplicated: ``exam_study_plan_tasks`` is the product's per-direction task
    store and the programming direction is addressed by its own ``subject_key`` prefix, the
    same way the course direction is.
    """
    from models import ExamStudyPlanTask

    prefix = f"{PROGRAMMING_NAMESPACE}:"
    rows = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username,
                    ExamStudyPlanTask.subject_key.like(f"{prefix}%"))
            .all())
    by_status: dict[str, int] = {}
    for row in rows:
        status = (row.status or "not_started").strip() or "not_started"
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "total": len(rows),
        "by_status": by_status,
        "open": sum(count for status, count in by_status.items() if status != "completed"),
    }


def programming_state(db: DbSession, user, *, recent_limit: int = DEFAULT_RECENT_LIMIT) -> dict:
    """The deterministic programming state for ONE learner. READ-ONLY; writes nothing."""
    languages = declared_languages(db, user)
    records = programming_records(db, user, limit=recent_limit)
    return {
        "service_namespace": PROGRAMMING_NAMESPACE,
        "languages": languages,
        "current_language": languages[0] if languages else None,
        "onboarding_completed": bool(onboarding_detail(db, user)
                                     .get("programming_onboarding_completed")),
        "exercise_progress": exercise_progress_state(db, user, limit=recent_limit),
        "practice": practice_state(db, user),
        "plan": plan_state(db, user),
        # Recent activity comes from the CANONICAL event stream, not from a second
        # projection: run / test / submit / start are all recorded there (see
        # learning.spaces.programming.events), so the timeline a learner sees and the
        # facts the platform holds are the same rows.
        "recent_activity": records["records"],
        "recent_activity_has_more": records["has_more"],
        "state_semantics": STATE_SEMANTICS,
    }
