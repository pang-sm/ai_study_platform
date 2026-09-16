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

from ai.gateway import AIRequestSpec, GatewayResponse
from ai.providers.common import extract_openai_usage, map_openai_error

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
        # Allow canonical alias → endpoint-id mapping; unknown ids pass through.
        return self.model_map.get(model, model)

    def complete(self, spec: AIRequestSpec) -> GatewayResponse:
        started_at = time.perf_counter()
        kwargs = {}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        if spec.max_tokens is not None:
            kwargs["max_tokens"] = spec.max_tokens
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
        return GatewayResponse(
            content=content.strip(),
            provider=self.name,
            model=getattr(response, "model", None) or spec.model or model,
            usage=extract_openai_usage(response),
            finish_reason=getattr(response.choices[0], "finish_reason", None) if response and response.choices else None,
            latency_ms=round((time.perf_counter() - started_at) * 1000),
            provider_request_id=getattr(response, "id", None),
        )
