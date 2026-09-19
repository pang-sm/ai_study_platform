"""add canonical learning context to AI requests

Revision ID: 20260915_0006
Revises: 20260915_0005
Create Date: 2026-09-16

STEP7G-C2 makes AI request ownership durable and carries its queryable namespace into
the usage ledger.  All columns are nullable so existing rows preserve their historical
shape. Additive-only: no table, row, constraint, or protected asset is removed/rebuilt.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migrations.guards import add_column_if_absent, create_index_if_absent

revision: str = "20260915_0006"
down_revision: Union[str, None] = "20260915_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    add_column_if_absent("ai_requests", sa.Column("service_namespace", sa.String(length=50), nullable=True))
    add_column_if_absent("ai_requests", sa.Column("context_json", sa.JSON(), nullable=True))
    create_index_if_absent("ix_ai_requests_service_namespace", "ai_requests", ["service_namespace"])
    add_column_if_absent("usage_ledger", sa.Column("service_namespace", sa.String(length=50), nullable=True))
    create_index_if_absent("ix_usage_ledger_service_namespace", "usage_ledger", ["service_namespace"])


def downgrade() -> None:
    raise NotImplementedError("additive-only; no downgrade is provided")
