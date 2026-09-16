"""Shared helpers for OpenAI-compatible provider adapters (usage + error mapping)."""
from __future__ import annotations

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
