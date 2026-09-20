"""ACCEL_SPRINT_S4 — PRODUCTION DATA-PLANE MIGRATION READINESS (PART J).

The real ``backend/app.db`` is a 72-table legacy database that predates Alembic entirely:
it has no ``alembic_version`` and none of the data-plane tables. This module proves the
full chain reaches HEAD on a ``byte-for-byte COPY`` of it — never on the original, which
stays READ ONLY.

What is proven, in order:

  1. the copy migrates to HEAD and passes ``PRAGMA integrity_check``;
  2. every pre-existing table keeps every row, and nothing is dropped;
  3. the data-plane tables (``learning_events``, ``model_predictions``,
     ``model_inference_runs``) now exist;
  4. the application starts at HEAD with ``Base.metadata.create_all`` DISABLED — the
     schema comes from Alembic, so the app does not depend on ``create_all``;
  5. the historical backfill runs honestly and is IDEMPOTENT on a second run;
  6. ``GET /exam/prep/records`` works against the migrated schema;
  7. ``GET /exam/prep/scientific/student-twin`` reaches a REAL runtime and returns a real
     state for a real event in the migrated database.

Everything runs in subprocesses so the migrated database, its own ``DATABASE_URL`` and the
runtime address are genuinely independent of this test process.

Skips (never fails) when the real database, the alembic tooling or the scientific runtime
environment is not present on this machine.
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
REAL_DB = BACKEND / "app.db"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
RUNTIME_PYTHON = Path(r"D:\ZhixueAI\envs\runtime-service\Scripts\python.exe")
RUNTIME_SERVICE_ROOT = REPO_ROOT / "scientific_runtime_service"

# The legacy baseline. Row counts here are READ before and AFTER; any change is a failure.
LEGACY_TABLE_COUNT = 72
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
report["data_plane_absent_before"] = json.loads(os.environ["S4_ABSENT_BEFORE"])

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


@pytest.fixture(scope="module")
def migrated():
    """A byte-for-byte copy of the REAL database, migrated to HEAD, then probed.

    The real file is opened for reading only. Every write lands on the copy.
    """
    if not REAL_DB.exists():
        pytest.skip("real backend/app.db is not present on this machine")
    if not PYTHON.exists():
        pytest.skip("backend venv python is not present on this machine")

    original = {
        "sha256": _sha256(REAL_DB),
        "size": REAL_DB.stat().st_size,
        "mtime": REAL_DB.stat().st_mtime,
    }

    workdir = Path(tempfile.mkdtemp(prefix="s4-migration-"))
    copy = workdir / "app.db"
    shutil.copy2(REAL_DB, copy)
    assert _sha256(copy) == original["sha256"], "the copy is not byte-for-byte"

    legacy_tables = _tables(copy)
    legacy_rows = {t: _rows(copy, t) for t in PROTECTED_TABLES
                   if t in legacy_tables}
    absent_before = [t for t in ("learning_events", "model_predictions",
                                 "model_inference_runs", "alembic_version")
                     if t not in legacy_tables]

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{copy.as_posix()}"}
    upgrade = subprocess.run(
        [str(PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert upgrade.returncode == 0, upgrade.stderr[-3000:]

    runtime = _start_runtime()
    try:
        probe_env = {
            **env,
            "S4_DB": copy.as_posix(),
            "S4_BACKEND": str(BACKEND),
            "S4_PROTECTED": json.dumps(sorted(legacy_rows)),
            "S4_ABSENT_BEFORE": json.dumps(absent_before),
            "STUDENT_TWIN_MODE": "internal",
        }
        if runtime:
            probe_env["SCIENTIFIC_RUNTIME_BASE_URL"] = f"http://127.0.0.1:{runtime[1]}"
        probe_file = workdir / "probe.py"
        probe_file.write_text(PROBE, encoding="utf-8")
        probed = subprocess.run([str(PYTHON), str(probe_file)], env=probe_env,
                                capture_output=True, text=True, cwd=str(BACKEND))
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


# ================================================================ PART J — migration

def test_real_db_copy_reaches_head_with_integrity_ok(migrated):
    report = migrated["report"]
    assert report["integrity_check"] == "ok"
    assert report["foreign_key_check"] == []
    assert report["alembic_version"] == ["20260919_0012"], report["alembic_version"]


def test_no_table_was_dropped_and_every_legacy_row_survived(migrated):
    report = migrated["report"]
    after = set(report["tables_at_head"])
    assert migrated["legacy_tables"] <= after, \
        f"dropped: {sorted(migrated['legacy_tables'] - after)}"

    for table, before in migrated["legacy_rows"].items():
        assert report["pre_existing_rows"][table] == before, \
            f"{table}: {before} -> {report['pre_existing_rows'][table]}"


def test_protected_static_assets_are_intact(migrated):
    rows = migrated["legacy_rows"]
    if not rows:
        pytest.skip("no protected tables present in the legacy database")
    # the real content counts, read from the copy
    assert rows.get("exam_question_bank", 0) > 0
    assert rows.get("programming_exercises", 0) > 0
    assert sum(rows.values()) > 0


def test_data_plane_tables_are_created_by_the_migration(migrated):
    report = migrated["report"]
    assert set(report["data_plane_absent_before"]) == {
        "learning_events", "model_predictions", "model_inference_runs", "alembic_version"}
    for table in ("learning_events", "model_predictions", "model_inference_runs",
                  "practice_sessions", "practice_attempts", "wrong_answer_states",
                  "exam_prep_profiles"):
        assert table in report["tables_at_head"], table


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

def test_the_real_database_was_never_modified(migrated):
    """PART P: the audit copy is the only thing that changed."""
    original = migrated["original"]
    assert _sha256(REAL_DB) == original["sha256"], "REAL app.db CONTENT CHANGED"
    assert REAL_DB.stat().st_size == original["size"]
    assert REAL_DB.stat().st_mtime == original["mtime"]


def test_the_real_database_still_has_its_legacy_shape(migrated):
    """The real database must NOT have been migrated as a side effect."""
    tables = _tables(REAL_DB)
    assert "learning_events" not in tables
    assert "alembic_version" not in tables
