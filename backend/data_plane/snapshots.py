"""Item snapshot + knowledge-point-ref construction for LearningEvents.

LIVE emitter builds a FULL snapshot from the in-memory AIGeneratedQuestion at submit
time (before it can be mutated).  BACKFILL builds a PARTIAL snapshot from the durable
attempt record (result_json), and must NOT claim FULL completeness.
"""
import json

SNAPSHOT_FIELDS = ["question_id", "question_text", "subject_key", "knowledge_point_ref",
                   "question_type", "options", "standard_answer"]


def build_knowledge_point_ref(attempt) -> dict:
    # knowledge_point_id is free-text / not a reliable FK (per Phase2A mapping)
    return {"type": "FREE_TEXT", "value": (attempt.knowledge_point_id or "")}


def build_live_item_snapshot(item) -> dict:
    """FULL snapshot from a live AIGeneratedQuestion (submit-time, immutable intent)."""
    opts = None
    if getattr(item, "options_json", None):
        try:
            opts = json.loads(item.options_json)
        except Exception:
            opts = None
    return {
        "question_id": str(item.id),
        "question_text": item.stem or "",
        "subject_key": item.subject_key or "",
        "knowledge_point_ref": {"type": "FREE_TEXT", "value": item.knowledge_point_id or ""},
        "question_type": item.question_type or "",
        "options": opts,
        "standard_answer": item.standard_answer or "",
    }


def build_backfill_item_snapshot(attempt, result_item: dict) -> dict:
    """PARTIAL snapshot from the durable attempt result_json (no mutable question lookup).

    course_learning result_json has: question_id, user_answer, standard_answer, correct,
    analysis, generation_mode.  It does NOT have stem/options/question_type, so those are
    marked missing rather than fabricated from the mutable AIGeneratedQuestion row.
    """
    snapshot = {
        "question_id": str(result_item.get("question_id") or ""),
        "question_text": None,          # NOT in result_json
        "subject_key": attempt.subject_key or "",
        "knowledge_point_ref": build_knowledge_point_ref(attempt),
        "question_type": None,          # NOT in result_json
        "options": None,                # NOT in result_json
        "standard_answer": result_item.get("standard_answer") or None,
    }
    missing = [k for k, v in snapshot.items() if v is None and k in ("question_text", "question_type", "options")]
    return snapshot, missing
