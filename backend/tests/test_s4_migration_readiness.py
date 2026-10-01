"""ACCEL_SPRINT_S4 — PRODUCTION DATA-PLANE MIGRATION READINESS (PART J).

The rehearsal database is built HERE, in this test's own temp directory: the application's own
bootstrap (``create_all`` + ``ensure_database_schema``) with no ``alembic_version`` — the state
every database of this product was in before Alembic — plus sentinel rows this module seeds.
Nothing is read from ``backend/app.db``, which is a gitignored runtime database rather than a
fixture, and no historical table-count is reconstructed. The rehearsal is therefore reproducible
on a fresh clone and in CI.

What is proven, in order:

  1. the rehearsal database migrates to HEAD and passes ``PRAGMA integrity_check``;
  2. every pre-existing table keeps every row, and nothing is dropped;
  3. the application starts at HEAD with ``Base.metadata.create_all`` DISABLED — the
     schema comes from Alembic, so the app does not depend on ``create_all``;
  4. the historical backfill runs honestly and is IDEMPOTENT on a second run;
  5. ``GET /exam/prep/records`` works against the migrated schema;
  6. ``GET /exam/prep/scientific/student-twin`` reaches a REAL runtime and returns a real
     state for a real event in the migrated database.

Everything runs in subprocesses so the migrated database, its own ``DATABASE_URL`` and the
runtime address are genuinely independent of this test process.

The only remaining external dependency is the scientific runtime environment, which is
conditional by design (a test skips only when the runtime itself is absent).
"""
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

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
# The interpreter that runs pytest, so subprocesses are portable instead of hard-coding a venv.
PYTHON = Path(sys.executable)
RUNTIME_PYTHON = Path(r"D:\ZhixueAI\envs\runtime-service\Scripts\python.exe")
RUNTIME_SERVICE_ROOT = REPO_ROOT / "scientific_runtime_service"

# Tables the rehearsal seeds and requires to survive the upgrade.
PROTECTED_TABLES = ("exam_question_bank", "programming_exercises", "knowledge_points")

# --------------------------------------------------------------------------- probe

