"""Practice backfill / reconciliation over the legacy practice sources.

Classifies every legacy source honestly and NEVER fabricates a value:

  FULL       — the mapping carries everything the canonical model can hold
  PARTIAL    — mappable, but specific canonical fields have no source (listed)
  INELIGIBLE — must not be mirrored at all (explained)

Idempotency comes from the same deterministic identity the live adapters use, so a
second run adds nothing and a partially-completed run can simply be re-run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from core.learning_context import LearningContext, ServiceNamespace

from . import service
from .adapters import course as course_adapter
from .adapters import exam as exam_adapter
from .adapters.base import MirrorOutcome, safe_mirror
from .refs import QuestionRef, QuestionSourceType

logger = logging.getLogger("learning.practice")

CLASS_FULL = "FULL"
CLASS_PARTIAL = "PARTIAL"
CLASS_INELIGIBLE = "INELIGIBLE"


@dataclass(frozen=True)
class SourceClassification:
    source: str
    namespace: str
    classification: str
    missing_fields: tuple[str, ...] = ()
    reason: str = ""


# The audited matrix. Every entry states what it can and cannot carry.
SOURCE_CLASSIFICATION: tuple[SourceClassification, ...] = (
    SourceClassification(
        "ai_question_attempts", ServiceNamespace.COURSE_LEARNING.value, CLASS_PARTIAL,
        ("response_time_ms", "item_score", "max_score"),
        "per-session row; per-question detail only inside result_json"),
    SourceClassification(
        "question_attempts", ServiceNamespace.COURSE_LEARNING.value, CLASS_PARTIAL,
        ("response_time_ms", "score", "max_score", "session_container"),
        "per-question row with a self-reported self_result; no session column"),
    SourceClassification(
        "exam_practice_attempts", ServiceNamespace.EXAM_PREP.value, CLASS_PARTIAL,
        ("response_time_ms", "item_score", "max_score"),
        "per-session row; per-question detail only inside result_json"),
    SourceClassification(
        "past_paper_attempts", ServiceNamespace.EXAM_PREP.value, CLASS_PARTIAL,
        ("response_time_ms",),
        "per-session row; per-question score/full_score and attempt_no preserved"),
    SourceClassification(
        "programming_exercise_progress", ServiceNamespace.PROGRAMMING.value, CLASS_PARTIAL,
        ("language_at_submit", "earlier_submissions", "code", "per_case_detail"),
        "durable aggregate: only the LAST submission per (user, exercise) is recoverable"),
    SourceClassification(
        "programming_exercise_submissions", ServiceNamespace.PROGRAMMING.value,
        CLASS_INELIGIBLE, (),
        "same submission as programming_exercise_progress; mirroring both would "
        "double-count one real submission"),
    SourceClassification(
        "code_challenge_attempts", ServiceNamespace.PROGRAMMING.value, CLASS_INELIGIBLE, (),
        "status is keyword-matched from AI prose (failed/partial/probable_pass/unknown), "
        "not an execution result — using it as correctness would fabricate a verdict"),
)


def classification_matrix() -> list[dict]:
    return [{"source": c.source, "service_namespace": c.namespace,
             "classification": c.classification,
             "missing_fields": list(c.missing_fields), "reason": c.reason}
            for c in SOURCE_CLASSIFICATION]


@dataclass
class BackfillReport:
    per_source: dict = field(default_factory=dict)
    totals: dict = field(default_factory=dict)

    def add(self, source: str, outcome: MirrorOutcome):
        row = self.per_source.setdefault(
            source, {"mirrored": 0, "deduped": 0, "conflicts": 0, "failed": 0})
        row["mirrored"] += outcome.mirrored
        row["deduped"] += outcome.deduped
        row["conflicts"] += outcome.conflicts
        row["failed"] += outcome.failed

    def finalize(self) -> dict:
        self.totals = {
            key: sum(r[key] for r in self.per_source.values())
            for key in ("mirrored", "deduped", "conflicts", "failed")
        }
        return {"per_source": self.per_source, "totals": self.totals,
                "classification": classification_matrix()}


def _user_index(db):
    from models import User
    return {u.username: u for u in db.query(User).all()}


def _self_result_to_correct(value) -> bool | None:
    """Legacy self_result string → tri-state. Unknown stays None, never False."""
    text = (value or "").strip().lower()
    if text == "correct":
        return True
    if text in ("incorrect", "wrong"):
        return False
    return None


def backfill_question_attempts(db, report: BackfillReport, users, limit=None):
    """Per-question course attempts (the ordinary practice flow)."""
    from models import Question, QuestionAttempt

    q = db.query(QuestionAttempt).order_by(QuestionAttempt.id.asc())
    if limit:
        q = q.limit(limit)
    paper_of = {}

    def _paper_id(question_id):
        if question_id not in paper_of:
            row = db.query(Question).filter(Question.id == question_id).first()
            paper_of[question_id] = getattr(row, "paper_id", None) if row else None
        return paper_of[question_id]

    for row in q.all():
        user = users.get(row.username)
        if user is None:
            report.add("question_attempts", MirrorOutcome(failed=1, reason="unknown_user"))
            continue
        # The container MUST match what the LIVE adapter uses for this source
        # (course:<course_id>), or a replayed attempt would land in a different session
        # than the one the live path created.
        container = f"course:{row.course_id}" if row.course_id else f"attempt:{row.id}"

        def _run(row=row, user=user, container=container):
            ns = ServiceNamespace.COURSE_LEARNING
            context = LearningContext(user_id=user.id, service_namespace=ns,
                                      course_id=row.course_id,
                                      knowledge_point_id=(str(row.knowledge_point_id)
                                                          if row.knowledge_point_id else None))
            session, created = service.ensure_legacy_session(
                db, user, ns, source_type="question_attempt",
                source_session_key=container, mode="course_practice",
                context=context, started_at=None)   # no real start time in the source
            ref = QuestionRef(
                source_type=QuestionSourceType.MATERIAL_GENERATED,
                source_id=str(row.question_id), service_namespace=ns,
                context={"course_id": row.course_id},
                raw_source={"table": "questions", "course_id": row.course_id,
                            "question_attempt_id": row.id},
            )
            res = service.record_attempt(
                db, user, session, ref,
                answer=row.user_answer,
                correct=_self_result_to_correct(row.self_result),
                result={"self_result": row.self_result,
                        "feedback_present": bool(row.ai_feedback)},
                submitted_at=row.created_at,
                source=service.SourceIdentity("question_attempt", str(row.id), None),
                context=context, _session_created=created)
            return MirrorOutcome(mirrored=1 if res.created else 0,
                                 deduped=0 if res.created else 1)

        report.add("question_attempts",
                   safe_mirror("backfill.question_attempt", "question_attempt", row.id,
                               _run, db=db))


def backfill_ai_question_attempts(db, report: BackfillReport, users, limit=None):
    from models import AIQuestionAttempt

    q = db.query(AIQuestionAttempt).order_by(AIQuestionAttempt.id.asc())
    if limit:
        q = q.limit(limit)
    for row in q.all():
        user = users.get(row.username)
        if user is None:
            report.add("ai_question_attempts",
                       MirrorOutcome(failed=1, reason="unknown_user"))
            continue
        outcome = course_adapter.mirror_ai_question_attempt(db, user, row)
        report.add("ai_question_attempts", outcome)


def backfill_exam_practice_attempts(db, report: BackfillReport, users, limit=None):
    from models import ExamPracticeAttempt

    q = db.query(ExamPracticeAttempt).order_by(ExamPracticeAttempt.id.asc())
    if limit:
        q = q.limit(limit)
    for row in q.all():
        user = users.get(row.username)
        if user is None:
            report.add("exam_practice_attempts",
                       MirrorOutcome(failed=1, reason="unknown_user"))
            continue
        report.add("exam_practice_attempts",
                   exam_adapter.mirror_exam_practice_attempt(db, user, row))


def backfill_past_paper_attempts(db, report: BackfillReport, users, limit=None):
    from models import PastPaperAttempt

    q = db.query(PastPaperAttempt).order_by(PastPaperAttempt.id.asc())
    if limit:
        q = q.limit(limit)
    for row in q.all():
        user = users.get(row.username)
        if user is None:
            report.add("past_paper_attempts",
                       MirrorOutcome(failed=1, reason="unknown_user"))
            continue
        report.add("past_paper_attempts",
                   exam_adapter.mirror_past_paper_attempt(db, user, row))


def backfill_programming(db, report: BackfillReport, users, limit=None):
    """Only the LAST real submission per (user, exercise) is recoverable."""
    from models import ProgrammingExercise, ProgrammingExerciseProgress

    q = db.query(ProgrammingExerciseProgress).order_by(
        ProgrammingExerciseProgress.id.asc())
    if limit:
        q = q.limit(limit)
    for row in q.all():
        if row.last_submit_at is None:
            continue
        user = users.get(row.username)
        if user is None:
            report.add("programming_exercise_progress",
                       MirrorOutcome(failed=1, reason="unknown_user"))
            continue
        exercise = (db.query(ProgrammingExercise)
                    .filter(ProgrammingExercise.id == row.exercise_id).first())
        if exercise is None:
            report.add("programming_exercise_progress",
                       MirrorOutcome(failed=1, reason="unknown_exercise"))
            continue
        from .adapters import programming as prog_adapter
        report.add("programming_exercise_progress",
                   prog_adapter.mirror_programming_submission(
                       db, user, exercise, row.id,
                       {"passed": bool(row.last_submit_passed),
                        "passed_count": row.last_public_passed_count,
                        "total_count": row.last_public_total_count},
                       submitted_at=row.last_submit_at,
                       language=getattr(exercise, "language", None)))


BACKFILLERS = (
    ("ai_question_attempts", backfill_ai_question_attempts),
    ("question_attempts", backfill_question_attempts),
    ("exam_practice_attempts", backfill_exam_practice_attempts),
    ("past_paper_attempts", backfill_past_paper_attempts),
    ("programming_exercise_progress", backfill_programming),
)


def run_backfill(db, *, sources=None, limit=None) -> dict:
    """Run the backfill. Safe to re-run: identity is deterministic."""
    report = BackfillReport()
    users = _user_index(db)
    wanted = set(sources) if sources else {name for name, _ in BACKFILLERS}
    for name, fn in BACKFILLERS:
        if name not in wanted:
            continue
        fn(db, report, users, limit=limit)
    result = report.finalize()
    logger.info("practice.backfill_inserted total=%s per_source=%s",
                result["totals"]["mirrored"],
                {k: v["mirrored"] for k, v in result["per_source"].items()})
    logger.info("practice.backfill_skipped total=%s", result["totals"]["deduped"])
    _ = datetime
    return result
