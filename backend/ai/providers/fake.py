"""Deterministic fake provider for tests. Never touches a real API / real balance.

Configurable behaviors cover the failure/settlement matrix without paid inference:
  success          → normal response with provider-reported usage
  unknown_usage    → success but usage unavailable (reconciliation-pending path)
  raise_auth       → fail before any usage (authentication error)
  raise_timeout    → fail after a provider request may have been sent (timeout)

A streamed turn is scripted separately (``stream_script``), one step per provider chunk, so the
whole streaming chain — orchestrator, endpoint, cancellation, billing — can be driven without a
paid call: ``("text", "…")`` for answer text, ``("usage", ProviderUsage(...))``, ``("finish",
"stop")``, and ``("raise", GatewayError(...))`` to fail MID-stream. With no script, the stream
behaves like ``complete()``: the same content, usage and finish reason, delivered in pieces.
"""
from __future__ import annotations

from ai.gateway import (
    AIRequestSpec,
    GatewayError,
    GatewayErrorCategory,
    GatewayResponse,
    ProviderUsage,
    StreamEvent,
)


class FakeProvider:
    name = "fake"

    def __init__(self, provider: str = "fake", model: str = "fake-model",
                 behavior: str = "success",
                 input_tokens: int | None = None, output_tokens: int | None = None,
                 stream_script: list | None = None):
        self.name = provider
        self.model = model
        self.behavior = behavior
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._stream_script = stream_script

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

    # ---- streaming ----

    def stream(self, spec: AIRequestSpec):
        """A scripted provider stream, in the gateway's context-manager shape.

        No network, no SDK: the events (and the failures) are whatever the test scripted. The
        close hook records that cancellation reached the provider.
        """
        from contextlib import contextmanager

        provider, model = self.name, spec.model or self.model
        script = self._stream_script
        closed: list = []
        self.stream_closed = closed

        @contextmanager
        def _stream():
            def _events():
                if script is None:
                    # Behave like complete(): same answer, same usage, delivered in two pieces.
                    if self.behavior == "raise_auth":
                        raise GatewayError(GatewayErrorCategory.authentication,
                                           "fake auth failure", provider)
                    if self.behavior == "raise_timeout":
                        raise GatewayError(GatewayErrorCategory.timeout, "fake timeout",
                                           provider, retriable=True)
                    text = "fake response"
                    half = max(1, len(text) // 2)
                    yield StreamEvent(type="text_delta", text=text[:half])
                    yield StreamEvent(type="text_delta", text=text[half:])
                    usage = self._deterministic_usage(spec)
                    if self.behavior == "unknown_usage":
                        usage = ProviderUsage(usage_source="UNKNOWN")
                    yield StreamEvent(type="usage", usage=usage)
                    yield StreamEvent(type="finish", finish_reason="stop")
                    return
                for step in script:
                    kind, value = step[0], (step[1] if len(step) > 1 else None)
                    if kind == "close_probe":
                        continue  # marker only; the close hook below is what is asserted
                    if kind == "text":
                        yield StreamEvent(type="text_delta", text=value)
                    elif kind == "usage":
                        yield StreamEvent(type="usage", usage=value)
                    elif kind == "finish":
                        yield StreamEvent(type="finish", finish_reason=value or "stop")
                    elif kind == "raise":
                        raise value
                    else:  # pragma: no cover - a script typo should be loud
                        raise AssertionError(f"unknown stream step {kind!r}")

            try:
                yield _events()
            finally:
                closed.append(True)

        return _stream()
