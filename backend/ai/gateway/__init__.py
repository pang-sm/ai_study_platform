"""External AI Gateway — unified minimal interface for third-party LLM providers.

This is the EXTERNAL AI boundary (DeepSeek / Qwen / ...). It is strictly separate from the
Scientific Runtime Service (self-developed models). The gateway never imports
``zhixue_runtime`` and never runs a self-developed scientific model.
"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@runtime_checkable
class ChatProvider(Protocol):
    """Minimal synchronous chat-completion contract shared by all third-party providers."""

    def chat(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        ...
