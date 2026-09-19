"""add module_key to wrong_answer_states

Revision ID: 20260919_0009
Revises: 20260917_0008
Create Date: 2026-09-19

BC7 (CS408 wrong-answer canonicalization). One additive column and one index.

WHY A COLUMN AND NOT A PARSE
------------------------------------------------------------------------------------
``wrong_answer_states`` already carried the module inside ``question_scope_key``
(``subject:cs_408|module:operating_system|year:2022``) for past-exam questions — and
nowhere at all for chapter-practice questions, whose scope is deliberately empty because
a bank id is globally unique. A module-scoped read (F1C4's 章节练习 / 历年真题 list per
module) therefore had to either parse a scope string or open a context blob, and the
chapter case had no scope string to parse. ``module_key`` makes the module a real,
indexed filter dimension.

It is a FILTER dimension, not an identity dimension. The uniqueness of one wrong state per
(logical question, user) is already enforced by ``uq_wrong_answer_state_identity`` — a
constraint SQLite cannot alter without rebuilding the table, which this project forbids.
Adding module to that key would therefore require a rebuild for no behavioural gain, so it
is deliberately NOT added.

HISTORY: WHY THIS IS A REAL MIGRATION AND NOT A create_all ACCIDENT
------------------------------------------------------------------------------------
``wrong_answer_states`` is created by revision ``20260915_0004``, but the deployed
``backend/app.db`` has no ``alembic_version`` table at all, so no revision has ever been
applied to it. The table exists at runtime only because ``Base.metadata.create_all``
creates it at import. That is incidental schema, not managed schema. This revision is the
first one that has to *modify* the canonical table, so it also pins down the property that
matters: the canonical wrong-answer schema comes from Alembic, and a deployment that runs
``alembic upgrade head`` has it.

SAFETY — additive-only, two starting points
------------------------------------------------------------------------------------
A. fresh / migrated-empty DB -> the column and index are added to the head-0004 table.
B. legacy backend/app.db     -> the table is absent on a DB where 0004 has not run, and
                                this revision is reached only through 0004 in the chain,
                                so the table always exists here. Both the column add and
                                the index create are guarded on inspection, so re-running
                                a partially-applied deployment is a no-op rather than an
                                error.

No DROP, no rebuild, no row rewrite. Existing rows keep their data; the new column
defaults to '' and is then backfilled by the projector/backfill from the facts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0009"
down_revision: Union[str, None] = "20260917_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "wrong_answer_states"
COLUMN = "module_key"
INDEX = "ix_wrong_answer_states_user_ns_module"


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if TABLE not in tables:
        # The chain guarantees 20260915_0004 ran. Reaching here means the revision graph
        # was violated (e.g. a hand-stamped database), and silently creating the table
        # would hide exactly the create_all masking BC7 exists to close.
        raise RuntimeError(
            f"{TABLE} is missing; revision 20260915_0004 must be applied first")

    columns = {c["name"] for c in inspector.get_columns(TABLE)}
    if COLUMN not in columns:
        op.add_column(TABLE, sa.Column(
            COLUMN, sa.String(length=50), nullable=False, server_default=""))

    indexes = {i["name"] for i in inspector.get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, ["user_id", "service_namespace", COLUMN])


def downgrade() -> None:
    # Additive-only project: dropping this column would discard the module a learner's
    # error history is filed under.
    raise NotImplementedError(
        "wrong_answer_states is additive-only; no downgrade is provided")
