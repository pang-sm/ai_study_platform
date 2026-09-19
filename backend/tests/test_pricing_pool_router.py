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
    assert PRICING_VERSION == "v4"


def test_doubao_pricing_is_verified_official():
    # Ark rows are registered against the canonical alias; the vendor model the price
    # belongs to is recorded separately for audit.
    for alias, upstream in (("doubao-general", "doubao-seed-2.1-pro"),
                            ("doubao-agent", "doubao-seed-evolving")):
        p = get_pricing("doubao", alias)
        assert p is not None and p.verified is True
        assert p.source == "OFFICIAL_DOC"
        assert p.upstream_model == upstream
        assert (p.input_cny_per_1m, p.output_cny_per_1m,
                p.cached_input_cny_per_1m) == (6.0, 30.0, 1.2)
        # Ark publishes no peak/off-peak schedule for these models
        assert p.peak_input_cny_per_1m is None


def test_doubao_cost_estimable():
    r = cost.estimate_credits("doubao", "doubao-general", 2000, 1500)
    assert r["ok"] is True and r["credits"] > 0


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


def test_knowledge_structure_inherits_question_generate_pool():
    for tier in ("standard", "advanced"):
        generated = [(entry.provider, entry.model) for entry in
                     pool.qualified_models_for(tier, "question.generate")]
        structured = [(entry.provider, entry.model) for entry in
                      pool.qualified_models_for(tier, "knowledge.structure")]
        assert structured == generated


def test_coding_models_for_programming():
    # standard programming.debug must have a coding-capable model
    models = [e.model for e in pool.qualified_models_for("standard", "programming.debug")]
    assert "MiniMax-M2.7-highspeed" in models
    assert "qwen3.8-max" in models


def test_pool_version_v4():
    assert pool.POOL_VERSION == "v4"


def test_all_six_providers_present_in_qualified_pool():
    # "all six integrated" is the hard requirement; NOT "every capability shows six".
    providers = {e.provider for e in pool.QUALIFIED_POOL}
    assert providers == {"deepseek", "qwen", "glm", "minimax", "kimi", "doubao"}


def test_doubao_entries_are_advanced_and_priced():
    for model, upstream in (("doubao-general", "doubao-seed-2.1-pro"),
                            ("doubao-agent", "doubao-seed-evolving")):
        entries = [e for e in pool.QUALIFIED_POOL if e.model == model]
        assert len(entries) == 1
        e = entries[0]
        assert e.provider == "doubao"
        assert e.eligible_tiers == ("advanced",)
        assert e.high_cost is True and e.thinking is True
        assert e.has_pricing() and e.pricing_verified()
        assert get_pricing("doubao", model).upstream_model == upstream


def test_doubao_agent_is_programming_scoped():
    # screened by the agent probe, not the general paper: only probed capabilities
    agent = next(e for e in pool.QUALIFIED_POOL if e.model == "doubao-agent")
    assert set(agent.capabilities) == {"programming.debug", "programming.explain"}
    internal = pool.qualified_models_for("advanced", "programming.debug",
                                         include_non_production=True)
    assert "doubao-agent" in [e.model for e in internal]


def test_doubao_not_in_free_or_standard():
    for tier in ("free", "standard"):
        for cap in pool.ALL_CAPABILITIES:
            models = [e.model for e in pool.qualified_models_for(tier, cap)]
            assert "doubao-general" not in models, (tier, cap)
            assert "doubao-agent" not in models, (tier, cap)


# ---- B: deployment eligibility (collaboration-reward endpoint isolation) ----

def test_production_pool_excludes_non_production_endpoint():
    for cap in pool.ALL_CAPABILITIES:
        models = [e.model for e in pool.qualified_models_for("advanced", cap)]
        assert "doubao-agent" not in models, cap


def test_non_production_endpoint_is_reachable_for_internal_tooling(monkeypatch):
    internal = pool.qualified_models_for("advanced", "programming.debug",
                                         include_non_production=True)
    assert "doubao-agent" in [e.model for e in internal]
    # The benchmark/probe path builds its adapter straight from the factory, so it
    # reaches the internal endpoint without production eligibility ever being asked.
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_ENDPOINT_DOUBAO_AGENT", "ep-agent-test")
    from ai.orchestrator import default_provider_factory
    adapter = default_provider_factory("doubao")
    assert adapter.model_map["doubao-agent"] == "ep-agent-test"


def test_production_candidate_system_still_covers_all_six_providers():
    # Part C: isolating the collaboration endpoint must NOT drop Doubao (or anyone)
    # from production model selection.
    providers = set()
    for cap in pool.ALL_CAPABILITIES:
        providers |= {e.provider for e in pool.qualified_models_for("advanced", cap)}
    assert providers == {"deepseek", "qwen", "doubao", "kimi", "glm", "minimax"}
    assert "doubao-general" in [e.model for e in
                                pool.qualified_models_for("advanced", "tutor.chat")]


def test_deployment_eligibility_metadata_is_explicit():
    general = next(e for e in pool.QUALIFIED_POOL if e.model == "doubao-general")
    agent = next(e for e in pool.QUALIFIED_POOL if e.model == "doubao-agent")
    assert general.deployment_eligibility == pool.PRODUCTION
    assert general.production_eligible() is True
    assert agent.deployment_eligibility == pool.BENCHMARK_ONLY
    assert agent.production_eligible() is False
    # every other entry is production by default
    for e in pool.QUALIFIED_POOL:
        if e.model != "doubao-agent":
            assert e.production_eligible() is True, e.model


def test_explicit_model_cannot_bypass_production_eligibility():
    d = select_model("advanced", "programming.debug", explicit_model="doubao-agent",
                     input_tokens=100, expected_output_tokens=200, available_budget=100000)
    assert d.ok is False and d.reason == "model_not_qualified"


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
