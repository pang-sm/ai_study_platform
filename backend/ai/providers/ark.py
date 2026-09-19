"""Volcengine Ark / Doubao provider (external AI boundary only).

Ark exposes an OpenAI-compatible endpoint. Accounts may be on the endpoint-id model
(``id:ep-...``); ``model_map`` translates a canonical alias to the account's endpoint
identifier. The product's normal online-inference endpoint must be preferred — never
silently route into a Coding/Agent plan endpoint the user happened to buy.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from ai.gateway import AIRequestSpec, GatewayError, GatewayErrorCategory, GatewayResponse
from ai.providers.common import extract_openai_usage, map_openai_error
from ai.secrets import ARK_ENDPOINT_ENV

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


class ArkProvider:
    name = "doubao"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model_map: dict[str, str] | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("ARK_API_KEY"),
            base_url=base_url or os.getenv("ARK_BASE_URL", DEFAULT_BASE_URL),
        )
        self.model_map = model_map or {}

    def _resolve_model(self, model: str) -> str:
        # Canonical alias → endpoint id; unknown ids (e.g. a raw ``ep-...``) pass through.
        resolved = self.model_map.get(model)
        if resolved:
            return resolved
        if model in ARK_ENDPOINT_ENV:
            # Known alias, no configured endpoint. Retriable so the orchestrator falls
            # over to another qualified provider instead of failing the request.
            raise GatewayError(
                GatewayErrorCategory.provider_unavailable,
                f"ark endpoint not configured for {model} "
                f"(set {ARK_ENDPOINT_ENV[model]})", self.name, retriable=True)
        return model

    def complete(self, spec: AIRequestSpec) -> GatewayResponse:
        started_at = time.perf_counter()
        kwargs = {}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        if spec.max_tokens is not None:
            kwargs["max_tokens"] = spec.max_tokens
        if spec.thinking is not None:
            # Ark thinking switch. Only enabled/disabled are accepted by Doubao seed
            # models ("auto" is rejected with InvalidParameter); reasoning has no hard
            # token cap, so disabling thinking is the only way to bound billable output.
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled" if spec.thinking else "disabled"}}
        model = self._resolve_model(spec.model or "")
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in spec.messages],
                **kwargs,
            )
        except Exception as exc:
            raise map_openai_error(exc, self.name) from exc

        content = (response.choices[0].message.content or "") if response and response.choices else ""
        # For aliased endpoints Ark echoes the deployment's underlying model id
        # (version-dated, e.g. "doubao-seed-2-1-pro-260915"), which is not a pricing or
        # pool key. Report the canonical alias the router selected instead; the wire id
        # stays visible in the request itself.
        reported = getattr(response, "model", None)
        canonical = spec.model if spec.model in self.model_map else (reported or spec.model or model)
        return GatewayResponse(
            content=content.strip(),
            provider=self.name,
            model=canonical,
            usage=extract_openai_usage(response),
            finish_reason=getattr(response.choices[0], "finish_reason", None) if response and response.choices else None,
            latency_ms=round((time.perf_counter() - started_at) * 1000),
            provider_request_id=getattr(response, "id", None),
        )
