"""STEP 7A: student_twin_mode via app_runtime_flags (KEEP + EVOLVE) integration tests.

Verifies the effective-mode resolution order: explicit env → app_runtime_flags → OFF,
with fail-closed behavior on invalid value / DB unavailability.
"""
import pytest
from sqlalchemy import text

from core import config


def _upsert_flag(session, key, value):
    session.execute(
        text("INSERT INTO app_runtime_flags (key, value) VALUES (:k, :v) "
             "ON CONFLICT(key) DO UPDATE SET value = :v"),
        {"k": key, "v": value},
    )
    session.commit()


def _clear_flag(session, key):
    session.execute(text("DELETE FROM app_runtime_flags WHERE key = :k"), {"k": key})
    session.commit()


def test_no_env_no_db_flag_off(monkeypatch, db_session):
    monkeypatch.delenv("STUDENT_TWIN_MODE", raising=False)
    _clear_flag(db_session, "student_twin_mode")
    assert config.effective_student_twin_mode(db_session) == "off"


def test_db_flag_internal_is_shadow(monkeypatch, db_session):
    monkeypatch.delenv("STUDENT_TWIN_MODE", raising=False)
    _upsert_flag(db_session, "student_twin_mode", "internal")
    assert config.effective_student_twin_mode(db_session) == "internal"
    assert config.student_twin_shadow_enabled(db_session) is True


def test_db_flag_advisory(monkeypatch, db_session):
    monkeypatch.delenv("STUDENT_TWIN_MODE", raising=False)
    _upsert_flag(db_session, "student_twin_mode", "advisory")
    assert config.effective_student_twin_mode(db_session) == "advisory"
    assert config.student_twin_shadow_enabled(db_session) is False


def test_invalid_db_flag_falls_back_off(monkeypatch, db_session):
    monkeypatch.delenv("STUDENT_TWIN_MODE", raising=False)
    _upsert_flag(db_session, "student_twin_mode", "bogus")
    assert config.effective_student_twin_mode(db_session) == "off"


def test_env_off_overrides_db_internal(monkeypatch, db_session):
    monkeypatch.setenv("STUDENT_TWIN_MODE", "off")
    _upsert_flag(db_session, "student_twin_mode", "internal")
    assert config.effective_student_twin_mode(db_session) == "off"


def test_env_internal_overrides_db_off(monkeypatch, db_session):
    monkeypatch.setenv("STUDENT_TWIN_MODE", "internal")
    _upsert_flag(db_session, "student_twin_mode", "off")
    assert config.effective_student_twin_mode(db_session) == "internal"


def test_db_unavailable_fails_closed_off(monkeypatch):
    monkeypatch.delenv("STUDENT_TWIN_MODE", raising=False)

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db unavailable")

    assert config.effective_student_twin_mode(_BrokenSession()) == "off"
