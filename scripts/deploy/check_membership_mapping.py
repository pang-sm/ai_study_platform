"""Pre-migration gate for ACCEL_PRODUCT_S10 revision 20260919_0011 — READ ONLY.

WHAT IT ANSWERS, BEFORE THE MIGRATION RUNS
------------------------------------------
"Can every paid entitlement on this database be translated to a unified tier
deterministically?" If yes, the back-fill will insert the right subscriptions. If no, the
deployment must stop and a human must decide — the migration would otherwise either guess a
tier or lose an entitlement, and both are worse than not deploying.

It writes nothing. It does not create tables, does not insert, does not migrate.

WHY IT IMPORTS THE MIGRATION
----------------------------
The mapping is read from ``20260919_0011_unified_membership_backfill`` itself rather than
restated here. A pre-check with its own copy of the rules is a pre-check that can disagree
with what the migration actually does — which is precisely the failure it exists to prevent.

EXIT CODES
----------
  0  every row maps (or there is nothing to map on this database)
  1  at least one row has no deterministic mapping — DO NOT MIGRATE
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (REPO_ROOT / "migrations" / "versions"
             / "20260919_0011_unified_membership_backfill.py")


def _load_migration():
    spec = importlib.util.spec_from_file_location("s10_mig_0011_precheck", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[membership-precheck] DATABASE_URL is required", file=sys.stderr)
        return 1

    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    migration = _load_migration()

    missing = [t for t in ("users", "user_service_memberships") if t not in tables]
    if missing:
        report = {
            "state": "NOT_APPLICABLE",
            "reason": f"no legacy entitlement storage ({', '.join(missing)} absent)",
            "legacy_paid_users_seen": 0,
            "unmappable_users": 0,
            "unmappable_rows": [],
        }
        print("[membership-precheck] " + json.dumps(report, ensure_ascii=False))
        return 0

    now_sql = "CURRENT_TIMESTAMP"
    unmappable: list[dict] = []
    seen: set[int] = set()
    with engine.connect() as connection:
        memberships = connection.execute(text(f"""
            SELECT user_id, service_key, plan FROM user_service_memberships
            WHERE is_enabled = 1
              AND (status IS NULL OR status = 'active')
              AND (expires_at IS NULL OR expires_at > {now_sql})
        """)).mappings().all()
        legacy_plans = connection.execute(text(f"""
            SELECT id AS user_id, plan FROM users
            WHERE plan IS NOT NULL AND plan != '' AND plan != 'free'
              AND (plan_expire_at IS NULL OR plan_expire_at > {now_sql})
        """)).mappings().all()

    for row in memberships:
        if migration._tier_from_service_plan(row["service_key"], row["plan"]) is None:
            unmappable.append({"user_id": row["user_id"],
                               "source": f"{row['service_key']}:{row['plan']}"})
        seen.add(row["user_id"])
    for row in legacy_plans:
        if migration._tier_from_legacy_user_plan(row["plan"]) is None:
            unmappable.append({"user_id": row["user_id"],
                               "source": f"users.plan:{row['plan']}"})
        seen.add(row["user_id"])

    report = {
        "state": "UNMAPPABLE" if unmappable else "OK",
        "legacy_paid_users_seen": len(seen),
        "active_membership_rows": len(memberships),
        "legacy_user_plan_rows": len(legacy_plans),
        "unmappable_users": len({r["user_id"] for r in unmappable}),
        "unmappable_rows": sorted(unmappable, key=lambda r: (r["user_id"], r["source"])),
    }
    print("[membership-precheck] " + json.dumps(report, ensure_ascii=False))

    if unmappable:
        print("[membership-precheck] STOP: refusing to migrate. The rows above have no "
              "deterministic unified tier. Decide them by hand before deploying; the "
              "migration would otherwise have to guess or drop an entitlement.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
