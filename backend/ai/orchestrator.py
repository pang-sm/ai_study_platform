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
from typing import Callable

from sqlalchemy.orm import Session

from core.learning_context import LearningContext

from usage import service as usage_service
from usage.capabilities import check_capability_permission
from usage.models import AIRequest

from . import cost
from .gateway import AIRequestSpec, ChatMessage, GatewayError, GatewayErrorCategory, GatewayProvider
from .providers import (
    ArkProvider, DeepSeekProvider, FakeProvider, MiniMaxProvider,
    MoonshotProvider, QwenProvider, ZhipuProvider,
)
from .router import RouterDecision, ordered_candidates, select_model
from .secrets import ark_endpoint_map

logger = logging.getLogger("ai.orchestrator")

DEFAULT_MAX_TOKENS = 2000
MAX_FALLBACK_ATTEMPTS = 3

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


class AIOrchestrator:
    def __init__(self, provider_factory: Callable[[str], GatewayProvider] | None = None):
        self._provider_factory = provider_factory or default_provider_factory

    def execute(self, db: Session, user_id: int, capability: str,
                messages: list[ChatMessage] | list[dict],
                explicit_model: str | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                request_id: str | None = None,
                learning_context: LearningContext | None = None) -> OrchestratorResult:
        """Public boundary: run the lifecycle, then record the terminal fact.

        The `ai_called` event is emitted here rather than at each of the six return
        paths so that every outcome — settled, failed, denied, pending — is recorded by
        one rule (§16). Emission is failure-isolated and happens strictly after the
        AIRequest row has committed.
        """
        if learning_context is not None and learning_context.user_id != user_id:
            raise ValueError("LearningContext user_id must match orchestrator user_id")
        result = self._execute(db, user_id, capability, messages,
                               explicit_model=explicit_model, temperature=temperature,
                               max_tokens=max_tokens, request_id=request_id,
                               learning_context=learning_context)
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

    def _execute(self, db: Session, user_id: int, capability: str,
                messages: list[ChatMessage] | list[dict],
                explicit_model: str | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                request_id: str | None = None,
                learning_context: LearningContext | None = None) -> OrchestratorResult:
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
                return OrchestratorResult(ok=False, request_id=request_id,
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
                                        available_budget=available)
        if not candidates:
            decision = select_model(gate_tier, capability, explicit_model=explicit_model,
                                    input_tokens=input_tokens,
                                    expected_output_tokens=expected_output,
                                    available_budget=available)
            return OrchestratorResult(
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
            return OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="already_exists", error_category="already_exists",
                error_message="request already processed",
                estimated_credits=primary_estimate["credits"],
                entitlement_grant=grant,
                router=self._decision_dict(primary_entry))
        if not reservation["reserved"]:
            return OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="denied", error_category="budget_reserve_failed",
                error_message=reservation["reason"],
                estimated_credits=primary_estimate["credits"],
                entitlement_grant=grant,
                router=self._decision_dict(primary_entry))

        self._mark_executing(db, request_id)

        # 4. external provider call with cross-provider fallback (outside transaction)
        last_entry, last_error = primary_entry, None
        failed_primary: str | None = None
        for index, (entry, estimate) in enumerate(candidates[:MAX_FALLBACK_ATTEMPTS]):
            last_entry = entry
            # The reservation already priced this model's thinking behaviour; the same
            # policy decides the switch actually sent, so reserved and billed output
            # are governed by one rule.
            thinking = cost.cost_policy_for(entry.provider, entry.model).request_thinking(
                capability)
            spec = AIRequestSpec(messages=tuple(chat_messages), model=entry.model,
                                 capability=capability, temperature=temperature,
                                 max_tokens=max_tokens, stream=False, thinking=thinking)
            try:
                provider = self._provider_factory(entry.provider)
                response = provider.complete(spec)
                return self._settle_success(
                    db, request_id, entry, primary_estimate, response, tier, capability,
                    candidate_count=len(candidates), fallback_from=failed_primary,
                    entitlement_grant=grant)
            except GatewayError as exc:
                last_error = exc
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
                    if exc.category.value not in ("invalid_request", "content_policy"):
                        health_registry().record_failure(entry.provider, entry.model,
                                                         exc.category.value)
                except Exception:  # noqa: BLE001 — health never blocks a request
                    pass
                if not exc.retriable:
                    break  # permanent error → no fallback

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
            usage_service.mark_reconciliation_pending(db, request_id)
            base.status = "reconciliation_pending"
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
            # Real cost exceeded the conservative reservation. Never silently absorbed:
            # flagged with its own category so it is measurable as an anomaly.
            usage_service.mark_reconciliation_pending(
                db, request_id, error_category="reservation_overage")
            base.status = "reconciliation_pending"
            base.error_category = "reservation_overage"
        else:
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

    def _settle_failure(self, db, request_id, entry, reserve_estimate: dict,
                        exc: GatewayError | None, tier: str, capability: str, *,
                        candidate_count: int | None = None,
                        entitlement_grant: dict | None = None) -> OrchestratorResult:
        # NOTE: the availability signal for a failed attempt is recorded where the attempt
        # fails (the fallback loop), so an attempt the fallback rescued is counted too.
        base = OrchestratorResult(
            ok=False, request_id=request_id, capability=capability, tier=tier,
            provider=entry.provider, model=entry.model,
            estimated_credits=reserve_estimate["credits"],
            entitlement_grant=entitlement_grant,
            error_category=(exc.category.value if exc else "provider_error"),
            error_message=(exc.message if exc else "provider call failed"),
            router=self._decision_dict(entry, estimate=reserve_estimate,
                                       candidate_count=candidate_count))
        if exc is not None and exc.category.value in _NO_USAGE_CATEGORIES:
            usage_service.release_credits(db, request_id)
            base.status = "released"
        else:
            usage_service.mark_reconciliation_pending(db, request_id)
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
