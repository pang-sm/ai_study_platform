"""STEP 7C-P hardening: provider-aware reservation (no live API).

Guards the class of bug found live on Ark: ``max_tokens`` does NOT bound a thinking
model's billable output, so a reservation computed from the visible answer alone
underestimates real cost and lets a request slip past the usage budget.
"""
import dataclasses

import pytest

from ai import cost
from ai.orchestrator import AIOrchestrator
from ai.providers import FakeProvider
from models import User
from usage import service

# Live-measured on Ark, doubao-agent, max_tokens=64: completion 1504 (reasoning 1465).
# The visible answer was 68 characters; the billable output was 22x the request limit.
ARK_MEASURED_WORST_COMPLETION_TOKENS = 1504


def _make_user(session, username, tier="advanced") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        service.activate_subscription(session, u.id, tier, 30)
    return u


def _messages(text="hello"):
    return [{"role": "user", "content": text}]


def _drain_weekly_to(session, user_id, remaining):
    budget = service.get_or_create_budget(session, user_id, "weekly")
    budget.settled_amount = budget.budget_amount - remaining
    session.commit()


# ---- A1: ordinary (non-thinking) models keep the existing rule ----

def test_ordinary_model_reserves_requested_output_only():
    r = cost.estimate_credits("deepseek", "deepseek-flash", 1000, 200,
                              capability="tutor.chat")
    assert r["ok"] is True
    assert r["expected_output_tokens"] == 200
    assert r["reasoning_reserved_tokens"] == 0
    assert r["thinking"] is None  # provider exposes no thinking switch


def test_ordinary_model_falls_back_to_capability_expectation():
    policy = cost.cost_policy_for("deepseek", "deepseek-flash")
    assert policy.reservation_output_tokens("tutor.chat", None) == \
        cost.EXPECTED_OUTPUT_TOKENS["tutor.chat"]


# ---- A1/A3: thinking models reserve a conservative reasoning allowance ----

def _thinking_policy(**overrides):
    base = dict(provider="x", model="y", supports_thinking_control=True,
                reasoning_billing=cost.REASONING_UNBOUNDED,
                reasoning_reserve_tokens=2048,
                thinking_capabilities=("programming.debug",))
    base.update(overrides)
    return cost.ModelCostPolicy(**base)


def test_thinking_capability_adds_conservative_reasoning_reserve():
    p = _thinking_policy()
    assert p.reservation_output_tokens("programming.debug", 200) == 200 + 2048
    # a capability the policy does not opt in stays on the ordinary rule
    assert p.reservation_output_tokens("tutor.chat", 200) == 200
    assert p.request_thinking("programming.debug") is True
    assert p.request_thinking("tutor.chat") is False


def test_thinking_reserve_strictly_exceeds_visible_only_estimate():
    p = _thinking_policy()
    with_reserve = p.reservation_output_tokens("programming.debug", 200)
    p_bounded = dataclasses.replace(p, reasoning_billing=cost.REASONING_BOUNDED)
    assert with_reserve > p_bounded.reservation_output_tokens("programming.debug", 200)


def test_conservative_reserve_covers_ark_measured_worst_case():
    # This is the regression the policy exists for: 64 requested, 1504 billed.
    p = cost.cost_policy_for("doubao", "doubao-agent")
    reserved = p.reservation_output_tokens("programming.debug", 64)
    assert reserved >= ARK_MEASURED_WORST_COMPLETION_TOKENS


def test_unverified_model_fails_conservative():
    """The headline rule: no evidence must never be read as 'bounded'."""
    p = cost.cost_policy_for("nobody", "nothing")
    assert p.reasoning_billing == cost.REASONING_UNVERIFIED
    assert p.supports_thinking_control is False
    assert p.reasoning_may_exceed_max_tokens("tutor.chat") is True
    assert p.reservation_output_tokens("tutor.chat", 100) == 100 + p.reasoning_reserve_tokens


def test_unverified_model_cannot_be_estimated_as_zero_reasoning():
    r = cost.estimate_credits("nobody", "nothing", 100, 100, capability="tutor.chat")
    # pricing is missing for an unknown model → fails closed before any of this
    assert r["ok"] is False and r["reason"] == "pricing_missing"


# ---- A2 evidence: measured Ark behaviour is what the policy encodes ----

