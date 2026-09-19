"""External AI Gateway — unified interface for third-party LLM providers (STEP 7C).

This is the EXTERNAL AI boundary (DeepSeek / Qwen / OpenAI-compatible). It is strictly
separate from the Scientific Runtime Service (self-developed models): the gateway never
imports ``zhixue_runtime`` and never runs a self-developed scientific model.

A provider only ever appears as a ``GatewayProvider`` here or in a compatibility
module. Business endpoints must NOT write their own direct provider HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class GatewayErrorCategory(str, Enum):
    authentication = "authentication"
    rate_limited = "rate_limited"
    timeout = "timeout"
    provider_unavailable = "provider_unavailable"
    invalid_request = "invalid_request"
    content_policy = "content_policy"
    provider_error = "provider_error"


class GatewayError(Exception):
    """Normalized provider error (raised as an exception; category is never raw)."""

    def __init__(self, category: GatewayErrorCategory, message: str,
                 provider: str | None = None, retriable: bool = False):
        super().__init__(message)
        self.category = category
        self.message = message
        self.provider = provider
        self.retriable = retriable


@dataclass(frozen=True)
class AIRequestSpec:
    """Normalized request spec. Providers are not forced to be fully isomorphic; only
    the common fields are normalized. ``model=None`` means "router auto-selected".

    ``thinking`` is tri-state: None = provider default, True/False = explicit. It
    exists because a thinking model's hidden reasoning is billable output that
    ``max_tokens`` does NOT bound (live-verified on Ark), so the reservation layer has
    to know whether this request will produce reasoning tokens.
    """
    messages: tuple[ChatMessage, ...] = ()
    model: str | None = None
    capability: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    thinking: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderUsage:
    """Normalized provider-reported usage. ``usage_source`` distinguishes real
    provider-reported tokens from local deterministic estimates."""
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: str = "UNKNOWN"  # PROVIDER_REPORTED / ESTIMATED / UNKNOWN
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayResponse:
    content: str
    provider: str
    model: str
    usage: ProviderUsage
    finish_reason: str | None = None
    latency_ms: int | None = None
    provider_request_id: str | None = None


@runtime_checkable
class ChatProvider(Protocol):
    """Minimal synchronous chat-completion contract (legacy, returns bare text)."""

    def chat(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        ...


@runtime_checkable
class GatewayProvider(Protocol):
    """Full gateway contract: returns a normalized GatewayResponse with usage."""

    name: str

    def complete(self, spec: AIRequestSpec) -> GatewayResponse:
        ...


def usage_is_reported(usage: ProviderUsage) -> bool:
    return usage.usage_source == "PROVIDER_REPORTED"
