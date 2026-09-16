"""
Clean User Reset (Auth V2 foundation).

Destructive, atomic, FK-safe reset of ALL user data while preserving system
content (exam question bank, programming exercises, knowledge maps, public
materials, system config, redemption code definitions, audit logs).

Run only AFTER a byte-identical backup exists. Pass the backup path so the
script refuses to run without one.

    python backend/scripts/clean_user_reset.py \
        --db backend/app.db \
        --backup backend/backups/pre_clean_user_reset_<ts>.db
"""
import argparse
import sqlite3
import sys

# FK-safe deletion order: deepest children first, users last.
# where_clause None => delete all rows (pure user table).
DELETES: list[tuple[str, str | None]] = [
    # Tier 1 — deepest children
    ("revenue_ledger_entries", None),
    ("refunds", None),
    ("payment_events", None),
    ("membership_grants", None),
    ("redemption_code_usages", None),
    ("learning_records", None),
    ("material_chunks", "material_id NOT IN (SELECT id FROM study_materials WHERE COALESCE(username,'')='system')"),
    ("material_knowledge_links", "material_id NOT IN (SELECT id FROM study_materials WHERE COALESCE(username,'')='system')"),
    ("support_messages", None),
    ("announcement_reads", None),
    ("code_project_files", None),
    ("material_chunks_fts", None),
    # Tier 2 — referenced by tier 1
    ("membership_orders", None),
    ("study_materials", "COALESCE(username,'') <> 'system'"),
    ("chat_messages", None),
    ("chat_sessions", None),
    ("support_tickets", None),
    ("code_projects", None),
    # Tier 3 — direct children of users (nothing references these)
    ("auth_sessions", None),
    ("user_service_memberships", None),
    ("user_learning_tracks", None),
    ("user_quota_overrides", None),
    ("programming_exercise_progress", None),
    # Tier 4 — username-keyed tables with no FK
    ("verification_codes", None),
    ("learning_tasks", None),
    ("course_progress", None),
    ("course_learning_preferences", None),
    ("user_learning_paths", None),
    ("user_knowledge_progress", None),
    ("user_knowledge_review_settings", None),
    ("knowledge_progress_events", None),
    ("exam_study_plan_settings", None),
    ("exam_study_plan_chapter_practice", None),
    ("exam_study_plan_tasks", None),
    ("code_sessions", None),
    ("code_ai_messages", None),
    ("code_ai_saved_chats", None),
    ("code_challenge_attempts", None),
    ("programming_exercise_submissions", None),
    ("ai_usage_logs", None),
    ("question_attempts", None),
    ("exam_practice_attempts", None),
    ("past_paper_attempts", None),
    ("exam_wrong_questions", None),
    ("past_paper_wrong_questions", None),
    ("exam_question_done_records", None),
    ("exam_favorite_questions", None),
    ("exam_favorite_questions_v2", None),
    ("ai_question_attempts", None),
    ("learning_reports", None),
    ("learning_report_shares", None),
    ("practice_import_jobs", None),
    ("ai_generated_questions", None),
    # Tier 5 — mixed knowledge map (user rows only, keep 'system')
    ("knowledge_points", "COALESCE(username,'') <> 'system'"),
    # Tier 6 — users last
    ("users", None),
]

# Column-level reset of user-specific state embedded in a system table.
REDEMPTION_RESET = (
    "UPDATE redemption_codes SET used_count=0, used_by_user_id=NULL, "
    "used_by_username=NULL, used_at=NULL, status='active' WHERE status='used'"
)

# Tables that MUST be empty after reset (acceptance anchors).
MUST_BE_EMPTY = ["users", "auth_sessions", "verification_codes"]

# System content that MUST remain (acceptance anchors).
MUST_REMAIN = {
    "exam_question_bank": 9333,
    "programming_exercises": 1923,
}


def all_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--backup", required=True)
    args = ap.parse_args()

    import os
    if not os.path.exists(args.backup):
        print(f"FATAL: backup not found: {args.backup}")
        return 1

    conn = sqlite3.connect(args.db, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    before = {t: cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in all_tables(conn)}

    try:
        conn.execute("BEGIN IMMEDIATE")

        deleted = {}
        for table, where in DELETES:
            sql = f'DELETE FROM "{table}"'
            if where:
                sql += f" WHERE {where}"
            cur.execute(sql)
            deleted[table] = cur.rowcount

        cur.execute(REDEMPTION_RESET)
        deleted["redemption_codes(column-reset)"] = cur.rowcount

        # Validation — any failure rolls back.
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        integrity = conn.execute("PRAGMA integrity_check").fetchall()

        empty_ok = all(cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] == 0 for t in MUST_BE_EMPTY)
        remain_ok = all(
            cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] >= n for t, n in MUST_REMAIN.items()
        )

        ok = not fk_violations and integrity == [("ok",)] and empty_ok and remain_ok
        if not ok:
            conn.execute("ROLLBACK")
            print("=== VALIDATION FAILED -> ROLLBACK ===")
            print("foreign_key_check:", fk_violations)
            print("integrity_check:", integrity)
            print("empty_ok:", empty_ok, "remain_ok:", remain_ok)
            return 2

        conn.execute("COMMIT")
    except Exception as e:  # noqa: BLE001
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        print("=== EXCEPTION -> ROLLBACK ===")
        print(repr(e))
        return 3

    after = {t: cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in all_tables(conn)}

    print("=== DELETE SUMMARY ===")
    for table, n in deleted.items():
        if n:
            print(f"  {table}: {n} rows deleted")

    print("\n=== BEFORE / AFTER (non-zero either side) ===")
    print(f"{'table':<34} {'before':>8} {'after':>8}")
    for t in sorted(before):
        b, a = before[t], after[t]
        if b or a:
            print(f"{t:<34} {b:>8} {a:>8}")

    print("\n=== POST-RESET ACCEPTANCE ===")
    for t in MUST_BE_EMPTY:
        print(f"  {t} = {after[t]}")
    for t, n in MUST_REMAIN.items():
        print(f"  {t} = {after[t]} (>= {n} required)")
    kp_system = cur.execute("SELECT COUNT(*) FROM knowledge_points WHERE COALESCE(username,'')='system'").fetchone()[0]
    sm_system = cur.execute("SELECT COUNT(*) FROM study_materials WHERE COALESCE(username,'')='system'").fetchone()[0]
    print(f"  knowledge_points(system) = {kp_system}")
    print(f"  study_materials(system) = {sm_system}")
    print(f"  foreign_key_check = {len(conn.execute('PRAGMA foreign_key_check').fetchall())} violations")
    print(f"  integrity_check = {conn.execute('PRAGMA integrity_check').fetchall()}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
