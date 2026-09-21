"""Feedback analytics — a READ-ONLY layer over the ratings P4 started collecting.

PURPOSE
-------
Champion/Challenger work needs to know how each capability/model/provider is actually doing in
the learner's eyes: how often a response was rated down, for what reason, with what latency and
what cost. This module answers that from the stored facts and does nothing else.

WHAT IT WILL NOT DO
-------------------
It does NOT train, tune or re-rank anything online, and it does not adjust a weight. There is
no write path here at all: the router keeps selecting by the same deterministic rules, and a
future Champion/Challenger comparison is an offline exercise with its own validation.

SCOPE AND PRIVACY
-----------------
Two scopes, and the difference is access control, not aggregation:

    mine      the caller's own ratings — always available to the caller
    platform  every learner's ratings, AGGREGATED ONLY — admin only, and it never returns a
              user id, a request id or a per-learner row
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

logger = logging.getLogger("learning.feedback_analytics")

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365
MIN_BUCKET_SAMPLE = 1


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _window_start_epoch(window_days) -> float:
    try:
        days = int(window_days)
    except (TypeError, ValueError):
        days = DEFAULT_WINDOW_DAYS
    days = max(1, min(days, MAX_WINDOW_DAYS))
    start = _now() - timedelta(days=days)
    return start.replace(tzinfo=timezone.utc).timestamp()


def _rows(db: DbSession, *, user_id: int | None, start_epoch: float) -> list[dict]:
    """The rating facts of the window — audit events, references and codes only."""
    from data_plane.models import LearningEvent

    q = (db.query(LearningEvent)
         .filter(LearningEvent.event_type == "ai_feedback_submitted",
                 LearningEvent.occurred_at >= start_epoch))
    if user_id is not None:
        q = q.filter(LearningEvent.user_id == user_id)
    out = []
    for row in q.order_by(LearningEvent.occurred_at.desc()).limit(5000).all():
        try:
            payload = json.loads(row.item_snapshot_json or "{}")
        except (TypeError, ValueError):
            continue
        payload["occurred_at"] = row.occurred_at
        out.append(payload)
    return out


def _empty_bucket() -> dict:
    return {"ratings": 0, "up": 0, "down": 0, "down_rate": None,
            "latency_samples": 0, "avg_latency_ms": None,
            "actual_credits": 0, "estimated_credits": 0,
            "regenerated_down": 0, "switched_model_down": 0}


def _accumulate(bucket: dict, row: dict) -> None:
    bucket["ratings"] += 1
    rating = row.get("rating")
    if rating == "up":
        bucket["up"] += 1
    elif rating == "down":
        bucket["down"] += 1
        if row.get("regenerated"):
            bucket["regenerated_down"] += 1
        if row.get("switched_model"):
            bucket["switched_model_down"] += 1
    latency = row.get("latency_ms")
    if isinstance(latency, (int, float)):
        bucket["latency_samples"] += 1
        bucket["avg_latency_ms"] = (
            bucket["avg_latency_ms"] or 0
        ) + (float(latency) - (bucket["avg_latency_ms"] or 0)) / bucket["latency_samples"]
    for key in ("actual_credits", "estimated_credits"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            bucket[key] += int(value)


def _finish(bucket: dict) -> dict:
    if bucket["ratings"]:
        bucket["down_rate"] = round(bucket["down"] / bucket["ratings"], 4)
    return bucket


def _grouped(rows: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        _accumulate(out.setdefault(value, _empty_bucket()), row)
    return {key_: _finish(bucket) for key_, bucket in sorted(out.items())}


def build_analytics(db: DbSession, *, user_id: int | None,
                    window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Aggregated feedback facts. ``user_id=None`` means the platform-wide view."""
    start_epoch = _window_start_epoch(window_days)
    rows = _rows(db, user_id=user_id, start_epoch=start_epoch)

    overall = _empty_bucket()
    for row in rows:
        _accumulate(overall, row)

    reasons: dict[str, int] = {}
    for row in rows:
        if row.get("rating") != "down":
            continue
        reason = str(row.get("reason") or "unspecified")
        reasons[reason] = reasons.get(reason, 0) + 1

    workflows: dict[str, dict] = {}
    for row in rows:
        workflow = str(row.get("workflow_id") or "unattributed")
        _accumulate(workflows.setdefault(workflow, _empty_bucket()), row)

    capabilities = _grouped(rows, "capability")
    models = _grouped(rows, "model")
    providers = _grouped(rows, "provider")

    # Champion/Challenger needs a comparable view per MODEL within a capability; the buckets
    # are returned as-is (counts and rates), never as a ranking the platform acts on.
    per_capability_model: dict[str, dict[str, dict]] = {}
    for row in rows:
        capability = str(row.get("capability") or "unknown")
        model = str(row.get("model") or "unknown")
        bucket = per_capability_model.setdefault(capability, {}).setdefault(
            model, _empty_bucket())
        _accumulate(bucket, row)
    per_capability_model = {
        capability: {model: _finish(bucket) for model, bucket in sorted(models_.items())}
        for capability, models_ in sorted(per_capability_model.items())
    }

    return {
        "scope": "platform" if user_id is None else "mine",
        "window_days": window_days,
        "generated_at": _now().isoformat(),
        "totals": _finish(overall),
        "by_reason": dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
        "by_workflow": {name: _finish(bucket) for name, bucket in sorted(workflows.items())},
        "by_capability": capabilities,
        "by_model": models,
        "by_provider": providers,
        "per_capability_model": per_capability_model,
        "min_bucket_sample": MIN_BUCKET_SAMPLE,
        "semantics": (
            "read-only aggregation of stored ratings. It never trains, tunes or re-ranks the "
            "router: a Champion/Challenger comparison is an offline exercise, and one "
            "learner's dislike changes nobody's model selection. Platform scope is aggregated "
            "only — no user id, no request id, no per-learner row."),
        "router_mutation": False,
    }