def test_doubao_general_runs_thinking_off_in_production():
    # 6/6 on the calibration benchmark with thinking OFF (and with it ON at ~8x the
    # output tokens), so production takes the bounded path for every capability.
    p = cost.cost_policy_for("doubao", "doubao-general")
    assert p.supports_thinking_control is True
    assert p.reasoning_billing == cost.REASONING_UNBOUNDED
    for capability in ("tutor.chat", "question.explain", "material.qa",
                       "question.generate", "programming.explain", "programming.debug"):
        assert p.request_thinking(capability) is False
        assert p.reservation_output_tokens(capability, 200) == 200


def test_doubao_general_reservation_equals_requested_output():
    r = cost.estimate_credits("doubao", "doubao-general", 410, 800, capability="tutor.chat")
    assert r["ok"] is True
    assert r["expected_output_tokens"] == 800
    assert r["reasoning_reserved_tokens"] == 0
    assert r["thinking"] is False
    assert r["credits"] > 0


def test_doubao_agent_reservation_includes_reasoning_reserve():
    p = cost.cost_policy_for("doubao", "doubao-agent")
    assert p.request_thinking("programming.debug") is True
    r = cost.estimate_credits("doubao", "doubao-agent", 350, 800,
                              capability="programming.debug")
    assert r["thinking"] is True
    assert r["reasoning_reserved_tokens"] == p.reasoning_reserve_tokens
    assert r["expected_output_tokens"] == 800 + p.reasoning_reserve_tokens


def test_ark_thinking_budget_parameter_is_not_relied_on():
    # Live probe: {"thinking": {"type": "enabled", "budget_tokens": 32}} still produced
    # 1308 reasoning tokens — the field is accepted and ignored, so the policy must
    # never treat it as a hard cap (it is not part of the policy surface at all).
    assert not hasattr(cost.ModelCostPolicy, "reasoning_budget_tokens")
    assert cost.cost_policy_for("doubao", "doubao-general").reasoning_billing == \
        cost.REASONING_UNBOUNDED


# ---- NON_ARK_REASONING_BILLING_VALIDATION (live probe 2026-09-16, fixed prompt,
# max_tokens=64, provider-default temperature) ----

_BOUNDED_MODELS = [
    ("deepseek", "deepseek-v4-pro"),      # completion 64 == max_tokens, reasoning 64
    ("deepseek", "deepseek-flash"),       # completion 64 == max_tokens, reasoning 64
    ("glm", "glm-5"),                     # completion 64 == max_tokens, reasoning 64
    ("glm", "glm-5.3-flash"),             # completion 64 == max_tokens, reasoning 64
    ("kimi", "kimi-k2.6"),                # completion 64 == max_tokens, reasoning 63
    ("minimax", "MiniMax-M3"),            # 64 == 64 and 512 == 512 (thinking inline)
    ("minimax", "MiniMax-M2.7-highspeed"),  # 64 == 64; 453 <= 512 (natural stop)
]


@pytest.mark.parametrize("provider,model", _BOUNDED_MODELS)
def test_max_tokens_bounds_billable_completion_for_verified_models(provider, model):
    p = cost.cost_policy_for(provider, model)
    assert p.reasoning_billing == cost.REASONING_BOUNDED
    assert p.reasoning_may_exceed_max_tokens("programming.debug") is False
    assert p.reservation_output_tokens("programming.debug", 64) == 64
    # no thinking switch is sent to these providers
    assert p.request_thinking("programming.debug") is None


def test_qwen_is_unbounded_and_keeps_thinking_on():
    """Option B for Qwen: disabling thinking was measured to cost quality."""
    for model in ("qwen3.8-flash", "qwen3.8-max"):
        p = cost.cost_policy_for("qwen", model)
        assert p.reasoning_billing == cost.REASONING_UNBOUNDED
        assert p.supports_thinking_control is True
        assert p.thinking_default_on is True
        # thinking stays on → the conservative reserve applies to every capability
        for capability in ("tutor.chat", "question.generate", "programming.debug"):
            assert p.request_thinking(capability) is True
            assert p.reasoning_may_exceed_max_tokens(capability) is True
            assert p.reservation_output_tokens(capability, 64) == 64 + p.reasoning_reserve_tokens


def test_qwen_reservation_covers_measured_overshoot():
    # max_tokens=64 but 452 completion tokens actually billed (qwen3.8-flash).
    QWEN_MEASURED_WORST_COMPLETION_TOKENS = 452
    p = cost.cost_policy_for("qwen", "qwen3.8-flash")
    assert p.reservation_output_tokens("tutor.chat", 64) >= \
        QWEN_MEASURED_WORST_COMPLETION_TOKENS


