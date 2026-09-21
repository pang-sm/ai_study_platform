"""Canonical Practice Core service — the only way practice rows are written or read.

Every function is scoped by BOTH ``user_id`` and ``service_namespace``. There is no
unscoped accessor: a session belonging to someone else, or to another learning space,
must not be reachable by constructing the right id.

Business endpoints call these functions; they never assemble practice SQL themselves.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from data_plane import origin
from core.learning_context import (
    LearningContext,
    ServiceNamespace,
    normalize_service_namespace,
)

from . import identity
from . import telemetry as telemetry_module
from .models import (
    ORIGIN_LEGACY_COMPAT,
    ORIGIN_LIVE,
    SESSION_ABANDONED,
    SESSION_ACTIVE,
    SESSION_COMPLETED,
    PracticeAttempt,
    PracticeSession,
)
from .refs import QuestionRef

logger = logging.getLogger("learning.practice")


class PracticeError(Exception):
    """Base class for practice-core refusals."""


class SessionNotFound(PracticeError):
    pass


class SessionClosed(PracticeError):
    """Attempt refused because the session is completed or abandoned."""


class CrossUserAccess(PracticeError):
    pass


class NamespaceMismatch(PracticeError):
    """A session may only hold attempts from its own learning space."""


class AttemptConflict(PracticeError):
    """The same source identity re-imported with a DIFFERENT fact. Never overwritten."""


def _log(event: str, **fields):
    """Structured, privacy-safe log line: ids / namespace / type / status only."""
    parts = " ".join(f"{k}={v}" for k, v in sorted(fields.items()))
    logger.info("practice.%s %s", event, parts)


# ---------------------------------------------------------------- sessions

def create_session(db: DbSession, user, service_namespace, *, mode: str | None = None,
                   context: LearningContext | None = None,
                   source_type: str | None = None,
                   source_session_key: str | None = None,
                   session_origin: str = ORIGIN_LIVE,
                   started_at: datetime | None = None,
                   session_uid: str | None = None) -> PracticeSession:
    ns = _namespace_value(service_namespace)
    _require_context_namespace(context, ns)
    session = PracticeSession(
        session_uid=session_uid or identity.live_session_uid(),
        user_id=user.id,
        username=getattr(user, "username", None),
        service_namespace=ns,
        mode=mode,
        source_type=source_type,
        source_session_key=_str_or_none(source_session_key),
        session_origin=session_origin,
        status=SESSION_ACTIVE,
        context_json=_context_json(context),
        started_at=started_at,          # never invented
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    _log("session_created", session_id=session.id, user_id=user.id, namespace=ns,
         origin=session_origin, source_type=source_type or "-")
    return session


def ensure_legacy_session(db: DbSession, user, service_namespace, *, source_type: str,
                          source_session_key, mode: str | None = None,
                          context: LearningContext | None = None,
                          started_at: datetime | None = None):
    """Find-or-create the deterministic compat session for a legacy container.

    Returns ``(session, created)``. The id is derived from the source container, so a
    retry or a second attempt in the same container reuses the session rather than
    creating another one.
    """
    ns = _namespace_value(service_namespace)
    key = _str_or_none(source_session_key)
    uid = identity.session_uid(ns, source_type, key, getattr(user, "id", None))
    existing = db.query(PracticeSession).filter(
        PracticeSession.session_uid == uid,
        PracticeSession.user_id == user.id,
        PracticeSession.service_namespace == ns,
    ).first()
    if existing is not None:
        return existing, False
    try:
        session = create_session(
            db, user, ns, mode=mode, context=context, source_type=source_type,
            source_session_key=key, session_origin=ORIGIN_LEGACY_COMPAT,
            started_at=started_at, session_uid=uid)
        return session, True
    except IntegrityError:
        # concurrent creation of the same deterministic session — the unique
        # constraint is the gate, so just read the winner.
        db.rollback()
        existing = db.query(PracticeSession).filter(PracticeSession.session_uid == uid).first()
        if existing is None:
            raise
        return existing, False


def get_session(db: DbSession, user_id: int, session_id: int,
                service_namespace: str | None = None) -> PracticeSession:
    q = db.query(PracticeSession).filter(PracticeSession.id == session_id,
                                         PracticeSession.user_id == user_id)
    if service_namespace is not None:
        q = q.filter(PracticeSession.service_namespace == _namespace_value(service_namespace))
    session = q.first()
    if session is None:
        raise SessionNotFound(f"session {session_id} not found for this user")
    return session


def _course_filter(q, model, course_id):
    """Restrict a practice query to ONE course's rows, in SQL.

    The course a practice row belongs to lives in its context JSON (a course is part of the
    question's identity, not a column on the attempt), so the filter is a JSON extract —
    applied in SQL, BEFORE any limit. Filtering the fetched page in Python instead would
    let another course's rows fill the page the caller asked for.
    """
    return q.filter(func.json_extract(model.context_json, "$.course_id") == str(course_id))


def list_sessions(db: DbSession, user_id: int, *, service_namespace: str | None = None,
                  status: str | None = None, course_id: str | None = None,
                  limit: int = 50, offset: int = 0) -> list[PracticeSession]:
    q = db.query(PracticeSession).filter(PracticeSession.user_id == user_id)
    if service_namespace is not None:
        q = q.filter(PracticeSession.service_namespace == _namespace_value(service_namespace))
    if status is not None:
        q = q.filter(PracticeSession.status == status)
    if course_id is not None:
        q = _course_filter(q, PracticeSession, course_id)
    return (q.order_by(PracticeSession.id.desc()).offset(offset).limit(limit).all())


def complete_session(db: DbSession, user_id: int, session_id: int) -> PracticeSession:
    """Mark a session completed. Idempotent; never reopens a terminal session."""
    session = get_session(db, user_id, session_id)
    return _close(db, session, SESSION_COMPLETED)


def abandon_session(db: DbSession, user_id: int, session_id: int) -> PracticeSession:
    """Mark a session abandoned. Idempotent; never reopens a terminal session."""
    session = get_session(db, user_id, session_id)
    return _close(db, session, SESSION_ABANDONED)


def _close(db: DbSession, session: PracticeSession, target: str) -> PracticeSession:
    if session.status == target:
        return session                      # idempotent
    if session.status != SESSION_ACTIVE:
        raise SessionClosed(
            f"session {session.id} is {session.status}; cannot become {target}")
    session.status = target
    session.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    _log("session_closed", session_id=session.id, user_id=session.user_id,
         namespace=session.service_namespace, status=target)
    return session


# ---------------------------------------------------------------- attempts

@dataclass(frozen=True)
class SourceIdentity:
    """Where a mirrored attempt came from in the legacy domain tables."""

    source_attempt_type: str
    source_attempt_id: str
    source_item_key: str | None = None


@dataclass
class AttemptResult:
    attempt: PracticeAttempt
    created: bool          # False → deduped (same source identity, same fact)
    session: PracticeSession
    session_created: bool = False


def record_attempt(db: DbSession, user, session: PracticeSession, question_ref: QuestionRef,
                   *, answer: str | None = None, correct: bool | None = None,
                   score: float | None = None, max_score: float | None = None,
                   result: dict | None = None, submitted_at: datetime | None = None,
                   response_time_ms: int | None = None, attempt_no: int | None = None,
                   telemetry=None,
                   source: SourceIdentity | None = None,
                   context: LearningContext | None = None,
                   _session_created: bool = False) -> AttemptResult:
    """Record one real answer/submission as an immutable fact.

    Idempotent for a repeated ``source`` identity with an identical fact; a differing
    fact for the same identity raises instead of overwriting history.

    ``telemetry`` is an :class:`~learning.practice.telemetry.AttemptTelemetry` — the ONE
    envelope for a measured duration and a canonical attempt index. When it is supplied it
    owns ``response_time_ms`` and stamps its provenance. A bare ``response_time_ms`` still
    round-trips for the legacy adapters that pass one, but it lands with a NULL
    ``response_time_source``, which is the honest encoding of "a number exists whose
    boundaries were never recorded".
    """
    _assert_session_usable(session, user, question_ref)

    if telemetry is not None:
        if response_time_ms is not None:
            raise ValueError(
                "pass either telemetry or response_time_ms, not both — the envelope "
                "already carries the duration and its provenance")
        response_time_ms = telemetry.duration_ms

    # ACCEL_SPRINT_S6 PART F — telemetry activation. ``attempt_index`` is the one S5 field
    # whose quantity the SERVER genuinely observes, so the live path derives it here rather
    # than waiting for a caller to supply it and never doing so. It is a real count over
    # canonical rows, which is exactly what the S5 rule requires ("supplied from a real
    # count"); the count is simply taken by the process that owns the rows.
    attempt_index = telemetry.attempt_index if telemetry is not None else None
    if attempt_index is None and source is None:
        attempt_index = _next_live_attempt_index(db, user, question_ref)

    if source is not None:
        uid = identity.attempt_uid(session.service_namespace, source.source_attempt_type,
                                   source.source_attempt_id, source.source_item_key,
                                   user_id=user.id)
    else:
        uid = identity.live_attempt_uid()

    payload = _fact_payload(session, question_ref, answer, correct, score, max_score,
                            submitted_at, response_time_ms, attempt_no)
    digest = identity.fact_hash(payload)

    existing = db.query(PracticeAttempt).filter(PracticeAttempt.attempt_uid == uid).first()
    if existing is not None:
        return _dedupe_or_conflict(db, existing, digest, session)

    attempt = PracticeAttempt(
        attempt_uid=uid,
        session_id=session.id,
        user_id=user.id,
        username=getattr(user, "username", None),
        service_namespace=session.service_namespace,
        question_source_type=question_ref.source_type.value,
        question_source_id=str(question_ref.source_id),
        question_ref_json=identity.canonical_json(question_ref.to_dict()),
        source_attempt_type=source.source_attempt_type if source else None,
        source_attempt_id=source.source_attempt_id if source else None,
        source_item_key=source.source_item_key if source else None,
        answer=answer if isinstance(answer, str) or answer is None else str(answer),
        correct=correct,                     # tri-state, never coerced
        score=score,
        max_score=max_score,
        result_json=identity.canonical_json(result) if result is not None else None,
        submitted_at=submitted_at,
        response_time_ms=response_time_ms,
        attempt_no=attempt_no,
        response_time_source=telemetry.duration_source if telemetry is not None else None,
        attempt_index=attempt_index,
        data_origin=origin.active_origin(),
        context_json=_context_json(context) or session.context_json,
        fact_hash=digest,
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        # same deterministic uid won a concurrent race — the unique constraint is the gate
        db.rollback()
        existing = db.query(PracticeAttempt).filter(
            PracticeAttempt.attempt_uid == uid).first()
        if existing is None:
            raise
        return _dedupe_or_conflict(db, existing, digest, session)
    db.refresh(attempt)
    _log("attempt_recorded", attempt_id=attempt.id, session_id=session.id,
         user_id=user.id, namespace=session.service_namespace,
         question_source=question_ref.source_type.value,
         correctness="null" if correct is None else str(bool(correct)).lower())
    # STEP 7E: project the durable attempt onto the wrong-answer state. Lazy import
    # keeps the dependency one-directional (wrong_answers reads practice, not vice
    # versa), and the projection is failure-isolated on its own side: the attempt is
    # already committed and is the fact of record, so a projection problem can never
    # lose it — and the state is rebuildable from these facts at any time.
    try:
        from ..wrong_answers import project as _wrong_project
        _wrong_project.project_attempt(db, attempt)
    except Exception as _wa_exc:  # noqa: BLE001
        logger.warning("practice wrong-answer projection hook failed: %s",
                       type(_wa_exc).__name__)
    # STEP 7F: the practice spine owns question_answered / code_submitted, so the event
    # is emitted HERE rather than at the HTTP layer — every write path (API, legacy
    # adapters, backfill) then produces the same event for the same durable fact.
    # course_learning is skipped by the producer: the existing data_plane emitter owns
    # that fact and a second event would double-count the learner's history.
    try:
        from . import events as _practice_events
        _practice_events.emit_for_attempt(db, attempt)
    except Exception as _ev_exc:  # noqa: BLE001
        logger.warning("practice event hook failed: %s", type(_ev_exc).__name__)
    return AttemptResult(attempt=attempt, created=True, session=session,
                         session_created=_session_created)


def _next_live_attempt_index(db: DbSession, user, question_ref: QuestionRef) -> int:
    """The 1-based ordinal for a NEW attempt born in the Practice Core.

    Counted over canonical ``practice_attempts`` for the SAME learner and the SAME question
    identity, which is what :data:`learning.practice.telemetry.ATTEMPT_INDEX_SEMANTICS`
    says the value means. The question identity is ``(question_source_type,
    question_source_id)`` — the pair the canonical question pointer is made of — and NOT
    the session, so two attempts in different sessions on the same question still count as
    the first and the second attempt at that question.

    DELIBERATELY NOT APPLIED TO MIRRORED ATTEMPTS. A mirrored row is replayed from a legacy
    source, and during a replay the rows already present are an artifact of the replay
    order rather than the learner's real history: an ordinal counted from that state would
    be a fact about the import, not about the learner, and it would silently change if the
    import were ever run in a different order. Mirrored rows keep NULL — and because the
    count below includes them once they exist, the NEXT live attempt on such a question
    still receives its true ordinal.
    """
    prior = (db.query(func.count(PracticeAttempt.id))
             .filter(PracticeAttempt.user_id == user.id,
                     PracticeAttempt.question_source_type == question_ref.source_type.value,
                     PracticeAttempt.question_source_id == str(question_ref.source_id))
             .scalar())
    return telemetry_module.derived_attempt_index(int(prior or 0))


def _dedupe_or_conflict(db: DbSession, existing: PracticeAttempt, digest: str,
                        session: PracticeSession) -> AttemptResult:
    if existing.fact_hash == digest:
        _log("attempt_deduped", attempt_id=existing.id, session_id=existing.session_id,
             user_id=existing.user_id, namespace=existing.service_namespace,
             source_attempt=existing.source_attempt_id or "-")
        return AttemptResult(attempt=existing, created=False, session=session)
    _log("attempt_conflict", attempt_id=existing.id, session_id=existing.session_id,
         user_id=existing.user_id, namespace=existing.service_namespace,
         source_attempt=existing.source_attempt_id or "-",
         source_type=existing.source_attempt_type or "-")
    raise AttemptConflict(
        "source identity "
        f"{existing.source_attempt_type}:{existing.source_attempt_id}:"
        f"{existing.source_item_key} already recorded with a different fact; "
        "refusing to overwrite history")


def get_attempt(db: DbSession, user_id: int, attempt_id: int,
                service_namespace: str | None = None) -> PracticeAttempt:
    q = db.query(PracticeAttempt).filter(PracticeAttempt.id == attempt_id,
                                         PracticeAttempt.user_id == user_id)
    if service_namespace is not None:
        q = q.filter(PracticeAttempt.service_namespace == _namespace_value(service_namespace))
    attempt = q.first()
    if attempt is None:
        raise SessionNotFound(f"attempt {attempt_id} not found for this user")
    return attempt


def list_attempts(db: DbSession, user_id: int, *, session_id: int | None = None,
                  service_namespace: str | None = None, course_id: str | None = None,
                  limit: int = 100, offset: int = 0) -> list[PracticeAttempt]:
    q = db.query(PracticeAttempt).filter(PracticeAttempt.user_id == user_id)
    if session_id is not None:
        q = q.filter(PracticeAttempt.session_id == session_id)
    if service_namespace is not None:
        q = q.filter(PracticeAttempt.service_namespace == _namespace_value(service_namespace))
    if course_id is not None:
        # the course travels on the attempt's QUESTION REF, which is where the ONE context
        # builder put it — the session is a container, the ref is the identity
        q = q.filter(func.json_extract(PracticeAttempt.question_ref_json,
                                       "$.context.course_id") == str(course_id))
    return (q.order_by(PracticeAttempt.id.desc()).offset(offset).limit(limit).all())


def attempt_counts(db: DbSession, user_id: int, *, service_namespace: str | None = None,
                   course_id: str | None = None) -> dict:
    """Factual attempt counts for one scope, computed in SQL.

    BOUNDED BY CONSTRUCTION: three aggregates, no rows materialized. Every figure is a
    count over the stored ``correct`` tri-state, which is why an ungraded attempt is
    reported rather than folded into "incorrect".
    """
    q = db.query(PracticeAttempt).filter(PracticeAttempt.user_id == user_id)
    if service_namespace is not None:
        q = q.filter(PracticeAttempt.service_namespace == _namespace_value(service_namespace))
    if course_id is not None:
        q = q.filter(func.json_extract(PracticeAttempt.question_ref_json,
                                       "$.context.course_id") == str(course_id))

    attempts = q.count()
    graded = (q.with_entities(PracticeAttempt.correct, func.count())
              .filter(PracticeAttempt.correct.isnot(None))
              .group_by(PracticeAttempt.correct).all())
    correct_true = next((c for v, c in graded if v is True), 0)
    correct_false = next((c for v, c in graded if v is False), 0)
    graded_total = correct_true + correct_false
    return {
        "attempts": attempts,
        "graded_attempts": graded_total,
        "factual_correct": correct_true,
        "factual_incorrect": correct_false,
        # a blank submission has no verdict and no score — it is counted, not scored
        "ungraded_attempts": attempts - graded_total,
    }


def session_summary(db: DbSession, user_id: int, session_id: int) -> dict:
    """Counts computed from the attempts themselves — no cached aggregate columns."""
    session = get_session(db, user_id, session_id)
    attempts = list_attempts(db, user_id, session_id=session.id, limit=10_000)
    scored = [a for a in attempts if a.correct is not None]
    return {
        "session_id": session.id,
        "status": session.status,
        "attempt_count": len(attempts),
        "graded_count": len(scored),
        "correct_count": sum(1 for a in scored if a.correct),
        "ungraded_count": len(attempts) - len(scored),
        "score_total": sum(a.score or 0.0 for a in attempts) or None,
        "max_score_total": sum(a.max_score or 0.0 for a in attempts) or None,
    }


# ---------------------------------------------------------------- guards / helpers

def _assert_session_usable(session: PracticeSession, user, question_ref: QuestionRef):
    if session.user_id != getattr(user, "id", None):
        raise CrossUserAccess("session belongs to another user")
    if session.status != SESSION_ACTIVE:
        raise SessionClosed(f"session {session.id} is {session.status}; "
                            "it no longer accepts attempts")
    if session.service_namespace != question_ref.service_namespace.value:
        raise NamespaceMismatch(
            f"session is {session.service_namespace} but the question is "
            f"{question_ref.service_namespace.value}")


def _fact_payload(session, question_ref, answer, correct, score, max_score,
                  submitted_at, response_time_ms, attempt_no) -> dict:
    # ACCEL_SPRINT_S5: ``response_time_source`` / ``attempt_index`` are deliberately NOT
    # part of this payload. This digest decides whether a replayed source identity carries
    # the SAME graded fact, or a conflicting one. Every attempt recorded before S5 was
    # hashed without telemetry, so adding a field here would change the digest of facts
    # that have not changed and make a legitimate replay raise AttemptConflict against
    # history. Provenance annotates the observation; it does not alter the graded fact.
    return {
        "namespace": session.service_namespace,
        "session_id": session.id,
        "question": question_ref.to_dict(),
        "answer": answer if isinstance(answer, str) or answer is None else str(answer),
        "correct": correct,
        "score": score,
        "max_score": max_score,
        "submitted_at": submitted_at.isoformat() if submitted_at else None,
        "response_time_ms": response_time_ms,
        "attempt_no": attempt_no,
    }


def _namespace_value(service_namespace) -> str:
    """Canonical namespace, normalized once via the shared boundary helper.

    Legacy aliases ("course") are accepted as INPUT here and never stored.
    """
    try:
        return normalize_service_namespace(service_namespace)
    except ValueError as exc:
        raise NamespaceMismatch(str(exc)) from exc


def _require_context_namespace(context: LearningContext | None, namespace: str):
    if context is not None and context.service_namespace.value != namespace:
        raise NamespaceMismatch(
            f"context is {context.service_namespace.value} but the session is {namespace}")


def _context_json(context: LearningContext | None) -> str | None:
    return identity.canonical_json(context.to_dict()) if context is not None else None


def _str_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
