"""Stateless StudentTwin scientific execution via the ``zhixue_runtime`` public API.

The runtime service owns NO product learner state. Every request is a deterministic replay
of the supplied (already worker-ordered) event history into a fresh StudentTwin, returning
the resulting scientific state. Only ``get_adapter("student_twin")`` is used — no scientific
formula is copied, no ``runtime_src``/``model_assets`` file is read directly.
"""
from __future__ import annotations

import os

from .contracts import StudentTwinEvent

_adapter_cls = None


def _ensure_runtime_path():
    import sys
    src = os.getenv("ZHIXUE_RUNTIME_SRC")
    if src and src not in sys.path:
        sys.path.insert(0, src)


def _get_adapter_cls():
    global _adapter_cls
    if _adapter_cls is None:
        _ensure_runtime_path()
        from zhixue_runtime.components.adapters import get_adapter
        _adapter_cls = get_adapter("student_twin")
    return _adapter_cls


def _to_scientific(ev: StudentTwinEvent, user_ref: str) -> dict:
    return {
        "event_id": ev.event_id,
        "user_id": user_ref,
        "timestamp": ev.occurred_at,
        "activity_type": ev.activity_type,
        "source": ev.source or "product",
        "concept_id": ev.concept_ref,
        "item_id": ev.item_id,
        "correctness": ev.correct,
        "response_time_ms": ev.response_time_ms,
        "attempts": ev.attempt_no,
        "hints": ev.hints,
    }


def replay_state(user_ref: str, events: list[StudentTwinEvent]) -> dict:
    """Replay ``events`` (in supplied order) into a fresh StudentTwin; return final state."""
    _ensure_runtime_path()
    from zhixue_runtime.config import RuntimeConfig

    cls = _get_adapter_cls()
    home = os.getenv("ZHIXUE_HOME")
    cfg = RuntimeConfig(home=home) if home else RuntimeConfig()
    adapter = cls(cfg)
    try:
        adapter.load()
        for ev in events:
            adapter.ingest_event(_to_scientific(ev, user_ref))
        return adapter.get_state(user_ref).output["result"]
    finally:
        adapter.unload()
