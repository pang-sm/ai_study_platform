"""add Learning Records query indexes to learning_events

Revision ID: 20260915_0005
Revises: 20260915_0004
Create Date: 2026-09-16

STEP 7F adds NO table and NO column: the LearningEvent envelope already expresses every
field the frozen target requires (service_namespace maps onto the existing ``service_key``
column, payload onto ``item_snapshot_json``, source onto the source_* columns).

The one thing the schema genuinely lacked is an index for the Records query pattern the
step must deliver — user-scoped, newest-first, optional time window and namespace
filter — so this revision adds exactly two indexes and nothing else:

  ix_learning_events_user_occurred  (user_id, occurred_at)
  ix_learning_events_ns_occurred    (service_key, occurred_at)

Additive-only. No column, constraint, table or data is touched.
"""
from typing import Sequence, Union

from alembic import op

from migrations.guards import create_index_if_absent

revision: str = "20260915_0005"
down_revision: Union[str, None] = "20260915_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    create_index_if_absent("ix_learning_events_user_occurred", "learning_events",
                    ["user_id", "occurred_at"])
    create_index_if_absent("ix_learning_events_ns_occurred", "learning_events",
                    ["service_key", "occurred_at"])


def downgrade() -> None:
    # Indexes only; dropping them would not destroy learner data, but this project's
    # product tables are additive-only, so no downgrade path is provided.
    raise NotImplementedError("additive-only; no downgrade is provided")