def test_every_production_pool_model_has_a_verified_reasoning_verdict():
    """No production model may rely on the fail-conservative default by accident."""
    from ai import pool
    unverified = [
        (e.provider, e.model) for e in pool.QUALIFIED_POOL
        if cost.cost_policy_for(e.provider, e.model).reasoning_billing ==
        cost.REASONING_UNVERIFIED
    ]
    assert unverified == [], f"production models without a verified verdict: {unverified}"


# ---- A4: settlement against the reservation ----

def test_actual_below_reservation_releases_difference(db_session):
    u = _make_user(db_session, "rv1")
    orch = AIOrchestrator(provider_factory=lambda name: FakeProvider(
        provider="doubao", model="doubao-general", behavior="success", output_tokens=100))
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model="doubao-general", max_tokens=2000)
    assert result.ok is True and result.status == "settled"
    assert result.estimated_credits > result.actual_credits

    summary = service.usage_summary(db_session, u.id)
    weekly = summary["periods"]["weekly"]
    assert weekly["reserved"] == 0                 # reservation fully resolved
    assert weekly["settled"] == result.actual_credits


def test_actual_equal_to_reservation_settles_exactly(db_session):
    u = _make_user(db_session, "rv2")
    orch = AIOrchestrator(provider_factory=lambda name: FakeProvider(
        provider="doubao", model="doubao-general", behavior="success", output_tokens=2000))
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model="doubao-general", max_tokens=2000)
    assert result.ok is True and result.status == "settled"
    assert result.actual_credits == result.estimated_credits


def test_actual_above_reservation_is_never_silently_absorbed(db_session):
    u = _make_user(db_session, "rv3")
    # provider bills far more output than the request limited itself to
    orch = AIOrchestrator(provider_factory=lambda name: FakeProvider(
        provider="doubao", model="doubao-general", behavior="success", output_tokens=9000))
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model="doubao-general", max_tokens=64)
    assert result.status == "reconciliation_pending"
    assert result.error_category == "reservation_overage"
    assert result.content is None                  # not served as if nothing happened
    assert result.actual_credits is None           # never settled as if it were fine

    from usage.models import AIRequest
    req = (db_session.query(AIRequest)
           .filter(AIRequest.request_id == result.request_id).first())
    assert req.error_category == "reservation_overage"


# ---- A5: Advanced weekly budget cannot be bypassed by under-reserved reasoning ----

def test_weekly_budget_rejects_before_any_provider_call(db_session):
    u = _make_user(db_session, "rv4")
    _drain_weekly_to(db_session, u.id, 1)          # a sliver is left

    calls = []

    def factory(name):
        calls.append(name)
        return FakeProvider(provider=name)

    orch = AIOrchestrator(provider_factory=factory)
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model="doubao-general", max_tokens=2000)
    assert result.ok is False
    assert result.status == "denied"
    assert calls == []                             # rejected BEFORE the provider call


def test_thinking_reserve_cannot_bypass_weekly_budget(db_session, monkeypatch):
    """The core regression: reasoning tokens were under-reserved, so an expensive
    thinking request fitted into a budget that could not actually pay for it."""
    u = _make_user(db_session, "rv5")

    visible_only = cost.estimate_credits("doubao", "doubao-general", 2, 200,
                                         capability="programming.debug")

    base = cost.cost_policy_for("doubao", "doubao-general")
    thinking = dataclasses.replace(base, thinking_capabilities=("programming.debug",))
    monkeypatch.setitem(cost._COST_POLICIES, ("doubao", "doubao-general"), thinking)

    with_reserve = cost.estimate_credits("doubao", "doubao-general", 2, 200,
                                         capability="programming.debug")
    assert with_reserve["credits"] > visible_only["credits"]  # reserved grew

    # the sliver fits the visible-only estimate but not the conservative one
    _drain_weekly_to(db_session, u.id, 3)
    calls = []

    def factory(name):
        calls.append(name)
        return FakeProvider(provider=name)

    orch = AIOrchestrator(provider_factory=factory)
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model="doubao-general", max_tokens=200)
    assert result.ok is False
    assert result.status == "denied"
    assert result.error_category == "budget_incompatible"
    assert calls == []


