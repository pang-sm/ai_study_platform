"""Router V1 — deterministic, explainable model selection.

V1 inputs: capability + tier + budget + QUALITY + COST + LATENCY + AVAILABILITY.
NO personalization, NO online learning from feedback: nothing about a learner's preferences or
past ratings enters a selection.

Selection is deterministic for the same (policy, inputs, budget, health) state. Every decision
carries a REASON CODE and the candidate pool it chose from, so a model choice can be explained
after the fact (see the ``ai_called`` event, which carries the same fields).

Availability is the ONE runtime input: a model whose provider has been failing is skipped while
at least one healthy candidate remains (``ai.health``), and the decision records what was
skipped. If EVERY candidate is degraded the router falls back to the full candidate list —
trying a degraded model is strictly better than refusing a learner their answer, and the
decision says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from usage.capabilities import check_capability_permission

from . import cost
from .health import registry as health_registry
from .pool import POOL_VERSION, qualified_models_for

ROUTER_VERSION = "router_v1"

# Closed vocabulary of SELECTION reason codes (observability, not policy).
REASON_ONLY_CANDIDATE = "only_qualified_candidate"
REASON_CHEAPEST = "cheapest_qualified_within_budget"
REASON_EXPLICIT = "explicit_model"


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
    # ---- Router V1 additions (all observable, none required by a caller) ----
    router_version: str = ROUTER_VERSION
    reason_code: str = ""
    quality_class: str | None = None
    latency_class: str | None = None
    cost_profile: str | None = None
    estimated_credits: int | None = None
    candidate_pool: list[dict] = field(default_factory=list)
    skipped_degraded: list[str] = field(default_factory=list)
    degraded_fallback: bool = False

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
            "router_version": self.router_version,
            "reason_code": self.reason_code,
            "quality_class": self.quality_class,
            "latency_class": self.latency_class,
            "cost_profile": self.cost_profile,
            "estimated_credits": self.estimated_credits,
            "candidate_pool": self.candidate_pool,
            "skipped_degraded": self.skipped_degraded,
            "degraded_fallback": self.degraded_fallback,
        }


def _candidate_view(entry, estimate: dict | None) -> dict:
    """One candidate, in the user-safe vocabulary the pool already exposes."""
    return {
        "provider": entry.provider,
        "model": entry.model,
        "quality_class": entry.quality_class,
        "cost_profile": entry.cost_profile,
        "latency_class": entry.latency_class,
        "estimated_credits": (estimate or {}).get("credits"),
    }


def _split_degraded(entries: list) -> tuple[list, list[str]]:
    """(usable, skipped) — degraded models are skipped only when something healthy is left."""
    if not entries:
        return [], []
    health = health_registry()
    healthy = [e for e in entries if not health.is_degraded(e.provider, e.model)]
    if not healthy:
        return entries, []          # everything is degraded → try anyway, and say so
    skipped = [e.model for e in entries if e not in healthy]
    return healthy, skipped


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

    candidates, skipped_degraded = _split_degraded(candidates)

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
    if explicit_model is not None:
        reason_code = REASON_EXPLICIT
    elif len(budget_fits) == 1:
        reason_code = REASON_ONLY_CANDIDATE
    else:
        reason_code = REASON_CHEAPEST
    return RouterDecision(
        ok=True,
        provider=entry.provider,
        model=entry.model,
        reason=reason,
        policy_version=POOL_VERSION,
        pool_candidates=candidate_names,
        budget_compatible=True,
        reason_code=reason_code,
        quality_class=entry.quality_class,
        latency_class=entry.latency_class,
        cost_profile=entry.cost_profile,
        estimated_credits=est.get("credits"),
        candidate_pool=[_candidate_view(e, s) for e, s in budget_fits],
        skipped_degraded=skipped_degraded,
        degraded_fallback=bool(skipped_degraded == [] and candidates
                               and all(health_registry().is_degraded(e.provider, e.model)
                                       for e in candidates)),
    )


def ordered_candidates(tier: str, capability: str,
                       explicit_model: str | None = None,
                       input_tokens: int = 0,
                       expected_output_tokens: int | None = None,
                       available_budget: int | None = None):
    """Ordered budget-compatible qualified candidates: [(ModelPoolEntry, estimate), ...].

    Cheapest first (cross-provider fallback order). Used by the orchestrator so a
    retriable primary failure can fall back to the next qualified model — never to an
    unqualified one. Models whose provider is currently degraded go LAST rather than being
    removed: a fallback chain that ends at a degraded model still beats an empty chain.
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
    health = health_registry()
    candidates = sorted(candidates,
                        key=lambda e: health.is_degraded(e.provider, e.model))

    out = []
    for e in candidates:
        est = cost.estimate_credits(e.provider, e.model, input_tokens,
                                    expected_output_tokens, capability=capability)
        if not est["ok"]:
            continue  # pricing missing → skip (fail closed)
        if available_budget is None or est["credits"] <= available_budget:
            out.append((e, est))
    return out
