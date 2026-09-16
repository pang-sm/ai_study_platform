"""Centralized Product Backend configuration (no secrets, no scientific runtime imports).

The Product Backend NEVER imports ``zhixue_runtime``/``runtime_src``/torch/transformers.
All scientific work is delegated to the Scientific Runtime Service over localhost HTTP.
"""
import os

# frozen scientific runtime release the Product Backend targets (engineering patch P1)
SCIENTIFIC_RUNTIME_RELEASE_ID = "zhixue-runtime-v1-phase1gr-p1"


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def data_plane_write_enabled() -> bool:
    """Gate LearningEvent emission (default false)."""
    return _env_bool("DATA_PLANE_WRITE_ENABLED", False)


def data_producer_execution_enabled() -> bool:
    """Gate the Data Producer worker (default false)."""
    return _env_bool("DATA_PRODUCER_EXECUTION_ENABLED", False)


_STUDENT_TWIN_MODES = ("off", "internal", "advisory")


def normalize_student_twin_mode(value) -> str:
    """Normalize any candidate value to off/internal/advisory; invalid/empty → OFF."""
    v = (value or "").strip().lower()
    return v if v in _STUDENT_TWIN_MODES else "off"


def student_twin_mode() -> str:
    """StudentTwin lifecycle mode — deployment ENV override only.

    OFF      = pipeline fully disabled (safe default)
    INTERNAL = shadow: emitter + worker + runtime run, predictions persist, NO product read
    ADVISORY = reserved for V1 product read path (NOT enabled in STEP 7A)

    This reads the explicit env override. The PERSISTED ``app_runtime_flags`` value is
    resolved by :func:`effective_student_twin_mode` (env > DB > OFF). Env is kept as a
    separate high-priority layer to support fail-closed deployment control without a DB read.
    """
    return normalize_student_twin_mode(os.getenv("STUDENT_TWIN_MODE", ""))


def read_runtime_flag(session, key: str):
    """Read a persisted ``app_runtime_flags`` value (None if absent / unreadable).

    app_runtime_flags is a raw key-value table (no SQLAlchemy model); this reads it with
    raw SQL and fails closed (returns None) so a DB error never breaks startup/import.
    """
    from sqlalchemy import text

    try:
        row = session.execute(
            text("SELECT value FROM app_runtime_flags WHERE key = :key"), {"key": key}
        ).first()
        return row[0] if row else None
    except Exception:
        return None


def effective_student_twin_mode(session=None) -> str:
    """Effective StudentTwin mode: explicit env → app_runtime_flags → OFF (fail closed).

    Priority:
      1. STUDENT_TWIN_MODE env explicitly set (deployment override, highest priority)
      2. app_runtime_flags["student_twin_mode"] persisted value
      3. OFF (safe default; also on invalid value or DB unavailability)
    """
    env_raw = os.getenv("STUDENT_TWIN_MODE", "").strip()
    if env_raw:
        return normalize_student_twin_mode(env_raw)
    if session is not None:
        db_value = read_runtime_flag(session, "student_twin_mode")
        if db_value:
            return normalize_student_twin_mode(db_value)
    return "off"


def student_twin_shadow_enabled(session=None) -> bool:
    """True when StudentTwin may run in SHADOW (INTERNAL) mode."""
    return effective_student_twin_mode(session) == "internal"


def scientific_runtime_base_url() -> str:
    return os.getenv("SCIENTIFIC_RUNTIME_BASE_URL", "http://127.0.0.1:8101")


def scientific_runtime_timeout() -> float:
    try:
        return float(os.getenv("SCIENTIFIC_RUNTIME_TIMEOUT", "10.0"))
    except ValueError:
        return 10.0
