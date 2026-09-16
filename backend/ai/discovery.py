"""Live account discovery + smoke test (STEP 7C-P).

Reads keys from the environment (via ``ai.secrets``) and performs:
  * model discovery (``/models`` where the provider exposes an OpenAI-compatible list)
  * a minimal smoke request through the gateway adapter (billable usage goes through
    the same code path as production).

No raw keys are ever returned or printed. This module is used by the health-check CLI
and by tests (tests use FakeProvider / mocked HTTP, never real keys).
"""
from __future__ import annotations

from .gateway import AIRequestSpec, ChatMessage, GatewayError
from .secrets import ALL_PROVIDERS, get_api_key, provider_status

SMOKE_PROMPT = "请用一句话回答：1+1等于几？"
SMOKE_MAX_TOKENS = 32


def _openai_client(provider: str):
    from openai import OpenAI
    from .secrets import PROVIDER_SPECS
    key = get_api_key(provider)
    spec = PROVIDER_SPECS.get(provider, {})
    return OpenAI(api_key=key, base_url=spec.get("base_url", "")), spec


def list_models(provider: str) -> dict:
    """Return {'ok', 'models': [...], 'error'} for a configured provider."""
    if not get_api_key(provider):
        return {"ok": False, "models": [], "error": "not_configured"}
    client, _ = _openai_client(provider)
    try:
        listing = client.models.list()
        models = [m.id for m in listing.data]
        return {"ok": True, "models": models, "error": None}
    except Exception as exc:
        return {"ok": False, "models": [], "error": type(exc).__name__}


def smoke_test(provider: str, model: str, max_tokens: int = SMOKE_MAX_TOKENS) -> dict:
    """One minimal billable request through the gateway adapter. Never returns content
    larger than ~max_tokens. Returns a normalized result (no raw key)."""
    from .orchestrator import default_provider_factory
    if not get_api_key(provider):
        return {"ok": False, "status": "not_configured", "error": "not_configured"}
    adapter = default_provider_factory(provider)
    spec = AIRequestSpec(
        messages=(ChatMessage(role="user", content=SMOKE_PROMPT),),
        model=model, temperature=None, max_tokens=max_tokens, stream=False,
    )
    try:
        response = adapter.complete(spec)
        usage = response.usage
        return {
            "ok": True,
            "status": "success",
            "model": response.model,
            "content_length": len(response.content),
            "finish_reason": response.finish_reason,
            "latency_ms": response.latency_ms,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "usage_source": usage.usage_source,
        }
    except GatewayError as exc:
        return {"ok": False, "status": exc.category.value,
                "error": exc.category.value, "message": exc.message}
    except Exception as exc:
        return {"ok": False, "status": "error", "error": type(exc).__name__}


def account_matrix() -> dict:
    """Provider account matrix (no raw keys)."""
    return {p: provider_status(p) for p in ALL_PROVIDERS}
