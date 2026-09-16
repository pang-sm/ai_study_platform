"""DeepSeek chat provider (third-party API) — the example provider for the AI gateway.

Wraps the OpenAI SDK against DeepSeek's OpenAI-compatible endpoint. This is the EXTERNAL AI
boundary only; it must never import ``zhixue_runtime`` or run a self-developed model.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from ai.gateway import AIRequestSpec, ChatMessage, GatewayResponse
from ai.providers.common import extract_openai_usage, map_openai_error

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekProvider:
    name = "deepseek"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
        )
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)

    def chat(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=model or self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        )
        return response.choices[0].message.content

    def complete(self, spec: AIRequestSpec) -> GatewayResponse:
        started_at = time.perf_counter()
        kwargs = {}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        if spec.max_tokens is not None:
            kwargs["max_tokens"] = spec.max_tokens
        try:
            response = self._client.chat.completions.create(
                model=spec.model or self.model,
                messages=[{"role": m.role, "content": m.content} for m in spec.messages],
                **kwargs,
            )
        except Exception as exc:
            raise map_openai_error(exc, self.name) from exc

        content = (response.choices[0].message.content or "") if response and response.choices else ""
        return GatewayResponse(
            content=content.strip(),
            provider=self.name,
            model=getattr(response, "model", None) or spec.model or self.model,
            usage=extract_openai_usage(response),
            finish_reason=getattr(response.choices[0], "finish_reason", None) if response and response.choices else None,
            latency_ms=round((time.perf_counter() - started_at) * 1000),
            provider_request_id=getattr(response, "_request_id", None) or getattr(response, "id", None),
        )
