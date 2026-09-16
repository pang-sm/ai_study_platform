"""STEP 7C-P: provider adapters (mocked OpenAI client, no real API)."""
from unittest.mock import MagicMock

import pytest

from ai.gateway import AIRequestSpec, ChatMessage, GatewayError, GatewayErrorCategory
from ai.providers import (
    ArkProvider, DeepSeekProvider, MiniMaxProvider, MoonshotProvider,
    QwenProvider, ZhipuProvider,
)

_ADAPTERS = [
    (DeepSeekProvider, "deepseek"),
    (QwenProvider, "qwen"),
    (ArkProvider, "doubao"),
    (MoonshotProvider, "kimi"),
    (ZhipuProvider, "glm"),
    (MiniMaxProvider, "minimax"),
]


def _fake_completion(content="ok", model="m"):
    fc = MagicMock()
    fc.choices = [MagicMock()]
    fc.choices[0].message.content = content
    fc.choices[0].finish_reason = "stop"
    fc.model = model
    fc.usage = MagicMock()
    fc.usage.prompt_tokens = 10
    fc.usage.completion_tokens = 5
    fc.usage.total_tokens = 15
    fc.id = "req-1"
    return fc


@pytest.mark.parametrize("cls,name", _ADAPTERS)
def test_adapter_name_and_complete(cls, name):
    a = cls(api_key="test-key")
    assert a.name == name
    a._client.chat.completions.create = MagicMock(return_value=_fake_completion())
    resp = a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                                    model="m", max_tokens=32))
    assert resp.content == "ok"
    assert resp.provider == name
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5
    assert resp.usage.usage_source == "PROVIDER_REPORTED"


def test_ark_model_map_resolution():
    a = ArkProvider(api_key="test-key", model_map={"doubao-pro": "ep-abc123"})
    a._client.chat.completions.create = MagicMock(return_value=_fake_completion(model="ep-abc123"))
    a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                             model="doubao-pro"))
    # the wire model is the endpoint-id, not the alias
    kwargs = a._client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "ep-abc123"


def _openai_status_error(cls, message, status_code):
    import httpx
    request = httpx.Request("POST", "http://test")
    response = httpx.Response(status_code, request=request)
    return cls(message, response=response, body=None)


def test_error_mapping_authentication():
    a = DeepSeekProvider(api_key="test-key")
    import openai
    a._client.chat.completions.create = MagicMock(
        side_effect=_openai_status_error(openai.AuthenticationError, "bad", 401))
    with pytest.raises(GatewayError) as exc:
        a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),), model="m"))
    assert exc.value.category == GatewayErrorCategory.authentication


def test_error_mapping_rate_limited():
    a = DeepSeekProvider(api_key="test-key")
    import openai
    a._client.chat.completions.create = MagicMock(
        side_effect=_openai_status_error(openai.RateLimitError, "rl", 429))
    with pytest.raises(GatewayError) as exc:
        a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),), model="m"))
    assert exc.value.category == GatewayErrorCategory.rate_limited
    assert exc.value.retriable is True
