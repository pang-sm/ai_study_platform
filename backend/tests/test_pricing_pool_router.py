"""STEP 7C-P: pricing registry + qualified model pool + Router V0 tests (no live API)."""
from ai import cost, pool
from ai.gateway import ProviderUsage
from ai.pricing import PRICING_VERSION, compute_cost_cny, get_pricing
from ai.router import select_model


# ---- B39: pricing ----

def test_different_models_produce_different_estimates():
    a = cost.estimate_credits("deepseek", "deepseek-flash", 2000, 1500)
    b = cost.estimate_credits("deepseek", "deepseek-v4-pro", 2000, 1500)
    assert a["ok"] and b["ok"]
    assert b["cost_cny"] > a["cost_cny"]
    assert b["credits"] >= a["credits"]


def test_input_output_pricing_differentiated():
    p = get_pricing("deepseek", "deepseek-flash")
    assert p.input_cny_per_1m != p.output_cny_per_1m
    assert p.output_cny_per_1m > p.input_cny_per_1m


def test_pricing_version_retained():
    p = get_pricing("deepseek", "deepseek-flash")
    assert p.verified is True
    assert p.source == "OFFICIAL_DOC"
    assert PRICING_VERSION == "v3"


def test_peak_offpeak_not_flattened():
    p = get_pricing("deepseek", "deepseek-flash")
    assert p.peak_input_cny_per_1m is not None
    assert p.peak_input_cny_per_1m > p.input_cny_per_1m  # peak = 2x off-peak
    # compute differs under peak
    off = compute_cost_cny(p, 1000, 0, 0, is_peak=False)
    peak = compute_cost_cny(p, 1000, 0, 0, is_peak=True)
    assert peak > off


def test_legacy_alias_resolves_to_canonical():
    # deepseek-chat / deepseek-reasoner are legacy aliases, not canonical ids
    assert get_pricing("deepseek", "deepseek-chat").model == "deepseek-flash"
    assert get_pricing("deepseek", "deepseek-reasoner").model == "deepseek-v4-pro"


def test_unknown_model_fails_closed():
    assert get_pricing("deepseek", "nope-model") is None
    r = cost.estimate_credits("deepseek", "nope-model", 100, 100)
    assert r["ok"] is False and r["reason"] == "pricing_missing"


def test_currency_normalization_controlled():
    # 1 credit ≈ ¥0.01 → ¥1.00 = 100 credits
    assert cost.normalize_cost_to_credits(1.0) == 100
    assert cost.normalize_cost_to_credits(0.01) == 1
    assert cost.normalize_cost_to_credits(0.0) == 0
    assert cost.normalize_cost_to_credits(None) == 0


def test_compute_cost_cached_not_additive():
    p = get_pricing("deepseek", "deepseek-flash")
    cached = compute_cost_cny(p, 1000, 0, 1000)
    miss = compute_cost_cny(p, 1000, 0, 0)
    assert cached >= 0
    assert cached < miss


# ---- B40: qualified pool ----

def test_free_sees_free_pool_only():
    opts = pool.user_visible_options("free", "tutor.chat")
    models = {o["model"] for o in opts}
    assert "deepseek-flash" in models
    assert "deepseek-v4-pro" not in models  # premium hidden from Free


def test_cross_provider_fallback_present():
    # free tutor.chat has both DeepSeek (primary) and Qwen (fallback)
    entries = pool.qualified_models_for("free", "tutor.chat")
    providers = {e.provider for e in entries}
    assert "deepseek" in providers and "qwen" in providers


def test_advanced_sees_high_cost_option():
    opts = pool.user_visible_options("advanced", "programming.debug")
    models = {o["model"] for o in opts}
    assert "deepseek-v4-pro" in models
    assert any(o.get("high_cost") for o in opts)


def test_premium_model_hidden_from_free():
    assert "deepseek-v4-pro" not in [e.model for e in pool.qualified_models_for("free", "question.generate")]


def test_unknown_capability_fails_closed():
    assert pool.qualified_models_for("free", "bogus.cap") == []


def test_coding_models_for_programming():
    # standard programming.debug must have a coding-capable model
    models = [e.model for e in pool.qualified_models_for("standard", "programming.debug")]
    assert "MiniMax-M2.7-highspeed" in models
    assert "qwen3.8-max" in models


# ---- B41: Router V0 ----

def test_router_deterministic():
    d1 = select_model("free", "tutor.chat", input_tokens=100, expected_output_tokens=200, available_budget=100)
    d2 = select_model("free", "tutor.chat", input_tokens=100, expected_output_tokens=200, available_budget=100)
    assert d1.model == d2.model and d1.provider == d2.provider


def test_router_capability_mismatch_rejected():
    d = select_model("free", "bogus.cap")
    assert d.ok is False
    assert d.reason in ("unknown_capability", "no_qualified_model_available")


def test_router_tier_mismatch_rejected():
    # Free cannot get a model for a capability it is not entitled to (question.generate)
    d = select_model("free", "question.generate")
    assert d.ok is False and d.reason == "tier_not_permitted"


def test_router_budget_incompatible_skipped():
    d = select_model("advanced", "report.generate", input_tokens=10000,
                     expected_output_tokens=8000, available_budget=1)
    assert d.ok is False and d.reason == "budget_incompatible"


def test_router_explicit_qualified_model():
    d = select_model("advanced", "programming.debug", explicit_model="deepseek-v4-pro",
                     input_tokens=100, expected_output_tokens=200, available_budget=1000)
    assert d.ok and d.model == "deepseek-v4-pro" and d.reason == "user_explicit"


def test_router_explicit_unqualified_model_rejected():
    d = select_model("free", "tutor.chat", explicit_model="deepseek-v4-pro")
    assert d.ok is False and d.reason == "model_not_qualified"
