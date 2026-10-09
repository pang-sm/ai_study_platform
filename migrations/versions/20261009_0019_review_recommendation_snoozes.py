"""Persist only the per-user snooze overlay for review recommendations.

Revision ID: 20261009_0019
Revises: 20261001_0018
"""
from alembic import op
import sqlalchemy as sa


revision = "20261009_0019"
down_revision = "20261001_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_recommendation_snoozes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_key", sa.String(length=64), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "recommendation_key", name="uq_review_snooze_user_key"),
    )
    op.create_index("ix_review_snooze_user_until", "review_recommendation_snoozes",
                    ["user_id", "snoozed_until"])


def downgrade() -> None:
    op.drop_index("ix_review_snooze_user_until", table_name="review_recommendation_snoozes")
    op.drop_table("review_recommendation_snoozes")
