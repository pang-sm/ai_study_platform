"""Legacy wrong-answer import (exam_wrong_questions / past_paper_wrong_questions).

These two tables are MERGEd into ``wrong_answer_states`` (frozen disposition). The
legacy rows are NOT dropped and their endpoints keep working — this is a compatibility
mirror, not a migration away from them.

DEDUPE / CONFLICT POLICY (§16 / §17)
------------------------------------
For a question that already has canonical PracticeAttempt facts, the FACTS decide the
status: a legacy ``mastered`` flag cannot overrule a newer factual incorrect attempt,
and a legacy ``active`` flag cannot overrule a newer factual correct answer. The legacy
row is still recorded as compatibility metadata (``legacy_*`` columns, origin
``legacy_merged``), so nothing is lost. When there are no facts at all, the legacy row
is the only source and its status is carried over directly.

BC7 ADDITIONS — three properties the blind row-by-row copy did not have
-----------------------------------------------------------------------
1. UNANSWERED ROWS ARE NOT IMPORTED. Both legacy tables hold rows written with
   ``user_answer = ''`` (the old graders treated "no answer" as "wrong answer"). The
   canonical store is a statement about ANSWERED questions, so a blank legacy row is
   counted and skipped. The row itself is left in place — this backfill never deletes
   legacy history (§18).
2. DUPLICATES ARE COLLAPSED. ``past_paper_wrong_questions`` has no uniqueness of any
   kind, so re-sitting a paper appended a second identical row per wrong question. The
   import groups by the canonical question identity, so N legacy rows for one question
   become ONE state, with ``wrong_count`` = N.
3. MODULE IS CARRIED. ``subject_key`` on both tables is the exam module. It is passed
   through so the state can be filtered by module without opening any legacy table.

None of this makes the legacy tables authoritative — where canonical PracticeAttempt
facts exist, they decide, and the legacy row is demoted to compatibility metadata.
"""
from __future__ import annotations

import logging
from datetime import datetime

from core.learning_context import ServiceNamespace
from sqlalchemy.orm import Session as DbSession

from ..practice.models import PracticeAttempt
from ..practice.refs import QuestionSourceType
from .models import (
    ORIGIN_LEGACY,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
    WrongAnswerState,
)
from .project import past_exam_scope, recompute

logger = logging.getLogger("learning.wrong_answers")

EXAM_WRONG_SOURCE = "exam_wrong_question"
PAST_PAPER_WRONG_SOURCE = "past_paper_wrong_question"

# Classification of every legacy wrong-ish structure (audited, not guessed).
LEGACY_WRONG_MATRIX = (
    {
        "table": "exam_wrong_questions",
        "namespace": "exam_prep",
        "question_identity": "question_bank_id (null for AI-generated rows, which are "
                             "matched on stem_snapshot)",
        "user_scope": "username",
        "status_values": ("active", "mastered", "removed"),
        "fields": ("mastered", "review_count", "resolved_at"),
        "source_attempt": "practice_attempt_id",
        "writer": "chapter submit (main.py:21251) / AI-question submit (20855)",
        "reader": "GET /exam/11408/{k}/wrong-questions (21649)",
        "rows": 0,
        "fidelity": "PARTIAL",
        "missing": ("attempt identity for AI-generated rows", "response_time_ms"),
    },
    {
        "table": "past_paper_wrong_questions",
        "namespace": "exam_prep",
        "question_identity": "question_id (string from the parsed paper)",
        "user_scope": "username",
        "status_values": ("active", "mastered"),
        "fields": ("mastered", "reviewed_at", "resolved_at"),
        "source_attempt": "attempt_id",
        "writer": "past-paper submit (main.py:19762)",
        "reader": "GET /exam/11408/{k}/wrong-questions (21667)",
        "rows": 0,
        "fidelity": "PARTIAL",
        "missing": ("question scope (year) must be carried into the identity",
                    "response_time_ms"),
    },
    {
        "table": "programming_exercise_progress",
        "namespace": "programming",
        "question_identity": "exercise_id",
        "user_scope": "username(+user_id)",
        "status_values": ("passed", "needs_work", "not_started"),
        "fields": (),
        "source_attempt": "last_submit_at",
        "writer": "exercise submit (main.py:10968)",
        "reader": "GET /programming/home (6647)",
        "rows": 0,
        "fidelity": "INELIGIBLE_AS_HISTORY",
        "missing": ("not an attempt history: only the LAST submission survives; wrong "
                    "states for programming come from canonical PracticeAttempts"),
    },
    {
        "table": "code_challenge_attempts",
        "namespace": "programming",
        "question_identity": "challenge_id",
        "user_scope": "username",
        "status_values": ("failed", "partial", "probable_pass", "unknown"),
        "fields": (),
        "source_attempt": None,
        "writer": "POST /code/challenges/{id}/submit (main.py:14366)",
        "reader": "GET /code/attempts (14924)",
        "rows": 0,
        "fidelity": "INELIGIBLE_AS_CORRECTNESS",
        "missing": ("status is keyword-matched from AI prose, not an execution result"),
    },
)


