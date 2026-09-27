"""Shared helpers for OpenAI-compatible provider adapters (usage, errors, streaming)."""
from __future__ import annotations

from contextlib import contextmanager

from ai.gateway import GatewayError, GatewayErrorCategory, ProviderUsage


def _read(obj, *names):
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return value
    return None


def extract_openai_usage(response) -> ProviderUsage:
    """Normalize an OpenAI-compatible response's usage. Never invents tokens."""
    usage = getattr(response, "usage", None)
    details = _read(usage, "prompt_tokens_details") or {}
    completion_details = _read(usage, "completion_tokens_details") or {}
    input_tokens = _read(usage, "prompt_tokens", "input_tokens")
    output_tokens = _read(usage, "completion_tokens", "output_tokens")
    cached = _read(details, "cached_tokens", "cached_input_tokens")
    reasoning = _read(completion_details, "reasoning_tokens")
    total = _read(usage, "total_tokens")
    reported = input_tokens is not None or output_tokens is not None or total is not None
    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached,
        reasoning_tokens=reasoning,
        total_tokens=total,
        usage_source="PROVIDER_REPORTED" if reported else "UNKNOWN",
    )


def map_openai_error(exc: Exception, provider: str) -> GatewayError:
    """Map an OpenAI SDK exception to a normalized gateway error category.

    Never leaks the raw exception, API key, or internal URL upstream.
    """
    try:
        import openai
    except ImportError:
        return GatewayError(GatewayErrorCategory.provider_error,
                            "provider call failed", provider, retriable=True)

    if isinstance(exc, openai.AuthenticationError):
        return GatewayError(GatewayErrorCategory.authentication,
                            "provider authentication failed", provider)
    if isinstance(exc, openai.RateLimitError):
        return GatewayError(GatewayErrorCategory.rate_limited,
                            "provider rate limited", provider, retriable=True)
    if isinstance(exc, openai.APITimeoutError) or isinstance(exc, TimeoutError):
        return GatewayError(GatewayErrorCategory.timeout,
                            "provider timed out", provider, retriable=True)
    if isinstance(exc, openai.APIConnectionError):
        return GatewayError(GatewayErrorCategory.provider_unavailable,
                            "provider unavailable", provider, retriable=True)
    if isinstance(exc, openai.BadRequestError):
        return GatewayError(GatewayErrorCategory.invalid_request,
                            "invalid request", provider)
    # Content-policy / permission refusals surface as 4xx status errors.
    status = getattr(exc, "status_code", None)
    if status == 401 or status == 403:
        return GatewayError(GatewayErrorCategory.authentication,
                            "provider access denied", provider)
    if status == 429:
        return GatewayError(GatewayErrorCategory.rate_limited,
                            "provider rate limited", provider, retriable=True)
    if status in (400, 404, 422):
        return GatewayError(GatewayErrorCategory.invalid_request,
                            "invalid request", provider)
    if status is not None and 500 <= status < 600:
        return GatewayError(GatewayErrorCategory.provider_unavailable,
                            "provider error", provider, retriable=True)
    return GatewayError(GatewayErrorCategory.provider_error,
                        "provider call failed", provider, retriable=True)


# ------------------------------------------------------------------ streaming

# The OpenAI-compatible stream options every adapter sends: ask the endpoint to report usage on
# the final chunk. Endpoints that do not support it simply never send one, which the ledger
# already handles as an unknown-usage request rather than as a zero-cost one.
STREAM_OPTIONS = {"include_usage": True}

# Fields a chunk may carry that are NOT the learner's answer. A thinking model's separate
# reasoning channel is the live case: it must stop here, in the one place a provider chunk is
# read, so no layer above can accidentally forward it.
_NON_ANSWER_DELTA_FIELDS = ("reasoning_content", "reasoning", "thinking", "analysis", "scratchpad")


@contextmanager
def stream_openai_chat(client, spec, *, provider: str, model: str | None = None,
                       extra_kwargs: dict | None = None):
    """Open one real provider stream, yielding normalized StreamEvents.

    ``with stream_openai_chat(...) as events:`` — leaving the block closes the upstream stream,
    whether the reader finished, an error escaped, or the reader was closed mid-answer. That is
    the cancellation path: the provider stops generating when this block is left.

    Only ``delta.content`` becomes a ``text_delta``. A chunk's usage (final chunk, when the
    endpoint reports it) becomes a ``usage`` event, and a finish reason becomes ``finish``.
    """
    from ai.gateway import StreamEvent

    # The adapter's OWN provider-specific kwargs (a thinking switch, a resolved endpoint id), so
    # a streamed turn asks for exactly what the non-streamed one would have.
    kwargs: dict = dict(extra_kwargs or {})
    kwargs["stream"] = True
    kwargs["stream_options"] = STREAM_OPTIONS
    if spec.temperature is not None:
        kwargs["temperature"] = spec.temperature
    if spec.max_tokens is not None:
        kwargs["max_tokens"] = spec.max_tokens
    try:
        stream = client.chat.completions.create(
            model=model or spec.model,
            messages=[{"role": m.role, "content": m.content} for m in spec.messages],
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001 — the SDK's own exception space
        raise map_openai_error(exc, provider) from exc

    def _events():
        try:
            for chunk in stream:
                usage = extract_openai_usage(chunk)
                if usage.usage_source == "PROVIDER_REPORTED":
                    yield StreamEvent(type="usage", usage=usage)
                choices = _read(chunk, "choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = _read(choice, "delta")
                text = _read(delta, "content")
                if isinstance(text, str) and text:
                    yield StreamEvent(type="text_delta", text=text)
                finish = _read(choice, "finish_reason")
                if finish:
                    yield StreamEvent(type="finish", finish_reason=str(finish))
        except Exception as exc:  # noqa: BLE001 — mid-stream provider failure
            raise map_openai_error(exc, provider) from exc

    try:
        yield _events()
    finally:
        # Closing the SDK stream is what tells the provider to stop: a reader that walked away
        # (client disconnect, user stop) leaves through here.
        close = getattr(stream, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 — a close failure must not mask the real outcome
                pass
