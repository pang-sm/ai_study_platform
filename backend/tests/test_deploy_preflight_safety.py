"""The 2026-09-28 outage, as a regression test.

The incident was not "the membership gate is wrong" — it was **where the gate ran**. The deploy
stopped the running backend first and only then ran the gate, so a refusal it had always been
capable of producing took production down for ~15 minutes. Two properties have to hold, and both
are pinned here:

  1. the gate REFUSES a global plan code it cannot map (and writes nothing while doing it), and
  2. a refusal is recoverable WITHOUT touching the unified tier in `subscriptions`, so repairing
     the data can never change what a learner is entitled to.

The deploy's ordering itself (preflight before stop) is not testable from pytest — it lives in
`.github/workflows/deploy.yml`. What IS testable is that the preflight is read-only and that the
repair is correctness-preserving, which is what makes running it first safe.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPTS = REPO_ROOT / "scripts" / "deploy"

# Every direction plan code the catalogs sell, plus the free case. A parameterised test over the
# whole set is the point: covering only `full_exam` is how the next catalog code ships a hole.
DIRECTION_CODES = ["monthly_sprint", "quarterly_boost", "full_exam", "monthly", "quarterly", "full"]


def _make_db(path: Path, plan: str | None) -> None:
    """A minimal database with just the tables the preflight and the repair actually read."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    import models  # noqa: PLC0415
    from sqlalchemy import create_engine  # noqa: PLC0415
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{path}")
    models.User.__table__.create(engine)
    models.UserServiceMembership.__table__.create(engine, checkfirst=True)
    if plan is not None:
        # Through the ORM, so every other NOT NULL column gets its model default rather than
        # having to be enumerated here (and re-enumerated whenever the model grows one).
        session = sessionmaker(bind=engine)()
        session.add(models.User(username="probe", plan=plan, hashed_password="x"))
        session.commit()
        session.close()
    engine.dispose()


def _run(script: str, db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{db_path}")
    return subprocess.run(
        [sys.executable, str(DEPLOY_SCRIPTS / script), *args],
        env=env, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=180)


def _plan_of(db_path: Path) -> str:
    con = sqlite3.connect(db_path)
    try:
        return (con.execute("SELECT plan FROM users WHERE id = 1").fetchone() or [""])[0]
    finally:
        con.close()


def test_the_membership_gate_accepts_a_clean_global_plan(tmp_path):
    db = tmp_path / "clean.db"
    _make_db(db, "full")
    result = _run("check_membership_mapping.py", db)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("direction_code", ["full_exam", "monthly_sprint", "quarterly_boost"])
def test_the_membership_gate_refuses_a_direction_code_written_into_the_global_field(
        tmp_path, direction_code):
    """The exact state that stopped production — and the gate MUST refuse it rather than guess."""
    db = tmp_path / "direction.db"
    _make_db(db, direction_code)
    result = _run("check_membership_mapping.py", db)
    assert result.returncode == 1
    assert "UNMAPPABLE" in result.stdout
    assert f"users.plan:{direction_code}" in result.stdout
    # And it refuses WITHOUT writing: a refusal the deploy can survive.
    assert _plan_of(db) == direction_code


def test_the_preflight_is_read_only(tmp_path):
    """A gate that mutates the database is not a gate the deploy may run before the stop."""
    db = tmp_path / "readonly.db"
    _make_db(db, "full_exam")
    before = db.read_bytes()
    _run("check_membership_mapping.py", db)
    assert db.read_bytes() == before


@pytest.mark.parametrize("direction_code", DIRECTION_CODES)
def test_repair_translates_every_direction_code_into_a_mappable_global_one(
        tmp_path, direction_code):
    """Parameterised across the whole catalog, not just the code that happened to break."""
    db = tmp_path / "repair.db"
    _make_db(db, direction_code)

    repaired = _run("repair_legacy_plan.py", db)
    assert repaired.returncode == 0, repaired.stderr

    assert _run("check_membership_mapping.py", db).returncode == 0, (
        f"{direction_code} was not translated into a code the gate accepts")


def test_repair_leaves_the_unified_tier_untouched(tmp_path):
    """`users.plan` is legacy compatibility. The tier lives in `subscriptions` and must not move.

    This is the property that lets the operator repair production without changing anyone's
    entitlements: the account kept `advanced` for the entire incident.
    """
    db = tmp_path / "tier.db"
    _make_db(db, "full_exam")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE subscriptions (id INTEGER PRIMARY KEY, user_id INTEGER, "
                "tier TEXT, status TEXT, end_at TEXT)")
    con.execute("INSERT INTO subscriptions (id, user_id, tier, status, end_at) "
                "VALUES (1, 1, 'advanced', 'active', NULL)")
    con.commit()
    con.close()

    assert _run("repair_legacy_plan.py", db).returncode == 0

    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT tier, status FROM subscriptions WHERE user_id = 1").fetchone() \
            == ("advanced", "active")
        assert con.execute("SELECT plan FROM users WHERE id = 1").fetchone() == ("full",)
    finally:
        con.close()


def test_repair_is_idempotent(tmp_path):
    db = tmp_path / "idem.db"
    _make_db(db, "full_exam")
    assert _run("repair_legacy_plan.py", db).returncode == 0
    first = _plan_of(db)
    second = _run("repair_legacy_plan.py", db)
    assert second.returncode == 0
    assert "ROWS_REWRITTEN=0" in second.stdout
    assert _plan_of(db) == first
