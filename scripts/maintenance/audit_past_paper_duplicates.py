"""Read-only audit of 11408 exam_question_bank over-seeding / duplicates.

Root cause: the 11408 question builders (build_*_past_papers_text.py and the
chapter builders) run on every deploy and use ``UPDATE is_active=False`` +
INSERT instead of ``DELETE`` + INSERT.  exam_question_bank has no unique
constraint, so every deploy accumulates one more batch of rows.

This script is STRICTLY READ-ONLY. It reports, per (subject, source_type,
year): total rows, distinct question_number, distinct normalized stem, active /
inactive counts, duplicate ratio, and the stem-hash intersection across years
(to detect year-crossing contamination).

Usage:
    python scripts/maintenance/audit_past_paper_duplicates.py [--db PATH]
"""
import argparse
import hashlib
import sqlite3
import sys


def norm_stem(stem: str) -> str:
    """Normalize a stem for hash/intersection comparison."""
    return "".join((stem or "").split())


def stem_hash(stem: str) -> str:
    return hashlib.sha1(norm_stem(stem).encode("utf-8")).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="backend/app.db", help="SQLite DB path")
    args = ap.parse_args()

    try:
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: cannot open DB read-only: {e}")
        return 1

    cur = conn.cursor()

    print("=== exam_question_bank: source_type x subject totals ===")
    for r in cur.execute(
        "SELECT source_type, subject_key, COUNT(*), SUM(is_active), "
        "SUM(CASE WHEN is_active=0 THEN 1 ELSE 0 END) "
        "FROM exam_question_bank GROUP BY source_type, subject_key "
        "ORDER BY source_type, subject_key"
    ):
        src, subj, total, active, inactive = r
        print(f"  {src:16s} {subj:22s} total={total:8d} active={active:6d} inactive={inactive:6d}")

    print("\n=== past_paper matrix: subject x year ===")
    print(f"  {'subject':22s} {'year':>4s} {'total':>7s} {'dist_qnum':>9s} {'dist_stem':>9s} {'active':>6s} {'inactive':>8s} {'dup_ratio':>9s} {'min_created':>19s} {'max_created':>19s}")
    rows = list(cur.execute(
        "SELECT subject_key, year, COUNT(*), COUNT(DISTINCT question_number), "
        "SUM(is_active), SUM(CASE WHEN is_active=0 THEN 1 ELSE 0 END), "
        "MIN(created_at), MAX(created_at) "
        "FROM exam_question_bank WHERE source_type='past_paper' "
        "GROUP BY subject_key, year ORDER BY subject_key, year"
    ))
    # distinct stems needs per-group query; do it inline below
    for subj, year, total, dqnum, active, inactive, mn, mx in rows:
        dstem = cur.execute(
            "SELECT COUNT(DISTINCT stem) FROM exam_question_bank "
            "WHERE subject_key=? AND source_type='past_paper' AND year=?",
            (subj, year),
        ).fetchone()[0]
        ratio = f"{total / max(dqnum, 1):.1f}x" if total else "-"
        print(f"  {subj:22s} {year:4d} {total:7d} {dqnum:9d} {dstem:9d} {active:6d} {inactive:8d} {ratio:>9s} {str(mn)[:19]:>19s} {str(mx)[:19]:>19s}")

    # Year-crossing check (stem intersection across years) for each subject
    print("\n=== year-crossing check (normalized stem hash intersection) ===")
    for subj in ("computer_organization", "operating_system", "computer_network"):
        years = [r[0] for r in cur.execute(
            "SELECT DISTINCT year FROM exam_question_bank "
            "WHERE subject_key=? AND source_type='past_paper' AND is_active=1 ORDER BY year",
            (subj,),
        )]
        if len(years) < 2:
            print(f"  {subj}: only {len(years)} year(s) -> skip")
            continue
        hashes = {}
        for y in years:
            hs = set()
            for (stem,) in cur.execute(
                "SELECT stem FROM exam_question_bank WHERE subject_key=? AND source_type='past_paper' AND year=? AND is_active=1",
                (subj, y),
            ):
                hs.add(stem_hash(stem))
            hashes[y] = hs
        print(f"  {subj} years={years}")
        for i in range(len(years)):
            for j in range(i + 1, len(years)):
                a, b = years[i], years[j]
                inter = len(hashes[a] & hashes[b])
                print(f"    {a} ∩ {b} = {inter} (of {len(hashes[a])}/{len(hashes[b])})")

    # FK reference audit (tables that could point at exam_question_bank.id)
    print("\n=== FK reference audit (rows pointing at exam_question_bank past_paper) ===")
    fk_specs = [
        ("past_paper_wrong_questions", "question_id"),
        ("exam_wrong_questions", "question_bank_id"),
        ("exam_question_done_records", "question_bank_id"),
        ("exam_favorite_questions_v2", "question_bank_id"),
    ]
    for table, col in fk_specs:
        try:
            n = cur.execute(
                f"SELECT COUNT(*) FROM {table} x JOIN exam_question_bank q "
                f"ON x.{col}=q.id WHERE q.source_type='past_paper'",
            ).fetchone()[0]
            n_inactive = cur.execute(
                f"SELECT COUNT(*) FROM {table} x JOIN exam_question_bank q "
                f"ON x.{col}=q.id WHERE q.source_type='past_paper' AND q.is_active=0",
            ).fetchone()[0]
            print(f"  {table}.{col} -> past_paper: {n} (inactive: {n_inactive})")
        except sqlite3.OperationalError as e:
            print(f"  {table}.{col}: ERROR {e}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
