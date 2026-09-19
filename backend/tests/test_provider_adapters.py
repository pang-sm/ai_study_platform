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


def test_ark_reports_canonical_alias_not_wire_model():
    # Ark echoes the deployment's version-dated model id; pricing + pool bookkeeping
    # key on the canonical alias, so the adapter must report the alias.
    a = ArkProvider(api_key="test-key", model_map={"doubao-general": "ep-abc123"})
    a._client.chat.completions.create = MagicMock(
        return_value=_fake_completion(model="doubao-seed-2-1-pro-260915"))
    resp = a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                                    model="doubao-general"))
    assert resp.model == "doubao-general"


def test_ark_unmapped_canonical_alias_fails_clearly(monkeypatch):
    # A canonical alias with no configured endpoint must fail with an explicit,
    # retriable provider_unavailable so the orchestrator falls over to another provider.
    monkeypatch.delenv("ARK_ENDPOINT_DOUBAO_GENERAL", raising=False)
    a = ArkProvider(api_key="test-key")  # no model_map → alias unresolvable
    with pytest.raises(GatewayError) as exc:
        a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                                 model="doubao-general"))
    assert exc.value.category == GatewayErrorCategory.provider_unavailable
    assert exc.value.retriable is True


def test_ark_raw_endpoint_id_passes_through(monkeypatch):
    a = ArkProvider(api_key="test-key")  # no model_map
    a._client.chat.completions.create = MagicMock(return_value=_fake_completion(model="ep-raw"))
    a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                             model="ep-raw"))
    kwargs = a._client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "ep-raw"


def test_default_provider_factory_wires_ark_endpoint_map(monkeypatch):
    from ai.orchestrator import default_provider_factory
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_ENDPOINT_DOUBAO_GENERAL", "ep-general-test")
    provider = default_provider_factory("doubao")
    assert provider.model_map == {"doubao-general": "ep-general-test"}


def _openai_status_error(cls, message, status_code):
    import httpx
    request = httpx.Request("POST", "http://test")
    response = httpx.Response(status_code, request=request)
    return cls(message, response=response, body=None)


def test_qwen_thinking_switch_translated_to_enable_thinking():
    from ai.providers import QwenProvider
    a = QwenProvider(api_key="test-key")
    a._client.chat.completions.create = MagicMock(return_value=_fake_completion())
    a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                             model="qwen3.8-flash", thinking=False))
    assert a._client.chat.completions.create.call_args.kwargs["extra_body"] == {
        "enable_thinking": False}


def test_qwen_sends_no_thinking_switch_when_unspecified():
    from ai.providers import QwenProvider
    a = QwenProvider(api_key="test-key")
    a._client.chat.completions.create = MagicMock(return_value=_fake_completion())
    a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                             model="qwen3.8-flash"))
    assert "extra_body" not in a._client.chat.completions.create.call_args.kwargs


def test_ark_sends_no_thinking_switch_when_unspecified():
    a = ArkProvider(api_key="test-key", model_map={"doubao-general": "ep-x"})
    a._client.chat.completions.create = MagicMock(return_value=_fake_completion())
    a.complete(AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),),
                             model="doubao-general"))
    assert "extra_body" not in a._client.chat.completions.create.call_args.kwargs


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
