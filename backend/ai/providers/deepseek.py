"""DeepSeek chat provider (third-party API) — the example provider for the AI gateway.

Wraps the OpenAI SDK against DeepSeek's OpenAI-compatible endpoint. This is the EXTERNAL AI
boundary only; it must never import ``zhixue_runtime`` or run a self-developed model.
"""
from __future__ import annotations

import os

from openai import OpenAI

from ai.gateway import ChatMessage

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekProvider:
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
