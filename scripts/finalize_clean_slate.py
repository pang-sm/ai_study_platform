"""Fixed production clean-slate finalization (no arbitrary input).

1. Purge production user-generated files (uploads/avatars, materials, practice_imports).
2. Purge old user-data DB backups (*.db / *.sqlite in the backup dirs).
3. Audit + resolve financial records: test/sandbox rows are deleted; real rows get their
   user identifiers minimized (never fabricated as "deleted").

Only counts / schema / types are printed — never real user or financial values.
"""
import os
import sqlite3
import sys

DB_PATH = os.environ.get("PURGE_DB_PATH") or "/var/lib/ai_study_platform/app.db"
UPLOADS_DIR = os.environ.get("UPLOADS_DIR") or ""
BACKUP_DIRS = [d for d in os.environ.get("BACKUP_DIRS", "").split(":") if d]

FINANCIAL_RESULT = {}


def _purge_uploads():
    if not UPLOADS_DIR or not os.path.isdir(UPLOADS_DIR):
        return {}
    deleted = {}
    for sub in ("avatars", "materials", "practice_imports"):
        d = os.path.join(UPLOADS_DIR, sub)
        if os.path.isdir(d):
            files = [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]
            for f in files:
                os.remove(os.path.join(d, f))
            deleted[sub] = len(files)
    return deleted


def _purge_backups():
    deleted = {}
    for bd in BACKUP_DIRS:
        if not os.path.isdir(bd):
            continue
        for f in os.listdir(bd):
            p = os.path.join(bd, f)
            if os.path.isfile(p) and (f.endswith((".db", ".sqlite", ".sqlite3")) or "app.db" in f):
                os.remove(p)
                deleted.setdefault(bd, []).append(f)
    return deleted


def _audit_financial():
    conn = sqlite3.connect(DB_PATH)
    try:
        out = {}
        out["membership_orders_schema"] = [r[1] for r in conn.execute("PRAGMA table_info(membership_orders)")]
        out["redemption_code_usages_schema"] = [r[1] for r in conn.execute("PRAGMA table_info(redemption_code_usages)")]
        out["membership_orders_groups"] = [
            {"provider": r[0], "status": r[1], "count": r[2], "sum_amount": r[3],
             "with_txn_ref": r[4], "paid": r[5]}
            for r in conn.execute(
                "SELECT payment_provider, status, COUNT(*), SUM(COALESCE(amount,0)), "
                "SUM(CASE WHEN provider_transaction_id IS NOT NULL THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN paid_at IS NOT NULL THEN 1 ELSE 0 END) "
                "FROM membership_orders GROUP BY payment_provider, status")
        ]
        out["redemption_code_usages_count"] = conn.execute("SELECT COUNT(*) FROM redemption_code_usages").fetchone()[0]
        return out
    finally:
        conn.close()


def _resolve_financial():
    conn = sqlite3.connect(DB_PATH)
    try:
        total_orders = conn.execute("SELECT COUNT(*) FROM membership_orders").fetchone()[0]
        real_txn = conn.execute("SELECT COUNT(*) FROM membership_orders WHERE provider_transaction_id IS NOT NULL").fetchone()[0]
        paid = conn.execute("SELECT COUNT(*) FROM membership_orders WHERE paid_at IS NOT NULL").fetchone()[0]
        total_usages = conn.execute("SELECT COUNT(*) FROM redemption_code_usages").fetchone()[0]

        conn.execute("BEGIN")
        if total_orders == 0:
            conn.commit()
            return {"classification": "NO_FINANCIAL_DATA", "action": "NOTHING_TO_DELETE",
                    "membership_orders": 0, "redemption_code_usages": 0}
        if real_txn == 0 and paid == 0:
            # No external transaction reference and nothing settled -> test/sandbox.
            conn.execute("DELETE FROM redemption_code_usages")
            conn.execute("DELETE FROM membership_orders")
            conn.commit()
            return {"classification": "TEST_SANDBOX", "action": "ALL_ROWS_DELETED_AS_TEST_DATA",
                    "membership_orders_deleted": total_orders,
                    "redemption_code_usages_deleted": total_usages}
        else:
            # Real financial records -> minimize user identifiers (do NOT fabricate "deleted").
            cols = [r[1] for r in conn.execute("PRAGMA table_info(membership_orders)")]
            if "user_id" in cols:
                conn.execute("UPDATE membership_orders SET user_id = NULL WHERE user_id IS NOT NULL")
            ucols = [r[1] for r in conn.execute("PRAGMA table_info(redemption_code_usages)")]
            if "user_id" in ucols:
                conn.execute("UPDATE redemption_code_usages SET user_id = NULL WHERE user_id IS NOT NULL")
            conn.commit()
            return {"classification": "REAL_FINANCIAL", "action": "USER_IDENTIFIERS_MINIMIZED",
                    "membership_orders_retained": total_orders,
                    "redemption_code_usages_retained": total_usages}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    uploads = _purge_uploads()
    backups = _purge_backups()
    audit = _audit_financial()
    financial = _resolve_financial()

    print("FINALIZE_CLEAN_SLATE: PASS")
    print("  uploads_deleted:", uploads)
    print("  backups_deleted:", backups)
    print("  financial_audit:", audit)
    print("  financial_result:", financial)
    return 0


if __name__ == "__main__":
    sys.exit(main())