def test_advanced_has_no_daily_cap_but_is_weekly_guarded(db_session):
    u = _make_user(db_session, "rv6")
    summary = service.usage_summary(db_session, u.id)
    assert summary["periods"]["daily"]["budget"] is None      # no membership daily cap
    assert summary["periods"]["weekly"]["budget"] == service.WEEKLY_BUDGET["advanced"]


# ---- §7: each Advanced model is individually proven budget-safe ----
#
# Two halves, both required: the reservation must be >= the largest billable output
# the model can produce (bounded models: verified completion <= max_tokens), AND the
# budget gate must reject before the provider is ever called.

def _reserve_for(provider, model, capability="programming.debug", max_tokens=2000):
    return cost.estimate_credits(provider, model, 2, max_tokens, capability=capability)


@pytest.mark.parametrize("provider,model", [
    ("deepseek", "deepseek-v4-pro"),
    ("minimax", "MiniMax-M3"),
    ("glm", "glm-5"),
    ("kimi", "kimi-k2.6"),
])
def test_advanced_model_cannot_bypass_weekly_budget(db_session, provider, model):
    est = _reserve_for(provider, model)
    assert est["ok"] is True and est["credits"] > 1

    u = _make_user(db_session, f"wb_{provider}_{model}".replace(".", "_")[:30])
    _drain_weekly_to(db_session, u.id, 1)          # less than a single request costs

    calls = []

    def factory(name):
        calls.append(name)
        return FakeProvider(provider=name, model=model)

    orch = AIOrchestrator(provider_factory=factory)
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model=model, max_tokens=2000)
    assert result.ok is False
    assert result.status == "denied"
    assert calls == []                             # rejected BEFORE any provider call
    assert result.router and result.router["budget_compatible"] is False


@pytest.mark.parametrize("provider,model", [
    ("deepseek", "deepseek-v4-pro"),
    ("minimax", "MiniMax-M3"),
    ("glm", "glm-5"),
    ("kimi", "kimi-k2.6"),
])
def test_advanced_model_reservation_is_an_upper_bound(provider, model):
    """The reservation must be >= the largest billable completion the model can emit.

    For a REASONING_BOUNDED model that bound is verified: live probes showed
    completion_tokens never exceeded max_tokens, so reserving max_tokens output tokens
    (plus the prompt) cannot be short.
    """
    p = cost.cost_policy_for(provider, model)
    assert p.reasoning_may_exceed_max_tokens("programming.debug") is False
    est = _reserve_for(provider, model)
    assert est["expected_output_tokens"] == 2000   # == requested max_tokens
    assert est["reasoning_reserved_tokens"] == 0

    # worst case the model can actually bill, priced at the same registry
    worst = cost.estimate_credits(provider, model, 2, 2000,
                                  capability="programming.debug")
    assert est["cost_cny"] >= worst["cost_cny"]
    assert est["credits"] >= worst["credits"]


@pytest.mark.parametrize("model", ["doubao-general", "doubao-agent"])
def test_doubao_models_have_a_cost_policy(model):
    p = cost.cost_policy_for("doubao", model)
    assert p.provider == "doubao" and p.model == model
    assert p.reasoning_reserve_tokens > 0


# ---- policy → request wiring (reserved and billed governed by one rule) ----

class _CapturingProvider(FakeProvider):
    def __init__(self, seen, **kwargs):
        super().__init__(**kwargs)
        self._seen = seen

    def complete(self, spec):
        self._seen.append(spec.thinking)
        return super().complete(spec)


def test_orchestrator_sends_policy_thinking_switch(db_session):
    u = _make_user(db_session, "rv7")
    seen = []
    orch = AIOrchestrator(provider_factory=lambda name: _CapturingProvider(
        seen, provider="doubao", model="doubao-general", behavior="success",
        output_tokens=50))
    result = orch.execute(db_session, u.id, "programming.debug", _messages(),
                          explicit_model="doubao-general", max_tokens=200)
    assert result.ok is True
    # doubao-general production runs thinking OFF — sent explicitly, not left to default
    assert seen == [False]


def test_orchestrator_sends_no_thinking_switch_for_plain_models(db_session):
    u = _make_user(db_session, "rv8")
    seen = []
    orch = AIOrchestrator(provider_factory=lambda name: _CapturingProvider(
        seen, provider="deepseek", model="deepseek-flash", behavior="success",
        output_tokens=50))
    orch.execute(db_session, u.id, "tutor.chat", _messages(),
                 explicit_model="deepseek-flash", max_tokens=200)
    # providers without a thinking switch must not receive one
    assert seen == [None]
