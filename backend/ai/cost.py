"""Cost Engine (STEP 7C) — estimate and normalize provider cost → usage credits.

Usage credits are a normalized representation of expected/actual model cost (NOT a
request count and NOT a fixed per-1000-token amount). Provider currency cost is
preserved separately (ai_cost_records), so nothing is lost.
"""
from __future__ import annotations

from dataclasses import dataclass

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
    "knowledge.structure": 800,  # STEP7G-C2 proxy for question.generate
    "programming.debug": 600,
    "programming.explain": 600,
    "planning.generate": 800,
    "report.generate": 1500,
    # P3A. Sized from the workflow, not from a target: a Deep Study answer is long and
    # reasoned (the endpoint's own default max_tokens is 2400), and one agent step answers
    # with a diagnosis or a whole revised file. Under-reserving here would surface as a
    # reservation overage, so both are deliberately generous.
    "tutor.strong_reasoning": 1500,
    "programming.agent": 900,
    # P3B. A wrong-cause analysis is a structured JSON answer (five fields, each bounded), and
    # a plan adjustment is a bounded list of task changes. Sized from the shape, not a target.
    "wrong_answer.analyze": 700,
    "planning.adjust": 900,
}
DEFAULT_EXPECTED_OUTPUT_TOKENS = 400


# ---- Model cost / reservation policy (STEP 7C-P hardening) ----
#
# A reservation must NOT assume ``max_tokens`` == maximum billable completion. Two
# providers are live-verified to bill output on top of it (see REASONING_* below), so
# the relationship is recorded per model as measured evidence rather than assumed from
# provider family, SDK naming, or documentation style.
#
# ``reasoning_billing`` is the single source of truth:
#   NONE        no billable reasoning at all → ordinary rule
#   BOUNDED     model reasons, but max_tokens caps TOTAL billable completion (verified)
#   UNBOUNDED   model reasons and max_tokens does NOT cap it (verified)
#   UNVERIFIED  no evidence recorded → FAIL CONSERVATIVE (reserve the allowance too)

REASONING_NONE = "NONE"
REASONING_BOUNDED = "BOUNDED"
REASONING_UNBOUNDED = "UNBOUNDED"
REASONING_UNVERIFIED = "UNVERIFIED"

# Conservative per-request allowance used whenever reasoning can escape max_tokens.
# Derived from the largest live sample: 11 Ark thinking-ON calls at
# max_tokens=64/800/2000 gave 397–1608 reasoning tokens (max 1608, doubao-agent);
# 2048 ≈ 1.27x that. Reasoning has no hard cap to derive from — that is the point of a
# conservative ceiling rather than a computed value.
DEFAULT_REASONING_RESERVE_TOKENS = 2048


@dataclass(frozen=True)
class ModelCostPolicy:
    provider: str
    model: str
    reasoning_billing: str = REASONING_UNVERIFIED
    supports_thinking_control: bool = False
    reasoning_reserve_tokens: int = DEFAULT_REASONING_RESERVE_TOKENS
    thinking_capabilities: tuple[str, ...] = ()
    thinking_default_on: bool = False

    def thinking_for(self, capability: str | None) -> bool:
        """Whether this request should run with the model's thinking mode ON."""
        if self.thinking_default_on:
            return True
        if not self.supports_thinking_control:
            return False
        return capability in self.thinking_capabilities

    def request_thinking(self, capability: str | None) -> bool | None:
        """Tri-state value for ``AIRequestSpec.thinking``; None = no switch to send."""
        if not self.supports_thinking_control:
            return None
        return self.thinking_for(capability)

    def reasoning_may_exceed_max_tokens(self, capability: str | None) -> bool:
        """Whether billable output may exceed the reserved ``max_tokens``.

        An unverified model answers True: without evidence, assuming "bounded" is
        exactly the under-reservation this policy exists to prevent.
        """
        if self.reasoning_billing == REASONING_NONE:
            return False
        if self.supports_thinking_control and not self.thinking_for(capability):
            return False  # thinking switched off for this request → output is bounded
        return self.reasoning_billing in (REASONING_UNBOUNDED, REASONING_UNVERIFIED)

    def reservation_output_tokens(self, capability: str | None,
                                  requested_output_tokens: int | None = None) -> int:
        """Billable output to reserve: visible output + unbounded reasoning, if any."""
        base = requested_output_tokens
        if base is None:
            base = EXPECTED_OUTPUT_TOKENS.get(capability or "", DEFAULT_EXPECTED_OUTPUT_TOKENS)
        if self.reasoning_may_exceed_max_tokens(capability):
            return base + self.reasoning_reserve_tokens
        return base


