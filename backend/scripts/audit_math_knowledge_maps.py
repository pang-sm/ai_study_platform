"""Print the structural audit of the 考研数学 canonical knowledge maps.

    backend/.venv/Scripts/python.exe scripts/audit_math_knowledge_maps.py

Read-only. Exits non-zero when any map fails its structural rules, so it can be used as a gate.
Also prints the source manifest, because a map whose provenance does not resolve is not auditable
even when its tree is well-formed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from learning.spaces.exam_prep import math_knowledge as mk  # noqa: E402


def main() -> int:
    domain_keys = [path.stem for path in sorted(mk.KNOWLEDGE_MAP_DIR.glob("*.json"))
                   if path.stem in {"calculus", "linear_algebra", "probability_statistics"}]

    print(f"inclusion policy: {mk.CANONICAL_INCLUSION_POLICY}")
    print()
    print(f"{'domain':24s} {'ch':>3s} {'sec':>4s} {'leaf':>5s} {'nodes':>6s} {'depth':>7s} "
          f"{'dup':>4s} {'badpar':>7s} {'cyc':>4s} {'granularity':22s} ok")
    totals = {"chapters": 0, "sections": 0, "leaves": 0, "node_count": 0}
    failed = False
    for key in domain_keys:
        audit = mk.audit_domain(key)
        for field in totals:
            totals[field] += getattr(audit, field)
        print(f"{audit.domain:24s} {audit.chapters:3d} {audit.sections:4d} {audit.leaves:5d} "
              f"{audit.node_count:6d} {audit.min_depth}-{audit.max_depth:<5d} "
              f"{audit.duplicate_count:4d} {audit.invalid_parent_count:7d} {audit.cycle_count:4d} "
              f"{audit.granularity_status:22s} {'yes' if audit.ok else 'NO'}")
        for issue in audit.issues:
            print(f"    ! {issue}")
        failed = failed or not audit.ok

    print()
    print(f"{'TOTAL':24s} {totals['chapters']:3d} {totals['sections']:4d} {totals['leaves']:5d} "
          f"{totals['node_count']:6d}")
    print()

    print("source manifest")
    for source in mk.manifest_sources():
        identity = source.get("isbn") or source.get("local_reference_name") or "(no identity)"
        digest = (source.get("sha256") or "")[:16] or "(no hash)"
        print(f"  {source['source_id']:28s} {source['role']:18s} "
              f"{source['verification_status']:18s} {digest:18s} {identity}")

    print()
    print(json.dumps({"ok": not failed}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