def legacy_wrong_matrix() -> list[dict]:
    return [dict(row) for row in LEGACY_WRONG_MATRIX]


def _has_canonical_facts(db: DbSession, *, user_id: int, namespace: str,
                         source_type: str, source_id: str) -> bool:
    return (db.query(PracticeAttempt.id)
            .filter(PracticeAttempt.user_id == user_id,
                    PracticeAttempt.service_namespace == namespace,
                    PracticeAttempt.question_source_type == source_type,
                    PracticeAttempt.question_source_id == str(source_id))
            .first() is not None)


def _legacy_payload(*, source_type: str, source_id, mastered, review_count, reviewed_at,
                    **extra) -> dict:
    payload = {"source_type": source_type, "source_id": source_id, "mastered": mastered,
               "review_count": review_count, "reviewed_at": reviewed_at}
    payload.update(extra)
    return payload


def _row_blank(row) -> bool:
    """True when the legacy record asserts a wrong answer the learner never gave."""
    return not str(getattr(row, "user_answer", "") or "").strip()


def _collapse(rows: list) -> dict:
    """The one canonical state that N legacy rows for the same question imply.

    The rows are ordered chronologically and the LAST one decides the status, which is
    what the legacy tables themselves mean: a row is the current record of a question
    being wrong, and a repeat either updates it (chapter table) or appends an identical
    copy (past-paper table). The earliest and latest timestamps are both kept, and
    ``wrong_count`` counts the distinct legacy records rather than inheriting the
    misnamed ``review_count`` (§10).
    """
    ordered = sorted(rows, key=lambda r: (r.created_at or datetime.min, r.id or 0))
    last = ordered[-1]
    resolved = bool(getattr(last, "mastered", False))
    review_counts = [r.review_count for r in ordered
                     if getattr(r, "review_count", None) is not None]
    reviewed_ats = [r.reviewed_at for r in ordered
                    if getattr(r, "reviewed_at", None) is not None]
    return {
        "first_wrong_at": ordered[0].created_at,
        "last_wrong_at": last.created_at,
        "wrong_count": len(ordered),
        "mastered": resolved,
        "resolved_at": last.resolved_at if resolved else None,
        "review_count": max(review_counts) if review_counts else None,
        "reviewed_at": max(reviewed_ats) if reviewed_ats else None,
        "source_id": last.id,
    }


def _upsert_legacy_only(db: DbSession, *, user_id: int, username: str, namespace: str,
                        source_type: str, source_id: str, scope_key: str,
                        module_key: str, legacy: dict) -> str:
    """Write a state whose ONLY source is a legacy row (or a group of them)."""
    key = dict(user_id=user_id, service_namespace=namespace,
               question_source_type=source_type, question_source_id=str(source_id),
               question_scope_key=scope_key)
    row = db.query(WrongAnswerState).filter_by(**key).first()
    created = row is None
    if row is None:
        row = WrongAnswerState(**key, username=username)
        db.add(row)
    row.origin = ORIGIN_LEGACY
    row.status = STATUS_RESOLVED if legacy.get("mastered") else STATUS_ACTIVE
    row.module_key = module_key or row.module_key or ""
    row.wrong_count = int(legacy.get("wrong_count") or 1)
    row.first_wrong_at = legacy.get("first_wrong_at")
    row.last_wrong_at = legacy.get("last_wrong_at")
    row.resolved_at = legacy.get("resolved_at")
    row.legacy_source_type = legacy.get("source_type")
    row.legacy_source_id = legacy.get("source_id")
    row.legacy_mastered = legacy.get("mastered")
    row.legacy_review_count = legacy.get("review_count")
    row.legacy_reviewed_at = legacy.get("reviewed_at")
    db.commit()
    return "created" if created else "updated"


