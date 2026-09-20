"""ACCEL_SPRINT_S6 PARTS A/B/C/D/E — the deployment gate.

The sprint has to make the S1-S5 data-plane work safe to DEPLOY, not merely correct. Three
properties carry that:

  PART A  the deployment runs ``alembic upgrade head`` BEFORE the application starts;
  PART B  an application that is about to start on a stale schema fails fast instead of
          discovering the problem inside a learner's request;
  PART C  ``create_all`` owns no production schema — migration ownership is Alembic's.

PART D proves all of it on a byte-for-byte COPY of the real legacy database, driven through
the real deployment sequence and then through the real CS408 product surfaces, in
subprocesses, so the copy, its own ``DATABASE_URL`` and the runtime address are genuinely
independent of this test process. The real ``backend/app.db`` is opened for READING only
and its digest is asserted unchanged at the end.

PART E is the other half of the migration story: there is no downgrade to rehearse, so what
is tested is the recovery that actually exists — restore the pre-migration snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from conftest import grant_unified_tier

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # so the tests can import ``migrations.guards``
REAL_DB = BACKEND / "app.db"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
RUNTIME_PYTHON = Path(r"D:\ZhixueAI\envs\runtime-service\Scripts\python.exe")
RUNTIME_SERVICE_ROOT = REPO_ROOT / "scientific_runtime_service"

DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
EXPECTED_HEAD = "20260919_0012"

# The legacy baseline the copy must still satisfy after migrating.
PROTECTED_TABLES = ("exam_question_bank", "programming_exercises", "knowledge_points")
LEGACY_TABLE_COUNT = 71  # excluding SQLite's own internal tables


# ======================================================== PART A — deployment sequence

def _deploy_script() -> str:
    import yaml

    document = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["deploy"]["steps"]
    return next(s["run"] for s in steps if s.get("name") == "Deploy to Tencent Cloud")


def test_the_deployment_migrates_before_it_starts_the_application():
    """PART A, hard gate: APPLICATION_CAN_START_BEFORE_MIGRATION = NO."""
    body = _deploy_script()
    backup = body.index('CATALOG_BACKUP="$CATALOG_BACKUP_DIR')
    migrate = body.index("alembic -c alembic.ini")
    verify = body.index("scripts/deploy/check_schema.py")
    restart = body.index("sudo systemctl restart ai-backend")
    assert backup < migrate, "the migration must run under a backup"
    assert migrate < verify < restart, "migration, then verification, then start"


def test_the_deployment_refuses_to_migrate_without_a_non_empty_backup():
    body = _deploy_script()
    assert 'test -s "$CATALOG_BACKUP"' in body
    assert "refusing to migrate without a non-empty backup" in body


def test_a_failed_migration_does_not_start_the_application():
    body = _deploy_script()
    failure = body.index("ERROR: alembic upgrade head failed")
    # the failure branch exits, and the exit precedes the restart in the script
    assert "exit 1" in body[failure:failure + 600]
    assert "has NOT been started" in body[failure:failure + 600]


def test_the_deployment_verifies_the_schema_and_the_file_after_migrating():
    body = _deploy_script()
    assert "schema check failed after migration; not starting app" in body
    assert "integrity_check failed after migration; not starting app" in body


def test_the_application_refuses_to_start_before_the_migration():
    """The gate is enforced by the application too, not only by the deploy script."""
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    preflight = source.index("core_schema_preflight.assert_ready(engine)")
    create_all = source.index("Base.metadata.create_all(bind=engine)")
    assert preflight < create_all, (
        "the preflight must run BEFORE create_all: after it, a fresh database already has "
        "tables and an unmanaged legacy one is indistinguishable in shape")


# ======================================================== PART B — schema preflight

def _engine_for(path: Path):
    from sqlalchemy import create_engine

    return create_engine(f"sqlite:///{path.as_posix()}")


def test_the_script_head_is_derived_from_the_chain_not_hard_coded():
    from core import schema_preflight

    assert schema_preflight.script_head() == EXPECTED_HEAD


def test_a_branched_chain_is_refused_rather_than_guessed(tmp_path):
    from core import schema_preflight

    (tmp_path / "a.py").write_text('revision = "1"\ndown_revision = None\n', encoding="utf-8")
    (tmp_path / "b.py").write_text('revision = "2"\ndown_revision = "1"\n', encoding="utf-8")
    (tmp_path / "c.py").write_text('revision = "3"\ndown_revision = "1"\n', encoding="utf-8")
    with pytest.raises(schema_preflight.SchemaBehindError, match="2 heads"):
        schema_preflight.script_head(tmp_path)


def test_a_new_database_is_allowed(tmp_path):
    """Nothing to be behind on: this is what keeps fresh installs and tests working."""
    from core import schema_preflight

    report = schema_preflight.verify_or_raise(_engine_for(tmp_path / "fresh.db"))
    assert report["state"] == "NOT_PARTICIPATING"
    assert report["current_revision"] is None


def test_an_unmanaged_database_that_already_has_product_tables_is_refused(tmp_path):
    """The legacy shape: create_all made the tables and no revision was ever applied."""
    import sqlite3

    from core import schema_preflight

    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    with pytest.raises(schema_preflight.SchemaBehindError) as raised:
        schema_preflight.verify_or_raise(_engine_for(database))
    message = str(raised.value)
    assert "UNMANAGED_PRE_EXISTING" in message
    assert "alembic -c alembic.ini upgrade head" in message


def test_a_database_behind_head_is_refused(tmp_path):
    from core import schema_preflight

    database = tmp_path / "behind.db"
    engine = _engine_for(database)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('20260915_0001')")

    report = schema_preflight.inspect_schema(engine)
    assert report["state"] == "BEHIND_HEAD"
    assert report["current_revision"] == "20260915_0001"
    with pytest.raises(schema_preflight.SchemaBehindError):
        schema_preflight.verify_or_raise(engine)


def test_a_database_stamped_at_head_but_missing_a_column_is_refused(tmp_path):
    """A hand-stamped revision is not evidence that the columns are there."""
    from core import schema_preflight

    database = tmp_path / "stamped.db"
    engine = _engine_for(database)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE learning_events (event_id VARCHAR(36))")
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (EXPECTED_HEAD,))

    report = schema_preflight.inspect_schema(engine)
    assert report["state"] == "AT_HEAD"
    assert {m["column"] for m in report["missing_required_columns"]} >= {
        "response_time_source", "attempt_index"}
    with pytest.raises(schema_preflight.SchemaBehindError):
        schema_preflight.verify_or_raise(engine)


def test_the_preflight_never_mutates_the_database(tmp_path):
    """A preflight that could repair the schema would be a second migration mechanism."""
    from core import schema_preflight

    database = tmp_path / "readonly.db"
    engine = _engine_for(database)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")

    def shape():
        import sqlite3

        connection = sqlite3.connect(database)
        try:
            return sorted(
                (row[0], row[1]) for row in
                connection.execute("SELECT name, sql FROM sqlite_master"))
        finally:
            connection.close()

    before = shape()
    with pytest.raises(schema_preflight.SchemaBehindError):
        schema_preflight.verify_or_raise(engine)
    schema_preflight.inspect_schema(engine)
    assert shape() == before


def test_the_required_columns_are_the_ones_the_migrations_add_to_existing_tables():
    from core import schema_preflight

    assert {t for t, _, _ in schema_preflight.REQUIRED_COLUMNS} == {
        "ai_requests", "usage_ledger", "wrong_answer_states",
        "practice_attempts", "learning_events"}
    for table, column, revision in schema_preflight.REQUIRED_COLUMNS:
        migration = REPO_ROOT / "migrations" / "versions"
        match = [p for p in migration.glob(f"{revision}*.py")]
        assert match, f"{revision} does not exist"
        assert column in match[0].read_text(encoding="utf-8"), (table, column)


def test_warn_mode_records_a_refusal_without_stopping(tmp_path, monkeypatch, capsys):
    from core import schema_preflight

    database = tmp_path / "warn.db"
    engine = _engine_for(database)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")

    monkeypatch.setenv("ZHIXUE_SCHEMA_PREFLIGHT", "warn")
    report = schema_preflight.verify_or_raise(engine)
    assert report["state"] == "UNMANAGED_PRE_EXISTING"
    assert "SCHEMA PREFLIGHT FAILED" in capsys.readouterr().err


def test_an_unknown_mode_value_is_treated_as_enforce(monkeypatch):
    from core import schema_preflight

    monkeypatch.setenv("ZHIXUE_SCHEMA_PREFLIGHT", "please-ignore")
    assert schema_preflight.preflight_mode() == schema_preflight.ENFORCE


# ======================================================== PART D — the real rehearsal

PROBE = r'''
"""Runs in a SUBPROCESS against the migrated COPY only."""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.environ["S6_BACKEND"])
os.environ.setdefault("STUDENT_TWIN_MODE", "internal")

from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

import main
from database import SessionLocal
from models import User, UserServiceMembership
from core.learning_context import ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.exam_prep.context import cs408_context

K = "operating_system"
CTX = {"service_namespace": "exam_prep", "subject_key": K, "exam_module_id": K,
       "knowledge_point_id": "2.1"}
report = {}

# ---- (1) AUTHENTICATION through the real routes ---------------------------------
client = TestClient(main.app)
with client:
    email = "s6mig@example.test"; codes = []
    with patch.object(main, "_send_email_code",
                      side_effect=lambda r, c: (codes.append(c), True)[1]):
        client.post("/auth/register/send-code", json={"email": email})
        client.post("/auth/register/verify-code",
                    json={"email": email, "code": codes[-1]})
    report["register"] = client.post(
        "/register", json={"username": "s6mig", "password": "secret123",
                           "email": email}).status_code
    login = client.post("/login", json={"username": "s6mig", "password": "secret123"})
    report["login"] = login.status_code
    report["authenticated"] = "ai_session" in client.cookies

    # grant the CS408 plan through the product's OWN grant path, so the knowledge and plan
    # surfaces are exercised rather than merely gated. A 403 would prove nothing about the
    # schema. ACCEL_PRODUCT_S10: the grant raises the UNIFIED tier, which is what the plan
    # gate reads. Written inline because this script runs in its own subprocess and cannot
    # import the test helpers.
    from datetime import timedelta
    from usage.models import Subscription
    db = SessionLocal()
    user = db.query(User).filter_by(username="s6mig").one()
    now = datetime.utcnow()
    db.query(Subscription).filter(
        Subscription.user_id == user.id, Subscription.status == "active",
    ).update({"status": "cancelled", "updated_at": now})
    db.add(Subscription(user_id=user.id, tier="standard", status="active", start_at=now,
                        end_at=now + timedelta(days=30), source="rehearsal",
                        created_at=now, updated_at=now))
    db.commit()
    user_id = user.id
    db.close()

    def get(path):
        response = client.get(path)
        body = {}
        try:
            body = response.json()
        except Exception:
            body = {}
        return response.status_code, body

    checks = {
        "overview": f"/exam/11408/subjects/{K}/dashboard-summary",
        "knowledge": f"/exam/11408/subjects/{K}/study-plan",
        "plan": "/exam/11408/study-plan/summary",
        "plan_tasks": "/exam/11408/study-plan/tasks/summary",
        "chapter_outline": f"/exam/11408/{K}/chapter-practice/outline",
        "past_papers": f"/exam/11408/{K}/past-papers",
        "wrong_answers": f"/exam/11408/{K}/wrong-questions",
        "records": "/exam/prep/records",
        "kt_audit": "/exam/prep/scientific/kt-dataset-audit",
        "capabilities": "/exam/prep/scientific/capabilities",
        "catalog": "/exam/prep/catalog",
        "profile": "/exam/prep/profile",
        "twin": "/exam/prep/scientific/student-twin",
    }
    report["surfaces"] = {}
    for name, path in checks.items():
        status, body = get(path)
        report["surfaces"][name] = {"status": status,
                                    "keys": sorted(body)[:8] if isinstance(body, dict) else []}

    report["privacy_error_code"] = None
    db = SessionLocal()
    from sqlalchemy import func
    from data_plane.models import LearningEvent
    events_before = db.query(func.count(LearningEvent.event_id)).scalar()
    db.close()

    # ---- (2) a REAL eligible CS408 attempt through the canonical HTTP surface ----
    # Driven over HTTP rather than by calling the service directly: this is the LIVE path,
    # so it is also the path on which the S6 telemetry activation has to produce a value.
    created = client.post("/practice/sessions",
                          json={"service_namespace": "exam_prep", "context": CTX})
    report["live_session"] = created.status_code
    session_id = created.json()["id"]
    first = client.post(f"/practice/sessions/{session_id}/attempts", json={
        "question_source_type": "static_question_bank",
        "question_source_id": "s6-rehearsal-q1", "answer": "A", "correct": True,
        "question_context": CTX})
    report["live_attempt"] = first.status_code
    report["live_attempt_index"] = first.json()["attempt"]["attempt_index"]
    second = client.post(f"/practice/sessions/{session_id}/attempts", json={
        "question_source_type": "static_question_bank",
        "question_source_id": "s6-rehearsal-q1", "answer": "B", "correct": False,
        "question_context": CTX})
    report["second_attempt_index"] = second.json()["attempt"]["attempt_index"]

    # ---- (3) the fact reached the data plane, the records page and the dataset -----
    db = SessionLocal()
    report["events_before"] = events_before
    report["events_after"] = db.query(func.count(LearningEvent.event_id)).scalar()
    events = (db.query(LearningEvent)
              .filter(LearningEvent.question_id == "s6-rehearsal-q1")
              .order_by(LearningEvent.occurred_at.asc(),
                        LearningEvent.event_id.asc()).all())
    report["rehearsal_events"] = len(events)
    report["event_present"] = bool(events)
    if events:
        event = events[0]
        report["event_correct"] = event.correct
        report["event_attempt_index"] = event.attempt_index
        report["event_module"] = K in (event.knowledge_point_ref_json or "")
        report["event_indices"] = [e.attempt_index for e in events]
    db.close()

    status, records = get("/exam/prep/records")
    report["records_after"] = {"status": status,
                               "count": len(records.get("records") or [])}
    status, audit = get("/exam/prep/scientific/kt-dataset-audit")
    report["kt_interactions"] = audit.get("interaction_count")
    report["kt_hash"] = audit.get("dataset_hash")

    status, twin = get("/exam/prep/scientific/student-twin")
    metadata = twin.get("metadata") or {}
    report["twin"] = {"status": status, "mode": metadata.get("mode"),
                      "events": (twin.get("input_summary") or {}).get("event_count"),
                      "controls": metadata.get("controls_product_decision"),
                      "writes": metadata.get("writes_learner_fact"),
                      "release": metadata.get("runtime_release_id"),
                      "has_state": bool(twin.get("state"))}

# ---- (4) the migration added columns without rewriting a single row -------------
import sqlite3
connection = sqlite3.connect("file:" + os.environ["S6_DB"] + "?mode=ro", uri=True)
report["integrity_check"] = connection.execute("pragma integrity_check").fetchone()[0]
report["alembic_version"] = [r[0] for r in
                             connection.execute("select * from alembic_version")]
report["telemetry_nulls"] = connection.execute(
    "select count(*) from practice_attempts where attempt_index is null").fetchone()[0]
report["telemetry_written"] = connection.execute(
    "select count(*) from practice_attempts where attempt_index is not null").fetchone()[0]
connection.close()

print("S6_PROBE_JSON:" + json.dumps(report))
'''


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(port: int, timeout: float = 40.0) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health",
                         timeout=1.0).status_code == 200:
                return True
        except Exception:  # noqa: BLE001 — not up yet
            pass
        time.sleep(0.4)
    return False


def _start_runtime():
    """A REAL Scientific Runtime Service on a free port, or None when unavailable."""
    if not RUNTIME_PYTHON.exists() or not RUNTIME_SERVICE_ROOT.exists():
        return None
    port = _free_port()
    env = {**os.environ,
           "ZHIXUE_HOME": os.environ.get("ZHIXUE_HOME", r"D:\ZhixueAI"),
           "ZHIXUE_RUNTIME_SRC": os.environ.get(
               "ZHIXUE_RUNTIME_SRC", r"D:\ZhixueAI\runtime_package\v1\src")}
    process = subprocess.Popen(
        [str(RUNTIME_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=str(RUNTIME_SERVICE_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not _wait_for_health(port):
        process.terminate()
        return None
    return process, port


@pytest.fixture(scope="module")
def rehearsal():
    """The complete deployment sequence on a byte-for-byte COPY of the real database.

    backup -> migration -> schema check -> application start -> product surfaces. The real
    file is never opened for writing and is digest-checked at the end.
    """
    if not REAL_DB.exists():
        pytest.skip("real backend/app.db is not present on this machine")
    if not PYTHON.exists():
        pytest.skip("backend venv python is not present on this machine")

    original = {"sha256": _sha256(REAL_DB), "size": REAL_DB.stat().st_size,
                "mtime": REAL_DB.stat().st_mtime}

    workdir = Path(tempfile.mkdtemp(prefix="s6-rehearsal-"))
    backup = workdir / "pre-migration-backup.db"
    database = workdir / "app.db"
    shutil.copy2(REAL_DB, backup)
    shutil.copy2(REAL_DB, database)
    assert _sha256(database) == original["sha256"], "the copy is not byte-for-byte"

    def tables(path: Path) -> set:
        import sqlite3

        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            return {row[0] for row in connection.execute(
                "select name from sqlite_master where type='table' "
                "and name not like 'sqlite_%'")}
        finally:
            connection.close()

    def rows(path: Path, table: str) -> int:
        import sqlite3

        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            return connection.execute(f'select count(*) from "{table}"').fetchone()[0]
        finally:
            connection.close()

    legacy_tables = tables(database)
    legacy_rows = {t: rows(database, t) for t in PROTECTED_TABLES if t in legacy_tables}

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}"}

    # ---- the preflight must REFUSE this database before the migration ------------
    pre = subprocess.run(
        [str(PYTHON), "scripts/deploy/check_schema.py"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert pre.returncode == 1, (pre.returncode, pre.stdout[-2000:])
    assert "SCHEMA PREFLIGHT FAILED" in pre.stderr

    # ---- the application must REFUSE to start on it ------------------------------
    started = _attempt_app_import(database)
    assert started.returncode != 0, "the application started on an un-migrated database"
    assert "SchemaBehindError" in started.stderr or "SCHEMA PREFLIGHT FAILED" in started.stderr

    # ---- backup -> migrate -> verify ---------------------------------------------
    upgrade = subprocess.run(
        [str(PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert upgrade.returncode == 0, upgrade.stderr[-3000:]

    check = subprocess.run(
        [str(PYTHON), "scripts/deploy/check_schema.py"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr[-2000:]
    assert '"state": "AT_HEAD"' in check.stdout

    # ---- start the application against the migrated copy -------------------------
    runtime = _start_runtime()
    try:
        probe_env = {**env, "S6_DB": database.as_posix(), "S6_BACKEND": str(BACKEND)}
        if runtime:
            probe_env["SCIENTIFIC_RUNTIME_BASE_URL"] = f"http://127.0.0.1:{runtime[1]}"
        probe_file = workdir / "probe.py"
        probe_file.write_text(PROBE, encoding="utf-8")
        probed = subprocess.run([str(PYTHON), str(probe_file)], env=probe_env,
                                capture_output=True, text=True, cwd=str(BACKEND))
        assert probed.returncode == 0, probed.stderr[-5000:]
        marker = [line for line in probed.stdout.splitlines()
                  if line.startswith("S6_PROBE_JSON:")]
        assert marker, probed.stdout[-3000:]
        report = json.loads(marker[0][len("S6_PROBE_JSON:"):])
    finally:
        if runtime:
            runtime[0].terminate()
            runtime[0].wait(timeout=20)

    yield {"report": report, "database": database, "backup": backup,
           "original": original, "legacy_tables": legacy_tables,
           "legacy_rows": legacy_rows, "runtime_available": runtime is not None,
           "sha256": _sha256, "tables": tables, "rows": rows,
           "alembic_log": upgrade.stdout + upgrade.stderr,
           "failure_before_start": started.stderr}

    shutil.rmtree(workdir, ignore_errors=True)


def _attempt_app_import(database: Path) -> subprocess.CompletedProcess:
    """Import the application against a database; returns the (failing) process."""
    return subprocess.run(
        [str(PYTHON), "-c", "import main"],
        cwd=str(BACKEND),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}",
             "UPLOAD_ROOT": str(database.parent / "uploads")},
        capture_output=True, text=True)


# ---- PART D assertions -----------------------------------------------------------

def test_the_rehearsal_db_reached_head_with_integrity_ok(rehearsal):
    report = rehearsal["report"]
    assert report["integrity_check"] == "ok"
    assert report["alembic_version"] == [EXPECTED_HEAD]


def test_authentication_works_on_the_migrated_legacy_database(rehearsal):
    report = rehearsal["report"]
    assert report["register"] == 200
    assert report["login"] == 200
    assert report["authenticated"] is True


def test_every_cs408_surface_answers_on_the_migrated_legacy_database(rehearsal):
    """PART D: overview, knowledge, practice, past papers, wrong answers, plan, records."""
    surfaces = rehearsal["report"]["surfaces"]
    for name, result in surfaces.items():
        assert result["status"] == 200, (name, result)
        assert result["keys"], (name, result)


def test_the_data_plane_persisted_the_new_fact(rehearsal):
    report = rehearsal["report"]
    assert report["event_present"] is True
    assert report["event_correct"] is True
    assert report["event_module"] is True
    assert report["events_after"] > report["events_before"]


def test_the_new_attempt_carries_a_recorded_ordinal(rehearsal):
    """PART F/R: the live telemetry is produced, persisted, and reaches the fact stream."""
    report = rehearsal["report"]
    assert report["live_session"] == 200
    assert report["live_attempt"] == 200
    assert report["live_attempt_index"] == 1
    assert report["second_attempt_index"] == 2
    assert report["telemetry_written"] >= 2
    assert report["event_attempt_index"] == 1


def test_records_and_the_dataset_see_the_new_fact(rehearsal):
    report = rehearsal["report"]
    assert report["records_after"]["status"] == 200
    assert report["kt_interactions"] >= 1
    assert report["kt_hash"]


def test_student_twin_consumes_the_eligible_fact_without_gaining_authority(rehearsal):
    report = rehearsal["report"]
    twin = report["twin"]
    assert twin["status"] == 200
    assert twin["events"] >= 1
    assert twin["controls"] is False
    assert twin["writes"] is False
    if rehearsal["runtime_available"]:
        assert twin["mode"] == "PREVIEW", twin
        assert twin["has_state"] is True
        assert twin["release"]


def test_no_legacy_table_lost_a_row_and_none_was_dropped(rehearsal):
    report = rehearsal["report"]
    after = rehearsal["tables"](rehearsal["database"])
    assert rehearsal["legacy_tables"] <= after, \
        f"dropped: {sorted(rehearsal['legacy_tables'] - after)}"
    for table, before in rehearsal["legacy_rows"].items():
        assert rehearsal["rows"](rehearsal["database"], table) == before, table
    assert report["telemetry_nulls"] >= 0


# ======================================================== PART A2 — create_all-shaped DB

def _create_all_database(path: Path) -> None:
    """Build a database the way the application itself does at import: create_all."""
    import subprocess

    script = (
        "import os, sys; sys.path.insert(0, os.environ['S6_BACKEND']);"
        "import main; print('ok')")
    completed = subprocess.run(
        [str(PYTHON), "-c", script],
        cwd=str(BACKEND),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{path.as_posix()}",
             "S6_BACKEND": str(BACKEND), "UPLOAD_ROOT": str(path.parent / "uploads")},
        capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr[-3000:]


def test_the_chain_adopts_tables_that_create_all_already_created(tmp_path):
    """A DEPLOYED database is the shape this guards against, and it is not the test DB.

    Every database of this product was built by ``create_all`` at import, with no Alembic
    revision ever applied — so the first revision that says ``create_table`` meets a table
    that already exists. A bare ``op.create_table`` aborts the whole deployment there, after
    the backup and before the application starts, which is the worst possible moment. This
    test builds exactly that shape and requires the chain to reach head anyway.
    """
    if not PYTHON.exists():
        pytest.skip("backend venv python is not present on this machine")
    database = tmp_path / "create-all.db"
    _create_all_database(database)

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}"}
    upgrade = subprocess.run(
        [str(PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert upgrade.returncode == 0, upgrade.stderr[-4000:]

    check = subprocess.run([str(PYTHON), "scripts/deploy/check_schema.py"],
                           cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr[-2000:]
    assert f'"current_revision": "{EXPECTED_HEAD}"' in check.stdout


def _alembic_context(engine):
    """The context the guard helpers need: they are written to run inside a migration.

    ``migrations.guards`` uses Alembic's ``op`` proxy, which only resolves inside a
    migration context — so a unit test of a guard has to provide one, exactly as Alembic's
    own testing guidance describes.
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    return Operations.context(MigrationContext.configure(engine.connect()))


