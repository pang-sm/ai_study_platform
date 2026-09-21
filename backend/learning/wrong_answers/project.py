"""PracticeAttempt → WrongAnswerState projection.

RECOMPUTE, NOT INCREMENT
------------------------
The state is always recomputed from the complete set of canonical attempts for that
(user, learning space, question). That single decision gives three properties for free:

  * idempotent — folding the same attempt twice cannot change anything, because nothing
    is accumulated; ``wrong_count`` is the count of distinct incorrect attempts, not the
    number of times the projector ran;
  * order-independent — attempts are sorted chronologically inside the recompute, so
    replaying out of order converges to exactly the same row as in-order replay;
  * rebuildable — the canonical attempts are sufficient to reconstruct every state, so
    the legacy wrong-answer tables are never the authority for a question that has facts.

TRI-STATE CORRECTNESS
---------------------
Only ``correct is False`` creates or sustains an error state, and only ``correct is
True`` resolves one. ``correct is None`` (ungraded, score-only, no verdict) never
triggers a transition and is never read as a failure.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from core.learning_context import ServiceNamespace

from ..practice.models import PracticeAttempt
from ..practice.refs import QuestionSourceType
from .models import (
    ORIGIN_LEGACY,
    ORIGIN_LEGACY_MERGED,
    ORIGIN_PRACTICE,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
    WrongAnswerState,
)

logger = logging.getLogger("learning.wrong_answers")

# Bounded compare-and-recompute passes (STEP7H2-C1). A second pass is only needed when a
# competing writer landed between our read and our write.
MAX_PROJECTION_PASSES = 5


# Legacy past-paper references (written before STEP7H2) carry only ``year``. Every one
# of them is cs_408, because that is the only exam the product ever had real data for —
# a fact about the legacy corpus, not an architectural assumption. It exists so that one
# question cannot derive two different scopes depending on when its attempt was written.
LEGACY_PAST_EXAM_SUBJECT = "cs_408"


def past_exam_scope(exam_subject_id=None, exam_module_id=None,
                    question_year=None) -> str:
    """The scope discriminator for a past-exam question (STEP7H2 §8).

    Audit evidence (235 past-paper rows): ``question_source_id`` is the
    ``exam_question_bank`` PK, globally unique across the whole bank. The scope therefore
    does not have to carry identity — it carries the CONTEXT a question belongs to, so
    that two different exams' "2022 question 12" can never be folded together:

        subject:cs_408|module:operating_system|year:2022

    All three components are derivable for every reference that exists, legacy included:
    the old adapter wrote the module under ``subject_key``, so nothing has to be split
    between "old" and "new" attempts. ``exam_track_id`` is never encoded — a track is the
    learner's bundle choice, not a property of the question.
    """
    subject = str(exam_subject_id or "").strip() or LEGACY_PAST_EXAM_SUBJECT
    parts = [f"subject:{subject}"]
    module = str(exam_module_id or "").strip()
    if module:
        parts.append(f"module:{module}")
    if question_year is not None:
        parts.append(f"year:{question_year}")
    return "|".join(parts)


def course_scope(course_id) -> str:
    """The scope discriminator for a COURSE question (§42 cross-course isolation).

    Two courses of the same learner may reuse the same question id, so the course is part
    of the question's identity rather than a filter over a shared pool. A course with no
    id yields "" — an unscoped row is of unknown provenance and must never be matched by a
    course-scoped read.
    """
    key = str(course_id or "").strip()
    return f"course:{key}" if key else ""


def scope_key(service_namespace: str, question_source_type: str,
              ref_context: dict | None) -> str:
    """Identity discriminator for a question that is NOT globally unique.

    Two cases need it, and both err toward SEPARATION — merging two genuinely different
    questions would be worse than keeping two rows:

      * past papers: scoped by exam subject + module + year, so a second exam subject or
        another module can never reuse the same slot;
      * course learning: the same question id can be reused by two different courses of
        the same user → scoped by course identity (§42 cross-course isolation).

    Bank / AI / programming ids are globally unique → no scope.
    """
    context = ref_context or {}
    if question_source_type == QuestionSourceType.PAST_EXAM.value:
        # ``subject_key`` is where the pre-STEP7H2 adapter put the module.
        return past_exam_scope(
            exam_subject_id=context.get("exam_subject_id"),
            exam_module_id=context.get("exam_module_id") or context.get("subject_key"),
            question_year=context.get("question_year", context.get("year")))
    if service_namespace == ServiceNamespace.COURSE_LEARNING.value:
        return course_scope(context.get("course_id"))
    return ""


def _ref_of(attempt: PracticeAttempt) -> dict:
    try:
        data = json.loads(attempt.question_ref_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def module_of(attempt: PracticeAttempt) -> str:
    """The exam module a question belongs to, read from the attempt's own QuestionRef.

    ``exam_module_id`` is the canonical field and ``subject_key`` is its frozen legacy
    mirror (see ``learning.spaces.exam_prep.context``); both are written by the ONE context
    builder, so this reads either without inventing a third spelling. A question that
    carries no module returns "" — never a guess derived from the id.
    """
    context = _ref_of(attempt).get("context") or {}
    return str(context.get("exam_module_id") or context.get("subject_key") or "").strip()


def _module_of(ordered: list[PracticeAttempt], legacy: dict | None) -> str:
    """Module for a state: the newest factual attempt that names one, else the legacy row."""
    for attempt in reversed(ordered):
        value = module_of(attempt)
        if value:
            return value
    return str((legacy or {}).get("module_key") or "").strip()


def _scope_of(attempt: PracticeAttempt) -> str:
    ref = _ref_of(attempt)
    return scope_key(attempt.service_namespace, attempt.question_source_type,
                     ref.get("context") or {})


def _chrono_key(attempt: PracticeAttempt):
    """Chronological order: submitted_at, then id. An unknown time sorts first so the
    ordering stays total and deterministic rather than accidental."""
    return (attempt.submitted_at or datetime.min, attempt.id or 0)


def attempts_for_question(db, *, user_id: int, service_namespace: str,
                          question_source_type: str, question_source_id: str,
                          question_scope_key: str = "") -> list[PracticeAttempt]:
    rows = (db.query(PracticeAttempt)
            .filter(PracticeAttempt.user_id == user_id,
                    PracticeAttempt.service_namespace == service_namespace,
                    PracticeAttempt.question_source_type == question_source_type,
                    PracticeAttempt.question_source_id == str(question_source_id))
            .all())
    scoped = [a for a in rows if _scope_of(a) == question_scope_key]
    return sorted(scoped, key=_chrono_key)


def derive_from_attempts(ordered: list[PracticeAttempt]) -> dict | None:
    """Pure function: chronological attempts → the state they imply (or None)."""
    wrongs = [a for a in ordered if a.correct is False]
    if not wrongs:
        return None                       # no factual failure → no error state
    rights = [a for a in ordered if a.correct is True]
    last_wrong = wrongs[-1]
    later_correct = [a for a in rights if _chrono_key(a) > _chrono_key(last_wrong)]
    resolving = later_correct[0] if later_correct else None
    return {
        "status": STATUS_RESOLVED if resolving else STATUS_ACTIVE,
        "wrong_count": len(wrongs),
        "first_wrong_attempt_id": wrongs[0].id,
        "latest_wrong_attempt_id": last_wrong.id,
        "latest_attempt_id": ordered[-1].id,
        "resolved_attempt_id": resolving.id if resolving else None,
        "first_wrong_at": wrongs[0].submitted_at,
        "last_wrong_at": last_wrong.submitted_at,
        "resolved_at": resolving.submitted_at if resolving else None,
        "context_json": last_wrong.context_json,
    }


def _adopt_legacy_past_exam_scope(db, key: dict) -> None:
    """Re-key a row written under the OLD past-exam scope form, in place (STEP7H2 §9).

    The scope used to be ``year:<y>``; it is now ``subject:<s>|year:<y>``. A deployment
    that already holds a row under the old form must not end up with a SECOND state for
    the same question, so a matching legacy row is adopted — it keeps its id and its
    provenance and simply moves to the canonical key. Idempotent: after the first call
    the legacy row no longer exists under the old key.
    """
    scope = key["question_scope_key"]
    if not scope.startswith("subject:") or "|year:" not in scope:
        return
    legacy_scope = f"year:{scope.rsplit('|year:', 1)[1]}"
    legacy_key = {**key, "question_scope_key": legacy_scope}
    legacy_row = db.query(WrongAnswerState).filter_by(**legacy_key).first()
    if legacy_row is None:
        return
    if db.query(WrongAnswerState).filter_by(**key).first() is not None:
        # Both forms exist. Do NOT merge silently: which one carries the real history is
        # an audit question, and the unique constraint would reject the move anyway.
        return
    legacy_row.question_scope_key = scope
    db.flush()


def _fact_set_stamp(ordered: list[PracticeAttempt]) -> tuple:
    """Identity + contents of the fact set a projection was derived from.

    The state is a MATERIALIZED VIEW of the canonical attempts, so "did my view go stale
    while I was writing it?" reduces exactly to "did the fact set change?". Sorted by the
    chronological key, so the stamp does not depend on the order rows came back in.
    """
    return tuple(a.id for a in sorted(ordered, key=_chrono_key))


def _fresh_fact_stamp(key: dict) -> tuple | None:
    """The fact-set stamp read through a NEW session.

    Verifying on the caller's session is not enough: after the projection commits, the
    ``refresh`` that follows it opens a read transaction, and a second read inside that
    transaction can be served from the snapshot taken at the refresh — so a competing
    attempt committed in between stays invisible and a stale pass would "verify" itself.
    A separate session opens its own snapshot, so what it sees is what is committed.
    Returns None when the read itself fails, which the caller treats as "not verified".
    """
    from database import SessionLocal
    try:
        with SessionLocal() as fresh:
            return _fact_set_stamp(attempts_for_question(fresh, **key))
    except Exception as exc:  # noqa: BLE001 — never fail the projection on a verify read
        logger.warning("wrong.projection_verify_failed error=%s", type(exc).__name__)
        return None


def _write_projection(db, key: dict, ordered: list[PracticeAttempt], *,
                      legacy: dict | None, username: str | None
                      ) -> tuple[WrongAnswerState | None, bool]:
    """Write the state implied by ``ordered``. One pass; no retry logic here.

    Returns ``(row, applied)``. ``applied`` is False when this pass LOST a concurrent
    first-insert race: the unique constraint rejected our row, so the derivation we just
    computed was never persisted and the caller must redo the pass (the row now exists, so
    the redo takes the update path and lands our values).
    """
    derived = derive_from_attempts(ordered)
    module = _module_of(ordered, legacy)
    row = db.query(WrongAnswerState).filter_by(**key).first()

    if derived is None:
        # No factual failure. Without a legacy record there is nothing to state, so a
        # correct-only question produces no row at all.
        if legacy is None:
            return row, True
        # A legacy record exists but the facts show no failure: the FACTS decide the
        # status (§17), and the legacy provenance is kept rather than discarded (§13).
        if row is None:
            row = WrongAnswerState(**key, username=username or _username_of(ordered))
            db.add(row)
        row.origin = ORIGIN_LEGACY_MERGED
        row.status = STATUS_RESOLVED
        row.wrong_count = 0
        row.first_wrong_attempt_id = None
        row.latest_wrong_attempt_id = None
        row.latest_attempt_id = ordered[-1].id if ordered else None
        row.resolved_attempt_id = ordered[-1].id if ordered else None
        row.first_wrong_at = None
        row.last_wrong_at = None
        row.resolved_at = ordered[-1].submitted_at if ordered else None
        if module:
            row.module_key = module
        _apply_legacy(row, legacy)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return db.query(WrongAnswerState).filter_by(**key).first(), False
        db.refresh(row)
        return row, True

    if row is None:
        row = WrongAnswerState(**key, username=_username_of(ordered))
        db.add(row)
    elif legacy is not None:
        row.origin = ORIGIN_LEGACY_MERGED

    row.status = derived["status"]
    row.wrong_count = derived["wrong_count"]
    row.first_wrong_attempt_id = derived["first_wrong_attempt_id"]
    row.latest_wrong_attempt_id = derived["latest_wrong_attempt_id"]
    row.latest_attempt_id = derived["latest_attempt_id"]
    row.resolved_attempt_id = derived["resolved_attempt_id"]
    row.first_wrong_at = derived["first_wrong_at"]
    row.last_wrong_at = derived["last_wrong_at"]
    row.resolved_at = derived["resolved_at"]
    row.context_json = derived["context_json"]
    if module:
        row.module_key = module
    if row.origin != ORIGIN_LEGACY_MERGED:
        row.origin = ORIGIN_PRACTICE
    # legacy review metadata is carried, never allowed to override the factual status
    _apply_legacy(row, legacy)

    try:
        db.commit()
    except IntegrityError:
        # Concurrent first-write for the same identity. The unique constraint is the gate,
        # but the losing pass must NOT settle here: its derivation was rolled back, so
        # returning the winner's row would silently publish a count computed from an
        # incomplete fact set.
        db.rollback()
        return db.query(WrongAnswerState).filter_by(**key).first(), False
    db.refresh(row)
    return row, True


def recompute(db, *, user_id: int, service_namespace: str, question_source_type: str,
              question_source_id: str, question_scope_key: str = "",
              legacy: dict | None = None,
              username: str | None = None) -> WrongAnswerState | None:
    """Bring one state row in line with the canonical facts (+ optional legacy input).

    CONCURRENCY (STEP7H2-C1)
    ------------------------
    Recompute-not-increment is only correct if the pass that writes LAST was derived from
    the complete fact set. Three things can break that, and each is handled here:

      1. another writer's attempt commits after our read → our derived count is short;
      2. we LOSE a concurrent first-insert race → our derivation is rolled back entirely
         and only the other writer's row survives;
      3. our read is fine but our write lands before a later writer's read.

    So each pass asserts its own read AND its own write: the fact set is re-read after the
    write, and a pass that lost the insert race is not settled. A pass that survives both
    checks provably derived from the final set, so the last writer always converges.

    This is compare-and-recompute — NOT incrementing, NOT a lock, no new column, and the
    frozen semantics stand (idempotent, order independent, rebuildable from facts). The
    loop is bounded; a set still changing means another writer is mid-flight, and the next
    call for that question converges anyway.
    """
    key = dict(user_id=user_id, service_namespace=service_namespace,
               question_source_type=question_source_type,
               question_source_id=str(question_source_id),
               question_scope_key=question_scope_key)

    if question_source_type == QuestionSourceType.PAST_EXAM.value:
        _adopt_legacy_past_exam_scope(db, key)

    row = None
    for _pass in range(MAX_PROJECTION_PASSES):
        ordered = attempts_for_question(db, **key)
        stamp = _fact_set_stamp(ordered)
        row, applied = _write_projection(db, key, ordered, legacy=legacy, username=username)
        if applied and _fresh_fact_stamp(key) == stamp:
            return row
        logger.info(
            "wrong.projection_pass_not_settled namespace=%s source_id=%s applied=%s",
            question_source_type, question_source_id, applied)

    logger.warning("wrong.projection_did_not_settle namespace=%s source_id=%s passes=%d",
                   question_source_type, question_source_id, MAX_PROJECTION_PASSES)
    return row


def _apply_legacy(row: WrongAnswerState, legacy: dict | None) -> None:
    if not legacy:
        return
    row.legacy_source_type = legacy.get("source_type")
    row.legacy_source_id = legacy.get("source_id")
    row.legacy_mastered = legacy.get("mastered")
    row.legacy_review_count = legacy.get("review_count")
    row.legacy_reviewed_at = legacy.get("reviewed_at")


def _username_of(ordered: list[PracticeAttempt]) -> str | None:
    return ordered[-1].username if ordered else None


def project_attempt(db, attempt: PracticeAttempt) -> dict:
    """Failure-isolated projection for one freshly recorded attempt.

    A projection problem must never lose the attempt that already committed — the
    state is rebuildable from the facts, so the correct response is to log and move on.
    """
    try:
        row = recompute(
            db,
            user_id=attempt.user_id,
            service_namespace=attempt.service_namespace,
            question_source_type=attempt.question_source_type,
            question_source_id=attempt.question_source_id,
            question_scope_key=_scope_of(attempt),
        )
    except Exception as exc:  # noqa: BLE001 — never fail the attempt that already committed
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning(
            "practice.wrong_answer_projection_failed attempt_id=%s namespace=%s error=%s",
            attempt.id, attempt.service_namespace, type(exc).__name__)
        return {"projected": False, "reason": type(exc).__name__}

    if row is None:
        return {"projected": True, "state_id": None, "status": None}
    return {"projected": True, "state_id": row.id, "status": row.status}


def rebuild(db, *, user_id: int | None = None, service_namespace: str | None = None,
            dry_run: bool = False) -> dict:
    """Reconcile states from canonical attempts. Idempotent; never destructive."""
    q = db.query(PracticeAttempt)
    if user_id is not None:
        q = q.filter(PracticeAttempt.user_id == user_id)
    if service_namespace is not None:
        q = q.filter(PracticeAttempt.service_namespace == service_namespace)

    identities = {}
    for attempt in q.all():
        key = (attempt.user_id, attempt.service_namespace, attempt.question_source_type,
               attempt.question_source_id, _scope_of(attempt))
        identities.setdefault(key, 0)
        identities[key] += 1

    created = updated = 0
    for (uid, ns, src_type, src_id, scope) in identities:
        existing = (db.query(WrongAnswerState)
                    .filter_by(user_id=uid, service_namespace=ns,
                               question_source_type=src_type,
                               question_source_id=src_id, question_scope_key=scope)
                    .first())
        if dry_run:
            if existing is None:
                created += 1
            else:
                updated += 1
            continue
        before = existing.id if existing else None
        row = recompute(db, user_id=uid, service_namespace=ns,
                        question_source_type=src_type, question_source_id=src_id,
                        question_scope_key=scope)
        if row is None:
            continue
        if before is None:
            created += 1
        else:
            updated += 1

    logger.info("practice.wrong_answer_rebuild created=%s updated=%s scanned=%s",
                created, updated, len(identities))
    return {"created": created, "updated": updated, "identities": len(identities),
            "dry_run": dry_run}
