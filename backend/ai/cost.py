"""Cost Engine (STEP 7C) — estimate and normalize provider cost → usage credits.

Usage credits are a normalized representation of expected/actual model cost (NOT a
request count and NOT a fixed per-1000-token amount). Provider currency cost is
preserved separately (ai_cost_records), so nothing is lost.
"""
from __future__ import annotations

from .gateway import ProviderUsage
from .pricing import ModelPricing, compute_cost_cny, get_pricing

# 1 credit ≈ ¥0.01 platform model cost (SSOT §6). Kept as the normalization unit;
# provider/model token pricing is a separate concern (ai/pricing.py).
CREDIT_UNIT_CNY = 0.01

# Per-capability expected output tokens (CONFIG). Used only for the estimate step,
# before any provider usage exists. Conservative defaults, not a billing claim.
EXPECTED_OUTPUT_TOKENS = {
    "tutor.chat": 300,
    "question.explain": 500,
    "material.qa": 400,
    "question.generate": 800,
    "programming.debug": 600,
    "programming.explain": 600,
    "planning.generate": 800,
    "report.generate": 1500,
}
DEFAULT_EXPECTED_OUTPUT_TOKENS = 400


def estimate_input_tokens(text: str) -> int:
    """Deterministic local estimate (~2 chars/token for Chinese/mixed). NOT a
    provider-reported count; always tagged as estimated at the usage layer."""
    if not text:
        return 0
    return max(1, len(text) // 2)


def normalize_cost_to_credits(provider_cost_cny: float) -> int:
    """Map provider CNY cost → normalized integer credits (1 credit ≈ ¥0.01)."""
    if provider_cost_cny is None or provider_cost_cny <= 0:
        return 0
    return max(1, int(round(provider_cost_cny / CREDIT_UNIT_CNY)))


def estimate_credits(provider: str, model: str, input_tokens: int,
                     expected_output_tokens: int | None = None,
                     cached_input_tokens: int = 0) -> dict:
    """Estimate normalized credits for a selected model. Fails closed on unknown model.

    Returns a dict (never raises for a pricing miss) so the router/orchestrator can
    surface a clear no_qualified_model / pricing_missing signal instead of guessing.
    """
    pricing = get_pricing(provider, model)
    if pricing is None:
        return {"ok": False, "reason": "pricing_missing", "provider": provider, "model": model}
    out = expected_output_tokens if expected_output_tokens is not None else DEFAULT_EXPECTED_OUTPUT_TOKENS
    cost_cny = compute_cost_cny(pricing, input_tokens, out, cached_input_tokens)
    credits = normalize_cost_to_credits(cost_cny)
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "input_tokens": int(input_tokens),
        "expected_output_tokens": int(out),
        "cost_cny": cost_cny,
        "credits": credits,
        "pricing_version": pricing.effective_from,
    }


def actual_credits_from_usage(provider: str, model: str, usage: ProviderUsage) -> dict:
    """Normalize actual provider usage → cost → credits. Fails closed on unknown model."""
    pricing = get_pricing(provider, model)
    if pricing is None:
        return {"ok": False, "reason": "pricing_missing", "provider": provider, "model": model}
    cost_cny = compute_cost_cny(pricing, usage.input_tokens or 0,
                                usage.output_tokens or 0,
                                usage.cached_input_tokens or 0)
    credits = normalize_cost_to_credits(cost_cny)
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "cost_cny": cost_cny,
        "credits": credits,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "usage_source": usage.usage_source,
        "pricing_version": pricing.effective_from,
    }
