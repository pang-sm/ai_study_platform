"""Capability Permission (STEP 7B) — MVP tier → capability policy is CONFIG, not a table.

Capability IDs are derived from the CURRENT product AI surface (not provider/model names).
``capability_permission_overrides`` (per-user) is V1 — NOT created this round.

Permission answers ONLY: "is this tier allowed to use this capability?"
It does NOT answer "how many credits remain?" (that is the budget layer).
"""
from __future__ import annotations

POLICY_VERSION = "v1"

# STEP7G-C2: this is a product capability, not a newly benchmarked model task.
# It temporarily uses the question.generate qualification profile; see ai.pool.
KNOWLEDGE_STRUCTURE_PROFILE = "STRUCTURED_GENERATION_PROXY_V1"

# STEP7H1: grading a learner's answer against the reference answer is a distinct
# semantic operation from explaining the question (score + feedback vs explanation).
# Approved by the user as a first-class capability; it temporarily uses the
# question.explain qualification profile — see ai.pool.
ANSWER_GRADE_PROFILE = "QUESTION_EXPLAIN_PROXY_V1"

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
        "knowledge.structure",
        "answer.grade",
    },
    "advanced": {
        "tutor.chat",
        "question.explain",
        "material.qa",
        "question.generate",
        "programming.debug",
        "programming.explain",
        "planning.generate",
        "knowledge.structure",
        "answer.grade",
        "report.generate",
    },
}

ALL_CAPABILITIES = frozenset().union(*CAPABILITY_TIER_POLICY.values())

# Unified tier ordering. Declared HERE (not in service.py) because the ordering is policy:
# every module that compares tiers must compare them the same way.
VALID_TIERS = ("free", "standard", "advanced")
TIER_RANK = {tier: rank for rank, tier in enumerate(VALID_TIERS)}


def normalize_tier(tier) -> str:
    t = (tier or "").strip().lower()
    return t if t in VALID_TIERS else "free"


# Product FEATURE → the capability whose tier permission decides it (CONFIG, like the tier
# policy above). This is the ONLY path from a paid product feature to a tier: a feature is
# opened by the unified subscription's capability permission, never by a second membership
# row that could be activated independently of it (SSOT §4).
#
# ``None`` = a BASE product feature: available on every tier, including Free. It is not a
# missing gate — SSOT §5.1 puts 学习记录 inside the Free learning loop, so ``learning_report``
# deliberately has no capability requirement. It must not be given one by accident.
FEATURE_CAPABILITY = {
    "learning_plan": "planning.generate",
    "learning_report": None,
}


def feature_requirement(feature_key: str) -> str | None:
    """Lowest tier that grants ``feature_key``; ``None`` when the feature is unknown."""
    if feature_key not in FEATURE_CAPABILITY:
        return None
    capability = FEATURE_CAPABILITY[feature_key]
    if capability is None:
        return "free"
    for tier in VALID_TIERS:
        if tier_allows(tier, capability):
            return tier
    return None


def feature_entitlement(tier: str, feature_key: str) -> dict:
    """Resolve one product feature from ONE unified tier. Pure; no database.

    Raises KeyError for an unknown feature so a caller cannot accidentally receive a
    verdict for something the product does not gate.
    """
    required_tier = feature_requirement(feature_key)
    if required_tier is None:
        raise KeyError(feature_key)
    tier = normalize_tier(tier)
    return {
        "allowed": TIER_RANK[tier] >= TIER_RANK[required_tier],
        "feature": feature_key,
        # `current_tier` rather than `tier`: the whole point of the pair is to compare the
        # tier held against the tier required, and a bare `tier` reads as either.
        "current_tier": tier,
        "required_tier": required_tier,
        "required_capability": FEATURE_CAPABILITY[feature_key],
    }


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
