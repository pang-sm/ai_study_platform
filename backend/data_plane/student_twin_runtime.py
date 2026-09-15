"""StudentTwin scientific runtime bridge (Phase 2B2).

Consumes the frozen ``zhixue_runtime`` public API (``get_adapter("student_twin")``).
Maps a product LearningEvent to the scientific StudentTwin event and performs the
deterministic from-history replay.  No scientific formula is copied here; the runtime
adapter is the single source of truth.

The zhixue_runtime package is imported LAZILY (only when inference actually executes),
and is NOT a hard dependency of the product backend at import time.
"""
import json
import logging
import os

logger = logging.getLogger("data_plane.student_twin")


def _import_runtime():
    import sys
    src = os.getenv("ZHIXUE_RUNTIME_SRC") or r"D:\ZhixueAI\runtime_package\v1\src"
    if src and src not in sys.path:
        sys.path.insert(0, src)
    import zhixue_runtime  # noqa: F401
    from zhixue_runtime.config import RuntimeConfig
    from zhixue_runtime.components.adapters import get_adapter
    return RuntimeConfig, get_adapter


def map_event(le) -> dict:
    """Map a product LearningEvent row to a scientific StudentTwin event dict.

    Optional fields are left None (NOT fabricated to 0/default).  concept_id uses the
    FREE_TEXT knowledge_point_ref value.
    """
    kp = None
    if getattr(le, "knowledge_point_ref_json", None):
        try:
            kp = json.loads(le.knowledge_point_ref_json)
        except Exception:
            kp = None
    concept = None
    if isinstance(kp, dict) and kp.get("value"):
        concept = kp["value"]

    return {
        "event_id": le.event_id,
        "user_id": str(le.user_id) if le.user_id is not None else (le.source_user_ref or le.event_id),
        "timestamp": le.occurred_at,
        "activity_type": "PRACTICE",
        "source": le.source_type or "course_practice",
        "course_id": le.course_id,
        "concept_id": concept,
        "item_id": le.question_id,
        "question_id": le.question_id,
        "answer": le.answer,
        "correctness": le.correct,
        "response_time_ms": le.response_time_ms,
        "attempts": le.attempt_no,
        "hints": None,
    }


class StudentTwinReplayer:
    """Cumulative deterministic replay of one user's ordered events."""

    def __init__(self):
        RuntimeConfig, get_adapter = _import_runtime()
        cfg = RuntimeConfig(home=os.getenv("ZHIXUE_HOME") or r"D:\ZhixueAI")
        self._adapter = get_adapter("student_twin")(cfg)
        self._adapter.load()

    def ingest(self, le):
        self._adapter.ingest_event(map_event(le))

    def state(self, user_id) -> dict:
        r = self._adapter.get_state(user_id)
        return r.output["result"]

    def close(self):
        self._adapter.unload()
