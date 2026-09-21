"""Admin ops API (P6) — AI operations, workflow operations and the feature-flag switches.

Admin-only, read-mostly, and AGGREGATED: these endpoints answer "how is the advanced AI layer
doing" without ever returning a prompt, a response, a learner's content or a per-learner row.
The ONE write surface is the feature-flag switch, which is audit-logged like every other admin
setting change.

    GET  /admin/ai-operations/summary            AI accounting aggregates + router + feedback
    GET  /admin/workflow-operations/summary      per-workflow aggregates
    GET  /admin/workflow-operations/agent-runs/{run_id}
                                                 ONE debug-agent run's durable trace
    GET  /admin/feature-flags                    the seven advanced-workflow kill switches
    PUT  /admin/feature-flags                    set one or more modes (OFF/INTERNAL/TIER/ALL)

Permission model: the read surfaces reuse the EXISTING ``ai_logs.view`` grant (operator and
auditor already hold it) and the flag switch uses the EXISTING ``feature_flags.manage`` grant
(super_admin only). No new permission is introduced.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from ops import ai_operations, feature_flags, workflow_operations

router = APIRouter(prefix="/admin", tags=["admin-ops"])

READ_PERMISSION = "ai_logs.view"
FLAG_PERMISSION = "feature_flags.manage"


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy: main imports this router at startup
    return get_current_user(request, db)


def _require_permission(user, permission: str):
    from main import require_admin_permission
    return require_admin_permission(user, permission)


# ---------------------------------------------------------------- response shapes
#
# The TOP-LEVEL shape is declared (and therefore validated on every response); the buckets
# inside are dynamic aggregates keyed by capability / model / provider / status, which is why
# they stay `dict`. Declaring the keys here is what makes the frozen contract in
# `P6_API_CONTRACT_FREEZE.md` a real fingerprint instead of an opaque `dict`.

class AIOperationsSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    scope: str
    window_days: int
    window_start: str
    generated_at: str
    requests: dict
    latency: dict
    credits: dict
    by_capability: dict
    by_model: dict
    by_provider: dict
    by_tier: dict
    by_service_namespace: dict
    router: dict
    feedback: dict
    availability: dict
    bounded: dict
    privacy: dict


class WorkflowOperationsSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    scope: str
    window_days: int
    window_start: str
    generated_at: str
    workflows: dict
    privacy: dict


class AgentRunDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_run_id: str
    found: bool
    exercise_id: int | None = None
    language: str | None = None
    run_status: str | None = None
    stopped_reason: str | None = None
    trace: list[dict] = Field(default_factory=list)
    model_steps: int = 0
    steps: list[dict] = Field(default_factory=list)
    durable_sources: list[str] = Field(default_factory=list)
    privacy: dict


class FeatureFlagItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature: str
    label: str
    capability: str | None = None
    scope: str
    mode: str
    stored: bool
    default_mode: str
    updated_by: str | None = None
    updated_at: str | None = None


class FeatureFlagList(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[FeatureFlagItem]
    modes: list[str]
    default_mode: str
    semantics: dict
    never_changes: list[str]


class FeatureFlagUpdateResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    updated: dict
    previous: dict
    modes: dict


# ---------------------------------------------------------------- AI operations


@router.get("/ai-operations/summary", response_model=AIOperationsSummary)
def ai_operations_summary(window_days: int = Query(ai_operations.DEFAULT_WINDOW_DAYS, ge=1,
                                                   le=ai_operations.MAX_WINDOW_DAYS),
                          db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """Platform-wide AI operations, AGGREGATED ONLY — requests, outcomes, latency, credits,
    capability/model/provider breakdown, router fallbacks, degraded availability and the
    learners' own ratings. No prompt, no response, no learner identity."""
    _require_permission(current_user, READ_PERMISSION)
    return ai_operations.build_ai_operations(db, window_days=window_days)


# ---------------------------------------------------------------- workflow operations


@router.get("/workflow-operations/summary", response_model=WorkflowOperationsSummary)
def workflow_operations_summary(window_days: int = Query(30, ge=1,
                                                         le=ai_operations.MAX_WINDOW_DAYS),
                                db: Session = Depends(get_db),
                                current_user=Depends(_require_user)):
    """Per-workflow aggregates for the advanced workflows: calls, success/failure, latency,
    credits and the NORMALIZED failure category. The debug agent also reports iterations and
    executions actually used, counted from its stored code-free step traces."""
    _require_permission(current_user, READ_PERMISSION)
    return workflow_operations.build_workflow_operations(db, window_days=window_days)


@router.get("/workflow-operations/agent-runs/{run_id}", response_model=AgentRunDetail)
def agent_run_detail(run_id: str, db: Session = Depends(get_db),
                     current_user=Depends(_require_user)):
    """ONE debug-agent run, read back from the durable stores that already exist.

    Both halves are committed independently of the process that produced them: the run's
    canonical events carry the code-free per-step trace, and each model step has its own
    ``ai_requests`` row under a deterministic id. This is the read that makes restart
    recovery, detail read and debugging answerable WITHOUT a per-step table.
    """
    _require_permission(current_user, READ_PERMISSION)
    try:
        detail = workflow_operations.build_agent_run_detail(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not detail["found"]:
        raise HTTPException(status_code=404, detail="agent run not found")
    return detail


# ---------------------------------------------------------------- feature flags


class FeatureFlagUpdate(BaseModel):
    """A mode per feature. The vocabulary is closed; an unknown key or mode is rejected."""

    model_config = ConfigDict(extra="forbid")

    flags: dict[str, str] = Field(min_length=1)


@router.get("/feature-flags", response_model=FeatureFlagList)
def list_feature_flags(db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """The advanced-workflow kill switches, with the mode each one is actually in."""
    _require_permission(current_user, FLAG_PERMISSION)
    return {
        "items": feature_flags.describe_flags(db),
        "modes": list(feature_flags.MODES),
        "default_mode": feature_flags.DEFAULT_MODE,
        "semantics": {
            "OFF": "closed to everyone",
            "INTERNAL": "admin accounts only (and admins may exercise it without a paid tier)",
            "TIER": "no flag-level restriction — the unified subscription policy decides",
            "ALL": ("the capability-permission step is granted for this feature; usage budget "
                    "and settlement still apply to every call"),
        },
        "never_changes": ["usage budget", "credits settlement", "subscription rows",
                          "the learner's recorded tier"],
    }


@router.put("/feature-flags", response_model=FeatureFlagUpdateResult)
def update_feature_flags(payload: FeatureFlagUpdate, db: Session = Depends(get_db),
                         current_user=Depends(_require_user)):
    """Set one or more modes. Takes effect on the NEXT request — no deploy, no restart.

    The change is audit-logged with its old and new values, exactly like an admin setting.
    """
    _require_permission(current_user, FLAG_PERMISSION)
    try:
        result = feature_flags.set_modes(db, payload.flags, updated_by=current_user.username)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"未知功能开关: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from main import _write_audit_log
    changed = result["updated"]
    _write_audit_log(
        current_user.username,
        f"更新功能开关 ({len(changed)}项)",
        db,
        target_type="feature_flags",
        detail=str(list(changed.keys())),
        details={"changed": changed, "previous": result["previous"]},
    )
    return result
