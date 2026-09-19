"""Qualified Model Pool (STEP 7C-P FINAL) — CONFIG, not a SQL table.

Calibrated 2026-09-16 from live account discovery + smoke tests + official pricing +
ZHIXUE_MODEL_POOL_CALIBRATION_V1 Stage 2 and the AGENT_CAPABILITY_PROBE.
POOL_QUALIFICATION_LEVEL = FINAL.

Selection principle: minimum quality gate first (Stage-2 pass), then budget + cost
preference (NOT cheapest-only). Cross-provider fallback across all 6 providers.

Doubao is on the Ark endpoint-id model: the pool names the canonical alias
(``doubao-general`` / ``doubao-agent``), and ``ai.secrets`` maps it to the account's
endpoint id at call time — endpoint ids are config, never source.
"""
from __future__ import annotations

from dataclasses import dataclass

from .pricing import pricing_for_model

POOL_VERSION = "v4"
POOL_QUALIFICATION_LEVEL = "FINAL"

# Deployment eligibility (STEP 7C-P hardening). Qualifying a model is not the same as
# clearing it for production: an endpoint whose contract differs from the platform's
# normal data terms must not carry real learner data. Config only — flipping an
# endpoint back to PRODUCTION is a one-field change, never an adapter rewrite.
PRODUCTION = "PRODUCTION"
INTERNAL_ONLY = "INTERNAL_ONLY"
BENCHMARK_ONLY = "BENCHMARK_ONLY"

ALL_CAPABILITIES = (
    "tutor.chat", "question.explain", "material.qa", "question.generate",
    "programming.debug", "programming.explain", "planning.generate", "report.generate",
    "knowledge.structure", "answer.grade",
)

# STEP7G-C2 is deliberately a proxy: structured Course knowledge previews use the
# already qualified question-generation model profile.  This is not a Pool v4
# qualification or benchmark expansion.
KNOWLEDGE_STRUCTURE_PROFILE = "STRUCTURED_GENERATION_PROXY_V1"

# STEP7H1: answer grading (score + feedback for a learner's answer) is its own semantic
# operation, but it is served by the already qualified question.explain profile. Pool v4
# is unchanged and no provider was re-benchmarked for it.
ANSWER_GRADE_PROFILE = "QUESTION_EXPLAIN_PROXY_V1"
CAPABILITY_QUALIFICATION_PROXIES = {
    "knowledge.structure": "question.generate",
    "answer.grade": "question.explain",
}


@dataclass(frozen=True)
class ModelPoolEntry:
    provider: str
    model: str
    eligible_tiers: tuple[str, ...]          # free / standard / advanced
    capabilities: tuple[str, ...]
    cost_profile: str                         # low / mid / high
    quality_class: str                        # basic / standard / premium
    latency_class: str = "normal"             # fast / normal / slow
    available: bool = True
    high_cost: bool = False
    thinking: bool = False                    # reasoning/thinking model → needs max_tokens
    deployment_eligibility: str = PRODUCTION  # PRODUCTION / INTERNAL_ONLY / BENCHMARK_ONLY

    def tier_allows(self, tier: str) -> bool:
        return tier in self.eligible_tiers

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def production_eligible(self) -> bool:
        return self.deployment_eligibility == PRODUCTION

    def has_pricing(self) -> bool:
        return pricing_for_model(self.model) is not None

    def pricing_verified(self) -> bool:
        p = pricing_for_model(self.model)
        return bool(p and p.verified)


