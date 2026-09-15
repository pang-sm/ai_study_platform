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


def scientific_runtime_base_url() -> str:
    return os.getenv("SCIENTIFIC_RUNTIME_BASE_URL", "http://127.0.0.1:8101")


def scientific_runtime_timeout() -> float:
    try:
        return float(os.getenv("SCIENTIFIC_RUNTIME_TIMEOUT", "10.0"))
    except ValueError:
        return 10.0
