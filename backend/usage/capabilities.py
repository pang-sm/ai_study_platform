"""Capability Permission (STEP 7B) — MVP tier → capability policy is CONFIG, not a table.

Capability IDs are derived from the CURRENT product AI surface (not provider/model names).
``capability_permission_overrides`` (per-user) is V1 — NOT created this round.

Permission answers ONLY: "is this tier allowed to use this capability?"
It does NOT answer "how many credits remain?" (that is the budget layer).
"""
from __future__ import annotations

POLICY_VERSION = "v1"

# Tier → allowed capability set (CONFIG). Unknown capability → fail closed.
CAPABILITY_TIER_POLICY = {
    "free": {
        "tutor.chat",
        "question.explain",
        "material.qa",
    },
    "standard": {
        "tutor.chat",
        "question.explain",
        "material.qa",
        "question.generate",
        "programming.debug",
        "programming.explain",
        "planning.generate",
    },
    "advanced": {
        "tutor.chat",
        "question.explain",
        "material.qa",
        "question.generate",
        "programming.debug",
        "programming.explain",
        "planning.generate",
        "report.generate",
    },
}

ALL_CAPABILITIES = frozenset().union(*CAPABILITY_TIER_POLICY.values())


def tier_allows(tier: str, capability: str) -> bool:
    return capability in CAPABILITY_TIER_POLICY.get(tier, set())


def check_capability_permission(tier: str, capability: str) -> dict:
    """Return allowed / tier / capability / reason / policy_version.

    Fail closed on unknown capability (reason=unknown_capability).
    Entitlement (permission) is distinct from budget (credits).
    """
    if capability not in ALL_CAPABILITIES:
        return {
            "allowed": False,
            "tier": tier,
            "capability": capability,
            "reason": "unknown_capability",
            "policy_version": POLICY_VERSION,
        }
    allowed = tier_allows(tier, capability)
    return {
        "allowed": allowed,
        "tier": tier,
        "capability": capability,
        "reason": "ok" if allowed else "tier_not_permitted",
        "policy_version": POLICY_VERSION,
    }
