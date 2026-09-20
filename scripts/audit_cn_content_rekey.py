"""Read-only ``computer_network`` content-rekey CANDIDATE report (ACCEL_PRODUCT_S9 PART D).

WHAT THIS IS FOR
----------------
``computer_network``'s question bank was ingested from a source whose own section numbering
runs ``4.1``..``4.51`` in the SAME numeric slots as the canonical leaves of canonical
chapter 4, which is a 7-leaf chapter:

    stored  '4.2 路由与转发'      canonical 4.2 = '4.2 IPv4'
    stored  '4.6 拥塞控制'        canonical 4.6 = '4.6 移动IP'

The resolver refuses all of them, so those questions stay reachable at CHAPTER level and
carry no concept. The open question is whether any of them can be re-keyed onto a canonical
leaf by a rule that does not invent anything.

This script answers that question with a measurement instead of an opinion, and it writes
NOTHING. It reports, for every question of the module whose concept is unresolved:

    question id · stored source identity · source_ref · current chapter · candidate (if any)

and a candidate is PROVABLE only when the product's own versioned resolver establishes one
— exact equality against a string the module's seed publishes (a leaf code, a leaf's own
title, or a strict-descent provenance triple). No model, no embedding, no fuzzy match, no
title similarity, no positional reasoning. A row that comes back without a candidate is a
row for which no mapping is provable from the content itself, and the report says so rather
than proposing one.

Re-keying ``exam_question_bank`` is a CONTENT decision, not an engineering one, and it is
NOT taken here. The script makes the size of that decision precise.

    python scripts/audit_cn_content_rekey.py --db C:/path/to/snapshot.db
    python scripts/audit_cn_content_rekey.py --db snapshot.db --json report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MODULE = "computer_network"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to a database SNAPSHOT (read-only)")
    parser.add_argument("--module", default=MODULE)
    parser.add_argument("--all-questions", action="store_true",
                        help="include inactive rows (default: active only)")
    parser.add_argument("--json", help="also write the full report to this path")
    args = parser.parse_args()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from science import concept_coverage

    snapshot = Path(args.db).resolve()
    if not snapshot.exists():
        print(f"snapshot not found: {snapshot}", file=sys.stderr)
        return 2
    # READ-ONLY. The snapshot is never opened for writing.
    engine = create_engine(f"sqlite:///{snapshot.as_posix()}",
                           connect_args={"check_same_thread": False})
    session = sessionmaker(bind=engine)()
    try:
        report = concept_coverage.unresolved_identity_report(
            session, args.module, active_only=not args.all_questions)
    finally:
        session.close()

    print(f"snapshot         : {snapshot}")
    print(f"module           : {report['module_key']}")
    print(f"active_only      : {report['active_only']}")
    print(f"rule_version     : {report['rule_version']}")
    print()
    print(f"questions examined        : {report['questions_examined']}")
    print(f"concept UNRESOLVED        : {report['unresolved']}")
    print(f"PROVABLE rekeys available : {report['provable_rekeys']}")
    print()
    print("unresolved by current level:")
    for level, count in report["by_current_level"].items():
        print(f"    {level:14s} {count}")
    print("unresolved by current chapter:")
    for chapter, count in report["by_current_chapter"].items():
        print(f"    {chapter:>8s} {count}")
    print("unresolved by reason:")
    for reason, count in report["by_reason"].items():
        print(f"    {reason:40s} {count}")
    print()
    print("candidates that ARE provable:")
    provable = [r for r in report["records"] if r["provable"]]
    if not provable:
        print("    (none — no stored identity resolves under the versioned rule set)")
    for record in provable:
        print(f"    q{record['question_id']} {record['stored_source_identity']!r} -> "
              f"{record['candidate']}")
    print()
    print("near-matches REFUSED (the shape a laxer rule would have accepted):")
    near = [r for r in report["records"] if r["near_match_leaf_code"]]
    if not near:
        print("    (none)")
    for record in near:
        print(f"    q{record['question_id']} {record['stored_source_identity']!r} ~ "
              f"canonical {record['near_match_leaf_code']}  "
              f"[chapter {record['current_chapter']}]")
    print()
    print(f"writes: {report['writes']}")

    if args.json:
        target = Path(args.json)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print(f"\nfull report written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