# Every production model is registered EXPLICITLY with the evidence behind its
# reasoning-billing verdict (probe: fixed prompt, max_tokens=64, provider-default
# temperature, 2026-09-16). An unregistered model falls back to REASONING_UNVERIFIED,
# which reserves conservatively — never silently "bounded".
_COST_POLICIES: dict[tuple[str, str], ModelCostPolicy] = {
    # --- UNBOUNDED: max_tokens did not cap billable completion ---
    # Ark: max_tokens=64 → completion 516 (reasoning 488). No usable reasoning cap
    # (budget_tokens is accepted then ignored), so the switch is the only bound.
    # general: 6/6 on the 6-case calibration with thinking OFF and with it ON at ~8x
    # the output tokens → production runs it OFF for every capability.
    ("doubao", "doubao-general"): ModelCostPolicy(
        "doubao", "doubao-general",
        reasoning_billing=REASONING_UNBOUNDED, supports_thinking_control=True,
        thinking_capabilities=(),
    ),
    # agent: reasoning-oriented endpoint for benchmark/internal tooling, where the
    # reasoning is the point → thinking stays ON there, under the conservative reserve.
    ("doubao", "doubao-agent"): ModelCostPolicy(
        "doubao", "doubao-agent",
        reasoning_billing=REASONING_UNBOUNDED, supports_thinking_control=True,
        thinking_capabilities=("programming.debug", "programming.explain"),
    ),
    # Qwen/DashScope: max_tokens=64 → completion 105/452 (flash) and 197/78 (max) —
    # reported reasoning 83/429/174/52, billed inside completion_tokens ON TOP of the
    # cap; `max_tokens` bounds the visible answer only. `enable_thinking=false` bounds
    # it (completion 15/21, no reasoning field reported).
    #
    # Option B, not A: disabling thinking was measured to COST QUALITY here, so Qwen
    # keeps thinking ON under the conservative reserve rather than being switched off.
    # Evidence (gen-json-1, `question.generate`): qwen3.8-max thinking OFF scored
    # 0/3 json_valid at max_tokens=200 and 2/3 at 800, vs 3/3 with thinking ON at both.
    # qwen3.8-flash also failed gen-json-1 in the 6-case run with thinking OFF (though
    # it passed 3/3 in isolation) — no reliable quality-neutral configuration was
    # observed, so neither model is switched off on the strength of five other cases.
    ("qwen", "qwen3.8-flash"): ModelCostPolicy(
        "qwen", "qwen3.8-flash",
        reasoning_billing=REASONING_UNBOUNDED, supports_thinking_control=True,
        thinking_default_on=True,
    ),
    ("qwen", "qwen3.8-max"): ModelCostPolicy(
        "qwen", "qwen3.8-max",
        reasoning_billing=REASONING_UNBOUNDED, supports_thinking_control=True,
        thinking_default_on=True,
    ),

    # --- BOUNDED: max_tokens capped total billable completion (verified) ---
    # DeepSeek: completion 64 == max_tokens 64, reasoning 64, content empty
    # (finish_reason=length) → completion_tokens is composed entirely of reasoning and
    # was capped. Same evidence for deepseek-flash.
    ("deepseek", "deepseek-v4-pro"): ModelCostPolicy(
        "deepseek", "deepseek-v4-pro", reasoning_billing=REASONING_BOUNDED),
    ("deepseek", "deepseek-flash"): ModelCostPolicy(
        "deepseek", "deepseek-flash", reasoning_billing=REASONING_BOUNDED),
    # GLM: completion 64 == 64, reasoning 64, content empty. Same for glm-5.3-flash.
    ("glm", "glm-5"): ModelCostPolicy(
        "glm", "glm-5", reasoning_billing=REASONING_BOUNDED),
    ("glm", "glm-5.3-flash"): ModelCostPolicy(
        "glm", "glm-5.3-flash", reasoning_billing=REASONING_BOUNDED),
    # Kimi: completion 64 == 64, reasoning 63.
    ("kimi", "kimi-k2.6"): ModelCostPolicy(
        "kimi", "kimi-k2.6", reasoning_billing=REASONING_BOUNDED),
    # MiniMax: completion tracked the cap at both 64 and 512 on both models
    # (64/64/64/512, one natural stop at 453 <= 512). M3's thinking arrives inline in
    # the content stream (`<think>…</think>`) and is counted by completion_tokens;
    # M2.7-highspeed reports no reasoning detail at all — either way the billable
    # output is the bounded completion_tokens.
    ("minimax", "MiniMax-M3"): ModelCostPolicy(
        "minimax", "MiniMax-M3", reasoning_billing=REASONING_BOUNDED),
    ("minimax", "MiniMax-M2.7-highspeed"): ModelCostPolicy(
        "minimax", "MiniMax-M2.7-highspeed", reasoning_billing=REASONING_BOUNDED),
}


def cost_policy_for(provider: str, model: str) -> ModelCostPolicy:
    """Reservation policy for a provider/model; unregistered models get the ordinary
    rule (max_tokens bounds billable output, no thinking switch)."""
    key = ((provider or "").strip().lower(), (model or "").strip())
    return _COST_POLICIES.get(key) or ModelCostPolicy(provider=provider, model=model)


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
                     cached_input_tokens: int = 0,
                     capability: str | None = None) -> dict:
    """Estimate normalized credits for a selected model. Fails closed on unknown model.

    ``expected_output_tokens`` is the *visible* output the caller expects; the model's
    cost policy adds any billable reasoning that ``max_tokens`` cannot bound, so the
    reserved amount stays a conservative upper bound.

    Returns a dict (never raises for a pricing miss) so the router/orchestrator can
    surface a clear no_qualified_model / pricing_missing signal instead of guessing.
    """
    pricing = get_pricing(provider, model)
    if pricing is None:
        return {"ok": False, "reason": "pricing_missing", "provider": provider, "model": model}
    policy = cost_policy_for(provider, model)
    out = policy.reservation_output_tokens(capability, expected_output_tokens)
    reserved_reasoning = out - (expected_output_tokens
                                if expected_output_tokens is not None
                                else EXPECTED_OUTPUT_TOKENS.get(
                                    capability or "", DEFAULT_EXPECTED_OUTPUT_TOKENS))
    cost_cny = compute_cost_cny(pricing, input_tokens, out, cached_input_tokens)
    credits = normalize_cost_to_credits(cost_cny)
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "input_tokens": int(input_tokens),
        "expected_output_tokens": int(out),
        "reasoning_reserved_tokens": int(reserved_reasoning),
        "thinking": policy.request_thinking(capability),
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
