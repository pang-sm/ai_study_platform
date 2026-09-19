"""Idempotent DDL helpers for the revision chain (ACCEL_SPRINT_S6 PART A/C).

WHY THIS MODULE EXISTS
----------------------
Every deployed database of this product predates Alembic. Its tables were created at
import by ``Base.metadata.create_all``, and no revision was ever applied — there is no
``alembic_version`` table in it at all. When the chain is finally run against such a
database, the first revision that says ``op.create_table("learning_events", ...)`` meets a
``learning_events`` that has existed for months and aborts the whole deployment on

    sqlite3.OperationalError: table learning_events already exists

which is exactly the failure S6 exists to prevent: the application would have run the
migration after the backup, the migration would have died on its first statement, and the
only way forward would be a manual restore.

Using these helpers changes NOTHING about a fresh database: the table is absent, so the
DDL runs identically. The revision ids, the chain order and the resulting schema are all
unchanged. The only difference is on a database that already holds the table.

WHAT A GUARD DOES NOT DO
------------------------
It does not "repair" a table. If the table exists but is missing a column this revision
declares, that is a divergence the guard CANNOT resolve by skipping and MUST NOT resolve by
guessing, so it raises and names the gap. Silently stamping a divergent schema as migrated
is how a database ends up claiming a revision it does not implement.

Indexes are guarded for the same reason: ``create_all`` created them too, and a duplicate
``CREATE INDEX`` aborts a deployment just as reliably as a duplicate table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def _existing_columns(table: str) -> set[str] | None:
    """The columns of ``table``, or None when the table is absent."""
    inspector = sa.inspect(op.get_bind())
    if table not in set(inspector.get_table_names()):
        return None
    return {column["name"] for column in inspector.get_columns(table)}


def create_table_if_absent(table: str, *columns, **kwargs) -> bool:
    """``op.create_table`` that adopts a pre-existing table instead of aborting.

    Returns True when the table was created, False when it was already there.
    """
    existing = _existing_columns(table)
    if existing is None:
        op.create_table(table, *columns, **kwargs)
        return True

    # only sa.Column items name a column: the same call also carries UniqueConstraint and
    # sa.PrimaryKeyConstraint objects, whose ``name`` is a constraint name
    declared = {column.name for column in columns if isinstance(column, sa.Column)}
    missing = sorted(name for name in declared if name and name not in existing)
    if missing:
        raise RuntimeError(
            f"{table} already exists but is missing column(s) this revision declares: "
            f"{missing}. The table was created outside Alembic and does not match the "
            f"revision being applied; refusing to stamp it as migrated.")
    return False


def add_column_if_absent(table: str, column: sa.Column) -> bool:
    """``op.add_column`` that skips a column which is already present."""
    existing = _existing_columns(table)
    if existing is None:
        raise RuntimeError(
            f"{table} is missing; the revision that creates it must be applied first")
    if column.name in existing:
        return False
    op.add_column(table, column)
    return True


def create_index_if_absent(name: str, table: str, columns: list[str], **kwargs) -> bool:
    """``op.create_index`` that skips an index which is already present."""
    inspector = sa.inspect(op.get_bind())
    if table not in set(inspector.get_table_names()):
        raise RuntimeError(
            f"{table} is missing; the revision that creates it must be applied first")
    if name in {index["name"] for index in inspector.get_indexes(table)}:
        return False
    op.create_index(name, table, columns, **kwargs)
    return True
