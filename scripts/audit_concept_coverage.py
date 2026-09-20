"""Read-only CS408 concept-coverage audit against a database SNAPSHOT (ACCEL_PRODUCT_S8).

WHY A SNAPSHOT AND NOT THE LIVE DATABASE
----------------------------------------
The product's real question bank is preservation-critical content, and this audit has no
business holding the live file open. So the script takes a path to a copy — a
``VACUUM INTO`` snapshot on the server, a local ``app.db`` copy on a workstation — opens it
READ-ONLY, and never writes to it.

    python scripts/audit_concept_coverage.py --db C:/path/to/snapshot.db
    python scripts/audit_concept_coverage.py --db snapshot.db --json report.json

WHAT IT REPORTS
---------------
The exact before/after numbers the sprint's PART 6 asks for, per module and in total, under
S6's strict rule and under the S8 normalization, plus the corroboration counters that make
the normalization auditable (rule disagreements, chapter-segment agreement, and every
near-match the normalization REFUSED).

It repairs nothing. ``science.concept_coverage`` is a measurement module and this script
only prints its result.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to a database SNAPSHOT (read-only)")
    parser.add_argument("--json", help="also write the full report to this path")
    parser.add_argument("--active-only", action="store_true", default=False,
                        help="restrict the audit to active questions")
    args = parser.parse_args()

    snapshot = Path(args.db).resolve()
    if not snapshot.exists():
        print(f"ERROR: snapshot not found: {snapshot}", file=sys.stderr)
        return 2

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    # READ-ONLY at the connection level, so a mistake here cannot become a content change.
    engine = create_engine(f"sqlite+pysqlite:///file:{snapshot.as_posix()}?mode=ro&uri=true")
    with Session(engine) as session:
        from science import concept_coverage as cc
        report = cc.question_bank_coverage(session, active_only=args.active_only)

    norm = report["normalization"]
    print(f"measured_against : {report['measured_against']}")
    print(f"rule_version     : {norm['rule_version']}")
    print(f"active_only      : {report['active_only']}")
    print()
    print(f"{'module':24} {'questions':>9} {'concept':>8} {'pct':>7} {'strict':>8} "
          f"{'chapter':>8} {'module_only':>11}")
    for module, row in report["per_module"].items():
        print(f"{module:24} {row['questions']:>9} {row['concept']:>8} "
              f"{row['concept_pct']:>6.2f}% {row['strict']['concept']:>8} "
              f"{row['chapter']:>8} {row['module_only']:>11}")
    print()
    print("BEFORE (strict: stored id equals a canonical leaf code)")
    print(f"  {json.dumps(norm['before'], ensure_ascii=False)}")
    print("AFTER  (strict + canonical-title echo + source-ref descendant rule)")
    print(f"  {json.dumps(norm['after'], ensure_ascii=False)}")
    print(f"  recovered_concept_rows = {norm['recovered_concept_rows']}")
    print(f"  resolved_by_rule       = {json.dumps(norm['resolved_by_rule'], ensure_ascii=False)}")
    print()
    corr = norm["corroboration"]
    print("CORROBORATION")
    print(f"  rules_disagreed           = {corr['rules_disagreed']}  (must be 0)")
    print(f"  chapter_segments agreed   = {corr['chapter_segments_agreed']}"
          f" / {corr['chapter_segments_compared']}  (must be equal)")
    print(f"  rows_resolved_by_two_rules= {corr['rows_resolved_by_two_rules']}")
    print("  REFUSED near-matches (listed, never silently dropped):")
    if not corr["rejected_near_matches"]:
        print("    (none)")
    for label, count in corr["rejected_near_matches"].items():
        print(f"    {label} -> {count} rows")

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nfull report written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