# Stage-2 pass counts (ZHIXUE_MODEL_POOL_CALIBRATION_V1, 6 cases):
#   qwen3.8-flash 6/6 · qwen3.8-max 6/6 · doubao-general 6/6 · glm-5.3-flash 5/6
#   MiniMax 5/6 · deepseek 4/6 · glm-5 4/6 · kimi-k2.6 4/6 · (kimi-k2.7-code 2/6 → excluded)
# Agent-native models are screened by AGENT_CAPABILITY_PROBE, not the general paper,
# and are not eliminated for failing general pedagogy cases.
QUALIFIED_POOL: tuple[ModelPoolEntry, ...] = (
    # --- basic / fast (free tier) ---
    ModelPoolEntry(
        "qwen", "qwen3.8-flash",
        eligible_tiers=("free", "standard", "advanced"),
        capabilities=("tutor.chat", "question.explain", "material.qa",
                      "question.generate", "programming.debug", "programming.explain",
                      "planning.generate"),
        cost_profile="low", quality_class="basic", latency_class="fast",
    ),
    ModelPoolEntry(
        "glm", "glm-5.3-flash",
        eligible_tiers=("free", "standard", "advanced"),
        capabilities=("tutor.chat", "question.explain", "material.qa",
                      "programming.explain"),
        cost_profile="low", quality_class="basic", latency_class="fast",
    ),
    ModelPoolEntry(
        "deepseek", "deepseek-flash",
        eligible_tiers=("free", "standard", "advanced"),
        capabilities=("tutor.chat", "question.explain", "material.qa",
                      "question.generate", "programming.explain", "planning.generate"),
        cost_profile="low", quality_class="basic", latency_class="fast",
    ),
    # --- standard ---
    ModelPoolEntry(
        "qwen", "qwen3.8-max",
        eligible_tiers=("standard", "advanced"),
        capabilities=ALL_CAPABILITIES,
        cost_profile="mid", quality_class="premium", latency_class="normal",
    ),
    ModelPoolEntry(
        "minimax", "MiniMax-M2.7-highspeed",
        eligible_tiers=("standard", "advanced"),
        capabilities=("tutor.chat", "question.explain", "material.qa",
                      "question.generate", "programming.debug", "programming.explain"),
        cost_profile="mid", quality_class="standard", latency_class="fast",
    ),
    # --- advanced (reasoning / premium) ---
    ModelPoolEntry(
        "deepseek", "deepseek-v4-pro",
        eligible_tiers=("advanced",),
        capabilities=("question.explain", "question.generate", "programming.debug",
                      "planning.generate", "report.generate"),
        cost_profile="high", quality_class="premium", latency_class="normal",
        high_cost=True, thinking=True,
    ),
    ModelPoolEntry(
        "minimax", "MiniMax-M3",
        eligible_tiers=("advanced",),
        capabilities=("question.explain", "question.generate", "programming.debug",
                      "planning.generate", "report.generate"),
        cost_profile="high", quality_class="premium", latency_class="normal",
        high_cost=True, thinking=True,
    ),
    ModelPoolEntry(
        "glm", "glm-5",
        eligible_tiers=("advanced",),
        capabilities=("question.generate", "programming.debug", "planning.generate",
                      "report.generate"),
        cost_profile="high", quality_class="premium", latency_class="slow",
        high_cost=True, thinking=True,
    ),
    ModelPoolEntry(
        "kimi", "kimi-k2.6",
        eligible_tiers=("advanced",),
        capabilities=("programming.debug", "planning.generate"),
        cost_profile="high", quality_class="premium", latency_class="slow",
        high_cost=True, thinking=True,
    ),
    # --- doubao (Volcengine Ark, endpoint-id) ---
    # general: 6/6 ZHIXUE_MODEL_POOL_CALIBRATION_V1
    ModelPoolEntry(
        "doubao", "doubao-general",
        eligible_tiers=("advanced",),
        capabilities=("tutor.chat", "question.explain", "material.qa",
                      "question.generate", "programming.explain", "programming.debug"),
        cost_profile="high", quality_class="premium", latency_class="slow",
        high_cost=True, thinking=True,
    ),
    # agent: 3/3 AGENT_CAPABILITY_PROBE (programming explanation / debugging /
    # structured instruction following). Screening scope is narrow on purpose — only
    # probed + passed capabilities are claimed.
    #
    # BENCHMARK_ONLY: this specific Ark endpoint is enrolled in 协作奖励计划, which the
    # Volcengine terms describe as an exception to the normal "your submitted content
    # is not used to train foundation models" rule. It therefore must not serve real
    # learner data. It stays qualified so benchmark/internal tooling can use it, and it
    # leaves production routing entirely — the Doubao *provider* is represented in
    # production by doubao-general. A future Seed-Evolving endpoint created WITHOUT the
    # reward plan can be flipped back to PRODUCTION after a fresh smoke/probe; no
    # adapter change is required.
    ModelPoolEntry(
        "doubao", "doubao-agent",
        eligible_tiers=("advanced",),
        capabilities=("programming.debug", "programming.explain"),
        cost_profile="high", quality_class="premium", latency_class="slow",
        high_cost=True, thinking=True,
        deployment_eligibility=BENCHMARK_ONLY,
    ),
)


def _entry_dict(entry: ModelPoolEntry) -> dict:
    return {
        "provider": entry.provider,
        "model": entry.model,
        "eligible_tiers": list(entry.eligible_tiers),
        "capabilities": list(entry.capabilities),
        "cost_profile": entry.cost_profile,
        "quality_class": entry.quality_class,
        "latency_class": entry.latency_class,
        "available": entry.available,
        "high_cost": entry.high_cost,
        "thinking": entry.thinking,
        "deployment_eligibility": entry.deployment_eligibility,
        "pricing_verified": entry.pricing_verified(),
    }


def qualified_models_for(tier: str, capability: str,
                         include_non_production: bool = False) -> list[ModelPoolEntry]:
    """Return the qualified model set for a capability + tier (available only).

    Production by default: only PRODUCTION-eligible entries. Internal / benchmark
    tooling opts in explicitly with ``include_non_production=True`` — the production
    router, orchestrator and user-facing model API never pass it.
    """
    tier = (tier or "").strip().lower()
    capability = CAPABILITY_QUALIFICATION_PROXIES.get(capability, capability)
    out = [
        e for e in QUALIFIED_POOL
        if e.available and e.tier_allows(tier) and e.supports(capability)
        and (include_non_production or e.production_eligible())
    ]
    # Deterministic order: verified first, cheapest first, premium/thinking last.
    return sorted(out, key=lambda e: (e.high_cost, not e.pricing_verified(),
                                      e.cost_profile, e.provider, e.model))


def user_visible_options(tier: str, capability: str) -> list[dict]:
    """Auto + a small qualified list. Never the full registry."""
    return [_entry_dict(e) for e in qualified_models_for(tier, capability)]
