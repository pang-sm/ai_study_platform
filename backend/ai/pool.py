"""Qualified Model Pool (STEP 7C-P FINAL) — CONFIG, not a SQL table.

Calibrated 2026-09-16 from live account discovery + smoke tests + official pricing +
ZHIXUE_MODEL_POOL_CALIBRATION_V1 Stage 2. POOL_QUALIFICATION_LEVEL = FINAL.

Selection principle: minimum quality gate first (Stage-2 pass), then budget + cost
preference (NOT cheapest-only). Cross-provider fallback across 5 providers.
"""
from __future__ import annotations

from dataclasses import dataclass

from .pricing import pricing_for_model

POOL_VERSION = "v3"
POOL_QUALIFICATION_LEVEL = "FINAL"

ALL_CAPABILITIES = (
    "tutor.chat", "question.explain", "material.qa", "question.generate",
    "programming.debug", "programming.explain", "planning.generate", "report.generate",
)


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

    def tier_allows(self, tier: str) -> bool:
        return tier in self.eligible_tiers

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def has_pricing(self) -> bool:
        return pricing_for_model(self.model) is not None

    def pricing_verified(self) -> bool:
        p = pricing_for_model(self.model)
        return bool(p and p.verified)


# Stage-2 pass counts (ZHIXUE_MODEL_POOL_CALIBRATION_V1, 6 cases):
#   qwen3.8-flash 6/6 · qwen3.8-max 6/6 · glm-5.3-flash 5/6 · MiniMax 5/6
#   deepseek 4/6 · glm-5 4/6 · kimi-k2.6 4/6 · (kimi-k2.7-code 2/6 → excluded)
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
        "pricing_verified": entry.pricing_verified(),
    }


def qualified_models_for(tier: str, capability: str) -> list[ModelPoolEntry]:
    """Return the qualified model set for a capability + tier (available only)."""
    tier = (tier or "").strip().lower()
    out = [
        e for e in QUALIFIED_POOL
        if e.available and e.tier_allows(tier) and e.supports(capability)
    ]
    # Deterministic order: verified first, cheapest first, premium/thinking last.
    return sorted(out, key=lambda e: (e.high_cost, not e.pricing_verified(),
                                      e.cost_profile, e.provider, e.model))


def user_visible_options(tier: str, capability: str) -> list[dict]:
    """Auto + a small qualified list. Never the full registry."""
    return [_entry_dict(e) for e in qualified_models_for(tier, capability)]
