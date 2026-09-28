"""Grant a unified subscription tier to one account — the operator path for production.

WHY THIS EXISTS. The only self-service way into a paid tier is a verified payment callback
(``payments.service.apply_verified_payment``), and the mock provider is correctly refused in
production (``is_mock_payment_allowed``). That leaves no product-supported path for an
operator to put an acceptance account on a paid tier, so this script is it: it calls the
SAME activation function the payment and redemption paths call
(``usage.service.activate_subscription``) rather than writing ``subscriptions`` by hand, so
the row it creates is indistinguishable from one a real purchase would have created.

SCOPE is deliberately one table, through one function. No raw SQL, no column lists, no
UPDATE of anything else. ``activate_subscription`` cancels any other active subscription for
the user first — that is its documented contract, and it is what makes "one effective tier
per user" true.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/grant_membership.py --username prod_acceptance_learner \
            --tier advanced --days 365

Exit codes:
    0  the account's effective tier is the requested tier
    1  the grant did not take effect (the run did not achieve its goal)
    2  the script could not run (bad/missing arguments, unknown user, unknown tier)

Never prints a password, a hash, or any other credential — only usernames, tiers and counts.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# The closed set the product actually sells. "free" is deliberately absent: it is the absence
# of a subscription, not a subscription, so it is not something this script can grant.
GRANTABLE_TIERS = ("standard", "advanced")


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant a unified subscription tier to one account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--tier", required=True, choices=GRANTABLE_TIERS)
    parser.add_argument("--days", type=int, required=True)
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("[grant] DATABASE_URL is required (never assume the default database)")
        return 2
    if args.days <= 0:
        print("[grant] --days must be positive")
        return 2

    import models  # noqa: E402  (import after DATABASE_URL is in place)
    from database import SessionLocal  # noqa: E402
    from usage.service import activate_subscription, effective_subscription  # noqa: E402

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == args.username).first()
        if user is None:
            print(f"[grant] ERROR: no such user: {args.username}")
            return 2

        before = effective_subscription(db, user.id)
        print(f"[grant] USER={user.username} USER_ID={user.id}")
        print(f"[grant] EFFECTIVE_TIER_BEFORE={before}")

        # commit=True: this is the whole transaction, and a partial grant would be worse than
        # none — the caller reads the tier back from the same session immediately after.
        sub = activate_subscription(db, user.id, args.tier, args.days, source="ops_grant", commit=True)

        after = effective_subscription(db, user.id)
        print(f"[grant] EFFECTIVE_TIER_AFTER={after}")
        print(f"[grant] SUBSCRIPTION_ID={sub.id} TIER={sub.tier} END_AT={sub.end_at}")

        if after != args.tier:
            print(f"[grant] ERROR: effective tier is {after}, expected {args.tier}")
            return 1
    finally:
        db.close()

    print(f"[grant] {args.username} now holds {args.tier} for {args.days} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
