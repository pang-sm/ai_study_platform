"""Practice Core SQLAlchemy models — exactly two tables (STEP 7D).

    practice_sessions
    practice_attempts

No wrong-answer / review / plan / outcome tables here; those are later STEPs. Legacy
practice tables are untouched and stay the domain source of truth during the
compatibility window.

Timestamps are never fabricated: a legacy session that carries no real start time gets
``started_at = NULL`` rather than a synthetic one.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)

from database import Base
from models import utc_now

SCHEMA_VERSION = 1

# session status
SESSION_ACTIVE = "active"
SESSION_COMPLETED = "completed"
SESSION_ABANDONED = "abandoned"
SESSION_STATUSES = (SESSION_ACTIVE, SESSION_COMPLETED, SESSION_ABANDONED)

# how the session came into being
ORIGIN_LIVE = "live"                     # created through the Practice Core API
ORIGIN_LEGACY_COMPAT = "legacy_compat"   # deterministic session for a legacy attempt


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        UniqueConstraint("session_uid", name="uq_practice_session_uid"),
        Index("ix_practice_sessions_user_ns", "user_id", "service_namespace"),
        Index("ix_practice_sessions_source", "source_type", "source_session_key"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Deterministic identity: UUIDv5 over (service_namespace, source_type,
    # source_session_key) for mirrored legacy containers, random UUID4 for live API
    # sessions. Recomputation always yields the same value, so re-importing the same
    # legacy container can never create a second session.
    session_uid = Column(String(36), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(50), nullable=True, index=True)  # legacy traceability
    service_namespace = Column(String(30), nullable=False, index=True)

    # practice mode / container description (e.g. chapter, past_paper, exercise)
    mode = Column(String(50), nullable=True)
    source_type = Column(String(50), nullable=True)        # legacy container type
    source_session_key = Column(String(255), nullable=True)  # legacy container identity
    session_origin = Column(String(20), nullable=False, default=ORIGIN_LIVE)

    status = Column(String(20), nullable=False, default=SESSION_ACTIVE)
    context_json = Column(Text, nullable=True)             # LearningContext snapshot

    started_at = Column(DateTime, nullable=True)           # NULL when the source had none
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    schema_version = Column(Integer, nullable=False, default=SCHEMA_VERSION)


class PracticeAttempt(Base):
    """One real answer/submission — an immutable historical fact.

    ``correct`` is intentionally tri-state: True / False / NULL. NULL means the source
    did not state correctness (e.g. an ungraded big question, or AI feedback that is
    not a verdict). It is never coerced to False, and no model is ever asked to guess.
    """

    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint("attempt_uid", name="uq_practice_attempt_uid"),
        Index("ix_practice_attempts_user_ns", "user_id", "service_namespace"),
        Index("ix_practice_attempts_source", "source_attempt_type", "source_attempt_id"),
        Index("ix_practice_attempts_question", "question_source_type", "question_source_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Deterministic for mirrored legacy rows (UUIDv5 over the source identity);
    # random UUID4 for attempts recorded directly through the Practice Core API.
    attempt_uid = Column(String(36), nullable=False)

    session_id = Column(Integer, ForeignKey("practice_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(50), nullable=True, index=True)
    service_namespace = Column(String(30), nullable=False, index=True)

    # canonical question pointer + its full typed payload (context + raw provenance)
    question_source_type = Column(String(50), nullable=False)
    question_source_id = Column(String(100), nullable=False)
    question_ref_json = Column(Text, nullable=False)

    # legacy provenance of this attempt (NULL for attempts born in the Practice Core)
    source_attempt_type = Column(String(50), nullable=True)
    source_attempt_id = Column(String(50), nullable=True)
    source_item_key = Column(String(255), nullable=True)

    answer = Column(Text, nullable=True)

    # result envelope — domain semantics preserved, never flattened
    correct = Column(Boolean, nullable=True)   # tri-state; NULL != False
    score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    result_json = Column(Text, nullable=True)  # the source's own result payload

    submitted_at = Column(DateTime, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    attempt_no = Column(Integer, nullable=True)

    # ACCEL_SPRINT_S5 attempt telemetry. ``response_time_ms`` has always been able to hold
    # a number; ``response_time_source`` records WHERE that number came from, which is what
    # makes it usable — a duration with no measured boundary is not a duration. NULL means
    # the provenance is unknown (every row written before S5, and any row whose duration
    # arrived without one). It is never backfilled: the boundary was not recorded at the
    # time and cannot be recovered afterwards.
    response_time_source = Column(String(30), nullable=True)
    # 1-based ordinal of this attempt among the SAME learner's attempts on the SAME
    # question. Distinct from ``attempt_no``, which is a paper-sitting number on the
    # past-paper path. NULL when the caller had no real count.
    attempt_index = Column(Integer, nullable=True)

    # ACCEL_PRODUCT_S10 dataset provenance — see ``data_plane.origin``. Only ``LEARNER``
    # attempts may train a model; a demo rehearsal writes rows of identical shape.
    data_origin = Column(String(30), nullable=True, index=True)

    context_json = Column(Text, nullable=True)  # LearningContext snapshot
    fact_hash = Column(String(64), nullable=True)  # sha256 of the canonical fact payload

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    schema_version = Column(Integer, nullable=False, default=SCHEMA_VERSION)
