"""STEP 7A tests: StudentTwin lifecycle mode (OFF / INTERNAL) + worker loop mode.

Asserts the SHADOW pipeline is gated by BOTH DATA_PRODUCER_EXECUTION_ENABLED and
STUDENT_TWIN_MODE, and that OFF (safe default) blocks the whole pipeline.
"""
import pytest

from core import config
from data_plane import worker


def test_mode_default_off(monkeypatch):
    monkeypatch.delenv("STUDENT_TWIN_MODE", raising=False)
    assert config.student_twin_mode() == "off"
    assert config.student_twin_shadow_enabled() is False


def test_mode_internal_is_shadow(monkeypatch):
    monkeypatch.setenv("STUDENT_TWIN_MODE", "internal")
    assert config.student_twin_mode() == "internal"
    assert config.student_twin_shadow_enabled() is True


def test_mode_advisory_reserved(monkeypatch):
    monkeypatch.setenv("STUDENT_TWIN_MODE", "advisory")
    assert config.student_twin_mode() == "advisory"
    assert config.student_twin_shadow_enabled() is False


def test_mode_invalid_falls_back_off(monkeypatch):
    monkeypatch.setenv("STUDENT_TWIN_MODE", "bogus")
    assert config.student_twin_mode() == "off"


def test_execution_blocked_when_mode_off(monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("STUDENT_TWIN_MODE", "off")
    assert worker.execution_enabled() is False


def test_execution_blocked_when_flag_off(monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("STUDENT_TWIN_MODE", "internal")
    assert worker.execution_enabled() is False


def test_execution_enabled_in_shadow(monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("STUDENT_TWIN_MODE", "internal")
    assert worker.execution_enabled() is True


def test_run_loop_terminates_when_disabled(monkeypatch):
    monkeypatch.setenv("DATA_PRODUCER_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("STUDENT_TWIN_MODE", "internal")
    report = worker.run_loop(object(), interval_seconds=0.0, max_iterations=1)
    assert report["iterations"] == 1
    assert report["skipped_not_enabled"] is True


def test_shadow_has_no_product_read_api():
    """SHADOW_NO_DECISION_INFLUENCE: no /student-twin user API, no /home prediction read."""
    import main
    paths = {getattr(r, "path", "") for r in main.app.routes}
    assert "/student-twin" not in paths
    assert "/api/student-twin" not in paths
    assert "/v1/inference/student-twin" not in paths  # runtime endpoint lives in the runtime service
