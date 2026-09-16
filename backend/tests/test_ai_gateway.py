"""AI gateway + example provider tests (mocked third-party client, no real API)."""
from unittest.mock import MagicMock

from ai.gateway import ChatMessage
from ai.providers import DeepSeekProvider


def test_chat_message_shape():
    m = ChatMessage(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_deepseek_provider_chat_roundtrip():
    provider = DeepSeekProvider(api_key="test-key", base_url="https://api.deepseek.com", model="deepseek-chat")

    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock()]
    fake_completion.choices[0].message.content = "olleh"
    provider._client.chat.completions.create = MagicMock(return_value=fake_completion)

    result = provider.chat([ChatMessage(role="user", content="hello")])
    assert result == "olleh"

    # verify the provider translated ChatMessage -> OpenAI wire shape and passed the model
    call_kwargs = provider._client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "deepseek-chat"
    assert call_kwargs.kwargs["messages"] == [{"role": "user", "content": "hello"}]
