"""add attempt-telemetry provenance columns

Revision ID: 20260919_0010
Revises: 20260919_0009
Create Date: 2026-09-19

ACCEL_SPRINT_S5 PART D/O. Four additive nullable columns across the two tables that hold
one attempt's facts: ``response_time_source`` and ``attempt_index`` on both
``practice_attempts`` and ``learning_events``.

WHY PROVENANCE IS A COLUMN AND NOT A CONVENTION
------------------------------------------------------------------------------------
``response_time_ms`` already existed. The problem was never that the column was missing —
it is that a duration and a number are not the same thing. A duration is only meaningful
together with the two boundaries it was measured between, and those are not recoverable
from the value: 40 000 ms could be an item answered in forty seconds, or a tab left open
while the learner made tea. Recording WHICH boundary pair produced the number is what
turns it into a fact a model may consume, and it is the reason ``learning.practice.
telemetry`` refuses to store a number whose source is UNAVAILABLE.

WHY attempt_index IS NOT attempt_no
------------------------------------------------------------------------------------
``attempt_no`` already holds a PAPER-SITTING number on the past-paper path — the third time
a learner sits the 2022 paper — which has nothing to do with how many times they have
attempted one question. Overloading it would silently give a future model the wrong
quantity. ``attempt_index`` is its own column with its own meaning: the 1-based ordinal of
this attempt among the same learner's attempts on the same question.

WHAT IS DELIBERATELY NOT ADDED
------------------------------------------------------------------------------------
No hint column. The product has no hint mechanism on any CS408 practice surface, so there
is nothing to record — and the one rule that matters here is that "this surface offers no
hints" must never be stored as ``hint_count = 0``. Adding an integer column now would
invite exactly that. When a hint system exists, its own migration adds its own column.

No backfill, and none is possible. Every existing row keeps NULL in all four columns
because the boundary, the count and the provenance were not observed when the row was
written. Reconstructing them from ``created_at`` / ``submitted_at`` is forbidden on the
record: those two do not bracket active answering. NULL here is the honest value, and it
stays NULL.

SAFETY — additive-only
------------------------------------------------------------------------------------
Both tables are created by earlier revisions in this chain (``20260915_0001`` for
``learning_events``, ``20260915_0003`` for ``practice_attempts``), so reaching this
revision means both exist. Each column add is guarded on inspection, so a partially
applied deployment re-runs as a no-op. No DROP, no rebuild, no row rewrite; existing rows
keep every value they had.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0010"
down_revision: Union[str, None] = "20260919_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table -> the columns this revision adds to it
NEW_COLUMNS = {
    "practice_attempts": (
        ("response_time_source", sa.String(length=30)),
        ("attempt_index", sa.Integer()),
    ),
    "learning_events": (
        ("response_time_source", sa.String(length=30)),
        ("attempt_index", sa.Integer()),
    ),
}

# every new column is nullable with no server default: an absent observation is NULL, and
# a default would silently manufacture one.
_FIRST_TABLE_REVISION = {"practice_attempts": "20260915_0003",
                         "learning_events": "20260915_0001"}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    for table, columns in NEW_COLUMNS.items():
        if table not in tables:
            raise RuntimeError(
                f"{table} is missing; revision {_FIRST_TABLE_REVISION[table]} must be "
                f"applied first")
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, type_ in columns:
            if name in existing:
                continue
            op.add_column(table, sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    # Additive-only project. Dropping these would destroy the only record of where a
    # measured duration came from, leaving numbers that can no longer be interpreted.
    raise NotImplementedError(
        "attempt telemetry is additive-only; no downgrade is provided")
