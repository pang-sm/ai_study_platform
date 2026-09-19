"""Shared authority metadata for every product-facing scientific response (B2).

A scientific number shown anywhere in the product must arrive with the statement of what
it is allowed to do. Two facts are constant and non-negotiable:

  * ``controls_product_decision = False`` — no scientific output may gate, grade, rank,
    unlock or mutate anything the learner sees as their own state.
  * ``writes_learner_fact = False`` — a preview is a read.

``mode`` says how far the capability has actually been productized:

  PREVIEW                 computed and safe to display as an experimental view
  SHADOW                  computed, recorded, NOT displayed to the learner
  SHADOW_NOT_USER_VISIBLE computed, recorded, and BLOCKED from the learner surface by a
                          known unresolved blocker (reported in ``blockers``)
  UNAVAILABLE             the runtime could not answer; this is not an error state
"""
from __future__ import annotations

from datetime import datetime, timezone

MODE_PREVIEW = "PREVIEW"
MODE_SHADOW = "SHADOW"
MODE_SHADOW_NOT_USER_VISIBLE = "SHADOW_NOT_USER_VISIBLE"
MODE_UNAVAILABLE = "UNAVAILABLE"

# Every scientific component in the pool is a DATA_PRODUCER: it produces evidence for
# later validation, never a decision.
CONTROLS_PRODUCT_DECISION = False
WRITES_LEARNER_FACT = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def metadata(*, component: str, mode: str, request_id: str | None = None,
             runtime_release_id: str | None = None,
             source_class: str | None = None,
             latency_ms: float | None = None,
             blockers: list[str] | None = None,
             semantics: str | None = None) -> dict:
    """Build the authority block carried by every scientific response."""
    block = {
        "component": component,
        "mode": mode,
        "controls_product_decision": CONTROLS_PRODUCT_DECISION,
        "writes_learner_fact": WRITES_LEARNER_FACT,
        "generated_at": _now_iso(),
        "request_id": request_id,
        "runtime_release_id": runtime_release_id,
        "source_class": source_class,
    }
    if latency_ms is not None:
        block["latency_ms"] = latency_ms
    if blockers:
        block["blockers"] = list(blockers)
    if semantics:
        block["semantics"] = semantics
    return block


def from_runtime_response(component: str, mode: str, body: dict,
                          *, blockers: list[str] | None = None,
                          semantics: str | None = None) -> dict:
    """Authority block derived from a Scientific Runtime response body.

    Only fields the runtime actually reported are copied; nothing is invented when the
    runtime leaves a field out.
    """
    return metadata(
        component=component,
        mode=mode,
        request_id=body.get("request_id"),
        runtime_release_id=body.get("runtime_release_id"),
        source_class=body.get("scientific_source_class"),
        latency_ms=body.get("latency_ms"),
        blockers=blockers,
        semantics=semantics,
    )
