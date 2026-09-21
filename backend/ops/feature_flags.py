"""Feature flags — ops kill switches for the high-risk advanced workflows (P6 §E).

WHY THIS EXISTS
---------------
Each advanced workflow (Deep Study, the programming Debug Agent, the learning report, the
wrong-cause analysis, dynamic planning, adaptive practice, intelligent review) is several
model calls' worth of work behind one endpoint. When one of them misbehaves in production,
closing it must not require a deploy: an operator sets a mode and the workflow refuses on the
NEXT request, while every other workflow keeps running.

MODES
-----
    OFF        closed to everyone
    INTERNAL   only admin accounts may reach it (canary)
    TIER       no flag-level restriction — the frozen Subscription → Capability Permission
               policy decides. DEFAULT: an unset flag changes nothing.
    ALL        additionally GRANTS the capability-permission step for this one feature, so
               every authenticated learner can reach it.

WHAT NO MODE EVER CHANGES
-------------------------
The usage chain. ``ALL`` (and ``INTERNAL`` for an admin) overrides the ENTITLEMENT step only:
estimate → reserve → execute → settle still runs for every call, an exhausted budget still
refuses (429), ``ai_requests.tier`` still records the learner's REAL tier, and no subscription
row is ever written. A granted call is recorded as granted (``entitlement_grant``) in its
audit fact so it is countable later.

STORAGE
-------
One row per flag in the EXISTING ``system_settings`` key/value table, under the
``feature_flag.<name>`` key namespace. No new table, and no second configuration system: the
whole flag set is readable and writable through ``/admin/feature-flags``.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession

logger = logging.getLogger("ops.feature_flags")

OFF = "OFF"
INTERNAL = "INTERNAL"
TIER = "TIER"
ALL = "ALL"
MODES = (OFF, INTERNAL, TIER, ALL)
DEFAULT_MODE = TIER

SETTING_KEY_PREFIX = "feature_flag."

# The seven high-risk advanced capabilities, with the AI capability each one bills through.
# ``capability=None`` marks a deterministic workflow: it has no entitlement step to grant, so
# only OFF / INTERNAL can restrict it (TIER and ALL are identical for it by construction).
FEATURES: dict[str, dict] = {
    "deep_study": {
        "label": "深度研习",
        "capability": "tutor.strong_reasoning",
        "scope": "ai_workflow",
    },
    "programming_agent": {
        "label": "编程调试智能体",
        "capability": "programming.agent",
        "scope": "ai_workflow",
    },
    "learning_report": {
        "label": "学习报告",
        "capability": "report.generate",
        "scope": "ai_workflow",
    },
    "wrong_analysis": {
        "label": "错因分析",
        "capability": "wrong_answer.analyze",
        "scope": "ai_workflow",
    },
    "dynamic_planning": {
        "label": "计划调整",
        "capability": "planning.adjust",
        "scope": "ai_workflow",
    },
    "adaptive_practice": {
        "label": "自适应练习",
        "capability": None,
        "scope": "deterministic_workflow",
    },
    "intelligent_review": {
        "label": "智能复习",
        "capability": None,
        "scope": "deterministic_workflow",
    },
}

FEATURE_FOR_CAPABILITY = {
    spec["capability"]: name for name, spec in FEATURES.items() if spec["capability"]
}


def setting_key(feature: str) -> str:
    return f"{SETTING_KEY_PREFIX}{feature}"


def normalize_mode(value) -> str:
    """Mode values are a closed vocabulary; anything else falls back to the safe default.

    An unreadable flag must never silently OPEN a workflow, and TIER is the mode that defers
    to the subscription policy — so it is the fallback for a missing, empty or corrupt value.
    """
    mode = str(value or "").strip().upper()
    return mode if mode in MODES else DEFAULT_MODE


def require_known_feature(feature: str) -> str:
    if feature not in FEATURES:
        raise KeyError(feature)
    return feature


# ---------------------------------------------------------------- read / write


def get_mode(db: DbSession, feature: str) -> str:
    from models import SystemSetting
    require_known_feature(feature)
    row = (db.query(SystemSetting)
           .filter(SystemSetting.key == setting_key(feature)).first())
    return normalize_mode(row.value if row else None)


def get_modes(db: DbSession) -> dict[str, str]:
    return {feature: get_mode(db, feature) for feature in FEATURES}


def describe_flags(db: DbSession) -> list[dict]:
    """The whole flag set, for the admin read contract."""
    from models import SystemSetting
    rows = {row.key: row for row in db.query(SystemSetting)
            .filter(SystemSetting.key.like(f"{SETTING_KEY_PREFIX}%")).all()}
    items = []
    for feature, spec in FEATURES.items():
        row = rows.get(setting_key(feature))
        mode = normalize_mode(row.value if row else None)
        items.append({
            "feature": feature,
            "label": spec["label"],
            "capability": spec["capability"],
            "scope": spec["scope"],
            "mode": mode,
            "stored": row is not None,
            "default_mode": DEFAULT_MODE,
            "updated_by": row.updated_by if row else None,
            "updated_at": (row.updated_at.isoformat()
                           if row is not None and row.updated_at else None),
        })
    return items


def set_modes(db: DbSession, updates: dict, updated_by: str) -> dict:
    """Set one or more flag modes. Validates EVERY key/value before writing ANY of them."""
    from models import SystemSetting
    from datetime import datetime, timezone

    if not isinstance(updates, dict) or not updates:
        raise ValueError("no_updates")
    validated: dict[str, str] = {}
    for feature, value in updates.items():
        require_known_feature(feature)
        mode = str(value or "").strip().upper()
        if mode not in MODES:
            raise ValueError(f"invalid_mode:{feature}")
        validated[feature] = mode

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    previous: dict[str, str] = {}
    for feature, mode in validated.items():
        key = setting_key(feature)
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        previous[feature] = normalize_mode(row.value if row else None)
        if row is None:
            row = SystemSetting(key=key, description=f"功能开关 {FEATURES[feature]['label']}")
        row.value = mode
        row.updated_by = updated_by
        row.updated_at = now
        db.add(row)
    db.commit()
    return {
        "updated": validated,
        "previous": previous,
        "modes": get_modes(db),
    }


# ---------------------------------------------------------------- enforcement


def decision(db: DbSession, user, feature: str) -> dict:
    """Can THIS caller reach THIS workflow? Never raises; the caller decides."""
    spec = FEATURES[require_known_feature(feature)]
    mode = get_mode(db, feature)
    is_admin = _is_admin(user)
    if mode == OFF:
        return _verdict(feature, spec, mode, allowed=False, reason="feature_disabled",
                        is_admin=is_admin)
    if mode == INTERNAL and not is_admin:
        return _verdict(feature, spec, mode, allowed=False, reason="feature_internal_only",
                        is_admin=is_admin)
    # TIER defers to the subscription policy; ALL additionally grants entitlement (below, at
    # the AI boundary). Neither is a refusal at THIS layer.
    return _verdict(feature, spec, mode, allowed=True, reason="ok", is_admin=is_admin)


def _verdict(feature, spec, mode, *, allowed, reason, is_admin) -> dict:
    grant = mode == ALL or (mode == INTERNAL and is_admin)
    return {
        "feature": feature,
        "mode": mode,
        "allowed": allowed,
        "reason": reason,
        "capability": spec["capability"],
        "entitlement_grant": bool(grant and spec["capability"]),
        "is_admin": is_admin,
    }


def ensure_feature_allowed(db: DbSession, user, feature: str) -> dict:
    """The ONE boundary gate. Call it BEFORE any work (retrieval, execution, model call).

    A refusal happens here, so a closed workflow costs nothing: no chunk is read, no test is
    run and no credit is reserved. The detail carries a machine-readable ``code``.
    """
    verdict = decision(db, user, feature)
    if not verdict["allowed"]:
        raise HTTPException(status_code=403, detail={
            "code": verdict["reason"],
            "feature": feature,
            "mode": verdict["mode"],
            "message": ("该功能当前已关闭" if verdict["mode"] == OFF
                        else "该功能当前仅限内部使用"),
        })
    return verdict


def capability_entitlement_grant(db: DbSession, user_id: int, capability: str) -> dict:
    """The entitlement grant the AI boundary consults when the tier policy DENIES a call.

    Consulted only on the denial path, so an ordinary request pays nothing for it. It grants
    the PERMISSION step for this one capability and nothing else: the usage budget, the
    settlement chain and the learner's recorded tier are untouched. ``gate_tier`` is the
    LOWEST tier that already permits the capability — the granted call is evaluated exactly
    as if the learner held it, never as if they held the top tier.
    """
    feature = FEATURE_FOR_CAPABILITY.get(str(capability or ""))
    if feature is None:
        return {"granted": False, "reason": "no_flag_for_capability"}
    mode = get_mode(db, feature)
    if mode == ALL:
        return {"granted": True, "feature": feature, "mode": mode,
                "gate_tier": minimum_tier_for(capability), "reason": "feature_flag_all"}
    if mode == INTERNAL:
        from models import User
        user = db.query(User).filter(User.id == user_id).first()
        if _is_admin(user):
            return {"granted": True, "feature": feature, "mode": mode,
                    "gate_tier": minimum_tier_for(capability),
                    "reason": "feature_flag_internal_admin"}
    return {"granted": False, "feature": feature, "mode": mode, "reason": "policy_decides"}


def minimum_tier_for(capability: str) -> str | None:
    """The lowest tier whose policy already permits ``capability`` (None when none does)."""
    from usage.capabilities import VALID_TIERS, tier_allows
    return next((tier for tier in VALID_TIERS if tier_allows(tier, capability)), None)


def capability_permitted(db: DbSession, user_id: int, tier: str, capability: str) -> dict:
    """The ONE composition of policy + flag grant, for the surfaces that pre-check.

    The subscription policy answers first. Only when it DENIES is the flag consulted — so a
    normal request never pays for a flag lookup, and a denied one pays exactly once.
    """
    from usage.capabilities import check_capability_permission
    perm = check_capability_permission(tier, capability)
    if perm["allowed"]:
        return {**perm, "entitlement_grant": None}
    grant = capability_entitlement_grant(db, user_id, capability)
    if grant.get("granted"):
        return {**perm, "allowed": True, "reason": grant["reason"],
                "entitlement_grant": grant["mode"]}
    return {**perm, "entitlement_grant": None}


def _is_admin(user) -> bool:
    from main import is_admin_user      # lazy: main imports this module at startup
    return bool(is_admin_user(user))
