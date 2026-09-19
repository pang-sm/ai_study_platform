"""FRONTEND_BLOCKER_BC4: the startup membership compatibility backfill must survive a
fresh TEMP database.

Reproduces the real production startup ordering on an isolated temp SQLite file:

    Base.metadata.create_all()        # main.py:353 — creates every model table
    init_user_profile_schema()        # main.py:354 — runs the ensure helpers
        └─ ensure_user_service_memberships_schema()
              └─ backfill INSERT ... (user_id, service_key, is_enabled, plan)

``create_all`` builds ``user_service_memberships.status`` from the SQLAlchemy model, where
``default="active"`` is a PYTHON-side default — it emits no ``DEFAULT`` in the DDL. The
generic ``ensure_columns`` spec (``VARCHAR(20) NOT NULL DEFAULT 'active'``) never runs
because the column already exists. So on a fresh file the backfill's INSERT omits a column
that has neither a DB default nor an ORM default, and SQLite raises

    NOT NULL constraint failed: user_service_memberships.status

The deployed database does not show this because it was built the other way round: the
column arrived via ``ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT 'active'``, which
does create a DB default.

These tests are written against the *observable* startup contract (rows exist, statuses
are canonical and non-null, repeat runs are inert) so they stay honest regardless of how
the fix is shaped.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

import database
from database import Base

# The canonical membership status vocabulary, evidenced by the four places that already
# write it: database.py:2233 (this very helper's normalization rule), main.py:28311,
# main.py:30691 and payments/service.py:114.
ACTIVE = "active"
INACTIVE = "inactive"
LEGAL_STATUSES = {ACTIVE, INACTIVE, "disabled", "expired"}

SERVICE_KEYS = ("exam_11408", "course_learning", "programming")


def _fresh_engine(tmp_path: Path):
    """A brand-new database built exactly the way main.py builds one at startup."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


def _add_user(engine, username="bc4_user", plan="free"):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (username, hashed_password, grade, major, semester, "
            "onboarding_completed, email_verified, phone_verified, plan, is_deleted, "
            "is_active) VALUES (:u, 'x', '', '', '', 1, 1, 0, :p, 0, 1)"),
            {"u": username, "p": plan})


def _run_startup(engine, monkeypatch):
    """Invoke the real startup schema path against this engine."""
    monkeypatch.setattr(database, "engine", engine)
    database.init_user_profile_schema()


def _rows(engine):
    with engine.begin() as conn:
        return conn.execute(text(
            "SELECT user_id, service_key, is_enabled, plan, status "
            "FROM user_service_memberships ORDER BY service_key")).fetchall()


def _column(engine, name="status"):
    with engine.begin() as conn:
        for row in conn.execute(text("PRAGMA table_info(user_service_memberships)")):
            if row[1] == name:
                return {"type": row[2], "notnull": bool(row[3]), "default": row[4]}
    return None


# ================================================================ the reproduction

def test_fresh_temp_db_startup_does_not_raise(tmp_path, monkeypatch):
    """THE blocker: fresh file + an existing user + startup compatibility path."""
    engine = _fresh_engine(tmp_path)
    _add_user(engine)
    _run_startup(engine, monkeypatch)          # <- IntegrityError before the fix
    assert len(_rows(engine)) == len(SERVICE_KEYS)


def test_fresh_schema_has_no_db_default_for_status(tmp_path):
    """Documents the precondition that makes the backfill's INSERT unsafe.

    If this ever stops holding (e.g. someone adds a server_default to the model), the
    reproduction above would go green for the wrong reason — so pin it.
    """
    engine = _fresh_engine(tmp_path)
    column = _column(engine)
    assert column is not None
    assert column["notnull"] is True, "the NOT NULL constraint must stay"
    assert column["default"] is None, "create_all emits no DB-level DEFAULT"


