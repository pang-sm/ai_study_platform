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
            producers.emit_ai_called(
                user_id=user_id, ai_request_id=result.request_id,
                capability=result.capability, status=status,
                occurred_at=None, provider=result.provider,
                credits=result.actual_credits,
                error_category=result.error_category if status == "failed" else None,
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
        if not perm["allowed"]:
            return OrchestratorResult(ok=False, request_id=request_id,
                                      capability=capability, tier=tier, status="denied",
                                      error_category="permission_denied",
                                      error_message=perm["reason"])

        chat_messages = [m if isinstance(m, ChatMessage)
                         else ChatMessage(role=m["role"], content=m["content"])
                         for m in messages]

        input_text = "".join(m.content for m in chat_messages)
        input_tokens = cost.estimate_input_tokens(input_text)
        expected_output = max_tokens or DEFAULT_MAX_TOKENS
        available = self._available_budget(db, user_id)

        # 2. ordered budget-compatible qualified candidates (cheapest first)
        candidates = ordered_candidates(tier, capability, explicit_model=explicit_model,
                                        input_tokens=input_tokens,
                                        expected_output_tokens=expected_output,
                                        available_budget=available)
        if not candidates:
            decision = select_model(tier, capability, explicit_model=explicit_model,
                                    input_tokens=input_tokens,
                                    expected_output_tokens=expected_output,
                                    available_budget=available)
            return OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="denied",
                error_category=decision.reason if decision else "no_qualified_model_available",
                error_message=decision.error if decision else "no_qualified_model_available",
                router=decision.to_dict() if decision else None)

        primary_entry, primary_estimate = candidates[0]

        # 3. reserve once for the primary (cheapest) estimate
        reservation = usage_service.reserve_credits(
            db, user_id, request_id, capability, primary_estimate["credits"],
            service_namespace=(learning_context.service_namespace.value
                               if learning_context is not None else None),
            context_json=(learning_context.to_dict() if learning_context is not None else None))
        if reservation.get("reason") == "already_exists":
            return OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="already_exists", error_category="already_exists",
                error_message="request already processed",
                estimated_credits=primary_estimate["credits"],
                router=self._decision_dict(primary_entry))
        if not reservation["reserved"]:
            return OrchestratorResult(
                ok=False, request_id=request_id, capability=capability, tier=tier,
                status="denied", error_category="budget_reserve_failed",
                error_message=reservation["reason"],
                estimated_credits=primary_estimate["credits"],
                router=self._decision_dict(primary_entry))

        self._mark_executing(db, request_id)

        # 4. external provider call with cross-provider fallback (outside transaction)
        last_entry, last_error = primary_entry, None
        for entry, estimate in candidates[:MAX_FALLBACK_ATTEMPTS]:
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
                return self._settle_success(db, request_id, entry, primary_estimate,
                                            response, tier, capability)
            except GatewayError as exc:
                last_error = exc
                if not exc.retriable:
                    break  # permanent error → no fallback

        return self._settle_failure(db, request_id, last_entry, primary_estimate,
                                    last_error, tier, capability)

    # ---- settlement helpers ----

    def _settle_success(self, db, request_id, entry, reserve_estimate: dict,
                        response, tier: str, capability: str) -> OrchestratorResult:
        actual = cost.actual_credits_from_usage(response.provider, response.model,
                                                response.usage)
        base = OrchestratorResult(
            ok=True, request_id=request_id, capability=capability, tier=tier,
            provider=response.provider, model=response.model,
            estimated_credits=reserve_estimate["credits"],
            router=self._decision_dict(entry, response.model))
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
                        exc: GatewayError | None, tier: str, capability: str) -> OrchestratorResult:
        base = OrchestratorResult(
            ok=False, request_id=request_id, capability=capability, tier=tier,
            provider=entry.provider, model=entry.model,
            estimated_credits=reserve_estimate["credits"],
            error_category=(exc.category.value if exc else "provider_error"),
            error_message=(exc.message if exc else "provider call failed"),
            router=self._decision_dict(entry))
        if exc is not None and exc.category.value in _NO_USAGE_CATEGORIES:
            usage_service.release_credits(db, request_id)
            base.status = "released"
        else:
            usage_service.mark_reconciliation_pending(db, request_id)
            base.status = "reconciliation_pending"
        return base

    # ---- helpers ----

    @staticmethod
    def _decision_dict(entry, model: str | None = None) -> dict:
        return RouterDecision(ok=True, provider=entry.provider,
                              model=model or entry.model,
                              reason="auto_recommended").to_dict()

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