PROBE = r'''
"""Run inside a subprocess against the MIGRATED COPY only."""
import json, os, sqlite3, sys

DB = os.environ["S4_DB"]
BACKEND = os.environ["S4_BACKEND"]
sys.path.insert(0, BACKEND)

def connect():
    return sqlite3.connect("file:" + DB + "?mode=ro", uri=True)

def table_set():
    c = connect()
    s = {r[0] for r in c.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%'")}
    c.close()
    return s

def rows(table):
    c = connect()
    n = c.execute('select count(*) from "%s"' % table).fetchone()[0]
    c.close()
    return n

report = {}
report["tables_at_head"] = sorted(table_set())
report["integrity_check"] = None
c = connect(); report["integrity_check"] = c.execute("pragma integrity_check").fetchone()[0]
report["foreign_key_check"] = [list(r) for r in c.execute("pragma foreign_key_check")]
report["alembic_version"] = [r[0] for r in c.execute("select * from alembic_version")]
c.close()
report["pre_existing_rows"] = {t: rows(t) for t in json.loads(os.environ["S4_PROTECTED"])}

# ---- create_all must be a pure no-op at HEAD --------------------------------------
created = {}
import database
_real_create_all = database.Base.metadata.create_all
def _spy(*a, **kw):
    created["invoked"] = True
    created["tables_before"] = len(table_set())
    return None
database.Base.metadata.create_all = _spy

before_import = {t for t in table_set()}
import main  # noqa: F401  — runs Base.metadata.create_all(...) -> the no-op above
after_import = {t for t in table_set()}

report["create_all_invoked"] = bool(created.get("invoked"))
report["tables_created_by_import"] = sorted(after_import - before_import)

# ---- historical backfill: real, honest, idempotent --------------------------------
from database import SessionLocal
from learning.practice import backfill as practice_backfill
from data_plane.models import LearningEvent
from sqlalchemy import func

db = SessionLocal()
def run_backfill():
    r = practice_backfill.run_backfill(db)
    db.commit()
    return r
b1 = run_backfill()
n1 = db.query(func.count(LearningEvent.event_id)).scalar()
b2 = run_backfill()
n2 = db.query(func.count(LearningEvent.event_id)).scalar()
report["backfill_run1_totals"] = b1["totals"]
report["backfill_run2_totals"] = b2["totals"]
report["backfill_run1_events"] = n1
report["backfill_run2_events"] = n2
report["backfill_classification"] = [
    {"source": c["source"], "classification": c["classification"]}
    for c in b1["classification"]]
db.close()

# ---- application flows against the migrated schema --------------------------------
from unittest.mock import patch
from fastapi.testclient import TestClient

client = TestClient(main.app)
with client:
    email = "s4mig@example.test"; codes = []
    with patch.object(main, "_send_email_code",
                      side_effect=lambda r, c: (codes.append(c), True)[1]):
        client.post("/auth/register/send-code", json={"email": email})
        client.post("/auth/register/verify-code",
                    json={"email": email, "code": codes[-1]})
    client.post("/register", json={"username": "s4mig", "password": "secret123",
                                   "email": email})
    client.post("/login", json={"username": "s4mig", "password": "secret123"})

    r = client.get("/exam/prep/records")
    report["records_status"] = r.status_code
    report["records_body_keys"] = sorted(r.json().keys())
    report["records_count"] = len(r.json().get("records") or [])

    r = client.get("/exam/prep/scientific/student-twin")
    body = r.json()
    report["student_twin_status"] = r.status_code
    report["student_twin_mode"] = body["metadata"]["mode"]
    report["student_twin_events"] = body["input_summary"]["event_count"]
    report["student_twin_state"] = body["state"]
    report["student_twin_runtime_release"] = body["metadata"].get("runtime_release_id")
    report["student_twin_controls"] = body["metadata"]["controls_product_decision"]
    report["student_twin_writes"] = body["metadata"]["writes_learner_fact"]

    # a REAL eligible CS408 practice event, written through the real product path
    from datetime import datetime
    from models import User
    from core.learning_context import ServiceNamespace
    from learning.practice import service as practice_service
    from learning.practice.refs import QuestionRef, QuestionSourceType
    from learning.spaces.exam_prep.context import cs408_context

    db = SessionLocal()
    user = db.query(User).filter_by(username="s4mig").one()
    ctx = cs408_context(user, module_key="operating_system", knowledge_point_id=None)
    s, _ = practice_service.ensure_legacy_session(
        db, user, ServiceNamespace.EXAM_PREP, source_type="exam_practice_attempt",
        source_session_key=4242, started_at=datetime(2026, 9, 19, 6, 30),
        context=ctx)
    practice_service.record_attempt(
        db, user, s, QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                                 source_id="s4-mig-q1",
                                 service_namespace=ServiceNamespace.EXAM_PREP,
                                 context={"subject_key": "operating_system",
                                          "exam_module_id": "operating_system"}),
        answer="A", correct=True, submitted_at=datetime(2026, 9, 19, 6, 30), context=ctx,
        result={"judge": None, "standard_answer": "B"},
        source=practice_service.SourceIdentity("exam_practice_attempt", "s4-mig-1", "s4-mig-q1:0"))
    db.close()

    r = client.get("/exam/prep/scientific/student-twin")
    body = r.json()
    report["student_twin_with_event_status"] = r.status_code
    report["student_twin_with_event_mode"] = body["metadata"]["mode"]
    report["student_twin_with_event_count"] = body["input_summary"]["event_count"]
    report["student_twin_with_event_state"] = body["state"]
    report["student_twin_with_event_release"] = body["metadata"].get("runtime_release_id")

    r2 = client.get("/exam/prep/records")
    report["records_after_event"] = len(r2.json().get("records") or [])

print("S4_PROBE_JSON:" + json.dumps(report))
'''

# --------------------------------------------------------------------------- helpers


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(port: int, timeout: float = 40.0) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0).status_code == 200:
                return True
        except Exception:  # noqa: BLE001 — not up yet
            pass
        time.sleep(0.4)
    return False


