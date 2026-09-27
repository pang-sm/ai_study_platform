"""AI Orchestrator (STEP 7C-P) — the single place the lifecycle is composed.

    permission → router → estimate → reserve → gateway → actual cost → settle

With cross-provider fallback: a retriable primary failure (provider_unavailable /
timeout / rate_limited / provider_error) falls back to the next qualified model in the
pool — never to an unqualified model, never bypassing budget or tier.

The external provider call is NOT wrapped in a long DB transaction: reserve is committed,
then the provider is called, then settlement is committed.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterator

from sqlalchemy.orm import Session

from core.learning_context import LearningContext

from usage import service as usage_service
from usage.capabilities import check_capability_permission
from usage.models import AIRequest

from . import cost
from .gateway import (AIRequestSpec, ChatMessage, GatewayError, GatewayErrorCategory,
                      GatewayProvider, GatewayResponse, StreamEvent)
from .providers import (
    ArkProvider, DeepSeekProvider, FakeProvider, MiniMaxProvider,
    MoonshotProvider, QwenProvider, ZhipuProvider,
)
from .router import RouterDecision, ordered_candidates, select_model
from .secrets import ark_endpoint_map

logger = logging.getLogger("ai.orchestrator")

DEFAULT_MAX_TOKENS = 2000
MAX_FALLBACK_ATTEMPTS = 3


def is_empty_answer(content) -> bool:
    """Is this provider content NOT an answer?

    The ONE definition: missing, or nothing but whitespace. A provider that returns no text did
    not answer, whatever it reports about the call. Deliberately NOT a length heuristic — ``"0"``,
    ``"是"`` and any other short answer are answers, and treating them as failures would reject
    correct output.
    """
    return not (content or "").strip()

# Orchestrator terminal status → the coarse status carried by an `ai_called` event.
# `already_exists` is absent on purpose: a replayed request_id is not a new call.
_AI_EVENT_STATUS = {
    "settled": "succeeded",
    "released": "failed",
    "reconciliation_pending": "pending",
    "denied": "denied",
}

# Error categories that prove NO billable usage occurred (release full).
_NO_USAGE_CATEGORIES = {"authentication", "invalid_request", "content_policy",
                        "rate_limited", "provider_unavailable"}


def default_provider_factory(name: str) -> GatewayProvider:
    if name == "deepseek":
        return DeepSeekProvider()
    if name == "qwen":
        return QwenProvider()
    if name == "doubao":
        # Canonical alias → Ark endpoint id, from the one shared mapping (ai.secrets).
        return ArkProvider(model_map=ark_endpoint_map())
    if name == "kimi":
        return MoonshotProvider()
    if name == "glm":
        return ZhipuProvider()
    if name == "minimax":
        return MiniMaxProvider()
    if name == "fake":
        return FakeProvider()
    raise GatewayError(GatewayErrorCategory.provider_unavailable,
                       f"unknown provider {name}")


@dataclass
class OrchestratorResult:
    ok: bool
    request_id: str
    capability: str
    tier: str
    status: str = ""              # settled / released / reconciliation_pending / denied
    content: str | None = None
    provider: str | None = None
    model: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    estimated_credits: int | None = None
    actual_credits: int | None = None
    usage: dict | None = None
    router: dict | None = field(default=None)
    # P6: set ONLY when an ops feature flag granted the entitlement step for this call. The
    # recorded tier stays the learner's REAL tier — the grant widens permission, never billing.
    entitlement_grant: dict | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "request_id": self.request_id,
            "capability": self.capability,
            "tier": self.tier,
            "status": self.status,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "estimated_credits": self.estimated_credits,
            "actual_credits": self.actual_credits,
            "usage": self.usage,
            "router": self.router,
            "entitlement_grant": self.entitlement_grant,
        }


@dataclass
class _Attempt:
    """One prepared request: authorised, budgeted, routed and reserved, waiting for a call.

    Shared by the non-streaming and the streaming path — the difference between them is how the
    model's answer is read, never whether the request may run or what it costs.
    """

    request_id: str
    user_id: int
    capability: str
    tier: str
    gate_tier: str
    grant: dict | None
    chat_messages: list
    expected_output: int
    candidates: list
    primary_entry: object
    primary_estimate: dict
    learning_context: LearningContext | None


class AIOrchestrator:
    def __init__(self, provider_factory: Callable[[str], GatewayProvider] | None = None):
        self._provider_factory = provider_factory or default_provider_factory

    def execute(self, db: Session, user_id: int, capability: str,
                messages: list[ChatMessage] | list[dict],
                explicit_model: str | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                request_id: str | None = None,
                learning_context: LearningContext | None = None,
                model_preference: str | None = None,
                thinking: bool | None = None) -> OrchestratorResult:
        """Public boundary: run the lifecycle, then record the terminal fact.

        The `ai_called` event is emitted here rather than at each of the six return
        paths so that every outcome — settled, failed, denied, pending — is recorded by
        one rule (§16). Emission is failure-isolated and happens strictly after the
        AIRequest row has committed.

        ``model_preference`` is a learner-safe CLASS (never a model name). It narrows
        selection; it never widens entitlement or changes billing.
        """
        if learning_context is not None and learning_context.user_id != user_id:
            raise ValueError("LearningContext user_id must match orchestrator user_id")
        result = self._execute(db, user_id, capability, messages,
                               explicit_model=explicit_model, temperature=temperature,
                               max_tokens=max_tokens, request_id=request_id,
                               learning_context=learning_context,
                               model_preference=model_preference, thinking=thinking)
        self._emit_ai_called(db, user_id, result, learning_context=learning_context)
        return result

    @staticmethod
    def _emit_ai_called(db: Session, user_id: int, result: OrchestratorResult,
                        learning_context: LearningContext | None = None) -> None:
        try:
            from learning.records import producers
            status = _AI_EVENT_STATUS.get(result.status)
            if status is None:
                return                     # no new call happened → no event
            username = None
            try:
                from models import User
                user = db.query(User).filter(User.id == user_id).first()
                username = getattr(user, "username", None)
            except Exception:  # noqa: BLE001
                username = None
            # Router V1: the decision travels with the accounting fact, so "which model,
            # chosen why, out of how many" is answerable from the audit stream alone.
            decision = result.router or {}
            grant = result.entitlement_grant or {}
            producers.emit_ai_called(
                user_id=user_id, ai_request_id=result.request_id,
                capability=result.capability, status=status,
                occurred_at=None, provider=result.provider,
                credits=result.actual_credits,
                error_category=result.error_category if status == "failed" else None,
                model=result.model,
                reason_code=decision.get("reason_code"),
                candidate_count=decision.get("candidate_count"),
                quality_class=decision.get("quality_class"),
                latency_class=decision.get("latency_class"),
                router_version=decision.get("router_version"),
                entitlement_grant=(grant.get("mode") if grant.get("granted") else None),
                source_user_ref=username, learning_context=learning_context)
        except Exception as exc:  # noqa: BLE001 — never fail the AI request
            logger.warning("records ai_called hook failed: %s", type(exc).__name__)

    def _prepare(self, db: Session, user_id: int, capability: str,
                 messages: list[ChatMessage] | list[dict],
                 explicit_model: str | None = None,
                 max_tokens: int | None = None,
                 request_id: str | None = None,
                 learning_context: LearningContext | None = None,
                 model_preference: str | None = None):
        """Everything one request needs BEFORE a provider is asked.

        Permission, capability/budget gate, the router's ordered candidates and the single
        reservation — one implementation, because the non-streaming call and the streaming one
        must decide identically: the caller's shape changes how the model's answer is READ, never
        whether the request may run or what it costs.

        Returns ``(attempt, None)`` to proceed, or ``(None, refusal)`` for the denial, duplicate
        and budget answers, which both callers return to their own caller unchanged.
        """
        request_id = request_id or uuid.uuid4().hex
        tier = usage_service.effective_subscription(db, user_id)

        # 1. permission (entitlement, not budget)
        perm = check_capability_permission(tier, capability)
        grant = None
        # P6: the tier every GATING step below is evaluated against. Normally the learner's
        # real tier; when an ops feature flag granted this one capability it is the lowest
        # tier that already permits it. BILLING never uses it: the reservation, the budget
        # caps, the settlement and the recorded tier all stay the learner's REAL tier.
        gate_tier = tier
        if not perm["allowed"]:
            # Consulted only here — on the denial path — so the ordinary request pays nothing
            # for the flag lookup.
            grant = self._feature_flag_grant(db, user_id, capability)
            if not grant["granted"]:
                return None, OrchestratorResult(ok=False, request_id=request_id,
                                                capability=capability, tier=tier, status="denied",
                                                error_category="permission_denied",
                                                error_message=perm["reason"])
            gate_tier = grant.get("gate_tier") or tier

        chat_messages = [m if isinstance(m, ChatMessage)
                         else ChatMessage(role=m["role"], content=m["content"])
                         for m in messages]

        input_text = "".join(m.content for m in chat_messages)
        input_tokens = cost.estimate_input_tokens(input_text)
        expected_output = max_tokens or DEFAULT_MAX_TOKENS
        available = self._available_budget(db, user_id)

        # 2. ordered budget-compatible qualified candidates (cheapest first)
        candidates = ordered_candidates(gate_tier, capability, explicit_model=explicit_model,
                                        input_tokens=input_tokens,
                                        expected_output_tokens=expected_output,
                                        available_budget=available,
                                        preference=model_preference)
        if not candidates:
            decision = select_model(gate_tier, capability, explicit_model=explicit_model,
                                    input_tokens=input_tokens,
                                    expected_output_tokens=expected_output,
                                    available_budget=available,
                                    preference=model_preference)
            return None, OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="denied",
                error_category=decision.reason if decision else "no_qualified_model_available",
                error_message=decision.error if decision else "no_qualified_model_available",
                entitlement_grant=grant,
                router=decision.to_dict() if decision else None)

        primary_entry, primary_estimate = candidates[0]

        # 3. reserve once for the primary (cheapest) estimate
        reservation = usage_service.reserve_credits(
            db, user_id, request_id, capability, primary_estimate["credits"],
            service_namespace=(learning_context.service_namespace.value
                               if learning_context is not None else None),
            context_json=(learning_context.to_dict() if learning_context is not None else None),
            permission_tier=gate_tier)
        if reservation.get("reason") == "already_exists":
            return None, OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="already_exists", error_category="already_exists",
                error_message="request already processed",
                estimated_credits=primary_estimate["credits"],
                entitlement_grant=grant,
                router=self._decision_dict(primary_entry))
        if not reservation["reserved"]:
            return None, OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="denied", error_category="budget_reserve_failed",
                error_message=reservation["reason"],
                estimated_credits=primary_estimate["credits"],
                entitlement_grant=grant,
                router=self._decision_dict(primary_entry))

        self._mark_executing(db, request_id)
        return _Attempt(request_id=request_id, user_id=user_id,
                        capability=capability, tier=tier,
                        gate_tier=gate_tier, grant=grant, chat_messages=chat_messages,
                        expected_output=expected_output, candidates=candidates,
                        primary_entry=primary_entry, primary_estimate=primary_estimate,
                        learning_context=learning_context), None

    def _execute(self, db: Session, user_id: int, capability: str,
                messages: list[ChatMessage] | list[dict],
                explicit_model: str | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                request_id: str | None = None,
                learning_context: LearningContext | None = None,
                model_preference: str | None = None,
                thinking: bool | None = None) -> OrchestratorResult:
        attempt, refusal = self._prepare(
            db, user_id, capability, messages, explicit_model=explicit_model,
            max_tokens=max_tokens, request_id=request_id, learning_context=learning_context,
            model_preference=model_preference)
        if refusal is not None:
            return refusal
        request_id = attempt.request_id
        tier, gate_tier = attempt.tier, attempt.gate_tier
        grant = attempt.grant
        chat_messages = attempt.chat_messages
        expected_output = attempt.expected_output
        candidates = attempt.candidates
        primary_entry, primary_estimate = attempt.primary_entry, attempt.primary_estimate

        # 4. external provider call with cross-provider fallback (outside transaction)
        last_entry, last_error = primary_entry, None
        failed_primary: str | None = None
        # The newest attempt that reached a provider and answered with nothing, if any: the chain
        # keeps going past it, but a request whose every attempt was empty has no answer to show.
        last_empty_response = None
        for index, (entry, estimate) in enumerate(candidates[:MAX_FALLBACK_ATTEMPTS]):
            last_entry = entry
            # The reservation already priced this model's thinking behaviour; the same
            # policy decides the switch actually sent, so reserved and billed output
            # are governed by one rule.
            provider_thinking = thinking if thinking is not None else cost.cost_policy_for(
                entry.provider, entry.model).request_thinking(capability)
            spec = AIRequestSpec(messages=tuple(chat_messages), model=entry.model,
                                 capability=capability, temperature=temperature,
                                 # The SAME ceiling `expected_output` was reserved from, resolved
                                 # (never None). Sending no max_tokens left the provider free to
                                 # produce more output than the reservation covered, and the
                                 # ledger then refused the call as an overage — the learner losing
                                 # an answer the product had already paid for. A reservation is
                                 # only an upper bound if the request it authorises carries it.
                                 max_tokens=expected_output, stream=False, thinking=provider_thinking)
            try:
                provider = self._provider_factory(entry.provider)
                response = provider.complete(spec)
                failure = None
            except GatewayError as exc:
                failure = exc
            except Exception as exc:  # noqa: BLE001 — the provider BOUNDARY only
                # A provider that cannot even be built (a missing credential is the live case) is
                # an unavailable candidate, not a failed request. It used to escape this loop —
                # the catch was narrower than the boundary — and turn the learner's question into
                # a 500 the moment a fallback reached it. The real exception is logged; what
                # travels on is a category, and nothing provider-specific ever reaches a learner.
                logger.exception("provider %s could not answer request %s", entry.provider,
                                 request_id)
                # The message stays category-level: the real exception (which names environment
                # variables and a vendor) belongs in the log above, never in anything a result or
                # an error body carries forward.
                failure = GatewayError(GatewayErrorCategory.provider_unavailable,
                                       f"{entry.provider} adapter unavailable",
                                       entry.provider, retriable=True)

            if failure is not None:
                last_error = failure
                last_empty_response = None
                if index == 0:
                    # Router V1: the failure of the selected model is recorded as such, so a
                    # fallback is never silently reported as if it were the first choice.
                    failed_primary = f"{entry.provider}/{entry.model}"
                # Router V1: EVERY provider failure is an availability signal — including an
                # attempt that the fallback then rescued, which is exactly the case a later
                # selection needs to know about. A failure that was really the REQUEST's fault
                # (invalid request / content policy) says nothing about the provider.
                try:
                    from .health import registry as health_registry
                    if failure.category.value not in ("invalid_request", "content_policy"):
                        health_registry().record_failure(entry.provider, entry.model,
                                                         failure.category.value)
                except Exception:  # noqa: BLE001 — health never blocks a request
                    pass
                if not failure.retriable:
                    break  # permanent error → no fallback
                continue

            if is_empty_answer(response.content):
                # The provider call SUCCEEDED but answered with nothing. That is not a completion:
                # this candidate failed to answer, so the chain moves on to the next qualified
                # one. It must never be returned as an empty success (the caller would then have
                # to invent a failure for a request the ledger already settled), and it must not
                # stop the chain — the learner asked a question, not for a specific model.
                # The call itself was billed, so its cost is recorded before moving on.
                last_error = None
                last_empty_response = response
                if index == 0:
                    failed_primary = f"{entry.provider}/{entry.model}"
                self._record_empty_answer(db, request_id, entry, response)
                continue

            return self._settle_success(
                db, request_id, entry, primary_estimate, response, tier, capability,
                candidate_count=len(candidates), fallback_from=failed_primary,
                entitlement_grant=grant)

        if last_empty_response is not None:
            # Every candidate that reached a provider answered with nothing. The request has no
            # answer to show, so it is NOT settled as a success — the distinction between "the
            # ledger settled this call" and "the learner got an answer" is the whole point here.
            return self._settle_failure(db, request_id, last_entry, primary_estimate,
                                        None, tier, capability,
                                        candidate_count=len(candidates),
                                        entitlement_grant=grant,
                                        error_category="empty_completion",
                                        error_message="every candidate returned an empty completion")

        return self._settle_failure(db, request_id, last_entry, primary_estimate,
                                    last_error, tier, capability,
                                    candidate_count=len(candidates),
                                    entitlement_grant=grant)

    # ---- settlement helpers ----

    def _settle_success(self, db, request_id, entry, reserve_estimate: dict,
                        response, tier: str, capability: str, *,
                        candidate_count: int | None = None,
                        fallback_from: str | None = None,
                        entitlement_grant: dict | None = None) -> OrchestratorResult:
        # Router V1: a real success is an availability signal for this (provider, model).
        try:
            from .health import registry as health_registry
            health_registry().record_success(entry.provider, entry.model)
        except Exception:  # noqa: BLE001 — health is telemetry, never a request blocker
            pass
        actual = cost.actual_credits_from_usage(response.provider, response.model,
                                                response.usage)
        base = OrchestratorResult(
            ok=True, request_id=request_id, capability=capability, tier=tier,
            provider=response.provider, model=response.model,
            estimated_credits=reserve_estimate["credits"],
            entitlement_grant=entitlement_grant,
            router=self._decision_dict(entry, response.model, estimate=reserve_estimate,
                                       candidate_count=candidate_count,
                                       fallback_from=fallback_from))
        if response.usage.usage_source != "PROVIDER_REPORTED" or not actual["ok"]:
            # The provider answered, but what the call COSTS is not known yet: it reported no
            # usage, or this model has no price on file. The reservation stays HELD (never
            # released, never zeroed — see mark_reconciliation_pending) and the request keeps its
            # reconciliation record, so nothing is written off; the learner is given the answer
            # that was produced rather than losing it to an accounting state.
            usage_service.mark_reconciliation_pending(db, request_id)
            base.status = "reconciliation_pending"
            base.content = response.content
            base.usage = {"usage_source": response.usage.usage_source}
            return base

        settle = usage_service.settle_credits(
            db, request_id, actual["credits"],
            provider=response.provider, model=response.model,
            input_tokens=actual["input_tokens"], output_tokens=actual["output_tokens"],
            provider_cost=actual["cost_cny"], currency="CNY",
            pricing_version=actual["pricing_version"])
        if settle["settled"]:
            base.status = "settled"
            base.content = response.content
            base.actual_credits = settle.get("settled_credits")
        elif settle["reason"] == "overage_not_permitted":
            # FAIL CLOSED, deliberately and with its own category. The provider billed beyond the
            # reservation this request authorized: that is the one reconciliation outcome the
            # product refuses to serve, so no answer is handed out and the request stays flagged
            # as an anomaly.
            usage_service.mark_reconciliation_pending(
                db, request_id, error_category="reservation_overage")
            base.status = "reconciliation_pending"
            base.error_category = "reservation_overage"
        else:
            # The ledger says this request is not charged (already released, or it has no
            # reservation at all). Serving it would hand out an unbilled answer, so it is not
            # served — the same fail-closed reading as an overage.
            base.status = "released"
        base.usage = {
            "input_tokens": actual["input_tokens"],
            "output_tokens": actual["output_tokens"],
            "cached_input_tokens": actual["cached_input_tokens"],
            "reasoning_tokens": actual["reasoning_tokens"],
            "usage_source": actual["usage_source"],
            "cost_cny": actual["cost_cny"],
        }
        return base

    def _thinking_for(self, entry, capability: str) -> bool | None:
        """The thinking switch for one candidate — the same rule the non-streaming call uses."""
        return cost.cost_policy_for(entry.provider, entry.model).request_thinking(capability)

    def _record_provider_failure(self, entry, exc: GatewayError) -> None:
        """Router V1: every provider failure is an availability signal, including one a fallback
        then rescued. A failure that was really the REQUEST's fault (invalid request / content
        policy) says nothing about the provider."""
        try:
            from .health import registry as health_registry
            if exc.category.value not in ("invalid_request", "content_policy"):
                health_registry().record_failure(entry.provider, entry.model, exc.category.value)
        except Exception:  # noqa: BLE001 — health never blocks a request
            pass

    def stream(self, db: Session, user_id: int, capability: str,
               messages: list[ChatMessage] | list[dict],
               explicit_model: str | None = None,
               max_tokens: int | None = None,
               request_id: str | None = None,
               learning_context: LearningContext | None = None,
               model_preference: str | None = None,
               thinking: bool | None = None) -> "StreamRun":
        """Public boundary for a streamed turn: same authorisation, same billing, read live."""
        if learning_context is not None and learning_context.user_id != user_id:
            raise ValueError("LearningContext user_id must match orchestrator user_id")
        attempt, refusal = self._prepare(
            db, user_id, capability, messages, explicit_model=explicit_model,
            max_tokens=max_tokens, request_id=request_id, learning_context=learning_context,
            model_preference=model_preference)
        if refusal is not None:
            return _RefusedStreamRun(refusal)
        return StreamRun(self, db, attempt, thinking=thinking)

    def _record_empty_answer(self, db, request_id: str, entry, response) -> None:
        """Record a candidate that answered with nothing — cost, log, availability signal.

        The provider ran and billed for it, so its usage goes to the ledger rather than being
        dropped with the empty answer. A model that answers with nothing is also an availability
        signal like any other failure, so repeated empties deprioritise it in later selections.
        """
        actual = cost.actual_credits_from_usage(response.provider, response.model, response.usage)
        # Only a call the provider actually reported usage for has a cost to record; an unreported
        # one is exactly what `reconciliation_pending` exists for, and writing a zero row for it
        # would claim it was free rather than unknown.
        if actual["ok"] and response.usage.usage_source == "PROVIDER_REPORTED":
            usage_service.record_attempt_cost(
                db, request_id, provider=response.provider, model=response.model,
                input_tokens=actual["input_tokens"], output_tokens=actual["output_tokens"],
                provider_cost=actual["cost_cny"], pricing_version=actual["pricing_version"],
                credits=actual["credits"])
        logger.warning("empty completion from %s/%s on request %s (usage_source=%s, tokens=%s)",
                       response.provider, response.model, request_id,
                       response.usage.usage_source, response.usage.output_tokens)
        try:
            from .health import registry as health_registry
            health_registry().record_failure(entry.provider, entry.model, "empty_completion")
        except Exception:  # noqa: BLE001 — health never blocks a request
            pass

    def _settle_failure(self, db, request_id, entry, reserve_estimate: dict,
                        exc: GatewayError | None, tier: str, capability: str, *,
                        candidate_count: int | None = None,
                        entitlement_grant: dict | None = None,
                        error_category: str | None = None,
                        error_message: str | None = None) -> OrchestratorResult:
        # NOTE: the availability signal for a failed attempt is recorded where the attempt
        # fails (the fallback loop), so an attempt the fallback rescued is counted too.
        base = OrchestratorResult(
            ok=False, request_id=request_id, capability=capability, tier=tier,
            provider=entry.provider, model=entry.model,
            estimated_credits=reserve_estimate["credits"],
            entitlement_grant=entitlement_grant,
            error_category=(error_category or (exc.category.value if exc else "provider_error")),
            error_message=(error_message or (exc.message if exc else "provider call failed")),
            router=self._decision_dict(entry, estimate=reserve_estimate,
                                       candidate_count=candidate_count))
        if exc is not None and exc.category.value in _NO_USAGE_CATEGORIES:
            usage_service.release_credits(db, request_id)
            base.status = "released"
        else:
            # `error_category` is carried onto the HELD row only when the caller named one: the
            # default stays the ledger's own `cost_reconciliation_pending`, so an existing
            # failure's recorded cause does not change shape.
            usage_service.mark_reconciliation_pending(
                db, request_id, **({"error_category": error_category} if error_category else {}))
            base.status = "reconciliation_pending"
        return base

    # ---- helpers ----

    @staticmethod
    def _decision_dict(entry, model: str | None = None, *, estimate: dict | None = None,
                       candidate_count: int | None = None,
                       fallback_from: str | None = None) -> dict:
        """The decision record attached to a result — Router V1 observability.

        A fallback that actually served the request is recorded AS a fallback (its own reason
        code), with the model that failed named — so "which model answered, and why that one"
        is answerable from the audit stream even when the primary failed.
        """
        from .router import (
            REASON_CHEAPEST, REASON_EXPLICIT, REASON_ONLY_CANDIDATE,
        )

        if fallback_from:
            reason_code = "fallback_after_failure"
            reason = "fallback_after_failure"
        elif candidate_count == 1:
            reason_code, reason = REASON_ONLY_CANDIDATE, "auto_recommended"
        else:
            reason_code, reason = REASON_CHEAPEST, "auto_recommended"
        decision = RouterDecision(ok=True, provider=entry.provider,
                                  model=model or entry.model, reason=reason,
                                  reason_code=reason_code,
                                  quality_class=entry.quality_class,
                                  latency_class=entry.latency_class,
                                  cost_profile=getattr(entry, "cost_profile", None),
                                  estimated_credits=(estimate or {}).get("credits"))
        payload = decision.to_dict()
        if candidate_count is not None:
            payload["candidate_count"] = int(candidate_count)
        if fallback_from:
            payload["fallback_from"] = fallback_from
        return payload

    @staticmethod
    def _feature_flag_grant(db: Session, user_id: int, capability: str) -> dict:
        """P6: may an ops feature flag grant this capability's ENTITLEMENT step?

        Failure-isolated: an ops-flag problem must never turn into a different AI answer than
        the policy already gave — a broken lookup is simply "no grant".
        """
        try:
            from ops import feature_flags
            return feature_flags.capability_entitlement_grant(db, user_id, capability)
        except Exception as exc:  # noqa: BLE001
            logger.warning("feature flag grant lookup failed: %s", type(exc).__name__)
            return {"granted": False, "reason": "lookup_failed"}

    @staticmethod
    def _available_budget(db: Session, user_id: int) -> int | None:
        summary = usage_service.usage_summary(db, user_id)
        remaining = [p["remaining"] for p in summary.get("periods", {}).values()
                     if p.get("remaining") is not None]
        return min(remaining) if remaining else None

    @staticmethod
    def _mark_executing(db: Session, request_id: str) -> None:
        req = db.query(AIRequest).filter(AIRequest.request_id == request_id).first()
        if req is not None and req.status == "reserved":
            req.status = "executing"
            req.started_at = datetime.utcnow()
            db.commit()

class StreamRun:
    """One streaming turn: iterate ``events()``, then read ``result``.

    The streaming half of the lifecycle. It shares EVERYTHING that decides a request — permission,
    capability/budget gate, router, the single reservation (`AIOrchestrator._prepare`) and the
    settlement helpers — and differs only in how the model's answer is read: from a live provider
    stream, in pieces, instead of from one response.

    THREE RULES THIS CLASS EXISTS TO KEEP
    1. A candidate is COMMITTED the moment its first non-empty text reached the caller. After
       that, a provider failure ends the turn with what was already shown — it never silently
       continues from a second model, which would splice two different answers together.
    2. Before that moment the chain behaves exactly like the non-streaming path: a retriable
       failure or an empty completion moves on to the next qualified candidate.
    3. The ledger is never bypassed: every attempt that reached a provider is settled from its own
       real usage — or held as pending when the provider never reported any.
    """

    def __init__(self, orchestrator: "AIOrchestrator", db: Session, attempt: "_Attempt",
                 thinking: bool | None = None):
        self._orchestrator = orchestrator
        self._thinking = thinking
        self._db = db
        self._attempt = attempt
        self._generator = None
        self._settled = False
        self._recorded = False
        #: The request id this turn was authorised under — known before the first byte streams.
        self.request_id = attempt.request_id
        self._failed_primary: str | None = None
        self._last_entry = None
        self._last_usage = None
        self.result: OrchestratorResult | None = None
        #: The answer text the caller has actually been given, in order.
        self.text = ""
        #: "stop" / "length" / "interrupted" / "stopped" / "error" — how the turn ended.
        self.finish_reason: str | None = None

    # ---- driving ----

    def events(self) -> Iterator["StreamEvent"]:
        """Provider answer deltas as they arrive, then exactly one terminal event.

        Only a provider's ANSWER channel is representable here: reasoning/hidden text is dropped
        in the adapter, so it cannot reach a caller by accident.
        """
        if self._generator is None:
            self._generator = self._run()
        return self._generator

    def close(self) -> None:
        """Stop the live provider stream (if any) and settle this turn exactly once.

        Called when the caller stops reading — a user pressing stop, a client disconnecting, a
        page navigating away. Safe to call again after a normal finish.
        """
        generator = self._generator
        if generator is not None:
            try:
                generator.close()          # GeneratorExit at the yield point
            except Exception:  # noqa: BLE001 — closing must never raise at a caller
                logger.warning("stream close failed", exc_info=True)
        self._settle_once(self._last_entry, self._last_usage, cancelled=True)

    # ---- the lifecycle ----

    def _run(self) -> Iterator["StreamEvent"]:
        attempt = self._attempt
        db = self._db
        request_id = attempt.request_id
        tier, capability = attempt.tier, attempt.capability
        last_entry, last_error = attempt.primary_entry, None
        last_empty_response = None
        committed = False
        self._last_entry = attempt.primary_entry
        self._last_usage = None
        self._failed_primary = None

        for index, (entry, _estimate) in enumerate(attempt.candidates[:MAX_FALLBACK_ATTEMPTS]):
            last_entry = entry
            self._last_entry = entry
            spec = AIRequestSpec(messages=tuple(attempt.chat_messages), model=entry.model,
                                 capability=capability, temperature=None,
                                 max_tokens=attempt.expected_output, stream=True,
                                 thinking=(self._thinking if self._thinking is not None
                                           else self._orchestrator._thinking_for(entry, capability)))
            usage = None
            finish_reason = None
            produced = False
            try:
                provider = self._orchestrator._provider_factory(entry.provider)
                with provider.stream(spec) as stream_events:
                    for event in stream_events:
                        if event.type == "usage" and event.usage is not None:
                            usage = event.usage
                            self._last_usage = usage
                        elif event.type == "finish":
                            finish_reason = event.finish_reason
                        elif event.type == "text_delta" and event.text:
                            committed = True
                            produced = True
                            self.text += event.text
                            yield event
            except GatewayError as exc:
                if committed:
                    # The learner has already read part of THIS model's answer; completing it from
                    # another model would produce one text out of two. The turn ends here, with
                    # what was really produced, and the settlement keeps the real usage.
                    self._settle_once(entry, usage, finish_reason="interrupted",
                                      error_category=exc.category.value)
                    self.finish_reason = "interrupted"
                    yield StreamEvent(type="error", error_category=exc.category.value,
                                      error_message="answer interrupted")
                    return
                last_error = exc
                last_empty_response = None
                if index == 0:
                    self._failed_primary = f"{entry.provider}/{entry.model}"
                self._orchestrator._record_provider_failure(entry, exc)
                if not exc.retriable:
                    break
                continue

            if not produced:
                # A stream that ended with no visible text is an empty completion, exactly as in
                # the non-streaming path: the attempt is recorded, and the chain moves on.
                last_empty_response = self._synthetic_response(entry, "", usage, finish_reason)
                last_error = None
                if index == 0:
                    self._failed_primary = f"{entry.provider}/{entry.model}"
                self._orchestrator._record_empty_answer(db, request_id, entry,
                                                        last_empty_response)
                continue

            self._settle_once(entry, usage, finish_reason=finish_reason or "stop")
            self.finish_reason = finish_reason or "stop"
            yield StreamEvent(type="finish", finish_reason=self.finish_reason)
            return

        # No candidate produced an answer at all.
        self._settled = True
        if last_empty_response is not None:
            self.result = self._orchestrator._settle_failure(
                db, request_id, last_entry, attempt.primary_estimate, None, tier, capability,
                candidate_count=len(attempt.candidates), entitlement_grant=attempt.grant,
                error_category="empty_completion",
                error_message="every candidate returned an empty completion")
        else:
            self.result = self._orchestrator._settle_failure(
                db, request_id, last_entry, attempt.primary_estimate, last_error, tier, capability,
                candidate_count=len(attempt.candidates), entitlement_grant=attempt.grant)
        self._record_called()
        self.finish_reason = "error"
        yield StreamEvent(type="error",
                          error_category=self.result.error_category or "provider_error",
                          error_message="AI could not answer")

    # ---- settlement ----

    def _settle_once(self, entry, usage, *, finish_reason: str | None = None,
                     error_category: str | None = None, cancelled: bool = False) -> None:
        """Write this turn's terminal ledger fact exactly once, from what really happened.

        A cancelled turn — or one whose provider stopped mid-answer — still SETTLES: the call
        happened and was billed, and the learner keeps the text they saw. When the provider never
        reported usage the request is held for reconciliation instead; it is never settled to zero.
        """
        if self._settled:
            return
        self._settled = True
        attempt = self._attempt
        entry = entry or attempt.primary_entry
        if cancelled and not self.text:
            # Nothing was shown and the caller walked away: this is the empty-completion shape —
            # the attempt still gets recorded, and the request keeps its held/pending state.
            self.result = self._orchestrator._settle_failure(
                self._db, attempt.request_id, entry, attempt.primary_estimate, None,
                attempt.tier, attempt.capability, candidate_count=len(attempt.candidates),
                entitlement_grant=attempt.grant, error_category="stream_cancelled",
                error_message="stream cancelled before any answer")
            self._record_called()
            return
        response = self._synthetic_response(entry, self.text, usage,
                                            finish_reason or ("stopped" if cancelled else None))
        result = self._orchestrator._settle_success(
            self._db, attempt.request_id, entry, attempt.primary_estimate, response,
            attempt.tier, attempt.capability, candidate_count=len(attempt.candidates),
            fallback_from=self._failed_primary, entitlement_grant=attempt.grant)
        if error_category:
            # The ledger's state stays whatever settlement decided (settled / held); this only
            # tells the CALLER how the stream ended. Nothing about billing is rewritten.
            result.error_category = error_category
        self.result = result
        self._record_called()

    def _record_called(self) -> None:
        if self._recorded:
            return
        self._recorded = True
        if self.result is None:
            return
        try:
            self._orchestrator._emit_ai_called(self._db, self._attempt.user_id, self.result,
                                               learning_context=self._attempt.learning_context)
        except Exception:  # noqa: BLE001 — the record hook never fails a request
            logger.warning("ai_called hook failed for streamed request", exc_info=True)

    @staticmethod
    def _synthetic_response(entry, content: str, usage, finish_reason: str | None):
        """The response shape the settlement helpers already understand, built from a stream."""
        from .gateway import ProviderUsage
        return GatewayResponse(
            content=content, provider=entry.provider, model=entry.model,
            usage=usage or ProviderUsage(usage_source="UNKNOWN"),
            finish_reason=finish_reason)


class _RefusedStreamRun:
    """A streamed turn that never reached a provider: the refusal is the whole answer.

    Same shape as StreamRun so an endpoint does not branch on which one it got.
    """

    def __init__(self, refusal: OrchestratorResult):
        self.result = refusal
        self.request_id = refusal.request_id
        self.text = ""
        self.finish_reason: str | None = "error"
        self._refusal = refusal

    def events(self) -> Iterator["StreamEvent"]:
        yield StreamEvent(type="error", error_category=self._refusal.error_category or "denied",
                          error_message="AI unavailable")

    def close(self) -> None:
        return None
