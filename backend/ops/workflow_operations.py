"""Workflow operations — admin-only aggregates per advanced workflow (P6 §B), plus the
per-run detail read that backs the agent-trace storage decision (P6 §C).

TWO LAYERS PER WORKFLOW
-----------------------
    accounting   the ``ai_requests`` rows of the workflow's capability: calls, success /
                 failure / denial, latency, estimated vs actual credits, and the NORMALIZED
                 error category of every failure
    activity     the workflow's own canonical events: how many runs were requested and how
                 they ended (for the debug agent: iterations and executions actually used)

The debug agent's numbers come from its run's CODE-FREE step trace, which is already durable in
``programming_agent_completed`` / ``programming_agent_failed``. Nothing here reads the learner's
source code, the patch text or a model response, and the per-run read never returns them.

WHAT THIS WILL NEVER RETURN
---------------------------
Prompt, response, learner source code, learner content, provider secrets, filesystem paths.
Failure detail is a NORMALIZED category (``timeout`` / ``rate_limited`` / …), never a provider
error body.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

from .ai_operations import (
    _empty_bucket, _finish, _latency_ms, _now, _clamp_window, MAX_EVENT_ROWS,
)

logger = logging.getLogger("ops.workflow_operations")

# workflow key → (capability billed, label, activity event families)
WORKFLOWS: dict[str, dict] = {
    "deep_study": {
        "label": "深度研习",
        "capability": "tutor.strong_reasoning",
        "activity_events": ("strong_reasoning_requested", "strong_reasoning_completed"),
        "agent_steps": False,
    },
    "programming_agent": {
        "label": "编程调试智能体",
        "capability": "programming.agent",
        "activity_events": ("programming_agent_started", "programming_agent_completed",
                            "programming_agent_failed"),
        "agent_steps": True,
    },
    "learning_report": {
        "label": "学习报告",
        "capability": "report.generate",
        "activity_events": ("report_generated",),
        "agent_steps": False,
    },
    "wrong_analysis": {
        "label": "错因分析",
        "capability": "wrong_answer.analyze",
        "activity_events": ("wrong_analysis_generated",),
        "agent_steps": False,
    },
    "plan_adjustment": {
        "label": "计划调整",
        "capability": "planning.adjust",
        "activity_events": ("plan_adjustment_proposed", "plan_adjustment_applied"),
        "agent_steps": False,
    },
}

# The agent's own closed step vocabulary (learning.spaces.programming.agent). Iterations are
# repair cycles; executions are real test runs. Both are counted from the stored trace.
STEP_PROPOSE_PATCH = "propose_patch"
AGENT_RUN_STATUSES = ("completed", "failed", "no_repair_needed")


def _window(window_days) -> tuple[int, datetime, datetime, float]:
    days = _clamp_window(window_days)
    end = _now()
    start = end - timedelta(days=days)
    return days, start, end, start.replace(tzinfo=timezone.utc).timestamp()


def _workflow_requests(db: DbSession, capability: str, start, end) -> list:
    from usage.models import AIRequest
    return (db.query(AIRequest)
            .filter(AIRequest.capability == capability,
                    AIRequest.created_at >= start, AIRequest.created_at <= end)
            .order_by(AIRequest.created_at.desc())
            .limit(MAX_EVENT_ROWS).all())


def _activity_events(db: DbSession, event_types: tuple, start_epoch: float) -> list[dict]:
    from data_plane.models import LearningEvent
    rows = (db.query(LearningEvent)
            .filter(LearningEvent.event_type.in_(event_types),
                    LearningEvent.occurred_at >= start_epoch)
            .order_by(LearningEvent.occurred_at.desc())
            .limit(MAX_EVENT_ROWS).all())
    out = []
    for row in rows:
        try:
            payload = json.loads(row.item_snapshot_json or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            payload["_event_type"] = row.event_type
            out.append(payload)
    return out


def _agent_step_aggregate(events: list[dict]) -> dict:
    """Iterations / executions / model steps, counted from the stored code-free traces."""
    iterations = executions = model_steps = 0
    credits = 0
    statuses: dict[str, int] = {}
    stop_reasons: dict[str, int] = {}
    error_categories: dict[str, int] = {}
    for payload in events:
        event_type = payload.get("_event_type")
        if event_type == "programming_agent_started":
            continue
        status = str(payload.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        reason = str(payload.get("reason") or payload.get("error_category") or "").strip()
        if reason:
            stop_reasons[reason] = stop_reasons.get(reason, 0) + 1
        if payload.get("error_category"):
            category = str(payload["error_category"])
            error_categories[category] = error_categories.get(category, 0) + 1
        for step in payload.get("steps") or []:
            if not isinstance(step, dict):
                continue
            action = str(step.get("action") or "")
            if action == STEP_PROPOSE_PATCH:
                iterations += 1
            if "tests" in step:
                executions += 1
            if step.get("ai_request_id"):
                model_steps += 1
            if isinstance(step.get("credits"), int):
                credits += step["credits"]
    return {
        "runs_finished": sum(statuses.values()),
        "by_status": dict(sorted(statuses.items())),
        "iterations": iterations,
        "executions": executions,
        "model_steps": model_steps,
        "step_credits": credits,
        "stop_reasons": dict(sorted(stop_reasons.items(), key=lambda item: (-item[1], item[0]))),
        "error_categories": dict(sorted(error_categories.items(),
                                        key=lambda item: (-item[1], item[0]))),
    }


def build_workflow_operations(db: DbSession, *, window_days: int = 30) -> dict:
    """Every advanced workflow in ONE read: calls, outcome, latency, credits, failure category."""
    days, start, end, start_epoch = _window(window_days)
    workflows: dict[str, dict] = {}

    for key, spec in WORKFLOWS.items():
        rows = _workflow_requests(db, spec["capability"], start, end)
        bucket = _empty_bucket()
        latencies: list[int] = []
        failure_categories: dict[str, int] = {}
        for row in rows:
            bucket["requests"] += 1
            status = str(row.status or "")
            if status == "settled":
                bucket["success"] += 1
            elif status == "released":
                bucket["failure"] += 1
            elif status == "denied":
                bucket["denied"] += 1
            elif status == "reconciliation_pending":
                bucket["held"] += 1
            else:
                bucket["in_flight"] += 1
            latency = _latency_ms(row)
            if latency is not None:
                latencies.append(latency)
                bucket["latency_samples"] += 1
            if isinstance(row.estimated_credits, int):
                bucket["estimated_credits"] += row.estimated_credits
            if isinstance(row.actual_credits, int):
                bucket["actual_credits"] += row.actual_credits
            if status in ("released", "reconciliation_pending"):
                category = str(row.error_category or "unspecified")
                failure_categories[category] = failure_categories.get(category, 0) + 1

        events = _activity_events(db, spec["activity_events"], start_epoch)
        activity: dict = {}
        for event_type in spec["activity_events"]:
            count = sum(1 for item in events if item.get("_event_type") == event_type)
            activity[event_type] = count
        if spec["agent_steps"]:
            activity["agent"] = _agent_step_aggregate(events)

        workflows[key] = {
            "label": spec["label"],
            "capability": spec["capability"],
            "calls": _finish(bucket),
            "latency": {
                "samples": len(latencies),
                "avg_ms": (int(round(sum(latencies) / len(latencies))) if latencies else None),
                "max_ms": (max(latencies) if latencies else None),
            },
            "credits": {
                "estimated_total": bucket["estimated_credits"],
                "actual_total": bucket["actual_credits"],
            },
            "failure_by_category": dict(sorted(failure_categories.items(),
                                               key=lambda item: (-item[1], item[0]))),
            "activity": activity,
        }

    return {
        "scope": "platform",
        "window_days": days,
        "window_start": start.isoformat(),
        "generated_at": end.isoformat(),
        "workflows": workflows,
        "privacy": {
            "never_returns": ["prompt", "response_text", "source_code", "patch_text",
                              "learner_content", "user_id", "username", "filesystem_path"],
            "failure_detail": "normalized error category only",
            "aggregate_only": True,
        },
    }


# ---------------------------------------------------------------- per-run detail (P6 §C)
#
# The evidence read for the agent-trace decision: ONE run's durable trace, reconstructed from
# the stores that already exist. Nothing is written and no new table is consulted.

def build_agent_run_detail(db: DbSession, run_id: str) -> dict:
    """ONE debug-agent run: its canonical events + the per-step ``ai_requests`` rows.

    Restart recovery is the POINT of this read: both halves are committed independently of the
    process that produced them, so the run can be read back after a backend restart with the
    same fidelity — per-step status, latency, credits, provider/model, and the exercise's own
    test result per execution step.
    """
    from data_plane.models import LearningEvent
    from usage.models import AIRequest

    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("run_id_required")

    events = (db.query(LearningEvent)
              .filter(LearningEvent.event_type.in_(WORKFLOWS["programming_agent"]["activity_events"]),
                      LearningEvent.source_attempt_id == run_id)
              .order_by(LearningEvent.occurred_at.asc()).all())

    trace: list[dict] = []
    run_status = None
    stopped_reason = None
    exercise_id = None
    language = None
    for row in events:
        try:
            payload = json.loads(row.item_snapshot_json or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if row.event_type == "programming_agent_started":
            exercise_id = payload.get("exercise_id")
            language = payload.get("language")
            continue
        run_status = payload.get("status") or run_status
        stopped_reason = payload.get("reason") or payload.get("error_category") or stopped_reason
        trace = payload.get("steps") or trace
        exercise_id = payload.get("exercise_id") or exercise_id
        language = payload.get("language") or language

    # Per-step accounting rows. The agent derives each step's request_id from the run id
    # (`{run_id}:{index}:{action}`), so the whole workflow's cost and latency are addressable
    # per step from `ai_requests` alone — no step table is needed to recover them.
    step_rows = (db.query(AIRequest)
                 .filter(AIRequest.request_id.like(f"{run_id}:%"))
                 .order_by(AIRequest.request_id.asc()).all())
    steps = [{
        "request_id": row.request_id,
        "capability": row.capability,
        "status": row.status,
        "provider": row.provider,
        "model": row.model,
        "latency_ms": _latency_ms(row),
        "estimated_credits": row.estimated_credits,
        "actual_credits": row.actual_credits,
        "error_category": row.error_category,
    } for row in step_rows]

    return {
        "agent_run_id": run_id,
        "found": bool(events) or bool(step_rows),
        "exercise_id": exercise_id,
        "language": language,
        "run_status": run_status,
        "stopped_reason": stopped_reason,
        "trace": trace,                    # code-free: action / status / latency / tests / size
        "model_steps": len(steps),
        "steps": steps,
        "durable_sources": ["learning_events:programming_agent_*", "ai_requests"],
        "privacy": {
            "returns": ["step index/action/status", "latency_ms", "credits",
                        "ai request ids", "normalized test results", "patch SIZE"],
            "never_returns": ["source_code", "patch_text", "prompt", "response_text"],
        },
    }
