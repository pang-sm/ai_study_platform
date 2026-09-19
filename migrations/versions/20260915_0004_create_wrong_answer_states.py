"""create STEP 7E Wrong Answer Core table

Revision ID: 20260915_0004
Revises: 20260915_0003
Create Date: 2026-09-16

Creates exactly ONE table:
  wrong_answer_states

Additive-only. Creates NO wrong_answer_attempt_history / wrong_answer_events /
review_items / review_attempts / review_schedules: attempt history is read from
practice_attempts, and review scheduling belongs to a later STEP.

Legacy wrong-answer tables (exam_wrong_questions, past_paper_wrong_questions) are not
touched — they are merged into the canonical state via a compatibility mirror.

Mirrors backend/learning/wrong_answers/models.py exactly.
"""
from typing import Sequence, Union

from alembic import op

from migrations.guards import create_index_if_absent, create_table_if_absent
import sqlalchemy as sa

revision: str = "20260915_0004"
down_revision: Union[str, None] = "20260915_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    create_table_if_absent(
        "wrong_answer_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("service_namespace", sa.String(30), nullable=False),
        sa.Column("question_source_type", sa.String(50), nullable=False),
        sa.Column("question_source_id", sa.String(100), nullable=False),
        sa.Column("question_scope_key", sa.String(120), nullable=False,
                  server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="practice"),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_wrong_attempt_id", sa.Integer(), nullable=True),
        sa.Column("latest_wrong_attempt_id", sa.Integer(), nullable=True),
        sa.Column("latest_attempt_id", sa.Integer(), nullable=True),
        sa.Column("resolved_attempt_id", sa.Integer(), nullable=True),
        sa.Column("first_wrong_at", sa.DateTime(), nullable=True),
        sa.Column("last_wrong_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("legacy_source_type", sa.String(50), nullable=True),
        sa.Column("legacy_source_id", sa.Integer(), nullable=True),
        sa.Column("legacy_mastered", sa.Boolean(), nullable=True),
        sa.Column("legacy_review_count", sa.Integer(), nullable=True),
        sa.Column("legacy_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "service_namespace", "question_source_type",
                            "question_source_id", "question_scope_key",
                            name="uq_wrong_answer_state_identity"),
    )
    create_index_if_absent("ix_wrong_answer_states_user_id", "wrong_answer_states", ["user_id"])
    create_index_if_absent("ix_wrong_answer_states_username", "wrong_answer_states", ["username"])
    create_index_if_absent("ix_wrong_answer_states_user_ns", "wrong_answer_states",
                    ["user_id", "service_namespace"])
    create_index_if_absent("ix_wrong_answer_states_status", "wrong_answer_states", ["status"])
    create_index_if_absent("ix_wrong_answer_states_question", "wrong_answer_states",
                    ["question_source_type", "question_source_id"])


def downgrade() -> None:
    # Additive-only project: dropping this table would destroy learner error history.
    raise NotImplementedError(
        "wrong_answer_states is additive-only; no downgrade is provided")
