"""add the trusted account-level data_origin marker to users

Revision ID: 20260921_0013
Revises: 20260919_0012
Create Date: 2026-09-21

ACCEL_PRODUCT provenance closure. One additive nullable column, ``users.data_origin``: the
account's own declared origin, which every training-relevant fact it produces inherits.

WHY AN ACCOUNT MARKER, WHEN 0012 ALREADY ADDED PER-FACT COLUMNS
------------------------------------------------------------------------------------
0012 answers "why does THIS fact exist" and is stamped by the writer at the moment of
recording. That is the right place for a real learner's facts, but it cannot express a
production ACCEPTANCE account: the only lever 0012 left is the process-wide ``DATA_ORIGIN``
env var, which production deliberately REFUSES (``data_plane/origin.py``), because a
deployment-wide switch that suppresses every learner's data from training is exactly the
kind of operator convenience that is destructive where it is wrong.

An acceptance account is a property of ONE account, not of a deployment. It is also trusted
state, not client input: the value lives in this column, is written only through the
admin-only contract (``PUT /admin/users/{username}/data-origin``), and is audit-logged. No
request body, header or cookie can set it.

WHY NULL IS THE CORRECT VALUE FOR EVERY EXISTING ROW, AND WHY NOTHING IS BACK-FILLED
------------------------------------------------------------------------------------
NULL means "this account has no marker, so its facts take the process origin" — which is
precisely true of every account that exists at this revision. Unlike the fact columns, no
history is reconstructed here because there is no historical question to answer: the marker
records an arrangement that begins when it is set. Back-filling it with a value would be
inventing a past arrangement, and 0012's own rule is that an arrangement is never guessed.

A marker may only ever name an origin that is EXCLUDED from training; the resolver refuses a
marker that would grant admissibility (see ``data_plane.origin.AccountOrigin`` /
``ALLOWED_ACCOUNT_ORIGINS``). So the worst a mis-set marker can do is exclude one account's
data from training — it can never smuggle a demo or test deployment's data INTO the set.

SAFETY — additive-only
------------------------------------------------------------------------------------
Guard on inspection so a partially applied deployment re-runs as a no-op. No table is
rebuilt, no existing row is rewritten, and no default is set (a default would make the
marker's absence indistinguishable from a decision to set it).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# Annotated like the rest of the chain: the chain-integrity tests read the revision graph by
# parsing these two declarations, and a bare assignment is invisible to that reader.
revision: str = "20260921_0013"
down_revision: Union[str, None] = "20260919_0012"
branch_labels = None
depends_on = None

TABLE = "users"
COLUMN = "data_origin"
COLUMN_TYPE = sa.String(30)


def upgrade() -> None:
    """Add the marker column when the table is there; do nothing when it is not.

    ``users`` is NOT created by this chain — it is a legacy table the application builds at
    startup (``create_all`` / ``ensure_database_schema``). So a fresh alembic-only database
    legitimately has no ``users`` table yet, and this revision must not demand one: the
    column arrives with the table itself, because the ORM model declares it. Refusing to run
    there would break a fresh install for no reason; adding the column unconditionally would
    fail on a database that has no such table.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE not in set(inspector.get_table_names()):
        print(f"[20260921_0013] {TABLE} does not exist yet (legacy-managed table); the ORM "
              f"model creates {COLUMN} with it at startup — nothing to alter here.")
        return

    if COLUMN in {c["name"] for c in inspector.get_columns(TABLE)}:
        print(f"[20260921_0013] {TABLE}.{COLUMN} already present; no-op.")
        return

    op.add_column(TABLE, sa.Column(COLUMN, COLUMN_TYPE, nullable=True))
    print(f"[20260921_0013] {TABLE}.{COLUMN} added (nullable, no default, no back-fill: "
          f"NULL means 'use the process origin', which is true of every existing account)")


def downgrade() -> None:
    """Refused, like the rest of the chain — and for this column it matters.

    Dropping the marker does not merely lose information: it silently makes an acceptance
    account's future facts training-admissible again, which is the exact state this revision
    exists to end. A chain where some revisions reverse and others do not is also worse than
    one where none do.
    """
    raise NotImplementedError(
        "the account data-origin marker is additive-only; no downgrade is provided")
