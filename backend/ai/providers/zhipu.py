"""Zhipu / GLM provider (external AI boundary only).

Zhipu BigModel exposes an OpenAI-compatible endpoint (``open.bigmodel.cn/api/paas/v4``).
Model IDs must be live-verified; do not rely on stale GLM-4 naming.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from ai.gateway import AIRequestSpec, GatewayResponse
from ai.providers.common import extract_openai_usage, map_openai_error

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


class ZhipuProvider:
    name = "glm"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("ZHIPUAI_API_KEY"),
            base_url=base_url or os.getenv("ZHIPUAI_BASE_URL", DEFAULT_BASE_URL),
        )

    def complete(self, spec: AIRequestSpec) -> GatewayResponse:
        started_at = time.perf_counter()
        kwargs = {}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        if spec.max_tokens is not None:
            kwargs["max_tokens"] = spec.max_tokens
        try:
            response = self._client.chat.completions.create(
                model=spec.model,
                messages=[{"role": m.role, "content": m.content} for m in spec.messages],
                **kwargs,
            )
        except Exception as exc:
            raise map_openai_error(exc, self.name) from exc

        content = (response.choices[0].message.content or "") if response and response.choices else ""
        return GatewayResponse(
            content=content.strip(),
            provider=self.name,
            model=getattr(response, "model", None) or spec.model,
            usage=extract_openai_usage(response),
            finish_reason=getattr(response.choices[0], "finish_reason", None) if response and response.choices else None,
            latency_ms=round((time.perf_counter() - started_at) * 1000),
            provider_request_id=getattr(response, "id", None),
        )