def test_compat_rows_are_inserted_with_a_canonical_non_null_status(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path)
    _add_user(engine)
    _run_startup(engine, monkeypatch)

    rows = _rows(engine)
    assert {r[1] for r in rows} == set(SERVICE_KEYS)
    for _uid, service_key, is_enabled, _plan, status in rows:
        assert status is not None, f"{service_key}: status must never be NULL"
        assert status in LEGAL_STATUSES, f"{service_key}: unexpected status {status!r}"
        # the value must follow the helper's own is_enabled -> status rule
        assert status == (ACTIVE if is_enabled else INACTIVE), service_key


def test_status_not_null_is_preserved(tmp_path, monkeypatch):
    """The fix must not be 'make the column nullable'."""
    engine = _fresh_engine(tmp_path)
    _add_user(engine)
    _run_startup(engine, monkeypatch)
    assert _column(engine)["notnull"] is True
    with engine.begin() as conn, pytest.raises(Exception):
        conn.execute(text(
            "INSERT INTO user_service_memberships (user_id, service_key, is_enabled, "
            "plan, status) VALUES (1, 'exam_11408', 1, 'free', NULL)"))


# ================================================================ idempotency

def test_repeated_startup_is_idempotent(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path)
    _add_user(engine)
    _run_startup(engine, monkeypatch)
    first = [tuple(r) for r in _rows(engine)]
    _run_startup(engine, monkeypatch)
    _run_startup(engine, monkeypatch)
    assert [tuple(r) for r in _rows(engine)] == first, "restart must not duplicate rows"


def test_existing_membership_row_is_not_overwritten(tmp_path, monkeypatch):
    """A real grant (paid plan, its own status) must survive the compatibility pass."""
    engine = _fresh_engine(tmp_path)
    _add_user(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO user_service_memberships "
            "(user_id, service_key, is_enabled, plan, status) "
            "VALUES (1, 'exam_11408', 1, 'monthly_sprint', 'expired')"))
    _run_startup(engine, monkeypatch)

    rows = _rows(engine)
    exam = next(r for r in rows if r[1] == "exam_11408")
    assert exam[3] == "monthly_sprint"
    assert exam[4] == "expired", "an existing row's status must not be rewritten"
    # the other two directions are still backfilled
    assert {r[1] for r in rows} == set(SERVICE_KEYS)


def test_deleted_users_are_not_backfilled(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path)
    _add_user(engine, username="bc4_live")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (username, hashed_password, grade, major, semester, "
            "onboarding_completed, email_verified, phone_verified, plan, is_deleted, "
            "is_active) VALUES ('bc4_gone', 'x', '', '', '', 1, 1, 0, 'free', 1, 1)"))
    _run_startup(engine, monkeypatch)
    assert {r[0] for r in _rows(engine)} == {1}


# ================================================================ the legacy shape

def test_deployed_shape_with_a_real_db_default_still_backfills(tmp_path, monkeypatch):
    """The other build order: the column arrives via ADD COLUMN with a DB default.

    This is what the real app.db looks like, and it must keep working.
    """
    engine = _fresh_engine(tmp_path)
    # simulate the deployed table: status added by ALTER, carrying a DEFAULT
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE user_service_memberships"))
        conn.execute(text(
            "CREATE TABLE user_service_memberships ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
            "service_key VARCHAR(50) NOT NULL, is_enabled BOOLEAN NOT NULL DEFAULT 0, "
            "plan VARCHAR(30) DEFAULT 'free', "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "status VARCHAR(20) NOT NULL DEFAULT 'active', activated_at DATETIME, "
            "expires_at DATETIME)"))
    _add_user(engine)
    _run_startup(engine, monkeypatch)
    rows = _rows(engine)
    assert {r[1] for r in rows} == set(SERVICE_KEYS)
    assert all(r[4] is not None for r in rows)


def test_legacy_course_service_key_is_still_canonicalized(tmp_path, monkeypatch):
    """The neighbouring compatibility rule in the same helper must keep working."""
    engine = _fresh_engine(tmp_path)
    _add_user(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO user_service_memberships "
            "(user_id, service_key, is_enabled, plan, status) "
            "VALUES (1, 'course', 1, 'free', 'active')"))
    _run_startup(engine, monkeypatch)
    keys = {r[1] for r in _rows(engine)}
    assert "course" not in keys
    assert "course_learning" in keys
