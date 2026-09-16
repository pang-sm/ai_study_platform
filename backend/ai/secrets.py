"""AI provider secret handling (STEP 7C-P).

Single source of truth for canonical env names + base URLs + auth method. This module
NEVER prints raw keys — only ``configured`` booleans and SHA256 prefix fingerprints.

Keys are read from the environment only (after the caller runs load_dotenv). The
canonical secret file is ``backend/.env.local`` (gitignored); ``backend/.env`` is the
legacy local file and is also gitignored.
"""
from __future__ import annotations

import hashlib
import os

# Canonical env names (frozen). Legacy aliases are mapped to these where the codebase
# already used a different name.
CANONICAL_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "doubao": "ARK_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "glm": "ZHIPUAI_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}

# Legacy aliases accepted for reading (never for writing).
_ALIASES = {
    "DEEPSEEK_API_KEY": ["DEEPSEEK_API_KEY"],
    "DASHSCOPE_API_KEY": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"],
    "ARK_API_KEY": ["ARK_API_KEY", "VOLCENGINE_API_KEY", "VOLC_ARK_API_KEY"],
    "MOONSHOT_API_KEY": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
    "ZHIPUAI_API_KEY": ["ZHIPUAI_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY"],
    "MINIMAX_API_KEY": ["MINIMAX_API_KEY", "MINIMAX_GROUP_ID"],
}

# Provider metadata: OpenAI-compatible base_url + notes on auth model.
PROVIDER_SPECS = {
    "deepseek": {"label": "DeepSeek", "base_url": "https://api.deepseek.com",
                 "auth": "Bearer", "openai_compatible": True},
    "qwen": {"label": "Alibaba Model Studio / Qwen",
             "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "auth": "Bearer", "openai_compatible": True},
    "doubao": {"label": "Volcengine Ark / Doubao",
               "base_url": "https://ark.cn-beijing.volces.com/api/v3",
               "auth": "Bearer", "openai_compatible": True,
               "note": "may require endpoint-id model mapping (id:ep-...)"},
    "kimi": {"label": "Moonshot / Kimi", "base_url": "https://api.moonshot.cn/v1",
             "auth": "Bearer", "openai_compatible": True},
    "glm": {"label": "Zhipu / GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "auth": "Bearer", "openai_compatible": True},
    "minimax": {"label": "MiniMax", "base_url": "https://api.minimax.chat/v1",
                "auth": "Bearer", "openai_compatible": True,
                "note": "OpenAI-compatible path; native SDK differs"},
}

ALL_PROVIDERS = tuple(CANONICAL_ENV.keys())


def _read_env(env_var: str) -> str:
    """Read a canonical env var, falling back to legacy aliases. Returns '' if unset."""
    for alias in _ALIASES.get(env_var, [env_var]):
        value = os.getenv(alias, "")
        if value and value.strip():
            return value.strip()
    return ""


def get_api_key(provider: str) -> str:
    env_var = CANONICAL_ENV.get((provider or "").strip().lower(), "")
    if not env_var:
        return ""
    return _read_env(env_var)


def is_configured(provider: str) -> bool:
    return bool(get_api_key(provider))


def fingerprint(key: str) -> str:
    """SHA256(key) prefix-8 hex — safe, non-reversible audit marker."""
    if not key:
        return ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def provider_status(provider: str) -> dict:
    key = get_api_key(provider)
    spec = PROVIDER_SPECS.get(provider, {})
    return {
        "provider": provider,
        "label": spec.get("label", provider),
        "env_var": CANONICAL_ENV.get(provider, ""),
        "base_url": spec.get("base_url", ""),
        "configured": bool(key),
        "fingerprint": fingerprint(key) if key else "",
    }


def configured_providers() -> dict[str, dict]:
    return {p: provider_status(p) for p in ALL_PROVIDERS}
