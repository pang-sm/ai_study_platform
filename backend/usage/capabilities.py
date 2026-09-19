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
