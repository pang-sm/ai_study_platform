"""backfill unified subscriptions from legacy paid entitlements

Revision ID: 20260919_0011
Revises: 20260919_0010
Create Date: 2026-09-20

ACCEL_PRODUCT_S10 PART B4. After this revision the unified ``subscriptions`` table is the
single tier authority: capability gates resolve from it, and the legacy
``user_service_memberships`` rows remain only as a compatibility record for the four fixed
-count quotas. This revision makes that safe for users who already paid under the OLD
storage, by giving every one of them the unified tier their purchase implies.

WHY A DATA MIGRATION AND NOT A FALLBACK IN THE RESOLVER
------------------------------------------------------------------------------------
A runtime "if there is no subscription, look at the legacy row" fallback would leave the two
systems permanently coupled: every gate would keep two possible answers, and the second one
would never be exercised in tests that always write a subscription. Translating the legacy
rows ONCE, at a known revision, is what lets the resolver have exactly one authority. The
legacy rows are then free to be dead weight rather than load-bearing.

WHAT IT WRITES, AND WHAT IT DOES NOT
------------------------------------------------------------------------------------
It writes ``subscriptions`` rows ONLY — INSERT, never UPDATE or DELETE. No legacy row is
touched, no user loses a plan, no quota changes. It is additive in both directions: the
insert is guarded on "the user's current unified tier is lower than the tier their legacy
entitlement implies", so re-running is a no-op and a later unified purchase is never
downgraded.

NO USER LOSES A PAID ENTITLEMENT
------------------------------------------------------------------------------------
Two sources are read, and the HIGHER tier wins:

  1. an enabled, unexpired ``user_service_memberships`` row, mapped through that direction's
     frozen catalog rank (rank 1-2 → standard, rank 3+ → advanced);
  2. the legacy global ``users.plan`` field, mapped through a frozen table — it predates the
     per-direction catalogs and is still written by the exam-package sync.

Both maps are INLINED below rather than imported from ``membership``. A migration records
what it meant on the day it ran; importing a catalog that keeps evolving would let a future
edit silently change what this revision did on a database that already ran it.

REFUSAL ON AMBIGUITY
------------------------------------------------------------------------------------
A non-free, non-expired plan code that appears in NO map is not guessed at. The upgrade
collects those rows and raises before writing anything, listing the affected users and
codes, so a human decides. Mapping an unknown code to ``free`` would be exactly the silent
entitlement loss this revision exists to prevent.

REVERSIBILITY
------------------------------------------------------------------------------------
No downgrade is offered, matching the rest of this chain. Recovery is the pre-migration
backup snapshot, which is the path S6 PART E rehearses; see ``downgrade`` below for why an
otherwise-safe DELETE is not provided anyway.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0011"
down_revision: Union[str, None] = "20260919_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MIGRATION_SOURCE = "migration"

TIER_RANK = {"free": 0, "standard": 1, "advanced": 2}

# Per-direction catalog ranks, FROZEN at this revision.
SERVICE_PLAN_RANKS = {
    "exam_11408": {"free": 0, "monthly_sprint": 1, "quarterly_boost": 2, "full_exam": 3},
    "course_learning": {"free": 0, "monthly": 1, "quarterly": 2, "full": 3},
    "programming": {"free": 0, "monthly": 1, "quarterly": 2, "full": 3},
}

# Codes with no catalog rank of their own.
EXPLICIT_PLAN_TIER = {"free": "free", "gift_pro": "advanced", "developer": "advanced"}

# The legacy GLOBAL users.plan field. Ranks first (monthly/quarterly/full appear in the
# direction catalogs), then the pre-catalog plan names.
LEGACY_GLOBAL_RANKS = {"free": 0, "monthly": 1, "quarterly": 2, "full": 3}
LEGACY_GLOBAL_PLAN_TIER = {
    "python_basic": "standard",
    "engineering_plus": "standard",
    "cs_pro": "standard",
    "gift_pro": "advanced",
    "developer": "advanced",
}


def _tier_from_rank(rank: int) -> str:
    if rank >= 3:
        return "advanced"
    if rank >= 1:
        return "standard"
    return "free"


def _tier_from_service_plan(service_key: str, plan_code) -> str | None:
    """Unified tier for a direction plan code; ``None`` when the code is not mappable."""
    plan = (plan_code or "").strip().lower() or "free"
    if plan in EXPLICIT_PLAN_TIER:
        return EXPLICIT_PLAN_TIER[plan]
    ranks = SERVICE_PLAN_RANKS.get(service_key)
    if ranks is None or plan not in ranks:
        return None
    return _tier_from_rank(ranks[plan])


def _tier_from_legacy_user_plan(plan_code) -> str | None:
    plan = (plan_code or "").strip().lower() or "free"
    if plan in LEGACY_GLOBAL_PLAN_TIER:
        return LEGACY_GLOBAL_PLAN_TIER[plan]
    if plan in LEGACY_GLOBAL_RANKS:
        return _tier_from_rank(LEGACY_GLOBAL_RANKS[plan])
    return None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    # ``subscriptions`` is created by revision 20260915_0002 in this same chain, so on any
    # database that reached this revision it is present. Its absence means the chain was
    # not applied, which is not a state this revision may silently write into.
    if "subscriptions" not in tables:
        raise RuntimeError(
            "subscriptions is missing; revision 20260915_0002 must be applied first")

    # ``users`` / ``user_service_memberships`` are LEGACY tables created by the application's
    # own schema path (database_schema.py), NOT by this migration chain. A fresh deployment
    # built from `alembic upgrade head` alone therefore has neither — and it also has no
    # legacy entitlement to translate, so the correct action is a no-op rather than a failure.
    # This is what makes `alembic upgrade head` sufficient for a fresh database.
    missing_legacy = [t for t in ("users", "user_service_memberships") if t not in tables]
    if missing_legacy:
        print(f"[20260919_0011] {', '.join(missing_legacy)} absent — no legacy "
              f"entitlement storage exists on this database; nothing to back-fill")
        return

    now_sql = "CURRENT_TIMESTAMP"

    # ---- 1. per-direction membership rows that are actually in force ----------------
    membership_rows = bind.execute(sa.text(f"""
        SELECT user_id, service_key, plan, expires_at
        FROM user_service_memberships
        WHERE is_enabled = 1
          AND (status IS NULL OR status = 'active')
          AND (expires_at IS NULL OR expires_at > {now_sql})
    """)).mappings().all()

    # ---- 2. the legacy global users.plan field --------------------------------------
    user_rows = bind.execute(sa.text(f"""
        SELECT id AS user_id, plan, plan_expire_at
        FROM users
        WHERE plan IS NOT NULL AND plan != '' AND plan != 'free'
          AND (plan_expire_at IS NULL OR plan_expire_at > {now_sql})
    """)).mappings().all()

    unmappable = []
    # user_id -> (tier, latest_expiry_or_None)
    derived: dict[int, tuple[str, object]] = {}

    def record(user_id: int, tier: str | None, expires_at, original: str):
        if tier is None:
            unmappable.append((user_id, original))
            return
        current = derived.get(user_id)
        if current is None or TIER_RANK[tier] > TIER_RANK[current[0]]:
            derived[user_id] = (tier, expires_at)
        elif TIER_RANK[tier] == TIER_RANK[current[0]] and expires_at is None:
            # No expiry means "does not lapse"; that is at least as strong as a dated one.
            derived[user_id] = (tier, None)

    for row in membership_rows:
        record(row["user_id"], _tier_from_service_plan(row["service_key"], row["plan"]),
               row["expires_at"], f"{row['service_key']}:{row['plan']}")
    for row in user_rows:
        record(row["user_id"], _tier_from_legacy_user_plan(row["plan"]),
               row["plan_expire_at"], f"users.plan:{row['plan']}")

    if unmappable:
        raise RuntimeError(
            "refusing to migrate: plan codes with no deterministic unified-tier mapping. "
            f"Affected rows (user_id, code): {sorted(set(unmappable))}. "
            "Map them explicitly in this revision, or decide them by hand, before deploying."
        )

    # ---- 3. compare against the tier each user already holds ------------------------
    existing = {
        row["user_id"]: row["tier"]
        for row in bind.execute(sa.text(f"""
            SELECT user_id, tier FROM subscriptions
            WHERE status = 'active' AND (end_at IS NULL OR end_at > {now_sql})
        """)).mappings().all()
    }

    to_insert = []
    for user_id, (tier, expires_at) in sorted(derived.items()):
        if TIER_RANK[tier] <= TIER_RANK.get((existing.get(user_id) or "free"), 0):
            continue
        to_insert.append((user_id, tier, expires_at))

    for user_id, tier, expires_at in to_insert:
        bind.execute(sa.text("""
            INSERT INTO subscriptions
                (user_id, tier, status, start_at, end_at, source, created_at, updated_at)
            VALUES
                (:user_id, :tier, 'active', CURRENT_TIMESTAMP, :end_at, :source,
                 CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"user_id": user_id, "tier": tier, "end_at": expires_at,
               "source": MIGRATION_SOURCE})

    print(f"[20260919_0011] legacy rows read: memberships={len(membership_rows)} "
          f"users.plan={len(user_rows)}; users derived={len(derived)}; "
          f"subscriptions inserted={len(to_insert)}; unmappable={len(unmappable)}")


def downgrade() -> None:
    """No downgrade is offered, matching the rest of this chain.

    A DELETE that removed only ``source = 'migration'`` rows would in fact be safe here, and
    it is deliberately NOT provided anyway. Two reasons, in order of weight: the project's
    recovery story is the pre-migration backup snapshot (S6 PART E rehearses exactly that),
    and a chain where some revisions can be reversed and others cannot is worse than one
    where none can — an operator cannot tell which is which without reading every file.
    """
    raise NotImplementedError(
        "unified membership back-fill is additive-only; recover from the pre-migration "
        "backup snapshot instead")
