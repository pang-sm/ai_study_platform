"""STEP 7D: migration 20260915_0003 acceptance.

Every case runs the real Alembic upgrade against a temporary SQLite file this module builds:
either a fresh database, or one the application's own bootstrap created and this module seeded.
``backend/app.db`` is never read, copied or used as a fixture — it is a gitignored runtime
database, not test input.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "20261009_0019"

PRACTICE_TABLES = {"practice_sessions", "practice_attempts"}
WRONG_ANSWER_TABLES = {"wrong_answer_states"}
# content tables the chain must carry through untouched (seeded by the fixture, not copied)
PROTECTED_TABLES = ("exam_question_bank", "programming_exercises", "knowledge_points")
# tables that must NEVER be created by these steps (later STEPs own them)
FORBIDDEN_TABLES = {"review_items", "review_attempts", "review_schedules",
                    "wrong_answer_attempt_history", "wrong_answer_events",
                    "plans", "tasks", "learning_outcomes"}

# What 0005 and 0006 declare. Neither adds a table, so a table-set diff can never prove them:
# these are the effects that must appear between the previous revision and the target one.
REVISION_0005_INDEXES = {"ix_learning_events_user_occurred", "ix_learning_events_ns_occurred"}
REVISION_0006_AI_REQUEST_COLUMNS = {"service_namespace", "context_json"}
REVISION_0006_INDEXES = {"ix_ai_requests_service_namespace", "ix_usage_ledger_service_namespace"}


def _run_upgrade(db_path: Path, revision: str = "head", *, capture: bool = False):
    env = {"DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}
    import os
    full_env = {**os.environ, **env}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=str(REPO_ROOT), env=full_env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr if capture else None


def _app_bootstrap(db_path: Path) -> None:
    """Build the schema the way the application does at import: create_all + ensure_*.

    Imports ``models``/``database``/``database_schema`` directly rather than ``main``, because
    ``main`` runs the schema preflight and would refuse a database that is behind head — which is
    exactly the database this helper is asked to equip.
    """
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
           "UPLOAD_ROOT": str(db_path.parent / "uploads")}
    script = (
        "import sys; sys.path.insert(0, '.');"
        "import models, usage.models, data_plane.models, learning.wrong_answers.models;"
        "from database import Base, engine;"
        "from database_schema import ensure_database_schema;"
        "Base.metadata.create_all(bind=engine); ensure_database_schema(engine);"
        "print('bootstrapped')")
    result = subprocess.run([sys.executable, "-c", script], cwd=str(BACKEND_DIR),
                            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


def _rows_in(db_path: Path, tables) -> dict[str, int]:
    con = sqlite3.connect(str(db_path))
    try:
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                for t in sorted(tables)}
    finally:
        con.close()


def _seed(db_path: Path, statements: str) -> None:
    """Insert test-owned sentinel rows into an existing schema (never a copy of real data)."""
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
           "UPLOAD_ROOT": str(db_path.parent / "uploads")}
    script = ("import sys; sys.path.insert(0, '.'); import models;"
              "from database import SessionLocal;"
              "db = SessionLocal();" + statements + "db.commit(); db.close(); print('seeded')")
    result = subprocess.run([sys.executable, "-c", script], cwd=str(BACKEND_DIR),
                            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
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


def _columns(db_path: Path, table: str) -> set[str]:
    """The columns of ``table`` in the database at ``db_path``."""
    con = sqlite3.connect(str(db_path))
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def _indexes(db_path: Path, table: str) -> set[str]:
    """The index names declared on ``table`` in the database at ``db_path``."""
    con = sqlite3.connect(str(db_path))
    try:
        return {r[1] for r in con.execute(f"PRAGMA index_list({table})")}
    finally:
        con.close()


@pytest.fixture
def fresh_db():
    tmp = Path(tempfile.mkdtemp(prefix="practice-mig-fresh-"))
    yield tmp / "fresh.db"
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def controlled_pre_alembic_db():
    """A database the APPLICATION built and filled, never migrated — built here, not copied.

    This replaces the old "copy of backend/app.db" fixture. app.db is gitignored, is not a
    fixture, and has since been migrated, so the pre-Alembic shape is constructed
    deterministically instead: the application's own bootstrap (create_all + ensure_*) plus
    sentinel rows this test owns. It is a controlled rehearsal database, NOT the historical
    production database — nothing here is copied from one.
    """
    tmp = Path(tempfile.mkdtemp(prefix="practice-mig-controlled-"))
    database = tmp / "controlled.db"
    _app_bootstrap(database)
    _seed(database,
          "db.add(models.KnowledgePoint(username='seed', course_id='data_structure',"
          " title='SEED-KP'));"
          "db.add(models.ExamQuestionBank(subject_key='operating_system',"
          " source_type='chapter', stem='SEED-QUESTION', standard_answer='A'));"
          "db.add(models.ProgrammingExercise(slug='seed-exercise', language='python',"
          " title='SEED', difficulty='easy', description='seed', source_repo='seed',"
          " source_path='seed', source_commit='0' * 40, license_text='MIT',"
          " attribution='seed'));")
    yield database
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


def test_migration_on_controlled_database_preserves_every_row(controlled_pre_alembic_db):
    """The deployment scenario that matters: a database that already holds business rows and
    has never been managed by Alembic upgrades without losing a row or dropping a table.

    The row counts asserted are the ones this fixture seeded — not 9333/1923/32, which described
    one machine's app.db and had no version-controlled source of truth.
    """
    before = _inspect(controlled_pre_alembic_db)
    before_rows = _rows_in(controlled_pre_alembic_db, PROTECTED_TABLES)
    assert all(count > 0 for count in before_rows.values()), \
        f"the fixture must seed every protected table: {before_rows}"
    assert "alembic_version" not in before["tables"], "the baseline must not be Alembic-managed"

    _run_upgrade(controlled_pre_alembic_db)
    after = _inspect(controlled_pre_alembic_db)

    assert after["integrity"] == "ok"
    assert after["head"] == EXPECTED_HEAD
    assert PRACTICE_TABLES <= after["tables"]
    assert WRONG_ANSWER_TABLES <= after["tables"]
    # Relative, because the application's own bootstrap already created some of these tables:
    # what this asserts is that the UPGRADE invented none of a later STEP's tables. The absolute
    # form (a fresh database has none of them) is asserted by test_migration_on_fresh_database.
    assert not ((after["tables"] - before["tables"]) & FORBIDDEN_TABLES), \
        "the upgrade must not create a later STEP's table"

    # nothing removed, and every protected row survived the upgrade
    assert before["tables"] <= after["tables"]
    assert _rows_in(controlled_pre_alembic_db, PROTECTED_TABLES) == before_rows


def test_revision_0003_adds_exactly_the_two_practice_tables(fresh_db):
    """Isolate 0003's own contribution: upgrade to 0002, then to 0003, and diff.

    Starting from a FRESH database is what makes the diff mean "0003's contribution": the DB
    holds only what the chain itself creates, so nothing outside 0003 can appear in it. The
    legacy path — a pre-Alembic database that already carries these tables — is covered on its
    own by ``test_migration_on_legacy_database_copy``.
    """
    _run_upgrade(fresh_db, "20260915_0002")
    at_0002 = _inspect(fresh_db)
    assert at_0002["head"] == "20260915_0002"
    assert not (PRACTICE_TABLES & at_0002["tables"]), \
        "0003's tables must not exist before 0003 runs"

    _run_upgrade(fresh_db, "20260915_0003")
    at_0003 = _inspect(fresh_db)
    assert at_0003["head"] == "20260915_0003"
    added = at_0003["tables"] - at_0002["tables"]
    assert added == PRACTICE_TABLES, f"unexpected new tables: {added - PRACTICE_TABLES}"


def test_revision_0004_adds_exactly_one_table(fresh_db):
    """STEP 7E adds wrong_answer_states and nothing else — no attempt-history table,
    no event table, no review tables.

    Fresh-DB basis for the same reason as the 0003 case above: the diff must be 0004's own
    contribution and nothing else.
    """
    _run_upgrade(fresh_db, "20260915_0003")
    at_0003 = _inspect(fresh_db)
    assert at_0003["head"] == "20260915_0003"
    assert not (WRONG_ANSWER_TABLES & at_0003["tables"]), \
        "0004's table must not exist before 0004 runs"

    # Upgrade to THIS revision, not to head: a later STEP's revision is a different
    # contribution and must not be attributed to 0004.
    _run_upgrade(fresh_db, "20260915_0004")
    at_0004 = _inspect(fresh_db)
    assert at_0004["head"] == "20260915_0004"
    added = at_0004["tables"] - at_0003["tables"]
    assert added == WRONG_ANSWER_TABLES, f"unexpected new tables: {added - WRONG_ANSWER_TABLES}"
    assert not (FORBIDDEN_TABLES & at_0004["tables"])
    # history still lives in practice_attempts — nothing else was added to hold it
    assert not {t for t in at_0004["tables"]
                if t.startswith("wrong_answer_") and t != "wrong_answer_states"}


def test_revision_0005_adds_no_table_only_record_indexes(fresh_db):
    """STEP 7F consolidates onto the existing event stream: no new table, no new column.

    A table-set diff alone cannot prove this revision — its whole contribution is two indexes
    on a table 0001 already created. So the test proves both halves: the indexes are ABSENT
    before 0005 runs and PRESENT after, and the revision actually advanced.
    """
    _run_upgrade(fresh_db, "20260915_0004")
    at_0004 = _inspect(fresh_db)
    assert at_0004["head"] == "20260915_0004"
    indexes_before = _indexes(fresh_db, "learning_events")
    assert not (REVISION_0005_INDEXES & indexes_before), \
        f"0005's indexes must not exist before 0005 runs: {REVISION_0005_INDEXES & indexes_before}"

    _run_upgrade(fresh_db, "20260915_0005")
    at_0005 = _inspect(fresh_db)
    assert at_0005["head"] == "20260915_0005"

    assert at_0005["tables"] - at_0004["tables"] == set(), "0005 must not add a table"
    assert at_0004["tables"] <= at_0005["tables"], "0005 must not drop a table"

    indexes_after = _indexes(fresh_db, "learning_events")
    assert REVISION_0005_INDEXES <= indexes_after, \
        f"0005 did not create: {REVISION_0005_INDEXES - indexes_after}"

    # and no second record infrastructure was introduced anywhere
    forbidden = {t for t in at_0005["tables"]
                 if t in ("learning_records_v2", "event_outbox", "derived_features",
                          "student_state", "timeline", "activity_log")}
    assert forbidden == set(), forbidden


def test_revision_0006_adds_no_table_only_ai_request_context_columns(fresh_db):
    """STEP 7G-C2 makes AI request ownership durable: additive columns + indexes only.

    No table, no row, no constraint, and nothing protected is touched — the whole point of
    putting the course namespace on ``ai_requests`` instead of inventing a second request
    table. Same proof shape as 0005: the columns/indexes are absent before and present after.
    """
    _run_upgrade(fresh_db, "20260915_0005")
    at_0005 = _inspect(fresh_db)
    assert at_0005["head"] == "20260915_0005"
    assert not (REVISION_0006_AI_REQUEST_COLUMNS & _columns(fresh_db, "ai_requests")), \
        "0006's columns must not exist before 0006 runs"
    assert "service_namespace" not in _columns(fresh_db, "usage_ledger"), \
        "0006's ledger column must not exist before 0006 runs"

    _run_upgrade(fresh_db, "20260915_0006")
    at_0006 = _inspect(fresh_db)
    assert at_0006["head"] == "20260915_0006"

    assert at_0006["tables"] - at_0005["tables"] == set(), "0006 must not add a table"
    assert at_0005["tables"] <= at_0006["tables"], "0006 must not drop a table"

    assert REVISION_0006_AI_REQUEST_COLUMNS <= _columns(fresh_db, "ai_requests")
    assert "service_namespace" in _columns(fresh_db, "usage_ledger")
    assert {"ix_ai_requests_service_namespace"} <= _indexes(fresh_db, "ai_requests")
    assert {"ix_usage_ledger_service_namespace"} <= _indexes(fresh_db, "usage_ledger")
    assert REVISION_0006_INDEXES <= (_indexes(fresh_db, "ai_requests")
                                     | _indexes(fresh_db, "usage_ledger"))


def test_revision_0007_adds_only_the_exam_prep_profile_table(fresh_db):
    """STEP 7H4 gives Exam Prep its own learner profile: ONE additive table.

    The exam CATALOG stays versioned config, so no catalog / track / subject / module
    table may appear, and the legacy exam runtime tables belong to 0008, not here. A fresh
    database makes all of that checkable directly: the only ``exam_*`` table the chain has
    produced by 0007 is the profile itself.
    """
    _run_upgrade(fresh_db, "20260915_0006")
    at_0006 = _inspect(fresh_db)
    assert at_0006["head"] == "20260915_0006"
    assert not ({"exam_prep_profiles"} & at_0006["tables"]), \
        "0007's table must not exist before 0007 runs"

    _run_upgrade(fresh_db, "20260917_0007")
    at_0007 = _inspect(fresh_db)

    assert at_0007["head"] == "20260917_0007"
    added = at_0007["tables"] - at_0006["tables"]
    assert added == {"exam_prep_profiles"}, f"unexpected new tables: {added - {'exam_prep_profiles'}}"
    assert at_0006["tables"] <= at_0007["tables"], "0007 must not drop a table"
    assert not (FORBIDDEN_TABLES & at_0007["tables"])
    # the legacy exam runtime tables are 0008's contribution, not this revision's
    assert {t for t in at_0007["tables"] if t.startswith("exam_")} == {"exam_prep_profiles"}

    catalog_tables = {t for t in at_0007["tables"] if "catalog" in t}
    assert catalog_tables == set(), f"the catalog must stay config: {catalog_tables}"

    # protected content is untouched by the migration
    assert at_0007["counts"] == at_0006["counts"]

    con = sqlite3.connect(str(fresh_db))
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

    # Upgrade to THIS revision, not to head: a later revision's table is a different
    # contribution and must not be attributed to 0008 (same rule the 0003/0004 cases state).
    # `test_migration_on_fresh_database` already covers the fresh DB all the way to head.
    _run_upgrade(fresh_db, "20260917_0008")
    at_head = _inspect(fresh_db)
    assert at_head["head"] == "20260917_0008"
    added = at_head["tables"] - at_0007["tables"]
    assert added == EXAM_RUNTIME_TABLES_0008, f"unexpected: {added ^ EXAM_RUNTIME_TABLES_0008}"
    assert "exam_favorite_questions_v2" not in at_head["tables"], \
        "the dead table must not become a canonical requirement"


def test_revision_0008_leaves_an_existing_exam_schema_intact(fresh_db):
    """A COMPATIBILITY fixture, not a historical one.

    The exam runtime schema also exists on databases the application built itself
    (``create_all`` / ``ensure_*``), which is the case 0008's guards exist to adopt. This builds
    that case deterministically: 0007, then the application's own bootstrap, then a sentinel row —
    and requires 0008 to adopt the schema without rebuilding it or touching the row.
    """
    _run_upgrade(fresh_db, "20260915_0006")
    _run_upgrade(fresh_db, "20260917_0007")
    at_0007 = _inspect(fresh_db)
    assert at_0007["head"] == "20260917_0007"
    assert not (EXAM_RUNTIME_TABLES_0008 & at_0007["tables"])

    # the schema the application builds outside Alembic, plus a row 0008 must not rewrite
    _app_bootstrap(fresh_db)
    _seed(fresh_db,
          "db.add(models.ExamQuestionBank(subject_key='operating_system',"
          " source_type='chapter', stem='SENTINEL-0008', standard_answer='A'));")
    before_tables = _inspect(fresh_db)["tables"]
    before_exam_rows = _rows_in(fresh_db, EXAM_RUNTIME_TABLES_0008)
    assert before_exam_rows["exam_question_bank"] == 1

    _run_upgrade(fresh_db, "20260917_0008")
    at_0008 = _inspect(fresh_db)
    assert at_0008["head"] == "20260917_0008"
    assert before_tables <= at_0008["tables"], "0008 must not drop a table"
    assert _rows_in(fresh_db, EXAM_RUNTIME_TABLES_0008) == before_exam_rows, \
        "0008 must adopt the existing exam schema, not rebuild it"


def test_revision_0008_is_idempotent_on_an_already_migrated_database(fresh_db):
    """Re-running the deployment's ``upgrade head`` must be a schema/data no-op.

    Run on a FRESH database migrated to head in this test: running it on a database that was
    already at head before the test started proves nothing about the second run.
    """
    _run_upgrade(fresh_db, "head")
    first_tables = _inspect(fresh_db)["tables"]
    first_rows = _rows_in(fresh_db, first_tables)
    assert first_rows  # the migrated database has tables to compare

    second_log = _run_upgrade(fresh_db, "head", capture=True)
    second = _inspect(fresh_db)

    assert second["head"] == EXPECTED_HEAD
    assert second["integrity"] == "ok"
    assert second["tables"] == first_tables
    assert _rows_in(fresh_db, first_tables) == first_rows
    assert "Running upgrade" not in second_log, \
        "a second `upgrade head` must apply no revision, not merely end up in the same state"


def test_new_tables_are_empty_after_migration(fresh_db):
    _run_upgrade(fresh_db)
    con = sqlite3.connect(str(fresh_db))
    try:
        for table in sorted(PRACTICE_TABLES | WRONG_ANSWER_TABLES):
            n = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            assert n == 0, f"{table} should start empty, has {n}"
    finally:
        con.close()
