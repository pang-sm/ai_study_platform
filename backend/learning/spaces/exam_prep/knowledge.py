"""Canonical Exam Prep knowledge write boundary (STEP7H4 §17–§24).

Until now the only live EXAM knowledge mutation was a direct write to
``user_knowledge_progress`` inside the study-plan PATCH route. That made the route the
de-facto owner of the exam knowledge state, its review scheduling and its event
semantics. This module is that owner now, and the route calls it.

WHY THIS IS NOT ``course_learning.knowledge``
---------------------------------------------
Both spaces share the PRODUCT principles (deterministic status, an event only on a real
transition, a learner's explicit confirmation is never overwritten by a practice
suggestion), but their KNOWLEDGE IDENTITY comes from different places:

  * course_learning resolves knowledge points through the ``knowledge_points`` table;
  * exam knowledge comes from the static course map
    (``seed_data/knowledge_maps/<module>_11408.json``) plus the question bank's
    knowledge-point fields — there is no ``KnowledgePoint`` row to look up, and none is
    required.

So the exam space gets its own adapter with its own identity resolution, and it reuses the
shared event producer rather than inventing a second event schema or a second status rule.

STORAGE COMPATIBILITY
---------------------
The persisted scope id stays ``<module>_11408`` (``UserKnowledgeProgress.course_id``).
H1's legacy scope adapter already interprets that id as ``exam_prep / cs_408 / <module>``;
nothing is rewritten here.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace
from learning.records import producers

from datetime import datetime, timedelta

from .catalog import CS408_MODULES, is_known_module, module_display
from .scope import build_legacy_exam_scope_id

logger = logging.getLogger("learning.spaces.exam_prep")

EXAM_NAMESPACE = ServiceNamespace.EXAM_PREP.value
EXAM_SUBJECT_ID = "cs_408"

# The statuses the study-plan UI can set. Same vocabulary the endpoint already accepted.
EXAM_KNOWLEDGE_STATUSES = ("not_started", "learning", "mastered", "review_due")

# The score the "learning" state implies when the learner has no score yet. Product
# constant, unchanged from the pre-H4 route.
LEARNING_DEFAULT_SCORE = 30
MASTERED_SCORE = 100


class ExamKnowledgeError(ValueError):
    """A knowledge change that must not be applied."""


def resolve_exam_scope_id(module_key: str | None) -> str:
    """``<module>`` → the persisted ``<module>_11408`` scope id. Fails closed."""
    module = str(module_key or "").strip()
    if not is_known_module(module):
        raise ExamKnowledgeError(f"unknown CS408 module {module_key!r}")
    return build_legacy_exam_scope_id(module)


def subject_supports_knowledge(subject_id: str | None) -> bool:
    """Only an ACTIVE subject has a knowledge tree at all."""
    from .catalog import subject_supports_content
    return subject_supports_content(subject_id)


class ExamKnowledgeTransition:
    """One applied exam knowledge change (whether or not the status really moved)."""

    __slots__ = ("user_id", "username", "module_key", "course_id", "knowledge_point_code",
                 "knowledge_point_title", "old_status", "new_status", "occurred_at")

    def __init__(self, *, user_id, username, module_key, course_id, knowledge_point_code,
                 knowledge_point_title, old_status, new_status, occurred_at):
        self.user_id = user_id
        self.username = username
        self.module_key = module_key
        self.course_id = course_id
        self.knowledge_point_code = knowledge_point_code
        self.knowledge_point_title = knowledge_point_title
        self.old_status = old_status
        self.new_status = new_status
        self.occurred_at = occurred_at

    @property
    def is_transition(self) -> bool:
        return self.old_status != self.new_status

    def event_source_id(self) -> str:
        """Stable per (scope, code, new status, instant) — one event per real transition.

        A later transition for the same knowledge point is a DIFFERENT fact and must not be
        folded into the earlier one, while replaying the same transition must dedupe.
        """
        stamp = self.occurred_at.isoformat() if self.occurred_at else "unknown"
        return f"{self.course_id}:{self.knowledge_point_code}:{self.new_status}:{stamp}"


def apply_exam_knowledge_change(db: DbSession, *, user, module_key: str,
                                knowledge_point_code: str, status: str,
                                title: str | None = None,
                                review_interval_days: int | None = None,
                                code_validator=None, now=None) -> ExamKnowledgeTransition:
    """The ONE way exam knowledge state is written.

    ``code_validator(code) -> bool`` is supplied by the caller so this module stays free of
    filesystem knowledge: the route already loads the course map and validates the code is
    a leaf, and passes that check down. A validator that rejects the code fails closed.

    ``user_confirmed_status`` is set to the requested status: this route IS the learner
    explicitly stating a status, so it is the confirmation. Later practice suggestions can
    then never overwrite it (the same principle course_learning protects).
    """
    from models import UserKnowledgeProgress

    if status not in EXAM_KNOWLEDGE_STATUSES:
        raise ExamKnowledgeError(f"invalid status {status!r}")
    code = str(knowledge_point_code or "").strip()
    if not code:
        raise ExamKnowledgeError("knowledge point code is required")
    if code_validator is not None and not code_validator(code):
        raise ExamKnowledgeError(f"knowledge point {code!r} is not in this course map")

    course_id = resolve_exam_scope_id(module_key)
    now = now or datetime.utcnow()
    canonical_title = str(title if title is not None else "").strip()

    progress = (db.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.username == user.username,
                        UserKnowledgeProgress.course_id == course_id,
                        UserKnowledgeProgress.knowledge_point_code == code)
                .first())
    created = progress is None
    if created:
        progress = UserKnowledgeProgress(
            username=user.username, course_id=course_id, knowledge_point_id=0,
            knowledge_point_code=code, knowledge_point_title=canonical_title,
            mastery_score=0, status="not_started", practice_count=0, task_count=0,
            created_at=now)
        db.add(progress)
        # autoflush is off in this app's SessionLocal: without a flush the row would be
        # invisible to a second call in the same transaction and we would create a
        # duplicate progress row for the same knowledge point.
        db.flush()

    old_status = progress.status

    progress.knowledge_point_code = code
    if canonical_title:
        progress.knowledge_point_title = canonical_title
    progress.status = status
    progress.user_confirmed_status = status
    progress.updated_at = now
    progress.last_studied_at = now

    # Deterministic product semantics, carried over verbatim from the pre-H4 route: the
    # score and the review fields follow the STATUS, and the review interval itself stays
    # the caller's policy (this module does not own review scheduling).
    if status == "not_started":
        progress.mastery_score = 0
        progress.learned_at = None
        progress.review_due_at = None
        progress.review_interval_days = None
    elif status == "learning":
        progress.mastery_score = (progress.mastery_score
                                  if progress.mastery_score is not None
                                  else LEARNING_DEFAULT_SCORE)
        progress.learned_at = None
        progress.review_due_at = None
        progress.review_interval_days = None
    elif status == "mastered":
        progress.mastery_score = MASTERED_SCORE
        progress.learned_at = now
        progress.review_interval_days = review_interval_days
        progress.review_due_at = (now + timedelta(days=review_interval_days)
                                  if review_interval_days is not None else None)
    else:  # review_due
        progress.learned_at = progress.learned_at or now
        progress.review_interval_days = review_interval_days
        progress.review_due_at = now

    return ExamKnowledgeTransition(
        user_id=getattr(user, "id", None), username=user.username, module_key=module_key,
        course_id=course_id, knowledge_point_code=code,
        knowledge_point_title=(progress.knowledge_point_title or canonical_title),
        old_status=old_status, new_status=status, occurred_at=now)


def commit_and_emit(db: DbSession, transition: ExamKnowledgeTransition | None) -> dict:
    """The single commit + emit step for an exam knowledge change."""
    db.commit()
    return emit_transition(transition)


def emit_transition(transition: ExamKnowledgeTransition | None) -> dict:
    """Emit ``knowledge_status_changed`` for a REAL transition. Failure-isolated.

    Own session, so a records problem can never disturb the caller's transaction, and a
    repeated write of the SAME status emits nothing — no fabricated transition.
    """
    if transition is None:
        return {"emitted": 0, "reason": "no_transition"}
    if not transition.is_transition:
        return {"emitted": 0, "reason": "status_unchanged"}
    try:
        return producers.emit_knowledge_status_changed(
            user_id=transition.user_id,
            knowledge_point_id=transition.knowledge_point_code,
            new_status=transition.new_status, old_status=transition.old_status,
            occurred_at=transition.occurred_at,
            source_type="exam_knowledge_progress",
            source_id=transition.event_source_id(),
            service_namespace=EXAM_NAMESPACE,
            # the event's subject is the EXAM SUBJECT (H1 contract), never the module
            subject_key=EXAM_SUBJECT_ID,
            course_id=None,
            exam_module_id=transition.module_key,
            source_user_ref=transition.username,
        )
    except Exception as exc:  # noqa: BLE001 — the durable write already committed
        logger.warning("exam knowledge event hook failed: %s", type(exc).__name__)
        return {"emitted": 0, "reason": "emit_failed"}


# ---------------------------------------------------------------- inventory

# The audited inventory of exam knowledge-mutation paths (STEP7H4 §24). ``status`` is the
# HONEST state after this step: a path is CANONICAL_WRITER only if it actually calls here.
EXAM_MUTATION_PATHS = (
    {"path": "PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}",
     "space": "exam_prep", "status": "CANONICAL_WRITER",
     "note": "study-plan leaf status; via exam_prep.knowledge.apply_exam_knowledge_change"},
    {"path": "PATCH /knowledge-map/progress (course_id='<module>_11408')",
     "space": "exam_prep", "status": "CANONICAL_WRITER",
     "note": "the generic course knowledge route is reachable with an EXAM scope id; an "
             "exam scope is detected via scope.parse_legacy_exam_scope_id and routed to "
             "apply_exam_knowledge_change, so the fact is not recorded as a "
             "course_learning event (STEP7H5)"},
    {"path": "POST /course-learning/practice/{attempt_id}/submit (exam mode)",
     "space": "exam_prep", "status": "SYSTEM_DERIVED_NO_EVENT",
     "note": "legacy 11408 practice submit path derives a course-scoped delta; exam "
             "practice itself is mirrored by the Practice Core (STEP7H2) and applies no "
             "exam knowledge delta"},
    {"path": "_materialize_due_review_statuses / review-interval recompute",
     "space": "exam_prep", "status": "SYSTEM_DERIVED_NO_EVENT",
     "note": "deterministic review-due scheduling recompute, not a learning transition"},
)

_DECLARED_STATUSES = ("CANONICAL_WRITER", "SYSTEM_DERIVED_NO_EVENT",
                      "CONTENT_REPLACEMENT_NO_EVENT")


def exam_mutation_paths() -> list[dict]:
    return [dict(row) for row in EXAM_MUTATION_PATHS]


def exam_paths_not_consolidated() -> list[dict]:
    """Exam paths that still write knowledge without declaring how."""
    return [row for row in EXAM_MUTATION_PATHS if row["status"] not in _DECLARED_STATUSES]
