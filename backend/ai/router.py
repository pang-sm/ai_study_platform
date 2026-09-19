"""Router V0 (STEP 7C) — deterministic, explainable model selection.

V0 inputs: capability + tier + budget + availability. NO personalization, NO online
learning, NO quality/cost/latency scoring (those are V1+).

Selection is deterministic for the same (policy, inputs, budget) state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from usage.capabilities import check_capability_permission

from . import cost
from .pool import POOL_VERSION, qualified_models_for


@dataclass(frozen=True)
class RouterDecision:
    ok: bool
    provider: str | None = None
    model: str | None = None
    reason: str = ""
    policy_version: str = POOL_VERSION
    pool_candidates: list[str] = field(default_factory=list)
    budget_compatible: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "model": self.model,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "pool_candidates": self.pool_candidates,
            "budget_compatible": self.budget_compatible,
            "error": self.error,
        }


def _fail(reason: str, error: str, pool_candidates: list[str],
          budget_compatible: bool = False) -> RouterDecision:
    return RouterDecision(ok=False, reason=reason, error=error,
                          pool_candidates=pool_candidates,
                          budget_compatible=budget_compatible)


def select_model(tier: str, capability: str, explicit_model: str | None = None,
                 input_tokens: int = 0, expected_output_tokens: int | None = None,
                 available_budget: int | None = None) -> RouterDecision:
    """Select a qualified model for (capability, tier), optionally honoring budget.

    ``available_budget`` (credits) is the amount the caller can reserve. When set,
    only models whose estimated cost fits are eligible. Explicit user choices are
    still validated against pool membership + availability + budget.
    """
    tier = (tier or "").strip().lower()

    # Tier-permitted gate (capability permission). The router itself enforces
    # entitlement so budget-incompatible callers can never sneak through.
    perm = check_capability_permission(tier, capability)
    if not perm["allowed"]:
        return _fail(perm["reason"], perm["reason"], [])

    candidates = qualified_models_for(tier, capability)
    candidate_names = [e.model for e in candidates]
    if not candidates:
        return _fail("no_qualified_model_available",
                     "no_qualified_model_available", [])

    if explicit_model is not None:
        chosen = next((e for e in candidates if e.model == explicit_model), None)
        if chosen is None:
            return _fail("model_not_qualified",
                         f"model {explicit_model} is not qualified for {capability}/{tier}",
                         candidate_names)
        candidates = [chosen]

    # Budget compatibility: cheapest-first (already sorted in the pool resolver).
    budget_fits = []
    for e in candidates:
        est = cost.estimate_credits(e.provider, e.model, input_tokens,
                                    expected_output_tokens, capability=capability)
        if not est["ok"]:
            continue  # pricing missing → cannot verify cost, skip (fail closed)
        if available_budget is None or est["credits"] <= available_budget:
            budget_fits.append((e, est))

    if not budget_fits:
        return _fail("budget_incompatible",
                     "no qualified model fits the reserved budget",
                     candidate_names, budget_compatible=False)

    entry, est = budget_fits[0]
    reason = "user_explicit" if explicit_model is not None else "auto_recommended"
    return RouterDecision(
        ok=True,
        provider=entry.provider,
        model=entry.model,
        reason=reason,
        policy_version=POOL_VERSION,
        pool_candidates=candidate_names,
        budget_compatible=True,
    )


def ordered_candidates(tier: str, capability: str,
                       explicit_model: str | None = None,
                       input_tokens: int = 0,
                       expected_output_tokens: int | None = None,
                       available_budget: int | None = None):
    """Ordered budget-compatible qualified candidates: [(ModelPoolEntry, estimate), ...].

    Cheapest first (cross-provider fallback order). Used by the orchestrator so a
    retriable primary failure can fall back to the next qualified model — never to an
    unqualified one.
    """
    tier = (tier or "").strip().lower()
    perm = check_capability_permission(tier, capability)
    if not perm["allowed"]:
        return []
    candidates = qualified_models_for(tier, capability)
    if explicit_model is not None:
        chosen = [e for e in candidates if e.model == explicit_model]
        if not chosen:
            return []
        candidates = chosen

    out = []
    for e in candidates:
        est = cost.estimate_credits(e.provider, e.model, input_tokens,
                                    expected_output_tokens, capability=capability)
        if not est["ok"]:
            continue  # pricing missing → skip (fail closed)
        if available_budget is None or est["credits"] <= available_budget:
            out.append((e, est))
    return out
