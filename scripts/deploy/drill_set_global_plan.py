"""DRILL ONLY — put one account's GLOBAL ``users.plan`` back into an unmappable state.

This exists for exactly one purpose: to reproduce, on demand and under control, the condition
that took production down on 2026-09-28 (a direction plan code sitting in the global field), so
the deploy's new preflight-before-stop ordering can be PROVEN rather than asserted. It is the
setup half of the deploy-safety drill; ``repair_legacy_plan.py`` is the teardown half.

It writes ONE column on ONE row and touches nothing else. ``subscriptions`` — the only thing that
grants a feature — is never touched, so a drilled account keeps its entitlements throughout.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/drill_set_global_plan.py --username X --plan full_exam

Exit codes:
    0  the row now holds the requested (deliberately unmappable) code
    2  could not run (no DATABASE_URL / no such user / plan not a direction code)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Restricted to direction codes on purpose: this tool must not be able to write anything the
# deploy's membership gate CAN map, or a "drill" could quietly become a real entitlement change.
DRILL_CODES = ("full_exam", "monthly_sprint", "quarterly_boost")


def main() -> int:
    parser = argparse.ArgumentParser(description="DRILL: set an unmappable global users.plan.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--plan", required=True, choices=DRILL_CODES)
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("[drill] DATABASE_URL is required (never assume the default database)")
        return 2

    import models  # noqa: E402
    from database import SessionLocal  # noqa: E402

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == args.username).first()
        if user is None:
            print(f"[drill] ERROR: no such user: {args.username}")
            return 2
        before = user.plan
        user.plan = args.plan
        db.commit()
        print(f"[drill] user={user.username} user_id={user.id} users.plan {before} -> {args.plan}")
        print("[drill] this account's subscriptions were NOT touched")
    finally:
        db.close()
    print("[drill] ready: the next deploy's preflight should now REFUSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
