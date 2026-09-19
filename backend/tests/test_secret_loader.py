"""STEP 7C-P: secret loader must never leak raw keys (fingerprint only)."""
from ai.secrets import (
    ALL_PROVIDERS, ARK_ENDPOINT_ENV, ark_endpoint_map, configured_providers, fingerprint,
    get_api_key, provider_status,
)


def test_fingerprint_is_not_raw_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-abcdef123456")
    key = get_api_key("deepseek")
    assert key == "sk-test-abcdef123456"
    fp = fingerprint(key)
    assert len(fp) == 8
    assert fp != key
    assert "sk-test" not in fp
    st = provider_status("deepseek")
    # the status dict never carries the raw key
    assert "sk-test" not in str(st)
    assert st["fingerprint"] == fp


def test_provider_status_has_no_raw_key(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-secret-dashscope-value")
    st = provider_status("qwen")
    assert st["configured"] is True
    assert "sk-secret" not in str(st)
    assert len(st["fingerprint"]) == 8


def test_unconfigured_provider_fingerprint_empty(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    st = provider_status("doubao")
    assert st["configured"] is False
    assert st["fingerprint"] == ""


def test_configured_providers_shape(monkeypatch):
    for p in ALL_PROVIDERS:
        monkeypatch.delenv(f"X_UNUSED_{p}", raising=False)
    status = configured_providers()
    assert set(status.keys()) == set(ALL_PROVIDERS)
    for row in status.values():
        assert "provider" in row and "configured" in row and "fingerprint" in row


def test_legacy_alias_read(monkeypatch):
    # DASHSCOPE key readable via legacy QWEN_API_KEY alias
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "sk-legacy-alias-value")
    assert get_api_key("qwen") == "sk-legacy-alias-value"


def test_ark_endpoint_map_reads_canonical_env(monkeypatch):
    monkeypatch.setenv("ARK_ENDPOINT_DOUBAO_GENERAL", "ep-general-test")
    monkeypatch.delenv("ARK_ENDPOINT_DOUBAO_AGENT", raising=False)
    assert ark_endpoint_map() == {"doubao-general": "ep-general-test"}


def test_ark_endpoint_map_empty_when_unset(monkeypatch):
    for env_var in ARK_ENDPOINT_ENV.values():
        monkeypatch.delenv(env_var, raising=False)
    assert ark_endpoint_map() == {}


def test_ark_endpoint_map_has_no_source_hardcoded_endpoint_ids():
    # endpoint ids are deployment config, never source
    for env_var in ARK_ENDPOINT_ENV.values():
        assert env_var.startswith("ARK_ENDPOINT_")
    assert all(not v.startswith("ep-") for v in ARK_ENDPOINT_ENV.values())
