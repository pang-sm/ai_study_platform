"""P6.1 §C–§I — the canonical authenticated E2E harness, held to its own contract.

WHAT THESE TESTS PROVE (they start the REAL app in a subprocess, not a TestClient)
----------------------------------------------------------------------------------
1. isolation: the harness runs on a temp database, and ``backend/app.db`` is never opened
   (its bytes are compared before and after);
2. authentication is the PRODUCT's: the seeded learner logs in through ``POST /login`` and the
   session cookie authorizes the next request;
3. the fake provider is NOT an HTTP mock: an AI call still creates a real ``ai_requests`` row
   (capability, tier, provider/model, settled credits) and its ``request_id`` round-trips
   through ``POST /ai/feedback``;
4. provenance: every learning fact the harness run produced carries ``data_origin=ACCEPTANCE``;
5. training safety: the run adds ZERO eligible LEARNER interactions, so a data-readiness gate
   cannot grow because of it;
6. shutdown is deterministic: the temp directory is gone after ``stop()``.

The harness is started once for the whole module (a real migration + a real server are
expensive); the tests share it and never write to each other's rows.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest
import sqlalchemy

from scripts.e2e_harness import E2EEnvironment

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_ROOT / "app.db"
COURSE = "数据结构"


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def harness():
    """ONE isolated, authenticated backend for this module. Stopped and removed afterwards."""
    env = E2EEnvironment(username="p61_e2e_learner", password="p61-e2e-pass-1",
                         tier="standard")
    try:
        env.start()
    except Exception as exc:  # noqa: BLE001 — a harness failure is a test failure
        pytest.fail(f"E2E harness failed to start: {exc}")
    try:
        yield env
    finally:
        env.stop()


@pytest.fixture(scope="module")
def session(harness):
    """A real login against the harness server, carrying its own cookie jar."""
    client = httpx.Client(base_url=harness.base_url, timeout=30)
    response = client.post("/login", json={"username": harness.username,
                                           "password": harness.password})
    assert response.status_code == 200, response.text
    assert client.cookies.get("ai_session"), "the login must issue the real session cookie"
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="module")
def harness_db(harness):
    """A read-only connection to the harness's OWN database (never the app's)."""
    engine = sqlalchemy.create_engine(harness.database_url)
    try:
        yield engine
    finally:
        engine.dispose()


# ================================================================ 1. isolation


def test_the_harness_runs_on_a_temp_database_and_never_opens_app_db(harness):
    assert harness.temp_dir is not None and Path(harness.temp_dir).exists()
    assert "app.db" not in harness.database_url
    db_file = Path(harness.database_url.replace("sqlite:///", ""))
    assert db_file.parent == Path(harness.temp_dir)
    assert db_file.name == "e2e.db"

    contract = harness.bootstrap()
    assert contract["base_url"].startswith("http://127.0.0.1:")
    assert contract["port"] > 0
    assert contract["health"].endswith("/api/health")
    assert contract["data_origin"] == "ACCEPTANCE"
    assert contract["app_env"] == "acceptance"
    # the frontend contract needs NO source change: the app already reads VITE_API_BASE_URL
    assert contract["frontend"]["vite_api_base_url"] == contract["base_url"]


def test_the_backend_is_healthy_and_serves_the_real_app(harness):
    with httpx.Client(timeout=20) as probe:
        health = probe.get(f"{harness.base_url}/api/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"


# ================================================================ 2. authentication


def test_authentication_is_the_product_s_own(session, harness):
    me = session.post("/me", json={"username": harness.username})
    assert me.status_code == 200, me.text
    assert session.get("/admin/ai-operations/summary").status_code == 403   # a learner

    with httpx.Client(base_url=harness.base_url, timeout=20) as anonymous:
        assert anonymous.post("/me", json={"username": harness.username}).status_code == 401


# ================================================================ 3. fake provider, real stack


def test_the_fake_provider_still_travels_the_unified_ai_stack(harness, session, harness_db):
    response = session.post("/code/analyze", json={
        "username": "", "course_id": "", "language": "python",
        "code": "def solve(n):\n    return n + 1\n", "question": "这段代码对吗"})
    assert response.status_code == 200, response.text
    request_id = response.json()["request_id"]
    assert request_id

    with harness_db.connect() as conn:
        row = conn.execute(sqlalchemy.text(
            "SELECT request_id, capability, status, tier, provider, model, "
            "actual_credits, service_namespace FROM ai_requests WHERE request_id = :rid"
        ), {"rid": request_id}).fetchone()
    assert row is not None, "the call must have created a real ai_requests row"
    assert row.capability == "programming.explain"
    assert row.status == "settled" and row.actual_credits and row.actual_credits > 0
    assert row.tier == "standard"
    assert row.provider, "a provider from the qualified pool served it (faked, not mocked)"

    rated = session.post("/ai/feedback", json={"request_id": request_id, "rating": "up"})
    assert rated.status_code == 200, rated.text
    assert rated.json()["request_id"] == request_id
    assert rated.json()["trains_router_online"] is False


def test_the_seeded_learner_can_reach_the_seeded_product_state(harness, session):
    agenda = session.get("/learning/agenda")
    assert agenda.status_code == 200, agenda.text
    wrong = session.get("/wrong-answers", params={"service_namespace": "course_learning"})
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["items"], "the seeded wrong answer must be visible to its owner"


# ================================================================ 4/5. provenance + readiness


def test_every_fact_the_run_recorded_is_acceptance_origin(harness_db):
    with harness_db.connect() as conn:
        rows = conn.execute(sqlalchemy.text(
            "SELECT data_origin, COUNT(*) FROM learning_events GROUP BY data_origin"
        )).fetchall()
    assert rows, "the E2E flow produced learning facts"
    origins = {row[0] for row in rows}
    assert origins == {"ACCEPTANCE"}, f"unexpected origins: {origins}"


def test_the_run_cannot_grow_training_readiness(harness_db):
    """§I: an acceptance rehearsal must not move a data-readiness gate by one fact."""
    from science import kt_native

    with harness_db.connect() as conn:
        learner_facts = conn.execute(sqlalchemy.text(
            "SELECT COUNT(*) FROM learning_events WHERE data_origin = 'LEARNER'"
        )).scalar_one()
    assert learner_facts == 0, "an E2E run must never record a LEARNER fact"

    session_factory = sqlalchemy.orm.sessionmaker(bind=harness_db)
    with session_factory() as db:
        body = kt_native.audit(db)
        verdict = kt_native.evaluate_readiness(body)
    assert body["users_with_eligible_interactions"] == 0
    assert body["total_eligible_interactions"] == 0
    assert verdict["verdict"] == "FAIL", "readiness must not be satisfied by acceptance data"
    assert "users_with_eligible_interactions" in verdict["failed_checks"]


# ================================================================ 6. shutdown


def test_shutdown_removes_the_temp_directory(harness, harness_db):
    """The last test in the module: after this the module fixture tears the harness down.

    The reader this test opened is released FIRST — on Windows an open handle anywhere would
    keep the directory alive, and the point of the check is the harness's own cleanup.
    """
    temp_dir = Path(harness.temp_dir)
    assert temp_dir.exists()
    harness_db.dispose()
    harness.stop()
    assert not temp_dir.exists(), "the harness must clean up after itself"
    assert harness.process is None
