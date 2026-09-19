"""WrongAnswerState — exactly one physical table (STEP 7E).

No attempt history table, no event table, no review tables. History is queried from
``practice_attempts``; review scheduling is a later STEP.

Review-ish columns from the legacy tables (``mastered``, ``review_count``,
``reviewed_at``) are carried as LEGACY COMPATIBILITY METADATA. They are not a review
system, and they never override the correctness of a newer factual attempt.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)

from database import Base
from models import utc_now

SCHEMA_VERSION = 1

# current error state
STATUS_ACTIVE = "active"
STATUS_RESOLVED = "resolved"
STATUSES = (STATUS_ACTIVE, STATUS_RESOLVED)

# how this row came to exist
ORIGIN_PRACTICE = "practice"          # derived from canonical PracticeAttempt facts
ORIGIN_LEGACY = "legacy"              # imported from a legacy wrong-answer table
ORIGIN_LEGACY_MERGED = "legacy_merged"  # legacy row for a question that also has facts


class WrongAnswerState(Base):
    __tablename__ = "wrong_answer_states"
    __table_args__ = (
        # identity = user × learning space × canonical question (× optional scope)
        UniqueConstraint("user_id", "service_namespace", "question_source_type",
                         "question_source_id", "question_scope_key",
                         name="uq_wrong_answer_state_identity"),
        Index("ix_wrong_answer_states_user_ns", "user_id", "service_namespace"),
        Index("ix_wrong_answer_states_user_ns_module", "user_id", "service_namespace",
              "module_key"),
        Index("ix_wrong_answer_states_status", "status"),
        Index("ix_wrong_answer_states_question", "question_source_type",
              "question_source_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(50), nullable=True, index=True)
    service_namespace = Column(String(30), nullable=False)

    # canonical question identity (question identity != attempt identity)
    question_source_type = Column(String(50), nullable=False)
    question_source_id = Column(String(100), nullable=False)
    question_scope_key = Column(String(120), nullable=False, default="")

    # The exam module the question belongs to (data_structure / computer_organization /
    # operating_system / computer_network). This is a FILTER dimension, not an identity
    # dimension: ``question_scope_key`` already carries the module for scoped questions,
    # and the unique constraint above is what enforces one state per logical question. A
    # first-class column exists so a module-scoped read is an indexed WHERE and never a
    # parse of a scope string or a context blob. Empty for a question that has no module.
    module_key = Column(String(50), nullable=False, default="")

    status = Column(String(20), nullable=False, default=STATUS_ACTIVE)
    origin = Column(String(20), nullable=False, default=ORIGIN_PRACTICE)

    # derived from the canonical attempt facts — never from projection call counts
    wrong_count = Column(Integer, nullable=False, default=0)
    first_wrong_attempt_id = Column(Integer, nullable=True)
    latest_wrong_attempt_id = Column(Integer, nullable=True)
    latest_attempt_id = Column(Integer, nullable=True)
    resolved_attempt_id = Column(Integer, nullable=True)

    first_wrong_at = Column(DateTime, nullable=True)
    last_wrong_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    context_json = Column(Text, nullable=True)   # LearningContext snapshot

    # legacy compatibility metadata (NOT a review system)
    legacy_source_type = Column(String(50), nullable=True)
    legacy_source_id = Column(Integer, nullable=True)
    legacy_mastered = Column(Boolean, nullable=True)
    legacy_review_count = Column(Integer, nullable=True)
    legacy_reviewed_at = Column(DateTime, nullable=True)

    schema_version = Column(Integer, nullable=False, default=SCHEMA_VERSION)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
