"""STEP 7C-P: model discovery / probe / usage normalization (mocked HTTP, no real key)."""
from unittest.mock import MagicMock, patch

from ai import discovery
from ai.gateway import ProviderUsage
from ai.providers.common import extract_openai_usage


def test_extract_openai_usage_reported():
    resp = MagicMock()
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    resp.usage.total_tokens = 150
    resp.usage.prompt_tokens_details = MagicMock()
    resp.usage.prompt_tokens_details.cached_tokens = 10
    u = extract_openai_usage(resp)
    assert u.input_tokens == 100 and u.output_tokens == 50
    assert u.cached_input_tokens == 10
    assert u.usage_source == "PROVIDER_REPORTED"


def test_extract_openai_usage_unknown():
    resp = MagicMock()
    resp.usage = None
    u = extract_openai_usage(resp)
    assert u.input_tokens is None and u.usage_source == "UNKNOWN"


def test_list_models_returns_ids(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    fake_client = MagicMock()
    fake_client.models.list.return_value.data = [MagicMock(id="m1"), MagicMock(id="m2")]
    with patch.object(discovery, "_openai_client", return_value=(fake_client, {})):
        r = discovery.list_models("deepseek")
    assert r["ok"] is True and r["models"] == ["m1", "m2"]


def test_list_models_not_configured(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    r = discovery.list_models("doubao")
    assert r["ok"] is False and r["error"] == "not_configured"


def test_smoke_test_no_raw_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-very-secret")
    from ai.providers import FakeProvider
    with patch("ai.orchestrator.default_provider_factory",
               return_value=FakeProvider(provider="deepseek", model="deepseek-flash")):
        r = discovery.smoke_test("deepseek", "deepseek-flash")
    assert r["ok"] is True
    assert "sk-test" not in str(r)  # never leaks the key
    assert "input_tokens" in r and "output_tokens" in r


def test_account_matrix_no_raw_keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-matrix-secret")
    matrix = discovery.account_matrix()
    assert "deepseek" in matrix
    assert "sk-matrix" not in str(matrix)
