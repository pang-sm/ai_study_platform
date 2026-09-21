"""AI operations summary — admin-only AGGREGATES over the AI accounting facts (P6 §A).

WHAT IT ANSWERS
---------------
"How is the AI layer doing right now?" — request volume, success / failure / denial, latency,
estimated vs actual credits, and the capability / model / provider breakdown, plus the router's
own view (fallback rate, which reason codes actually fired) and the learners' own ratings.

WHERE THE NUMBERS COME FROM (stated per metric, because two sources can disagree)
---------------------------------------------------------------------------------
    ai_requests            the accounting row of every orchestrated call: status, tier,
                           credits, provider/model, started_at → finished_at (latency)
    learning_events        the canonical ``ai_called`` audit fact: the router's reason code
      (ai_called)          and the candidate-pool size — the ONE place a fallback is recorded
    learning_events        the learners' ratings (``ai_feedback_submitted``), read through the
      (feedback)           EXISTING ``learning.feedback_analytics`` aggregate — not a second one
    ai.health registry     process-local provider/model availability

WHAT IT WILL NEVER RETURN
-------------------------
No prompt, no response text, no learner content, no user id, no request id, no error message
body, no filesystem path, no provider secret. Buckets are keyed by capability / model /
provider / tier / space / status / error category — closed vocabularies and public model names
the operator already sees in ``/admin/model-config``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

logger = logging.getLogger("ops.ai_operations")

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365

# Bounded scans: the ops view is a dashboard, not an export. Both bounds are reported in the
# response (`bounded`) so a truncated window can never be mistaken for a complete one.
MAX_REQUEST_ROWS = 20000
MAX_EVENT_ROWS = 20000

# Terminal status → the coarse outcome an operator reads. `reconciliation_pending` is NOT a
# failure (real provider usage happened and awaits settlement) and `denied` is not a fault
# (the policy answered) — collapsing either into "failure" would make the failure rate lie.
SUCCESS_STATUSES = ("settled",)
FAILURE_STATUSES = ("released",)
HELD_STATUSES = ("reconciliation_pending",)
DENIED_STATUSES = ("denied",)
IN_FLIGHT_STATUSES = ("reserved", "executing")

FALLBACK_REASON_CODE = "fallback_after_failure"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clamp_window(window_days) -> int:
    try:
        days = int(window_days)
    except (TypeError, ValueError):
        days = DEFAULT_WINDOW_DAYS
    return max(1, min(days, MAX_WINDOW_DAYS))


def _percentile(values: list[int], fraction: float) -> int | None:
    """Nearest-rank percentile over a small, in-memory list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(fraction * len(ordered) + 0.5))))
    return int(ordered[rank - 1])


def _requests(db: DbSession, start: datetime, end: datetime) -> tuple[list, bool]:
    from usage.models import AIRequest
    rows = (db.query(AIRequest)
            .filter(AIRequest.created_at >= start, AIRequest.created_at <= end)
            .order_by(AIRequest.created_at.desc())
            .limit(MAX_REQUEST_ROWS + 1).all())
    truncated = len(rows) > MAX_REQUEST_ROWS
    return rows[:MAX_REQUEST_ROWS], truncated


