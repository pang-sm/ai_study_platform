"""create STEP 7D Practice Core tables

Revision ID: 20260915_0003
Revises: 20260915_0002
Create Date: 2026-09-16

Creates exactly two tables:
  practice_sessions
  practice_attempts

Additive-only. Creates NO wrong-answer / review / plan / outcome tables (later STEPs).
Does not touch, rewrite or drop any legacy practice table: exam_question_bank,
programming_exercises, question_attempts, ai_question_attempts, exam_practice_attempts,
exam_question_done_records, past_paper_attempts, code_challenge_attempts and
programming_exercise_submissions all stay exactly as they are.

Mirrors backend/learning/practice/models.py exactly.
"""
from typing import Sequence, Union

from alembic import op

from migrations.guards import create_index_if_absent, create_table_if_absent
import sqlalchemy as sa

revision: str = "20260915_0003"
down_revision: Union[str, None] = "20260915_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    create_table_if_absent(
        "practice_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_uid", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("service_namespace", sa.String(30), nullable=False),
        sa.Column("mode", sa.String(50), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_session_key", sa.String(255), nullable=True),
        sa.Column("session_origin", sa.String(20), nullable=False,
                  server_default="live"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("session_uid", name="uq_practice_session_uid"),
    )
    create_index_if_absent("ix_practice_sessions_user_id", "practice_sessions", ["user_id"])
    create_index_if_absent("ix_practice_sessions_username", "practice_sessions", ["username"])
    create_index_if_absent("ix_practice_sessions_service_namespace", "practice_sessions",
                    ["service_namespace"])
    create_index_if_absent("ix_practice_sessions_user_ns", "practice_sessions",
                    ["user_id", "service_namespace"])
    create_index_if_absent("ix_practice_sessions_source", "practice_sessions",
                    ["source_type", "source_session_key"])

    create_table_if_absent(
        "practice_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("attempt_uid", sa.String(36), nullable=False),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("practice_sessions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("service_namespace", sa.String(30), nullable=False),
        sa.Column("question_source_type", sa.String(50), nullable=False),
        sa.Column("question_source_id", sa.String(100), nullable=False),
        sa.Column("question_ref_json", sa.Text(), nullable=False),
        sa.Column("source_attempt_type", sa.String(50), nullable=True),
        sa.Column("source_attempt_id", sa.String(50), nullable=True),
        sa.Column("source_item_key", sa.String(255), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("fact_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("attempt_uid", name="uq_practice_attempt_uid"),
    )
    create_index_if_absent("ix_practice_attempts_session_id", "practice_attempts", ["session_id"])
    create_index_if_absent("ix_practice_attempts_user_id", "practice_attempts", ["user_id"])
    create_index_if_absent("ix_practice_attempts_username", "practice_attempts", ["username"])
    create_index_if_absent("ix_practice_attempts_service_namespace", "practice_attempts",
                    ["service_namespace"])
    create_index_if_absent("ix_practice_attempts_user_ns", "practice_attempts",
                    ["user_id", "service_namespace"])
    create_index_if_absent("ix_practice_attempts_source", "practice_attempts",
                    ["source_attempt_type", "source_attempt_id"])
    create_index_if_absent("ix_practice_attempts_question", "practice_attempts",
                    ["question_source_type", "question_source_id"])


def downgrade() -> None:
    # Additive-only project: no destructive downgrade path is provided for product
    # tables. Dropping these two tables would destroy learner practice history.
    raise NotImplementedError(
        "practice core tables are additive-only; no downgrade is provided")
