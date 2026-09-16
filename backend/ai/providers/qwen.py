"""Qwen chat provider (OpenAI-compatible via DASHSCOPE) — external AI boundary only.

The current product's Qwen usage is multimodal OCR (qwen_parser.py), which is a separate
compatibility path and is NOT routed through the text gateway. This adapter provides the
OpenAI-compatible text path for completeness; it is opt-in (pool availability=False).
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from ai.gateway import AIRequestSpec, GatewayResponse
from ai.providers.common import extract_openai_usage, map_openai_error

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"


class QwenProvider:
    name = "qwen"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY"),
            base_url=base_url or os.getenv("QWEN_BASE_URL", DEFAULT_BASE_URL),
        )
        self.model = model or os.getenv("QWEN_MODEL", DEFAULT_MODEL)

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
