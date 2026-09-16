"""Pricing Registry (STEP 7C-P) — provider/model → token pricing, versioned CONFIG.

Prices are CNY per 1,000,000 (1M) tokens, split by input / cached input / output.
``verified`` distinguishes official-provider pricing from conservative ceilings. An
unverified model is a CANDIDATE and is only auto-routable with a conservative cost
ceiling (SSOT §23) — never treated as verified.

Peak/off-peak is NOT flattened: off-peak is the default, peak is stored separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PRICING_VERSION = "v3"
USD_CNY = 7.2  # matches the codebase's existing deepseek cost conversion


@dataclass(frozen=True)
class ModelPricing:
    provider: str
    model: str
    input_cny_per_1m: float      # off-peak cache-miss input (default)
    output_cny_per_1m: float     # off-peak output
    cached_input_cny_per_1m: float = 0.0
    peak_input_cny_per_1m: float | None = None   # peak (if provider has peak pricing)
    peak_output_cny_per_1m: float | None = None
    peak_cached_input_cny_per_1m: float | None = None
    currency: str = "CNY"
    effective_from: str = "2026-09-01"
    verified: bool = False
    source: str = "UNVERIFIED"   # OFFICIAL_DOC / CONSERVATIVE_CEILING / UNVERIFIED
    verified_at: str | None = None


def _usd_per_1m(usd: float) -> float:
    return round(usd * USD_CNY, 4)


# STEP 7C-P — calibrated against live account discovery + official pricing (2026-09-16).
_PRICING = {
    # DeepSeek — official (api-docs.deepseek.com/quick_start/pricing). Off-peak = half
    # of peak; peak hours 01:00-04:00 & 06:00-10:00 UTC Mon-Fri.
    ("deepseek", "deepseek-flash"): ModelPricing(
        "deepseek", "deepseek-flash",
        input_cny_per_1m=_usd_per_1m(0.15), output_cny_per_1m=_usd_per_1m(0.60),
        cached_input_cny_per_1m=_usd_per_1m(0.003),
        peak_input_cny_per_1m=_usd_per_1m(0.30), peak_output_cny_per_1m=_usd_per_1m(1.20),
        peak_cached_input_cny_per_1m=_usd_per_1m(0.006),
        effective_from="2026-08-13", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),
    ("deepseek", "deepseek-v4-pro"): ModelPricing(
        "deepseek", "deepseek-v4-pro",
        input_cny_per_1m=_usd_per_1m(0.66), output_cny_per_1m=_usd_per_1m(1.98),
        cached_input_cny_per_1m=_usd_per_1m(0.022),
        peak_input_cny_per_1m=_usd_per_1m(1.32), peak_output_cny_per_1m=_usd_per_1m(3.96),
        peak_cached_input_cny_per_1m=_usd_per_1m(0.044),
        effective_from="2026-08-13", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),

    # Qwen / DashScope — official RMB (developer.aliyun.com pricing, Beijing region).
    ("qwen", "qwen3.8-flash"): ModelPricing(
        "qwen", "qwen3.8-flash", 0.8, 2.7, 0.1,
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),
    ("qwen", "qwen3.8-max"): ModelPricing(
        "qwen", "qwen3.8-max", 12.0, 36.0, 1.5,
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),

    # Moonshot / Kimi — official USD (platform.kimi.ai/docs/pricing/chat).
    ("kimi", "kimi-k2.6"): ModelPricing(
        "kimi", "kimi-k2.6", _usd_per_1m(0.95), _usd_per_1m(4.00), _usd_per_1m(0.16),
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),
    ("kimi", "kimi-k2.7-code"): ModelPricing(
        "kimi", "kimi-k2.7-code", _usd_per_1m(0.95), _usd_per_1m(4.00), _usd_per_1m(0.19),
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),

    # Zhipu / GLM — official RMB (docs.bigmodel.cn/cn/guide/start/pricing).
    ("glm", "glm-5.3-flash"): ModelPricing(
        "glm", "glm-5.3-flash", 0.8, 2.8, 0.0,
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),
    ("glm", "glm-5.3"): ModelPricing(
        "glm", "glm-5.3", 8.0, 28.0, 0.0,
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),
    ("glm", "glm-5"): ModelPricing(
        "glm", "glm-5", 4.0, 18.0, 0.0,
        effective_from="2026-09-01", verified=True, source="OFFICIAL_DOC",
        verified_at="2026-09-16"),

    # MiniMax — official per-model pricing not confirmable this round → conservative
    # cost CEILING (unverified). Model IDs are case-sensitive ("MiniMax-M3").
    ("minimax", "minimax-m3"): ModelPricing(
        "minimax", "MiniMax-M3", 6.0, 30.0, 0.0, source="CONSERVATIVE_CEILING"),
    ("minimax", "minimax-m2.7-highspeed"): ModelPricing(
        "minimax", "MiniMax-M2.7-highspeed", 1.0, 5.0, 0.0, source="CONSERVATIVE_CEILING"),
}

# Legacy aliases → canonical model (older STEP 7C names are no longer canonical).
_LEGACY_ALIASES = {
    "deepseek-chat": "deepseek-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-flash",
    "qwen-flash": "qwen3.8-flash",
    "qwen-max": "qwen3.8-max",
    "qwen-plus": "qwen3.8-flash",
    "qwen-turbo": "qwen3.8-flash",
    "qwen3-coder-plus": "qwen3.8-max",
    "qwen-long": "qwen3.8-max",
}


def get_pricing(provider: str, model: str) -> ModelPricing | None:
    """Return pricing for a provider/model (resolving legacy aliases), or None."""
    model = _norm(model)
    model = _LEGACY_ALIASES.get(model, model)
    return _PRICING.get((_norm(provider), model))


def pricing_for_model(model: str) -> ModelPricing | None:
    model = _norm(model)
    model = _LEGACY_ALIASES.get(model, model)
    for (_, m), p in _PRICING.items():
        if m == model:
            return p
    return None


def resolve_price(pricing: ModelPricing, is_peak: bool) -> tuple[float, float, float]:
    """Return (input, cached_input, output) CNY/1M for off-peak or peak."""
    if is_peak and pricing.peak_input_cny_per_1m is not None:
        return (pricing.peak_input_cny_per_1m,
                pricing.peak_cached_input_cny_per_1m or 0.0,
                pricing.peak_output_cny_per_1m or pricing.output_cny_per_1m)
    return (pricing.input_cny_per_1m, pricing.cached_input_cny_per_1m,
            pricing.output_cny_per_1m)


def compute_cost_cny(pricing: ModelPricing, input_tokens: int,
                     output_tokens: int, cached_input_tokens: int = 0,
                     is_peak: bool = False) -> float:
    """Provider currency cost from usage. Cached input is a subset of input, never
    additive (matches the existing deepseek semantic)."""
    inp = max(0, int(input_tokens or 0))
    cached = min(max(0, int(cached_input_tokens or 0)), inp)
    out = max(0, int(output_tokens or 0))
    in_p, cached_p, out_p = resolve_price(pricing, is_peak)
    cost = ((inp - cached) * in_p + cached * cached_p + out * out_p) / 1_000_000
    return round(cost, 8)


def _norm(value) -> str:
    return (value or "").strip().lower()
