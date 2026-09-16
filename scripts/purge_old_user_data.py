"""Fixed production user-data purge (transactional). No arbitrary SQL/shell/path input.

Deletes all user / person-specific / user-derived data while preserving static content
(question bank, programming catalog, knowledge graph, system config, model provenance).
Runs only via the restricted maintenance workflow.

Classification is a FIXED allow/deny list; anything unknown is reported, never deleted.
"""
import os
import sqlite3
import sys

DB_PATH = os.environ.get("PURGE_DB_PATH") or "/var/lib/ai_study_platform/app.db"

# Static / system / model-provenance tables that MUST be preserved.
PRESERVE_TABLES = {
    "exam_question_bank",
    "programming_exercises",
    "knowledge_points",
    "system_settings",
    "system_announcements",
    "app_runtime_flags",
    "redemption_codes",
    "model_versions",
    "sqlite_sequence",
    # FTS5 shadow tables for material_chunks
    "material_chunks_fts",
    "material_chunks_fts_config",
    "material_chunks_fts_content",
    "material_chunks_fts_data",
    "material_chunks_fts_docsize",
    "material_chunks_fts_idx",
}

# User data / user-derived / model-execution data to DELETE.
DELETE_TABLES = [
    # identity / auth
    "users", "auth_sessions", "verification_codes",
    # chat / support
    "chat_sessions", "chat_messages", "support_tickets", "support_messages",
    # learning records + progress
    "learning_records", "course_progress", "user_knowledge_progress",
    "user_knowledge_review_settings", "user_learning_paths", "user_learning_tracks",
    "user_service_memberships", "user_quota_overrides",
    "knowledge_progress_events", "learning_tasks", "learning_reports", "learning_report_shares",
    "course_learning_preferences",
    # exam
    "exam_favorite_questions", "exam_favorite_questions_v2", "exam_wrong_questions",
    "exam_practice_attempts", "exam_question_done_records", "past_paper_attempts",
    "past_paper_wrong_questions", "exam_study_plan_settings",
    "exam_study_plan_chapter_practice", "exam_study_plan_tasks",
    # question attempts
    "question_attempts", "ai_question_attempts", "ai_generated_questions",
    # programming
    "code_sessions", "code_ai_messages", "code_projects", "code_project_files",
    "code_challenges", "code_challenge_attempts", "code_ai_saved_chats",
    "programming_exercise_progress", "programming_exercise_submissions",
    # materials / imports
    "material_chunks", "material_knowledge_links", "practice_import_jobs",
    "practice_papers", "questions",
    # usage / audit
    "ai_usage_logs", "admin_audit_logs", "announcement_reads", "major_classification_cache",
    # data plane (model execution data; model_versions preserved separately)
    "learning_events", "learning_outcomes", "model_inference_runs", "model_predictions",
    "training_examples", "dataset_snapshots", "pipeline_runs",
]

# Legal/financial tables: only deleted if empty (test/sandbox). If non-empty, they are
# reported as a retention blocker and left untouched.
FINANCIAL_TABLES = {
    "payment_events", "membership_orders", "membership_grants", "refunds",
    "revenue_ledger_entries", "redemption_code_usages",
}


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    report = {"deleted": {}, "preserved": {}, "unknown": [], "financial_blocked": {}}
    try:
        existing = _tables(conn)
        conn.execute("BEGIN")

        # capture static row counts before deletion (for the invariant check)
        static_before = {}
        for t in PRESERVE_TABLES:
            if t in existing:
                static_before[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

        # financial review: only delete empty financial tables
        for t in sorted(FINANCIAL_TABLES):
            if t not in existing:
                continue
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if n == 0:
                conn.execute(f"DELETE FROM {t}")
                report["deleted"][t] = 0
            else:
                report["financial_blocked"][t] = n

        # delete user data
        for t in DELETE_TABLES:
            if t not in existing:
                continue
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            conn.execute(f"DELETE FROM {t}")
            report["deleted"][t] = n

        # special: study_materials keeps the system default reference only
        if "study_materials" in existing:
            n = conn.execute(
                "SELECT COUNT(*) FROM study_materials WHERE COALESCE(is_default_reference,0)=0"
            ).fetchone()[0]
            conn.execute(
                "DELETE FROM study_materials WHERE COALESCE(is_default_reference,0)=0"
            )
            report["deleted"]["study_materials(user)"] = n
            report["preserved"]["study_materials(default)"] = conn.execute(
                "SELECT COUNT(*) FROM study_materials WHERE COALESCE(is_default_reference,0)=1"
            ).fetchone()[0]

        # report UNKNOWN tables (not in preserve/delete/financial lists)
        handled = PRESERVE_TABLES | set(DELETE_TABLES) | FINANCIAL_TABLES | {"study_materials"}
        for t in sorted(existing):
            if t not in handled:
                report["unknown"].append(t)

        # invariant: users == 0
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert users == 0, f"users still present: {users}"

        # invariant: static content unchanged
        for t, before in static_before.items():
            after = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            assert after == before, f"static table {t} changed: {before} -> {after}"
            report["preserved"][t] = after

        conn.commit()
        print("PURGE_OLD_USER_DATA: PASS")
        for k, v in sorted(report.items()):
            print(f"  {k}: {v}")
        return 0
    except Exception as e:  # rollback on any invariant failure
        conn.rollback()
        print(f"PURGE_OLD_USER_DATA: FAILED ({type(e).__name__}: {e})")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