def _import_groups(db: DbSession, report: dict, groups: list[dict], *,
                   source_type: str, legacy_source: str, namespace: str) -> None:
    """Import one table's grouped legacy rows into the canonical store."""
    for group in groups:
        user = group["user"]
        source_id = group["source_id"]
        summary = _collapse(group["rows"])
        legacy = _legacy_payload(
            source_type=legacy_source, source_id=summary["source_id"],
            mastered=summary["mastered"], review_count=summary["review_count"],
            reviewed_at=summary["reviewed_at"],
            wrong_count=summary["wrong_count"], first_wrong_at=summary["first_wrong_at"],
            last_wrong_at=summary["last_wrong_at"], resolved_at=summary["resolved_at"])
        if _has_canonical_facts(db, user_id=user.id, namespace=namespace,
                                source_type=source_type, source_id=str(source_id)):
            # Facts exist: they decide the status and the count, the legacy row is metadata.
            recompute(db, user_id=user.id, service_namespace=namespace,
                      question_source_type=source_type,
                      question_source_id=str(source_id),
                      question_scope_key=group["scope"], legacy=legacy)
            report["merged"] += 1
        else:
            outcome = _upsert_legacy_only(
                db, user_id=user.id, username=group["username"], namespace=namespace,
                source_type=source_type, source_id=str(source_id),
                scope_key=group["scope"], module_key=group["module"],
                legacy=legacy)
            report[outcome] += 1


def backfill_exam_wrong_questions(db: DbSession, report: dict) -> None:
    from models import ExamWrongQuestion, User

    users = {u.username: u for u in db.query(User).all()}
    groups: dict[tuple, dict] = {}
    blank = 0
    for row in db.query(ExamWrongQuestion).order_by(ExamWrongQuestion.id.asc()).all():
        user = users.get(row.username)
        if user is None or row.question_bank_id is None:
            # An AI-generated legacy row has no bank identity; its canonical state comes
            # from the AIQuestionAttempt facts, never from this table.
            report["skipped"] += 1
            continue
        if _row_blank(row):
            blank += 1
            continue
        key = (user.id, str(row.question_bank_id))
        group = groups.setdefault(key, {
            "user": user, "username": row.username, "scope": "",
            "module": (row.subject_key or "").strip(),
            "source_id": str(row.question_bank_id), "rows": []})
        group["rows"].append(row)

    report["legacy_blank_rows"] += blank
    report["legacy_duplicate_rows"] += sum(
        len(g["rows"]) - 1 for g in groups.values())
    _import_groups(
        db, report, list(groups.values()),
        source_type=QuestionSourceType.STATIC_QUESTION_BANK.value,
        legacy_source=EXAM_WRONG_SOURCE, namespace=ServiceNamespace.EXAM_PREP.value)


def backfill_past_paper_wrong_questions(db: DbSession, report: dict) -> None:
    from models import PastPaperWrongQuestion, User

    users = {u.username: u for u in db.query(User).all()}
    groups: dict[tuple, dict] = {}
    blank = 0
    for row in db.query(PastPaperWrongQuestion).order_by(
            PastPaperWrongQuestion.id.asc()).all():
        user = users.get(row.username)
        if user is None or not row.question_id:
            report["skipped"] += 1
            continue
        if _row_blank(row):
            blank += 1
            continue
        # The legacy table has no subject column; the row is cs_408 by construction (it is
        # the only past-paper corpus). Its subject_key IS the module. Derive the scope
        # through the ONE shared function so the legacy import and the live projector can
        # never disagree.
        scope = past_exam_scope(exam_module_id=row.subject_key, question_year=row.year)
        key = (user.id, scope, str(row.question_id))
        group = groups.setdefault(key, {
            "user": user, "username": row.username, "scope": scope,
            "module": (row.subject_key or "").strip(),
            "source_id": str(row.question_id), "rows": []})
        group["rows"].append(row)

    report["legacy_blank_rows"] += blank
    report["legacy_duplicate_rows"] += sum(
        len(g["rows"]) - 1 for g in groups.values())
    _import_groups(
        db, report, list(groups.values()),
        source_type=QuestionSourceType.PAST_EXAM.value,
        legacy_source=PAST_PAPER_WRONG_SOURCE, namespace=ServiceNamespace.EXAM_PREP.value)


def run_legacy_wrong_backfill(db: DbSession) -> dict:
    """Import both legacy wrong tables. Idempotent (identity-keyed upsert)."""
    report = {"created": 0, "updated": 0, "merged": 0, "skipped": 0,
              "legacy_blank_rows": 0, "legacy_duplicate_rows": 0}
    backfill_exam_wrong_questions(db, report)
    backfill_past_paper_wrong_questions(db, report)
    logger.info("practice.wrong_answer_legacy_backfill created=%s merged=%s skipped=%s "
                "blank_excluded=%s", report["created"], report["merged"], report["skipped"],
                report["legacy_blank_rows"])
    return report