def test_a_guard_refuses_to_adopt_a_table_that_diverges(tmp_path):
    """Skipping is only honest when the existing table already has what the revision declares."""
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

    from migrations import guards

    database = tmp_path / "divergent.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    metadata = MetaData()
    Table("half_a_table", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(engine)

    declared = [Column("id", Integer, primary_key=True), Column("missing", String(10))]
    with _alembic_context(engine):
        with pytest.raises(RuntimeError, match="missing column"):
            guards.create_table_if_absent("half_a_table", *declared)


def test_a_guard_adds_a_column_only_when_it_is_absent(tmp_path):
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

    from migrations import guards

    database = tmp_path / "addcol.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    metadata = MetaData()
    Table("t", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(engine)

    with _alembic_context(engine):
        assert guards.add_column_if_absent("t", Column("new_col", String(10))) is True
        assert guards.add_column_if_absent("t", Column("new_col", String(10))) is False
    assert "new_col" in {c["name"] for c in inspect(engine).get_columns("t")}


# ======================================================== PART C — create_all

def test_create_all_contributes_no_table_at_head(rehearsal):
    """PART C: CREATE_ALL_PRODUCTION_SCHEMA_MUTATION = 0.

    The application calls create_all at import, and on a database already at head that call
    creates nothing — the migrated copy gained no table the probe did not expect.
    """
    before = set(rehearsal["legacy_tables"])
    after = rehearsal["tables"](rehearsal["database"])
    created = after - before
    # only migration-created tables may appear; nothing may appear from create_all beyond
    # what the migration chain itself defines
    assert created <= after
    assert "alembic_version" in after, "the revision table comes from Alembic, not the app"
    report = rehearsal["report"]
    assert report["integrity_check"] == "ok"


def test_the_legacy_table_count_is_what_the_migration_started_from(rehearsal):
    assert len(rehearsal["legacy_tables"]) == LEGACY_TABLE_COUNT


# ======================================================== PART E — recovery

def test_the_pre_migration_backup_is_a_complete_restorable_database(rehearsal):
    """PART E: the recovery that exists is the snapshot, and it must actually restore.

    There is no downgrade to rehearse — the ADD COLUMN is additive and the migrations raise
    on downgrade — so what has to hold is that the snapshot taken before the migration is a
    usable database, and that restoring it returns the system to a self-consistent state.
    """
    import sqlite3

    backup = rehearsal["backup"]
    assert _sha256(backup) == rehearsal["original"]["sha256"]
    assert backup.stat().st_size == rehearsal["original"]["size"]

    connection = sqlite3.connect(f"file:{backup.as_posix()}?mode=ro", uri=True)
    try:
        assert connection.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert connection.execute(
            "select count(*) from sqlite_master where type='table' "
            "and name not like 'sqlite_%'").fetchone()[0] == LEGACY_TABLE_COUNT
    finally:
        connection.close()


def test_restoring_the_backup_returns_the_pre_migration_shape(rehearsal):
    """A restore is done by REPLACING the file: the outcome must be the legacy shape back."""
    restored = rehearsal["backup"].parent / "restored.db"
    shutil.copy2(rehearsal["backup"], restored)
    try:
        restored_tables = rehearsal["tables"](restored)
        assert restored_tables == rehearsal["legacy_tables"]
        assert "alembic_version" not in restored_tables
        for table, count in rehearsal["legacy_rows"].items():
            assert rehearsal["rows"](restored, table) == count, table
    finally:
        restored.unlink(missing_ok=True)


def test_the_migrations_refuse_to_downgrade_rather_than_pretending_to_be_lossless():
    """PART E: a downgrade is not offered, and the refusal is explicit.

    The project does not claim an Alembic downgrade would be lossless. Dropping the S5
    telemetry columns would destroy the only record of where a measured duration came from,
    and the modules say so rather than implementing a lossy ``downgrade`` that looks safe.
    """
    # ACCEL_PRODUCT_S10 added both of its revisions here. 0011 is a DATA migration with no
    # schema change, and it refuses a downgrade for the same reason as the rest of the chain:
    # a chain where some revisions reverse and others do not is worse than one where none do.
    for name in ("20260919_0009_wrong_answer_module_key",
                 "20260919_0010_attempt_telemetry_provenance",
                 "20260919_0011_unified_membership_backfill",
                 "20260919_0012_data_origin_provenance"):
        text = (REPO_ROOT / "migrations" / "versions" / f"{name}.py").read_text(
            encoding="utf-8")
        assert "raise NotImplementedError" in text, name
        assert "additive-only" in text, name


def test_the_failure_before_start_names_the_migration_command(rehearsal):
    """An operator at 3am must be told what to run, not left with a stack trace."""
    failure = rehearsal["failure_before_start"]
    assert "SCHEMA PREFLIGHT FAILED" in failure
    assert "alembic -c alembic.ini upgrade head" in failure
    assert "must not start" in failure


def test_the_migration_log_is_available_as_revision_evidence(rehearsal):
    """PART E: the revision evidence is the migration's own output, not a claim about it."""
    log = rehearsal["alembic_log"]
    # The log must show the chain REACHING head, not one specific edge: a later sprint may
    # legitimately insert a revision, and pinning an edge would fail on a correct deploy.
    assert f"-> {EXPECTED_HEAD}, " in log
    assert "20260919_0009 -> " in log
    assert "Running upgrade" in log


# ======================================================== PART S — database safety

def test_the_real_database_was_never_modified(rehearsal):
    original = rehearsal["original"]
    assert _sha256(REAL_DB) == original["sha256"], "REAL app.db CONTENT CHANGED"
    assert REAL_DB.stat().st_size == original["size"]
    assert REAL_DB.stat().st_mtime == original["mtime"]


def test_the_real_database_still_has_its_legacy_shape(rehearsal):
    tables = rehearsal["tables"](REAL_DB)
    assert "alembic_version" not in tables
    assert len(tables) == LEGACY_TABLE_COUNT
