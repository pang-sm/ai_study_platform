"""Deterministic fake provider for tests. Never touches a real API / real balance.

Configurable behaviors cover the failure/settlement matrix without paid inference:
  success          → normal response with provider-reported usage
  unknown_usage    → success but usage unavailable (reconciliation-pending path)
  raise_auth       → fail before any usage (authentication error)
  raise_timeout    → fail after a provider request may have been sent (timeout)
"""
from __future__ import annotations

from ai.gateway import (
    AIRequestSpec,
    GatewayError,
    GatewayErrorCategory,
    GatewayResponse,
    ProviderUsage,
)


class FakeProvider:
    name = "fake"

    def __init__(self, provider: str = "fake", model: str = "fake-model",
                 behavior: str = "success",
                 input_tokens: int | None = None, output_tokens: int | None = None):
        self.name = provider
        self.model = model
        self.behavior = behavior
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    def _deterministic_usage(self, spec: AIRequestSpec) -> ProviderUsage:
        inp = self._input_tokens
        if inp is None:
            inp = sum(max(1, len(m.content) // 2) for m in spec.messages)
        out = self._output_tokens if self._output_tokens is not None else (spec.max_tokens or 200)
        return ProviderUsage(input_tokens=inp, output_tokens=out,
                             total_tokens=inp + out, usage_source="PROVIDER_REPORTED")

    def complete(self, spec: AIRequestSpec) -> GatewayResponse:
        if self.behavior == "raise_auth":
            raise GatewayError(GatewayErrorCategory.authentication,
                               "fake auth failure", self.name)
        if self.behavior == "raise_timeout":
            raise GatewayError(GatewayErrorCategory.timeout,
                               "fake timeout", self.name, retriable=True)
        usage = self._deterministic_usage(spec)
        if self.behavior == "unknown_usage":
            usage = ProviderUsage(usage_source="UNKNOWN")
        return GatewayResponse(
            content="fake response",
            provider=self.name,
            model=spec.model or self.model,
            usage=usage,
            finish_reason="stop",
            latency_ms=1,
            provider_request_id="fake-req-id",
        )
