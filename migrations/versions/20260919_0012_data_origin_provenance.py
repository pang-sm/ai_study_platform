"""add data_origin provenance to the two fact tables

Revision ID: 20260919_0012
Revises: 20260919_0011
Create Date: 2026-09-20

ACCEL_PRODUCT_S10 PART F/G. One additive nullable column, ``data_origin``, on the two tables
that hold one attempt's fact: ``practice_attempts`` (the Practice Core's durable record) and
``learning_events`` (the canonical fact stream a training export reads).

WHY A COLUMN AND NOT A CONVENTION
------------------------------------------------------------------------------------
A demo rehearsal and a real learner answering a real question write rows of IDENTICAL shape.
Nothing in the row distinguishes them, and the difference is not recoverable afterwards: it
is not a function of the timestamp, the user id, the session, or the score. So it has to be
written down by the only code that knows — the writer — at the moment of recording. The rule
it encodes: only ``LEARNER`` facts may train a model or satisfy a data-readiness gate
(``backend/data_plane/origin.py``).

The column is NULLABLE WITH NO DEFAULT, deliberately. ``LEARNER`` is not the default because
a default would let a writer that forgot to declare its origin silently contribute to the
training set. NULL is reported as ``UNCLASSIFIED`` and excluded, so forgetting produces a
visible empty bucket rather than an invisible inclusion.

WHY HISTORY IS BACK-FILLED TO ``LEARNER``, AND WHY THAT IS NOT A GUESS
------------------------------------------------------------------------------------
Every row that exists at this revision was written by a live product path. That is
checkable from the code, not assumed: the only writers of these two tables are
``learning/practice/service.py`` (the Practice Core), ``data_plane/emitter.py`` and
``learning/records/producers.py`` (the live emitters), and ``data_plane/backfill.py``, which
re-projects REAL recorded source attempts and invents nothing. No demo, acceptance or test
writer existed before this revision, and the one pre-existing acceptance script
(``scripts/verify_s9_product_flows.py``) refuses to run against production and works on a
database COPY.

The alternative — leaving history NULL — would report a genuinely real dataset as empty and
exclude it from the readiness gate, which is the same class of error in the opposite
direction. Rows are therefore classified by evidence that is actually in the schema:
``SOURCE_BACKFILL`` rows are real re-projections, not synthetic facts.

SAFETY — additive-only
------------------------------------------------------------------------------------
Both tables are created by earlier revisions in this chain (``20260915_0001`` for
``learning_events``, ``20260915_0003`` for ``practice_attempts``). Column adds are guarded on
inspection so a partially applied deployment re-runs as a no-op. The back-fill only writes
the new column; no other value on any row is touched, and no row is added or removed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0012"
down_revision: Union[str, None] = "20260919_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMN = "data_origin"
COLUMN_TYPE = sa.String(length=30)

# table -> the revision that creates it in this chain
TABLES = {
    "learning_events": "20260915_0001",
    "practice_attempts": "20260915_0003",
}

LEARNER = "LEARNER"
INDEX_NAME = "ix_learning_events_data_origin"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table, first_revision in TABLES.items():
        if table not in tables:
            raise RuntimeError(f"{table} is missing; revision {first_revision} must be "
                               f"applied first")
        existing = {c["name"] for c in inspector.get_columns(table)}
        if COLUMN in existing:
            continue
        op.add_column(table, sa.Column(COLUMN, COLUMN_TYPE, nullable=True))

    # Index the column on the fact stream: the export and the diagnostics both filter on it,
    # and a full scan of the canonical fact table is the one cost that grows without bound.
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("learning_events")}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, "learning_events", [COLUMN])

    # Back-fill history. Only rows that are still NULL are touched, so re-running is a no-op
    # and a row written by a NEWER code path (which stamps its own origin) is never relabelled.
    for table in TABLES:
        result = bind.execute(sa.text(
            f"UPDATE {table} SET {COLUMN} = :origin WHERE {COLUMN} IS NULL"),
            {"origin": LEARNER})
        print(f"[20260919_0012] {table}: classified {result.rowcount or 0} historical "
              f"rows as {LEARNER} (live product writers only; see this revision's docstring)")


def downgrade() -> None:
    """This column is the only record of WHY a fact exists. Dropping it would make every
    demo row indistinguishable from a real learner's, which is exactly the state this
    revision exists to end."""
    raise NotImplementedError(
        "dataset provenance is additive-only; no downgrade is provided")
