"""Deployment schema check — the operator-facing entry point (ACCEL_SPRINT_S6 PART B).

Runs the same preflight the application runs at startup, against an explicitly named
database, and reports the answer as a process exit code so a deployment script can gate on
it. It performs NO migration and mutates nothing: it answers "may the application start
against this database?" and nothing else.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/check_schema.py

Exit codes:
    0  the database is at the required revision (or is new and has nothing to be behind)
    1  the database is behind / unmanaged / missing a required column
    2  the check itself could not run (no DATABASE_URL, no migration scripts, …)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402

from core import schema_preflight  # noqa: E402


def main(argv: list[str]) -> int:
    url = (argv[1] if len(argv) > 1 else "") or os.getenv("DATABASE_URL", "")
    if not url:
        print("check_schema: DATABASE_URL is required (argument or environment)",
              file=sys.stderr)
        return 2
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        # relative sqlite path: resolve against the repository root so the check reads the
        # same file the service does regardless of the caller's working directory
        tail = url[len("sqlite:///"):]
        url = "sqlite:///" + (REPO_ROOT / tail).as_posix()

    try:
        engine = create_engine(url)
        report = schema_preflight.inspect_schema(engine)
    except Exception as exc:  # noqa: BLE001 — an unreadable database is a check failure
        print(f"check_schema: the schema could not be read: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    ok = (report["state"] == "NOT_PARTICIPATING"
          or (report["state"] == "AT_HEAD" and not report["missing_required_columns"]))
    if ok:
        print(f"[schema-check] OK: {report['state']} "
              f"revision={report['current_revision'] or '(new database)'}")
        return 0

    print(schema_preflight.operational_error(report), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