def _app_bootstrap(database: Path) -> None:
    """Build the schema the way the application builds it at import: create_all + ensure_*.

    Imports ``models``/``database``/``database_schema`` rather than ``main``, because ``main``
    runs the schema preflight and would refuse this not-yet-migrated database.
    """
    script = (
        "import os, sys; sys.path.insert(0, os.environ['S4_BACKEND']);"
        "import models, usage.models, data_plane.models, learning.wrong_answers.models;"
        "from database import Base, engine, init_user_profile_schema;"
        "from database_schema import ensure_database_schema;"
        # the SAME bootstrap order main.py uses at import, minus the schema preflight
        "Base.metadata.create_all(bind=engine);"
        "init_user_profile_schema();"
        "ensure_database_schema(engine);"
        "print('bootstrapped')")
    completed = subprocess.run(
        [str(PYTHON), "-c", script], cwd=str(BACKEND),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}",
             "S4_BACKEND": str(BACKEND), "UPLOAD_ROOT": str(database.parent / "uploads")},
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert completed.returncode == 0, completed.stderr[-3000:]


def _seed_rehearsal(database: Path) -> None:
    """Sentinel rows this rehearsal owns — deterministic, small, never a copy of real data."""
    script = (
        "import os, sys; sys.path.insert(0, os.environ['S4_BACKEND']);"
        "import models; from database import SessionLocal;"
        "db = SessionLocal();"
        "db.add(models.KnowledgePoint(username='s4seed', course_id='data_structure',"
        " title='S4-SENTINEL-KP'));"
        "db.add(models.ExamQuestionBank(subject_key='operating_system', source_type='chapter',"
        " stem='S4-SENTINEL-QUESTION', standard_answer='A'));"
        "db.add(models.ProgrammingExercise(slug='s4-sentinel', language='python',"
        " title='S4-SENTINEL', difficulty='easy', description='sentinel', source_repo='seed',"
        " source_path='seed', source_commit='0' * 40, license_text='MIT',"
        " attribution='seed'));"
        "db.commit(); db.close(); print('seeded')")
    completed = subprocess.run(
        [str(PYTHON), "-c", script], cwd=str(BACKEND),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}",
             "S4_BACKEND": str(BACKEND), "UPLOAD_ROOT": str(database.parent / "uploads")},
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert completed.returncode == 0, completed.stderr[-3000:]


