"""Normalise ``users.plan`` into the GLOBAL legacy vocabulary — operator repair.

WHY THIS EXISTS. ``users.plan`` is the global legacy field. Migration 20260919_0011 can only map
the codes it lists (``free`` / ``monthly`` / ``quarterly`` / ``full``, plus the pre-catalog
names), and the deploy runs that migration's own pre-check *before* it starts the service. A
DIRECTION code written into the global field therefore has no mapping, the gate refuses to guess,
and the application is never started — a stopped production backend.

``_sync_membership_to_track`` used to write exactly that: ``exam_11408`` sells
``monthly_sprint`` / ``quarterly_boost`` / ``full_exam``, and it wrote the raw code into
``users.plan``. Every reader already degraded an unknown code to ``free``, so the write bought
nothing. The code path is fixed; this repairs the rows it already produced.

WHAT IT TOUCHES. Only rows the gate would reject. Each stored code is translated through
``membership.DIRECTION_PLAN_TO_GLOBAL_PLAN`` (rank-preserving: ``full_exam`` → ``full``), or set
to ``free`` when even that map does not know it. **The unified tier is not touched** — it lives in
``subscriptions`` and is the only thing that grants a feature. Idempotent: a second run is a no-op.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/repair_legacy_plan.py

Exit codes:
    0  no unmappable row remains
    1  a row is still unmappable after the rewrite
    2  could not run (no DATABASE_URL)
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

MIGRATION = (REPO_ROOT / "migrations" / "versions"
             / "20260919_0011_unified_membership_backfill.py")


def _legacy_mapper():
    """The migration's own mapper, so this repair cannot disagree with the gate that blocked us."""
    spec = importlib.util.spec_from_file_location("s10_mig_0011_repair", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._tier_from_legacy_user_plan


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("[repair] DATABASE_URL is required (never assume the default database)")
        return 2

    import models  # noqa: E402
    from database import SessionLocal  # noqa: E402
    from membership import DIRECTION_PLAN_TO_GLOBAL_PLAN  # noqa: E402

    mappable = _legacy_mapper()

    db = SessionLocal()
    fixed = 0
    try:
        users = db.query(models.User).all()
        for user in users:
            plan = (user.plan or "").strip().lower()
            if not plan or plan == "free":
                continue
            if mappable(plan) is not None:
                continue
            replacement = DIRECTION_PLAN_TO_GLOBAL_PLAN.get(plan, "free")
            print(f"[repair] user={user.username} user_id={user.id} "
                  f"users.plan {plan} -> {replacement}")
            user.plan = replacement
            fixed += 1
        db.commit()

        remaining = [f"{u.username}:{u.plan}" for u in db.query(models.User).all()
                     if (u.plan or "").strip() and (u.plan or "").strip().lower() != "free"
                     and mappable((u.plan or "").strip().lower()) is None]
    finally:
        db.close()

    print(f"[repair] ROWS_REWRITTEN={fixed}")
    if remaining:
        print(f"[repair] ERROR: still unmappable: {sorted(remaining)}")
        return 1
    print("[repair] every users.plan row is in the global vocabulary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
