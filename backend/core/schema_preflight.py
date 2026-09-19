"""Deployment schema preflight — refuse to serve a database that is behind the code.

ACCEL_SPRINT_S6 PART B.

WHY THIS EXISTS
---------------
From ``20260919_0010`` onward the application's ORM models select columns that only a
migration can add. ``Base.metadata.create_all`` does NOT add columns to a table that
already exists, so on a legacy database the app used to start successfully and then fail
much later, at the first ``SELECT`` that touched a new column — i.e. inside a request, in
front of a learner, with a 500 that says nothing about the real cause.

This module moves that failure to STARTUP, before any traffic. It answers one question:
"is the schema this process is about to use the schema this code was written for?"

WHAT IT DOES NOT DO
-------------------
It is a READ-ONLY check. It never runs DDL, never creates or repairs a table, never
stamps a revision, and never calls ``create_all``. Migration ownership stays with Alembic;
a preflight that could fix the schema would be a second migration mechanism wearing a
different name.

THE THREE DATABASE STATES
-------------------------
1. NOT PARTICIPATING — the database holds none of the product's tables. This is a brand
   new file, an ephemeral test database, or a first install before anything ran. There is
   nothing to be behind on, and the revision table does not exist because no migration has
   ever been needed. ALLOWED.

2. MANAGED — ``alembic_version`` exists. The database is under Alembic's control, so the
   question is exact: it must be at ``SCRIPT_HEAD``. Strictly behind, on a branch, or at a
   revision this checkout does not contain — all refused.

3. UNMANAGED BUT PRE-EXISTING — the database holds product tables and has no
   ``alembic_version`` at all. This is the legacy shape: the tables were created at import
   by ``create_all`` and no revision was ever applied. It is exactly the database the new
   columns are missing from, so it is refused with the command that fixes it.

State 3 is the one that matters most, because it is the shape of every deployed database
today and the shape that used to start silently.

ESCALATION
----------
``ZHIXUE_SCHEMA_PREFLIGHT=warn`` downgrades a refusal to a loud stderr warning, and
``=off`` skips the check. Both exist for one narrow purpose: a long-running process, or a
maintenance tool, that must inspect a database which is legitimately not at head. They are
NOT a supported way to run the product server, and ``warn`` still prints the full
operational error. The default is ``enforce``.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from sqlalchemy import inspect as sa_inspect

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations" / "versions"

# The columns the application's ORM selects and a migration — not create_all — adds.
# Each entry is the revision that introduces it; the revision is carried so the
# operational error can name the smallest fix rather than "upgrade everything".
REQUIRED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("ai_requests", "service_namespace", "20260915_0006"),
    ("ai_requests", "context_json", "20260915_0006"),
    ("usage_ledger", "service_namespace", "20260915_0006"),
    ("wrong_answer_states", "module_key", "20260919_0009"),
    ("practice_attempts", "response_time_source", "20260919_0010"),
    ("practice_attempts", "attempt_index", "20260919_0010"),
    ("learning_events", "response_time_source", "20260919_0010"),
    ("learning_events", "attempt_index", "20260919_0010"),
)

# The tables whose presence means "this database is part of the product's lifecycle".
# Used only to tell state 1 from state 3; deliberately few, and all of them long-lived.
_PRODUCT_SENTINEL_TABLES = ("users", "study_materials", "exam_question_bank")

ENFORCE = "enforce"
WARN = "warn"
OFF = "off"
_MODES = (ENFORCE, WARN, OFF)


class SchemaBehindError(RuntimeError):
    """The database is not at the revision this code requires."""


_REVISION_RE = re.compile(r"^revision\s*(?::[^=\n]+)?=\s*[\"']([^\"']+)[\"']",
                          re.MULTILINE)
_DOWN_REVISION_RE = re.compile(r"^down_revision\s*(?::[^=\n]+)?=\s*(.+)$",
                               re.MULTILINE)
_QUOTED_RE = re.compile(r"[\"']([^\"']+)[\"']")


def script_head(versions_dir: Path | None = None) -> str:
    """The head revision of the migration scripts in this checkout.

    Derived from the files rather than from a constant, so it cannot drift from the chain
    it is supposed to describe. A branched chain is an error here: the deployment expects
    exactly one head, and guessing which branch is "the" head would be worse than refusing.
    """
    directory = versions_dir or MIGRATIONS_DIR
    if not directory.is_dir():
        raise SchemaBehindError(
            f"migration scripts not found at {directory}; the schema preflight cannot "
            f"determine the expected revision of this deployment")

    revisions: set[str] = set()
    parents: set[str] = set()
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("__"):
            continue
        text = path.read_text(encoding="utf-8")
        found = _REVISION_RE.search(text)
        if not found:
            continue
        revisions.add(found.group(1))
        # a merge revision names several parents; every one of them is a parent
        down_match = _DOWN_REVISION_RE.search(text)
        if down_match:
            parents.update(_QUOTED_RE.findall(down_match.group(1)))

    if not revisions:
        raise SchemaBehindError(f"no revisions found under {directory}")
    heads = sorted(revisions - parents)
    if len(heads) != 1:
        raise SchemaBehindError(
            f"the migration chain has {len(heads)} heads ({', '.join(heads)}); a "
            f"deployment must have exactly one, so the preflight refuses to guess")
    return heads[0]


def _current_revision(engine) -> str | None:
    """The revision the database is stamped at, or None when it has no revision table."""
    inspector = sa_inspect(engine)
    if "alembic_version" not in set(inspector.get_table_names()):
        return None
    with engine.connect() as connection:
        values = [r[0] for r in
                  connection.exec_driver_sql("SELECT version_num FROM alembic_version")]
    if not values:
        return None
    if len(values) > 1:
        return ",".join(sorted(str(v) for v in values))
    return str(values[0])


def _missing_columns(engine) -> list[tuple[str, str, str]]:
    """Required columns that are absent. Read-only; a missing table counts as missing."""
    inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())
    missing = []
    columns: dict[str, set[str]] = {}
    for table, column, revision in REQUIRED_COLUMNS:
        if table not in tables:
            missing.append((table, column, revision))
            continue
        if table not in columns:
            columns[table] = {c["name"] for c in inspector.get_columns(table)}
        if column not in columns[table]:
            missing.append((table, column, revision))
    return missing


def inspect_schema(engine, *, versions_dir: Path | None = None) -> dict:
    """The full, read-only picture. Never raises for a schema problem; reports it."""
    expected = script_head(versions_dir)
    inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())
    current = _current_revision(engine)
    missing = _missing_columns(engine)
    participating = bool(tables & set(_PRODUCT_SENTINEL_TABLES))

    if current is None:
        state = "UNMANAGED_PRE_EXISTING" if participating else "NOT_PARTICIPATING"
    elif current == expected:
        state = "AT_HEAD"
    else:
        state = "BEHIND_HEAD"

    return {
        "state": state,
        "expected_revision": expected,
        "current_revision": current,
        "table_count": len(tables),
        "missing_required_columns": [
            {"table": t, "column": c, "added_by_revision": r} for t, c, r in missing],
    }


def operational_error(report: dict) -> str:
    """The message an operator sees at 3am. It names the state and the exact command."""
    head = report["expected_revision"]
    lines = [
        "SCHEMA PREFLIGHT FAILED - this deployment must not start.",
        f"  database state : {report['state']}",
        f"  database revision : {report['current_revision'] or '(none - no alembic_version)'}",
        f"  required revision : {head}",
    ]
    if report["missing_required_columns"]:
        shown = report["missing_required_columns"][:8]
        lines.append("  missing columns the ORM selects:")
        lines.extend(
            f"    {m['table']}.{m['column']}  (added by {m['added_by_revision']})"
            for m in shown)
        remaining = len(report["missing_required_columns"]) - len(shown)
        if remaining:
            lines.append(f"    ... and {remaining} more")
    lines += [
        "  migration ownership is Alembic, so create_all cannot repair this: SQLAlchemy",
        "  never adds a column to a table that already exists.",
        "  FIX: back up the database, then run",
        f"         alembic -c alembic.ini upgrade head      (from the repository root)",
        "       and start the application only after it reports success.",
    ]
    return "\n".join(lines)


def preflight_mode() -> str:
    """enforce (default) / warn / off. An unknown value is treated as enforce."""
    value = (os.getenv("ZHIXUE_SCHEMA_PREFLIGHT") or "").strip().lower()
    return value if value in _MODES else ENFORCE


def verify_or_raise(engine, *, versions_dir: Path | None = None) -> dict:
    """Run the preflight. Raises :class:`SchemaBehindError` unless the schema is usable.

    NOT_PARTICIPATING and AT_HEAD pass. Everything else raises, unless the operator has
    explicitly downgraded the check to ``warn``.
    """
    report = inspect_schema(engine, versions_dir=versions_dir)
    # AT_HEAD alone is not enough: a database stamped at head whose columns were removed
    # by hand is still a database the ORM cannot read.
    ok = (report["state"] == "NOT_PARTICIPATING"
          or (report["state"] == "AT_HEAD" and not report["missing_required_columns"]))
    if ok:
        return report

    message = operational_error(report)
    mode = preflight_mode()
    if mode == OFF:
        return report
    if mode == WARN:
        print(message + "\n  (ZHIXUE_SCHEMA_PREFLIGHT=warn - continuing anyway)",
              file=sys.stderr, flush=True)
        return report
    raise SchemaBehindError(message)


def assert_ready(engine, *, versions_dir: Path | None = None) -> dict:
    """Alias used at application startup; reads as the question being asked."""
    return verify_or_raise(engine, versions_dir=versions_dir)