@pytest.fixture(scope="module")
def migrated():
    """The rehearsal database, migrated to HEAD, then probed.

    Built here: the application's own bootstrap with no ``alembic_version``, plus sentinel rows
    this module owns. Every write lands in this fixture's temp directory — no runtime database
    and no checkout path is read or written.
    """
    workdir = Path(tempfile.mkdtemp(prefix="s4-migration-"))
    copy = workdir / "app.db"

    _app_bootstrap(copy)
    _seed_rehearsal(copy)

    original = {
        "sha256": _sha256(copy),
        "size": copy.stat().st_size,
        "mtime": copy.stat().st_mtime,
    }

    legacy_tables = _tables(copy)
    legacy_rows = {t: _rows(copy, t) for t in PROTECTED_TABLES if t in legacy_tables}
    assert all(count > 0 for count in legacy_rows.values()), \
        f"the rehearsal must seed every protected table: {legacy_rows}"

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{copy.as_posix()}"}
    upgrade = subprocess.run(
        [str(PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert upgrade.returncode == 0, upgrade.stderr[-3000:]

    runtime = _start_runtime()
    try:
        probe_env = {
            **env,
            "S4_DB": copy.as_posix(),
            "S4_BACKEND": str(BACKEND),
            "S4_PROTECTED": json.dumps(sorted(legacy_rows)),
            "STUDENT_TWIN_MODE": "internal",
        }
        if runtime:
            probe_env["SCIENTIFIC_RUNTIME_BASE_URL"] = f"http://127.0.0.1:{runtime[1]}"
        probe_file = workdir / "probe.py"
        probe_file.write_text(PROBE, encoding="utf-8")
        probed = subprocess.run([str(PYTHON), str(probe_file)], env=probe_env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(BACKEND))
        assert probed.returncode == 0, probed.stderr[-4000:]
        marker = [line for line in probed.stdout.splitlines()
                  if line.startswith("S4_PROBE_JSON:")]
        assert marker, probed.stdout[-3000:]
        report = json.loads(marker[0][len("S4_PROBE_JSON:"):])
    finally:
        if runtime:
            runtime[0].terminate()
            runtime[0].wait(timeout=20)

    yield {
        "report": report,
        "copy": copy,
        "original": original,
        "legacy_tables": legacy_tables,
        "legacy_rows": legacy_rows,
        "runtime_available": runtime is not None,
        "alembic_log": upgrade.stdout + upgrade.stderr,
    }
    shutil.rmtree(workdir, ignore_errors=True)


def _start_runtime():
    """A REAL Scientific Runtime Service on a free port, or None when unavailable."""
    if not RUNTIME_PYTHON.exists() or not RUNTIME_SERVICE_ROOT.exists():
        return None
    port = _free_port()
    env = {**os.environ,
           "ZHIXUE_HOME": os.environ.get("ZHIXUE_HOME", r"D:\ZhixueAI"),
           "ZHIXUE_RUNTIME_SRC": os.environ.get(
               "ZHIXUE_RUNTIME_SRC",
               r"D:\ZhixueAI\runtime_package\v1\src")}
    proc = subprocess.Popen(
        [str(RUNTIME_PYTHON), "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(RUNTIME_SERVICE_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not _wait_for_health(port):
        proc.terminate()
        return None
    return proc, port


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tables(path: Path) -> set:
    import sqlite3

    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {r[0] for r in con.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%'")}
    finally:
        con.close()


def _rows(path: Path, table: str) -> int:
    import sqlite3

    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(f'select count(*) from "{table}"').fetchone()[0]
    finally:
        con.close()


def _run_alembic(db_path: Path, revision: str) -> None:
    """Run the real Alembic upgrade against a temporary database."""
    result = subprocess.run(
        [str(PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=str(REPO_ROOT),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


def _alembic_revision(db_path: Path) -> str:
    import sqlite3

    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("select version_num from alembic_version").fetchone()[0]
    finally:
        con.close()


@pytest.fixture
def fresh_db():
    """An empty temporary SQLite file — Alembic creates it on first upgrade."""
    workdir = Path(tempfile.mkdtemp(prefix="s4-fresh-"))
    yield workdir / "fresh.db"
    shutil.rmtree(workdir, ignore_errors=True)


# ================================================================ PART J — migration

def test_the_rehearsal_database_reaches_head_with_integrity_ok(migrated):
    report = migrated["report"]
    assert report["integrity_check"] == "ok"
    assert report["foreign_key_check"] == []
    assert report["alembic_version"] == ["20261001_0018"], report["alembic_version"]


def test_no_table_was_dropped_and_every_legacy_row_survived(migrated):
    report = migrated["report"]
    after = set(report["tables_at_head"])
    assert migrated["legacy_tables"] <= after, \
        f"dropped: {sorted(migrated['legacy_tables'] - after)}"

    for table, before in migrated["legacy_rows"].items():
        assert report["pre_existing_rows"][table] == before, \
            f"{table}: {before} -> {report['pre_existing_rows'][table]}"


def test_protected_static_assets_are_intact(migrated):
    """The seeded content tables survive the upgrade with their rows.

    The fixture seeds these tables, so a missing table is a failure here, not a reason to skip:
    skipping on absence is what let this assertion go vacuous before.
    """
    rows = migrated["legacy_rows"]
    assert set(rows) == set(PROTECTED_TABLES), \
        f"the fixture must seed every protected table: {sorted(rows)}"
    for table, count in rows.items():
        assert count > 0, table


def test_data_plane_tables_are_created_by_the_migration(fresh_db):
    """Revision-isolated: 0001's OWN contribution, on a database this test builds.

    A fresh database has no data-plane tables; upgrading to the revision that introduces them
    must create them and nothing else's. This no longer depends on the shape of any existing
    database (see the sibling case in test_practice_migration.py for 0003-0008).
    """
    before = _tables(fresh_db) if fresh_db.exists() else set()
    assert before == set(), "the fresh database must start empty"

    _run_alembic(fresh_db, "20260915_0001")
    at_0001 = _tables(fresh_db)
    for table in ("learning_events", "model_predictions", "model_inference_runs",
                  "alembic_version"):
        assert table in at_0001, table

    _run_alembic(fresh_db, "head")
    at_head = _tables(fresh_db)
    for table in ("practice_sessions", "practice_attempts", "wrong_answer_states",
                  "exam_prep_profiles"):
        assert table in at_head, table
    assert _alembic_revision(fresh_db) == "20261001_0018"


def test_application_starts_without_create_all(migrated):
    """PART J: at HEAD, create_all contributes nothing — the schema IS the migration."""
    report = migrated["report"]
    assert report["create_all_invoked"] is True, "create_all was never reached"
    assert report["tables_created_by_import"] == [], \
        f"the app still relied on create_all for {report['tables_created_by_import']}"


# ================================================================ PART J1 — backfill

def test_backfill_reconstructs_only_what_is_reconstructable(migrated):
    report = migrated["report"]
    assert report["backfill_run1_events"] == report["backfill_run1_totals"]["mirrored"]
    # nothing is fabricated: sources with no legacy rows contribute nothing
    assert report["backfill_run1_totals"]["failed"] == 0


def test_backfill_is_idempotent(migrated):
    report = migrated["report"]
    assert report["backfill_run2_events"] == report["backfill_run1_events"]
    assert report["backfill_run2_totals"]["mirrored"] == 0
    assert report["backfill_run2_totals"]["deduped"] >= 0


def test_backfill_reports_every_source_classification(migrated):
    """A source that cannot be mirrored must say so rather than be skipped silently."""
    report = migrated["report"]
    classes = {c["source"]: c["classification"]
               for c in report["backfill_classification"]}
    assert classes, "the backfill classified no sources"
    from learning.practice.backfill import CLASS_INELIGIBLE, CLASS_PARTIAL

    assert set(classes.values()) <= {CLASS_PARTIAL, CLASS_INELIGIBLE, "FULL"}
    # the two sources the audit found duplicative / non-authoritative stay INELIGIBLE
    assert classes.get("programming_exercise_submissions") == CLASS_INELIGIBLE
    assert classes.get("code_challenge_attempts") == CLASS_INELIGIBLE


# ================================================================ PART J2 — product flows

def test_records_api_works_against_the_migrated_schema(migrated):
    report = migrated["report"]
    assert report["records_status"] == 200
    assert "records" in report["records_body_keys"]
    # a core record read must not need the scientific runtime at all
    assert report["records_after_event"] >= report["records_count"]


def test_student_twin_operates_against_the_migrated_data_plane(migrated):
    """PART J2: the preview reads the migrated canonical facts and writes nothing."""
    report = migrated["report"]
    assert report["student_twin_status"] == 200
    assert report["student_twin_controls"] is False
    assert report["student_twin_writes"] is False
    if report["student_twin_events"]:
        assert report["student_twin_mode"] == "PREVIEW"


def test_student_twin_reaches_the_real_runtime_for_a_real_event(migrated):
    """The full chain: migrated DB -> product API -> REAL runtime -> real state."""
    if not migrated["runtime_available"]:
        pytest.skip("scientific runtime environment not available on this machine")
    report = migrated["report"]
    assert report["student_twin_with_event_status"] == 200
    assert report["student_twin_with_event_count"] == 1
    assert report["student_twin_with_event_mode"] == "PREVIEW", \
        report["student_twin_with_event_status"]
    assert report["student_twin_with_event_state"], "no state came back from the runtime"
    assert report["student_twin_with_event_release"]


# ================================================================ PART P — DB safety

def test_the_rehearsal_writes_nothing_outside_its_own_directory(migrated):
    """PART P: the rehearsal is side-effect-free on the repository.

    Only the database it built in its own temp directory is migrated, and every artifact it
    exposes lives there — so a suite run cannot touch a runtime database or any checkout path.
    """
    workdir = migrated["copy"].parent
    assert workdir.name.startswith("s4-migration-"), workdir
    assert migrated["copy"].is_file()
    assert migrated["copy"].parent == workdir
    assert BACKEND not in migrated["copy"].parents
    assert REPO_ROOT not in migrated["copy"].parents
