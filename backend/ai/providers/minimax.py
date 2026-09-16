"""MiniMax provider (external AI boundary only).

MiniMax exposes an OpenAI-compatible endpoint (``api.minimax.chat/v1``). The native
MiniMax SDK and the OpenAI-compatible path are distinct; this adapter uses only the
OpenAI-compatible path. Do not conflate a Token Plan with metered-API pricing.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from ai.gateway import AIRequestSpec, GatewayResponse
from ai.providers.common import extract_openai_usage, map_openai_error

DEFAULT_BASE_URL = "https://api.minimax.chat/v1"


class MiniMaxProvider:
    name = "minimax"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("MINIMAX_API_KEY"),
            base_url=base_url or os.getenv("MINIMAX_BASE_URL", DEFAULT_BASE_URL),
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
