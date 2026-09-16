"""create Unified Subscription / Usage Budget & Ledger / AI cost tables

Revision ID: 20260915_0002
Revises: 20260915_0001
Create Date: 2026-09-15

Creates the five STEP 7B tables:
  subscriptions, usage_budgets, usage_ledger, ai_requests, ai_cost_records.

Additive-only. Does NOT create capability_permission_overrides (V1) or a
qualified_model_pool table (CONFIG). Mirrors backend/usage/models.py exactly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260915_0002"
down_revision: Union[str, None] = "20260915_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "usage_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("budget_amount", sa.Integer(), nullable=False),
        sa.Column("reserved_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settled_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "period_type", "period_start",
                            name="uq_usage_budget_period"),
    )

    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reference_key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "ai_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("capability", sa.String(50), nullable=False),
        sa.Column("tier", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("estimated_credits", sa.Integer(), nullable=True),
        sa.Column("reserved_credits", sa.Integer(), nullable=True),
        sa.Column("actual_credits", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("error_category", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "ai_cost_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(64), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("normalized_credits", sa.Integer(), nullable=False),
        sa.Column("pricing_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ai_cost_records")
    op.drop_table("ai_requests")
    op.drop_table("usage_ledger")
    op.drop_table("usage_budgets")
    op.drop_table("subscriptions")
