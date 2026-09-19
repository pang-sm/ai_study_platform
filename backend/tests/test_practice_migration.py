"""STEP 7D: migration 20260915_0003 acceptance.

Runs the real Alembic upgrade against (A) a fresh temporary SQLite file and (B) a
temporary COPY of the working database. Never touches backend/app.db itself.
"""
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"
EXPECTED_HEAD = "20260919_0010"

PRACTICE_TABLES = {"practice_sessions", "practice_attempts"}
WRONG_ANSWER_TABLES = {"wrong_answer_states"}
# tables that must NEVER be created by these steps (later STEPs own them)
FORBIDDEN_TABLES = {"review_items", "review_attempts", "review_schedules",
                    "wrong_answer_attempt_history", "wrong_answer_events",
                    "plans", "tasks", "learning_outcomes"}


def _run_upgrade(db_path: Path, revision: str = "head"):
    env = {"DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}
    import os
    full_env = {**os.environ, **env}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=str(REPO_ROOT), env=full_env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


def _inspect(db_path: Path) -> dict:
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        head = None
        if "alembic_version" in tables:
            head = cur.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        counts = {}
        for t in ("exam_question_bank", "programming_exercises", "knowledge_points"):
            if t in tables:
                counts[t] = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        return {"integrity": integrity, "tables": tables, "head": head, "counts": counts}
    finally:
        con.close()


@pytest.fixture
def fresh_db():
    tmp = Path(tempfile.mkdtemp(prefix="practice-mig-fresh-"))
    yield tmp / "fresh.db"
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def legacy_db():
    tmp = Path(tempfile.mkdtemp(prefix="practice-mig-legacy-"))
    target = tmp / "copy.db"
    if not APP_DB.exists():
        pytest.skip("no working database to copy")
    shutil.copy2(APP_DB, target)
    yield target
    shutil.rmtree(tmp, ignore_errors=True)


def test_migration_on_fresh_database(fresh_db):
    _run_upgrade(fresh_db)
    info = _inspect(fresh_db)
    assert info["integrity"] == "ok"
    assert info["head"] == EXPECTED_HEAD
    assert PRACTICE_TABLES <= info["tables"]
    assert WRONG_ANSWER_TABLES <= info["tables"]
    assert not (FORBIDDEN_TABLES & info["tables"]), \
        f"must not create {FORBIDDEN_TABLES & info['tables']}"


def test_migration_on_legacy_database_copy(legacy_db):
    before = _inspect(legacy_db)
    _run_upgrade(legacy_db)
    after = _inspect(legacy_db)

    assert after["integrity"] == "ok"
    assert after["head"] == EXPECTED_HEAD
    assert PRACTICE_TABLES <= after["tables"]
    assert WRONG_ANSWER_TABLES <= after["tables"]
    assert not (FORBIDDEN_TABLES & after["tables"])

    # static assets untouched
    assert after["counts"] == before["counts"]
    assert after["counts"].get("exam_question_bank") == 9333
    assert after["counts"].get("programming_exercises") == 1923
    assert after["counts"].get("knowledge_points") == 32

    # nothing removed: every pre-existing table still present
    assert before["tables"] <= after["tables"]


def test_revision_0003_adds_exactly_the_two_practice_tables(legacy_db):
    """Isolate 0003's own contribution: upgrade to 0002, then to 0003, and diff."""
    _run_upgrade(legacy_db, "20260915_0002")
    at_0002 = _inspect(legacy_db)
    assert at_0002["head"] == "20260915_0002"
    assert not (PRACTICE_TABLES & at_0002["tables"])

    _run_upgrade(legacy_db, "20260915_0003")
    at_0003 = _inspect(legacy_db)
    added = at_0003["tables"] - at_0002["tables"]
    assert added == PRACTICE_TABLES, f"unexpected new tables: {added - PRACTICE_TABLES}"


def test_revision_0004_adds_exactly_one_table(legacy_db):
    """STEP 7E adds wrong_answer_states and nothing else — no attempt-history table,
    no event table, no review tables."""
    _run_upgrade(legacy_db, "20260915_0003")
    at_0003 = _inspect(legacy_db)
    assert not (WRONG_ANSWER_TABLES & at_0003["tables"])

    # Upgrade to THIS revision, not to head: a later STEP's revision is a different
    # contribution and must not be attributed to 0004.
    _run_upgrade(legacy_db, "20260915_0004")
    at_0004 = _inspect(legacy_db)
    added = at_0004["tables"] - at_0003["tables"]
    assert added == WRONG_ANSWER_TABLES, f"unexpected new tables: {added - WRONG_ANSWER_TABLES}"
    assert not (FORBIDDEN_TABLES & at_0004["tables"])
    # history still lives in practice_attempts — nothing else was added to hold it
    assert not {t for t in at_0004["tables"]
                if t.startswith("wrong_answer_") and t != "wrong_answer_states"}


def test_revision_0005_adds_no_table_only_record_indexes(legacy_db):
    """STEP 7F consolidates onto the existing event stream: no new table, no new column.
    It adds only the indexes the Learning Records query pattern needs."""
    _run_upgrade(legacy_db, "20260915_0004")
    at_0004 = _inspect(legacy_db)

    _run_upgrade(legacy_db, "20260915_0005")
    at_0005 = _inspect(legacy_db)

    assert at_0005["tables"] - at_0004["tables"] == set(), "0005 must not add a table"

    con = sqlite3.connect(str(legacy_db))
    try:
        indexes = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='learning_events'")}
    finally:
        con.close()
    assert {"ix_learning_events_user_occurred",
            "ix_learning_events_ns_occurred"} <= indexes

    # and no second record infrastructure was introduced anywhere
    forbidden = {t for t in at_0005["tables"]
                 if t in ("learning_records_v2", "event_outbox", "derived_features",
                          "student_state", "timeline", "activity_log")}
    assert forbidden == set(), forbidden


def test_revision_0006_adds_no_table_only_ai_request_context_columns(legacy_db):
    """STEP 7G-C2 makes AI request ownership durable: additive columns + indexes only.

    No table, no row, no constraint, and nothing protected is touched — the whole
    point of putting the course namespace on ``ai_requests`` instead of inventing a
    second request table.
    """
    _run_upgrade(legacy_db, "20260915_0005")
    at_0005 = _inspect(legacy_db)

    _run_upgrade(legacy_db, "20260915_0006")
    at_0006 = _inspect(legacy_db)

    assert at_0006["tables"] - at_0005["tables"] == set(), "0006 must not add a table"
    assert at_0005["tables"] <= at_0006["tables"], "0006 must not drop a table"

    con = sqlite3.connect(str(legacy_db))
    try:
        cols = {"ai_requests": {r[1] for r in con.execute("PRAGMA table_info(ai_requests)")},
                "usage_ledger": {r[1] for r in con.execute("PRAGMA table_info(usage_ledger)")}}
        idx = {"ai_requests": {r[1] for r in con.execute("PRAGMA index_list(ai_requests)")},
               "usage_ledger": {r[1] for r in con.execute("PRAGMA index_list(usage_ledger)")}}
    finally:
        con.close()

    assert {"service_namespace", "context_json"} <= cols["ai_requests"]
    assert "service_namespace" in cols["usage_ledger"]
    assert "ix_ai_requests_service_namespace" in idx["ai_requests"]
    assert "ix_usage_ledger_service_namespace" in idx["usage_ledger"]


def test_revision_0007_adds_only_the_exam_prep_profile_table(legacy_db):
    """STEP 7H4 gives Exam Prep its own learner profile: ONE additive table.

    The exam CATALOG stays versioned config, so no catalog / track / subject / module
    table may appear, the 14 legacy exam tables must not be created, and no question
    row is touched.
    """
    _run_upgrade(legacy_db, "20260915_0006")
    at_0006 = _inspect(legacy_db)
    assert not ({"exam_prep_profiles"} & at_0006["tables"])

    _run_upgrade(legacy_db, "20260917_0007")
    at_0007 = _inspect(legacy_db)

    assert at_0007["head"] == "20260917_0007"
    added = at_0007["tables"] - at_0006["tables"]
    assert added == {"exam_prep_profiles"}, f"unexpected new tables: {added - {'exam_prep_profiles'}}"
    assert at_0006["tables"] <= at_0007["tables"], "0007 must not drop a table"
    assert not (FORBIDDEN_TABLES & at_0007["tables"])

    catalog_tables = {t for t in at_0007["tables"] if "catalog" in t}
    assert catalog_tables == set(), f"the catalog must stay config: {catalog_tables}"

    # protected content is untouched by the migration
    assert at_0007["counts"] == at_0006["counts"]

    con = sqlite3.connect(str(legacy_db))
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(exam_prep_profiles)")}
        idx = {r[1] for r in con.execute("PRAGMA index_list(exam_prep_profiles)")}
    finally:
        con.close()
    assert {"user_id", "exam_type", "selected_track", "selected_subjects_json",
            "target_exam_year", "created_at", "updated_at"} <= cols
    assert "ix_exam_prep_profiles_user_id" in idx


EXAM_RUNTIME_TABLES_0008 = {
    "exam_question_bank", "exam_practice_attempts", "exam_wrong_questions",
    "exam_question_done_records", "exam_favorite_questions", "past_paper_attempts",
    "past_paper_wrong_questions", "exam_study_plan_settings",
    "exam_study_plan_chapter_practice", "exam_study_plan_tasks",
    "ai_generated_questions", "user_knowledge_progress", "user_knowledge_review_settings",
}


def test_revision_0008_creates_the_exam_runtime_tables_on_a_fresh_database(fresh_db):
    """STEP 7H5 gives the Exam runtime schema its own Alembic owner.

    Before 0008 these tables came only from ``ensure_*`` / ``create_all``, so a fresh
    deployment had no Exam schema at all. The dead ``exam_favorite_questions_v2`` is
    deliberately NOT promoted to a canonical requirement.
    """
    _run_upgrade(fresh_db, "20260917_0007")
    at_0007 = _inspect(fresh_db)
    assert not (EXAM_RUNTIME_TABLES_0008 & at_0007["tables"])

    _run_upgrade(fresh_db, "head")
    at_head = _inspect(fresh_db)
    assert at_head["head"] == EXPECTED_HEAD
    added = at_head["tables"] - at_0007["tables"]
    assert added == EXAM_RUNTIME_TABLES_0008, f"unexpected: {added ^ EXAM_RUNTIME_TABLES_0008}"
    assert "exam_favorite_questions_v2" not in at_head["tables"], \
        "the dead table must not become a canonical requirement"


def test_revision_0008_leaves_an_existing_exam_schema_intact(legacy_db):
    """The same revision on a legacy copy must not rebuild what is already there."""
    _run_upgrade(legacy_db, "20260917_0007")
    at_0007 = _inspect(legacy_db)
    assert EXAM_RUNTIME_TABLES_0008 <= at_0007["tables"], "pre-existing legacy schema"

    _run_upgrade(legacy_db, "head")
    at_head = _inspect(legacy_db)
    assert at_head["head"] == EXPECTED_HEAD
    assert at_0007["tables"] <= at_head["tables"], "0008 must not drop a table"
    # rows, including the question bank, are untouched
    assert at_head["counts"] == at_0007["counts"]


def test_revision_0008_is_idempotent_on_an_already_migrated_database(legacy_db):
    """Re-running head on a database that already has the tables must be a no-op."""
    _run_upgrade(legacy_db, "head")
    first = _inspect(legacy_db)
    _run_upgrade(legacy_db, "head")
    second = _inspect(legacy_db)
    assert first["tables"] == second["tables"]
    assert second["head"] == EXPECTED_HEAD
    assert second["integrity"] == "ok"
    assert second["counts"] == first["counts"]


def test_new_tables_are_empty_after_migration(fresh_db):
    _run_upgrade(fresh_db)
    con = sqlite3.connect(str(fresh_db))
    try:
        for table in sorted(PRACTICE_TABLES | WRONG_ANSWER_TABLES):
            n = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            assert n == 0, f"{table} should start empty, has {n}"
    finally:
        con.close()
