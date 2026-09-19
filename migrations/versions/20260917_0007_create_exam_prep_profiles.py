"""create exam_prep_profiles

Revision ID: 20260917_0007
Revises: 20260915_0006
Create Date: 2026-09-17

STEP7H4 gives Exam Prep its own canonical learner profile. The exam CATALOG stays versioned
config (``learning.spaces.exam_prep.catalog``) — this table is only the learner's selection,
so that the legacy ``user_learning_tracks`` (membership/direction carrier) is not reused as
the Exam Prep profile.

Additive-only: one new table. No legacy exam table is created, rebuilt, renamed or dropped
here, no question row is touched, and no dead table is removed — those are separate steps.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migrations.guards import create_index_if_absent, create_table_if_absent

revision: str = "20260917_0007"
down_revision: Union[str, None] = "20260915_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    create_table_if_absent(
        "exam_prep_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("exam_type", sa.String(length=50), nullable=False,
                  server_default="postgraduate"),
        sa.Column("selected_track", sa.String(length=64), nullable=True),
        sa.Column("selected_subjects_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("target_exam_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # one CURRENT exam-prep profile per user
        sa.UniqueConstraint("user_id", name="uq_exam_prep_profile_user"),
    )
    create_index_if_absent("ix_exam_prep_profiles_user_id", "exam_prep_profiles", ["user_id"])


def downgrade() -> None:
    raise NotImplementedError("additive-only; no downgrade is provided")
