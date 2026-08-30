"""Deduplicate 11408 past-paper questions in exam_question_bank.

Natural key: (subject_key, source_type, year, question_number).
Canonical row per key: the active row (is_active=1); tie-break by highest id.
Duplicate rows: every other row in the same key group.

The importer bug left 390 inactive batches of identical rows per year for
computer_organization (deactivate-and-insert instead of delete-and-insert).
This script removes the accumulated duplicates and migrates any FK references
to the canonical row id.

SAFETY: defaults to --dry-run. Writes happen only with explicit --execute.
Before writing it takes a consistent backup of the DB (SQLite online backup).

Usage:
    python scripts/maintenance/dedupe_past_paper_questions.py [--db PATH] [--subject SUBJECT] [--year YEAR]
                                                              [--dry-run | --execute] [--backup PATH]
"""
import argparse
import datetime
import os
import sqlite3
import sys

# Tables that may reference exam_question_bank.id by a foreign-key-like column.
FK_SPECS = [
    ("past_paper_wrong_questions", "question_id"),
    ("exam_wrong_questions", "question_bank_id"),
    ("exam_question_done_records", "question_bank_id"),
    ("exam_favorite_questions_v2", "question_bank_id"),
]


def backup_db(src_path: str, backup_path: str) -> str:
    """Create a consistent online backup; return the backup path."""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(backup_path)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return backup_path


def collect_duplicates(cur: sqlite3.Cursor, subject: str | None, year: int | None) -> dict:
    """Return {canonical_id: [duplicate_id, ...]} plus per-key stats."""
    where = ["source_type='past_paper'"]
    params = []
    if subject:
        where.append("subject_key=?")
        params.append(subject)
    if year is not None:
        where.append("year=?")
        params.append(year)
    cond = " AND ".join(where)

    # Group rows by natural key and pick canonical per key.
    rows = cur.execute(
        f"SELECT id, subject_key, year, question_number, is_active FROM exam_question_bank "
        f"WHERE {cond} ORDER BY subject_key, year, question_number, is_active DESC, id DESC",
        params,
    ).fetchall()

    groups: dict[tuple, list[int]] = {}
    active_ids: dict[tuple, int] = {}
    for rid, subj, yr, qnum, is_active in rows:
        key = (subj, yr, qnum)
        groups.setdefault(key, []).append(rid)
        if is_active and key not in active_ids:
            active_ids[key] = rid

    mapping: dict[int, int] = {}  # duplicate_id -> canonical_id
    for key, ids in groups.items():
        canonical = active_ids.get(key) or max(ids)
        for rid in ids:
            if rid != canonical:
                mapping[rid] = canonical

    return mapping


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="backend/app.db")
    ap.add_argument("--subject", default=None, help="e.g. computer_organization")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=False)
    ap.add_argument("--execute", dest="execute", action="store_true", default=False)
    ap.add_argument("--backup", default=None, help="backup file path (required-safe in execute)")
    args = ap.parse_args()

    if args.execute and args.dry_run:
        print("ERROR: --execute and --dry-run are mutually exclusive.")
        return 2
    # Default to dry-run when neither flag is present.
    if not args.execute:
        args.dry_run = True

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    where = ["source_type='past_paper'"]
    params = []
    if args.subject:
        where.append("subject_key=?")
        params.append(args.subject)
    if args.year is not None:
        where.append("year=?")
        params.append(args.year)
    cond = " AND ".join(where)

    before_total = cur.execute(f"SELECT COUNT(*) FROM exam_question_bank WHERE {cond}", params).fetchone()[0]
    before_active = cur.execute(
        f"SELECT SUM(is_active) FROM exam_question_bank WHERE {cond}", params
    ).fetchone()[0] or 0
    before_distinct = cur.execute(
        f"SELECT COUNT(DISTINCT subject_key||'/'||year||'/'||question_number) "
        f"FROM exam_question_bank WHERE {cond}", params
    ).fetchone()[0]

    mapping = collect_duplicates(cur, args.subject, args.year)
    dup_ids = sorted(mapping.keys())
    n_dup = len(dup_ids)
    n_canonical = before_distinct

    print("=== dedupe plan ===")
    print(f"  scope: subject={args.subject or 'ALL'} year={args.year or 'ALL'} source_type=past_paper")
    print(f"  before: total={before_total} active={before_active} distinct_keys={before_distinct}")
    print(f"  canonical rows to KEEP: {n_canonical}")
    print(f"  duplicate rows to DELETE: {n_dup}")
    print(f"  after projected: total={before_total - n_dup}")

    # FK references that would be affected (point at duplicate ids)
    affected_fk = {}
    for table, col in FK_SPECS:
        try:
            q = f"SELECT COUNT(*) FROM {table} WHERE {col} IN ({','.join('?' * len(dup_ids))})" if dup_ids else None
            if q:
                n = cur.execute(q, dup_ids).fetchone()[0]
            else:
                n = 0
            affected_fk[table] = n
            if n:
                print(f"  FK migrate: {table}.{col} rows to remap: {n}")
        except sqlite3.OperationalError as e:
            print(f"  FK check {table}.{col}: skipped ({e})")

    if args.dry_run or not args.execute:
        print("\nDRY-RUN: no changes written. Re-run with --execute to apply.")
        conn.close()
        return 0

    # === EXECUTE ===
    if any(affected_fk.values()):
        print("NOTE: will migrate FK references from duplicate -> canonical before delete.")

    # 1. Backup (consistent online backup)
    if not args.backup:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.backup = f"{args.db}.dedupe-backup-{ts}.db"
    backup_path = backup_db(args.db, args.backup)
    print(f"\nBackup created: {backup_path} ({os.path.getsize(backup_path)} bytes)")

    # 2. Transaction: migrate FK + delete duplicates
    try:
        cur.execute("BEGIN IMMEDIATE")
        for table, col in FK_SPECS:
            if not affected_fk.get(table):
                continue
            for dup_id in dup_ids:
                canonical = mapping[dup_id]
                # For each row pointing at dup, move to canonical; on conflict delete the duplicate reference.
                rows = cur.execute(
                    f"SELECT rowid FROM {table} WHERE {col}=?", (dup_id,)
                ).fetchall()
                for (rowid,) in rows:
                    # try update to canonical; if unique conflict, drop this row
                    try:
                        cur.execute(f"UPDATE {table} SET {col}=? WHERE rowid=?", (canonical, rowid))
                    except sqlite3.IntegrityError:
                        cur.execute(f"DELETE FROM {table} WHERE rowid=?", (rowid,))

        # Delete duplicates in batches
        BATCH = 5000
        for i in range(0, len(dup_ids), BATCH):
            chunk = dup_ids[i:i + BATCH]
            cur.execute(
                f"DELETE FROM exam_question_bank WHERE id IN ({','.join('?' * len(chunk))})",
                chunk,
            )
        cur.execute("COMMIT")
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"\nERROR during execute, ROLLED BACK: {e}")
        conn.close()
        return 1

    after_total = cur.execute(f"SELECT COUNT(*) FROM exam_question_bank WHERE {cond}", params).fetchone()[0]
    after_active = cur.execute(
        f"SELECT SUM(is_active) FROM exam_question_bank WHERE {cond}", params
    ).fetchone()[0] or 0
    print("\n=== after ===")
    print(f"  total={after_total} active={after_active} (deleted {before_total - after_total})")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
