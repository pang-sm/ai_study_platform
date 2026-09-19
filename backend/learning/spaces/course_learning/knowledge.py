"""Canonical course knowledge write boundary (STEP 7G §22).

Before this module, course knowledge status was mutated from several places, and only
some of them recorded a ``knowledge_progress_events`` row — so the history was partially
invisible and the live event stream could not be complete.

Every course knowledge change now goes through ``apply_knowledge_change``:

    1. durable state write (``user_knowledge_progress``)
    2. the SAME deterministic status rule everywhere (clamp + thresholds)
    3. a ``knowledge_status_changed`` event when — and only when — the status really
       changes, emitted after the caller's commit

``target_status`` exists for the explicitly-user-set status (the "confirmed" path),
which is a real transition but not a delta. It goes through the same writer so it is
covered by the same event rule.

SEMANTICS NOTE: ``mastery_score`` / ``mastery_level`` are legacy product field names for
a deterministic point counter derived from answers. They are NOT a mastery probability,
not a learner-state estimate, and nothing here upgrades their meaning.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace

from .context import COURSE_NAMESPACE, CourseContextError, normalize_course_id

logger = logging.getLogger("learning.spaces.course_learning")

# the product's own derivation rule (unchanged by STEP 7G)
STATUS_THRESHOLDS = ((80, "mastered"), (40, "reviewing"), (1, "learning"))
INITIAL_STATUS = "not_started"

# event types that count as practice activity on the knowledge point
PRACTICE_EVENT_TYPES = ("question_correct", "question_incorrect", "question_attempt",
                        "practice_result", "ai_feedback_correct", "ai_feedback_incorrect")


def clamp_score(value) -> int:
    return max(0, min(100, int(value or 0)))


def derive_status(score: int) -> str:
    for threshold, status in STATUS_THRESHOLDS:
        if score >= threshold:
            return status
    return INITIAL_STATUS


@dataclass
class KnowledgeTransition:
    username: str
    course_id: str
    knowledge_point_id: int | None
    knowledge_point_code: str | None
    old_status: str | None
    new_status: str
    old_score: int
    new_score: int
    occurred_at: datetime
    source_type: str | None = None
    source_id: int | None = None
    event_type: str | None = None

    @property
    def is_transition(self) -> bool:
        return self.old_status != self.new_status

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "course_id": self.course_id,
            "knowledge_point_id": self.knowledge_point_id,
            "knowledge_point_code": self.knowledge_point_code,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "old_score": self.old_score,
            "new_score": self.new_score,
            "occurred_at": self.occurred_at,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


def apply_knowledge_change(db: DbSession, *, username: str, course_id, event_type: str,
                           knowledge_point_id=None, knowledge_point_code=None,
                           delta: int | None = None, target_status: str | None = None,
                           target_score: int | None = None, confirm: bool = False,
                           reason: str = "", source_type: str | None = None,
                           source_id: int | None = None,
                           knowledge_point_title: str | None = None,
                           set_system_suggested: bool = False,
                           protect_user_confirmed: bool = False,
                           touch_activity: bool = True,
                           target_user_id: int | None = None) -> KnowledgeTransition | None:
    """Apply ONE course knowledge change. Flushes; the caller commits and emits.

    ``delta`` magnitude stays a per-flow pedagogy choice (different flows award
    different points), but the STATUS is always derived by the one rule below, and the
    event is always emitted by this module's emitter.

    ``protect_user_confirmed`` preserves the existing rule that a learner's explicit
    status choice is never overwritten by a practice suggestion — the suggestion is
    written to ``system_suggested_status`` instead.

    Returns the transition (whether or not the status changed), or None when the
    knowledge point does not belong to this user+course.
    """
    from models import KnowledgePoint, UserKnowledgeProgress

    # The app's SessionLocal runs with autoflush=False, so a row the caller just added
    # would be invisible to the lookups below and this writer would create a DUPLICATE
    # progress row. Flush first so we always operate on the caller's row.
    db.flush()

    key = normalize_course_id(course_id)
    kp_id = int(knowledge_point_id) if knowledge_point_id is not None else None
    code = str(knowledge_point_code).strip() if knowledge_point_code else None

    if kp_id is None and not code:
        raise CourseContextError("knowledge point identity (id or code) is required")

    # The knowledge point must belong to this user + course — this is what stops a
    # knowledge write from crossing into another course.
    if kp_id is not None:
        point = (db.query(KnowledgePoint)
                 .filter(KnowledgePoint.id == kp_id,
                         KnowledgePoint.username == username,
                         KnowledgePoint.course_id == key)
                 .first())
        if point is None:
            return None
        code = code or getattr(point, "node_key", None)
        knowledge_point_title = knowledge_point_title or getattr(point, "title", None)

    now = datetime.utcnow()
    progress = _find_progress(db, UserKnowledgeProgress, username, key, kp_id, code)
    if progress is None:
        progress = UserKnowledgeProgress(
            user_id=target_user_id or _user_id(db, username),
            username=username, course_id=key,
            knowledge_point_id=kp_id if kp_id is not None else 0,
            knowledge_point_code=code,
            knowledge_point_title=knowledge_point_title,
            mastery_score=0, status=INITIAL_STATUS, practice_count=0, task_count=0,
            created_at=now,
        )
        db.add(progress)
        db.flush()
    elif target_user_id is not None:
        progress.user_id = target_user_id

    old_status = progress.status
    old_score = clamp_score(progress.mastery_score)

    if delta is not None:
        new_score = clamp_score(old_score + int(delta))
        new_status = target_status or derive_status(new_score)
    elif target_score is not None:
        new_score = clamp_score(target_score)
        new_status = target_status or derive_status(new_score)
    else:
        new_score = old_score
        new_status = target_status or old_status or INITIAL_STATUS

    progress.mastery_score = new_score
    if knowledge_point_title:
        progress.knowledge_point_title = knowledge_point_title
    if code:
        progress.knowledge_point_code = code

    if protect_user_confirmed and progress.user_confirmed_status:
        # a practice result is a SUGGESTION; the learner's explicit choice stands
        progress.system_suggested_status = new_status
    else:
        progress.status = new_status
        if confirm:
            # an explicit learner choice, recorded as such
            progress.user_confirmed_status = new_status
        if set_system_suggested:
            progress.system_suggested_status = new_status

    if touch_activity:
        if event_type in PRACTICE_EVENT_TYPES:
            progress.practice_count = (progress.practice_count or 0) + 1
        elif event_type in ("task_done", "task_reopened"):
            progress.task_count = (progress.task_count or 0) + 1
        if (delta or 0) > 0:
            progress.last_studied_at = now
    progress.updated_at = now
    db.flush()

    return KnowledgeTransition(
        username=username, course_id=key, knowledge_point_id=kp_id,
        knowledge_point_code=code, old_status=old_status,
        new_status=progress.status, old_score=old_score, new_score=new_score,
        occurred_at=now, source_type=source_type, source_id=source_id,
        event_type=event_type)


def _find_progress(db, model, username, course_id, kp_id, code):
    q = db.query(model).filter(model.username == username, model.course_id == course_id)
    if kp_id is not None:
        row = q.filter(model.knowledge_point_id == kp_id).first()
        if row is not None:
            return row
    if code:
        return q.filter(model.knowledge_point_code == code).first()
    return None


def _user_id(db, username) -> int | None:
    from models import User
    user = db.query(User).filter(User.username == username).first()
    return getattr(user, "id", None)


# ---------------------------------------------------------------- emit

def commit_and_emit(db: DbSession, transition: KnowledgeTransition | None) -> dict:
    """The single commit + emit step for a course knowledge change."""
    db.commit()
    return emit_transition(transition)


def emit_transition(transition: KnowledgeTransition | None) -> dict:
    """Emit ``knowledge_status_changed`` for a REAL transition. Failure-isolated.

    Own session, so a records problem can never disturb the caller's transaction; and
    nothing is emitted when the score moved without crossing a threshold.
    """
    if transition is None:
        return {"emitted": 0, "reason": "no_transition"}
    if not transition.is_transition:
        return {"emitted": 0, "reason": "status_unchanged"}
    try:
        from learning.records import producers
        from database import SessionLocal

        db = SessionLocal()
        try:
            user = _user_id(db, transition.username)
            if user is None:
                return {"emitted": 0, "reason": "unknown_user"}
            return producers.emit_knowledge_status_changed(
                user_id=user, knowledge_point_id=(
                    transition.knowledge_point_id or transition.knowledge_point_code),
                new_status=transition.new_status, old_status=transition.old_status,
                occurred_at=transition.occurred_at,
                source_type=transition.source_type or "knowledge_progress",
                source_id=(transition.source_id if transition.source_id is not None
                           else (transition.knowledge_point_id
                                 or transition.knowledge_point_code)),
                service_namespace=ServiceNamespace.COURSE_LEARNING.value,
                course_id=transition.course_id,
                source_user_ref=transition.username,
                extra_payload={"change_event_type": transition.event_type,
                               "score_after": transition.new_score})
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("course knowledge event hook failed: %s", type(exc).__name__)
        return {"emitted": 0, "reason": "emit_failed"}


# The audited inventory of every knowledge-mutation path in the product (§56).
# ``status`` is the HONEST state after STEP 7G — a path is only marked
# CANONICAL_WRITER once it actually calls apply_knowledge_change.
MUTATION_PATHS = (
    {"path": "POST /practice/questions/{id}/attempts", "space": "course_learning",
     "status": "CANONICAL_WRITER", "note": "delta; via apply_knowledge_progress_event"},
    {"path": "POST /practice/questions/{id}/feedback", "space": "course_learning",
     "status": "CANONICAL_WRITER", "note": "delta; via apply_knowledge_progress_event"},
    {"path": "PUT /learning/tasks/{id}", "space": "course_learning",
     "status": "CANONICAL_WRITER", "note": "task delta; via apply_knowledge_progress_event"},
    {"path": "POST /course-learning/practice/{attempt_id}/submit", "space": "course_learning",
     "status": "CANONICAL_WRITER",
     "note": "_update_course_learning_progress rewired; +15/-8 pedagogy delta and the "
             "user-confirmed protection preserved"},
    {"path": "PATCH /knowledge-map/progress", "space": "course_learning",
     "status": "CANONICAL_WRITER",
     "note": "explicit learner status via target_status + confirm; review scheduling "
             "stays local to the route"},
    {"path": "PUT /knowledge-points/{point_id}/progress", "space": "course_learning",
     "status": "CANONICAL_WRITER",
     "note": "manual score/status via target_score/target_status"},
    {"path": "POST /practice/submit-result", "space": "course_learning",
     "status": "CANONICAL_WRITER",
     "note": "batch practice_result deltas; legacy knowledge_progress_events row kept"},
    {"path": "_materialize_due_review_statuses / review-interval recompute",
     "space": "course_learning", "status": "SYSTEM_DERIVED_NO_EVENT",
     "note": "deterministic review-due scheduling recompute, not a learning transition; "
             "Review Core is a later STEP (§36)"},
    {"path": "POST /knowledge-path/generate-from-materials", "space": "course_learning",
     "status": "CONTENT_REPLACEMENT_NO_EVENT",
     "note": "regenerating the course knowledge tree from materials REPLACES the previous "
             "tree for that course: the replaced points' progress rows are removed with "
             "their points, and the new points start at the zero state (mastery_score=0, "
             "status=not_started). This is content replacement, not a learner transition, "
             "so it does not call the writer and emits no knowledge_status_changed — there "
             "is no surviving point whose status changed"},
    {"path": "PATCH /course-progress", "space": "course_learning",
     "status": "SEPARATE_LEGACY_STATE",
     "note": "writes the legacy CourseProgress table (course-level completion), which is "
             "not a knowledge-point status"},
    {"path": "PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}", "space": "exam_prep",
     "status": "OUT_OF_SCOPE_SPACE", "note": "exam_11408 → STEP7H"},
    {"path": "_record_programming_submission_progress (knowledge part)", "space": "programming",
     "status": "OUT_OF_SCOPE_SPACE", "note": "programming → STEP7I"},
)


def mutation_path_inventory() -> list[dict]:
    return [dict(row) for row in MUTATION_PATHS]


def course_mutation_paths() -> list[dict]:
    """Only the paths that mutate COURSE knowledge state (§56 scope)."""
    return [dict(row) for row in MUTATION_PATHS
            if row["space"] == "course_learning"
            and row["status"] != "SEPARATE_LEGACY_STATE"]


# Statuses that are a DECLARED, audited answer — not a silent bypass.
_DECLARED_STATUSES = ("CANONICAL_WRITER", "SYSTEM_DERIVED_NO_EVENT",
                      "CONTENT_REPLACEMENT_NO_EVENT")


def course_paths_not_consolidated() -> list[dict]:
    """Course paths that still bypass the canonical writer without declaring it."""
    return [row for row in course_mutation_paths()
            if row["status"] not in _DECLARED_STATUSES]