def _ai_events(db: DbSession, start_epoch: float) -> tuple[list[dict], bool]:
    """The ``ai_called`` audit facts of the window — references and codes only."""
    from data_plane.models import LearningEvent
    q = (db.query(LearningEvent)
         .filter(LearningEvent.event_type == "ai_called",
                 LearningEvent.occurred_at >= start_epoch)
         .order_by(LearningEvent.occurred_at.desc())
         .limit(MAX_EVENT_ROWS + 1))
    rows = q.all()
    truncated = len(rows) > MAX_EVENT_ROWS
    out = []
    for row in rows[:MAX_EVENT_ROWS]:
        try:
            payload = json.loads(row.item_snapshot_json or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out, truncated


def _latency_ms(row) -> int | None:
    if row.started_at and row.finished_at:
        delta = (row.finished_at - row.started_at).total_seconds() * 1000
        return int(delta) if delta >= 0 else None
    return None


def _empty_bucket() -> dict:
    return {"requests": 0, "success": 0, "failure": 0, "denied": 0, "held": 0,
            "in_flight": 0, "latency_samples": 0, "avg_latency_ms": None,
            "estimated_credits": 0, "actual_credits": 0}


def _accumulate(bucket: dict, row) -> None:
    bucket["requests"] += 1
    status = str(row.status or "")
    if status in SUCCESS_STATUSES:
        bucket["success"] += 1
    elif status in FAILURE_STATUSES:
        bucket["failure"] += 1
    elif status in DENIED_STATUSES:
        bucket["denied"] += 1
    elif status in HELD_STATUSES:
        bucket["held"] += 1
    else:
        bucket["in_flight"] += 1
    latency = _latency_ms(row)
    if latency is not None:
        bucket["latency_samples"] += 1
        bucket["avg_latency_ms"] = (
            (bucket["avg_latency_ms"] or 0)
            + (latency - (bucket["avg_latency_ms"] or 0)) / bucket["latency_samples"])
    for key, value in (("estimated_credits", row.estimated_credits),
                       ("actual_credits", row.actual_credits)):
        if isinstance(value, int):
            bucket[key] += value


def _finish(bucket: dict) -> dict:
    bucket = dict(bucket)
    if bucket["avg_latency_ms"] is not None:
        bucket["avg_latency_ms"] = int(round(bucket["avg_latency_ms"]))
    if bucket["requests"]:
        bucket["success_rate"] = round(bucket["success"] / bucket["requests"], 4)
        bucket["failure_rate"] = round(bucket["failure"] / bucket["requests"], 4)
    else:
        bucket["success_rate"] = None
        bucket["failure_rate"] = None
    return bucket


def _grouped(rows: list, key_of) -> dict[str, dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        key = str(key_of(row) or "unknown")
        _accumulate(buckets.setdefault(key, _empty_bucket()), row)
    return {key: _finish(bucket) for key, bucket in sorted(buckets.items())}


def build_ai_operations(db: DbSession, *, window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """The platform-wide AI operations picture. Aggregated only; admin gated by the router."""
    days = _clamp_window(window_days)
    end = _now()
    start = end - timedelta(days=days)
    start_epoch = start.replace(tzinfo=timezone.utc).timestamp()

    rows, requests_truncated = _requests(db, start, end)
    events, events_truncated = _ai_events(db, start_epoch)

    overall = _empty_bucket()
    latencies: list[int] = []
    for row in rows:
        _accumulate(overall, row)
        latency = _latency_ms(row)
        if latency is not None:
            latencies.append(latency)

    fallback_count = sum(1 for payload in events
                         if payload.get("router_reason_code") == FALLBACK_REASON_CODE)
    router_reasons: dict[str, int] = {}
    for payload in events:
        code = str(payload.get("router_reason_code") or "unspecified")
        router_reasons[code] = router_reasons.get(code, 0) + 1

    error_categories: dict[str, int] = {}
    for payload in events:
        if str(payload.get("status") or "") != "failed":
            continue
        category = str(payload.get("error_category") or "unspecified")
        error_categories[category] = error_categories.get(category, 0) + 1

    events_by_status: dict[str, int] = {}
    for payload in events:
        status = str(payload.get("status") or "unknown")
        events_by_status[status] = events_by_status.get(status, 0) + 1

    from learning import feedback_analytics
    feedback = feedback_analytics.build_analytics(db, user_id=None, window_days=days)

    from ai.health import registry as health_registry
    availability = health_registry().describe()

    settled = overall["success"]
    return {
        "scope": "platform",
        "window_days": days,
        "window_start": start.isoformat(),
        "generated_at": end.isoformat(),
        "requests": {
            **_finish(overall),
            "total": overall["requests"],
            "by_status": {status: sum(1 for row in rows if str(row.status or "") == status)
                          for status in sorted({str(row.status or "unknown") for row in rows})},
        },
        "latency": {
            "samples": len(latencies),
            "avg_ms": (int(round(sum(latencies) / len(latencies))) if latencies else None),
            "p50_ms": _percentile(latencies, 0.50),
            "p95_ms": _percentile(latencies, 0.95),
        },
        "credits": {
            "estimated_total": overall["estimated_credits"],
            "actual_total": overall["actual_credits"],
            "settled_calls": settled,
            "held_calls": overall["held"],
        },
        "by_capability": _grouped(rows, lambda row: row.capability),
        "by_model": _grouped(rows, lambda row: row.model),
        "by_provider": _grouped(rows, lambda row: row.provider),
        "by_tier": _grouped(rows, lambda row: row.tier),
        "by_service_namespace": _grouped(rows, lambda row: row.service_namespace),
        "router": {
            "source": "learning_events:ai_called",
            "event_count": len(events),
            "by_reason_code": dict(sorted(router_reasons.items(),
                                          key=lambda item: (-item[1], item[0]))),
            "fallback_count": fallback_count,
            "fallback_rate": (round(fallback_count / len(events), 4) if events else None),
            "by_status": dict(sorted(events_by_status.items())),
            "failed_by_error_category": dict(sorted(error_categories.items(),
                                                    key=lambda item: (-item[1], item[0]))),
        },
        "feedback": {
            "source": "learning_events:ai_feedback_submitted",
            "up": feedback["totals"]["up"],
            "down": feedback["totals"]["down"],
            "ratings": feedback["totals"]["ratings"],
            "down_rate": feedback["totals"]["down_rate"],
            "by_reason": feedback["by_reason"],
        },
        "availability": {
            "scope": availability["scope"],
            "deployment_requirement": availability["deployment_requirement"],
            "failure_threshold": availability["failure_threshold"],
            "cooldown_seconds": availability["cooldown_seconds"],
            "tracked_models": availability["tracked_models"],
            "degraded_models": availability["degraded_models"],
            "models": availability["models"],
        },
        "bounded": {
            "max_request_rows": MAX_REQUEST_ROWS,
            "max_event_rows": MAX_EVENT_ROWS,
            "requests_truncated": requests_truncated,
            "events_truncated": events_truncated,
        },
        "privacy": {
            "returns": ["counts", "rates", "latency_ms", "credits", "closed-vocabulary codes",
                        "public model/provider names"],
            "never_returns": ["prompt", "response_text", "user_id", "username", "request_id",
                              "learner_content", "error_message", "filesystem_path"],
            "aggregate_only": True,
        },
    }
