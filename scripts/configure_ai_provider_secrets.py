"""Interactive AI-provider secret configuration (STEP 7C-P).

Run locally:
    python scripts/configure_ai_provider_secrets.py

Uses getpass.getpass() so keys are typed hidden in PowerShell and never echoed.
Writes ONLY to ``backend/.env.local`` (gitignored). Empty input keeps the current
value / skips the provider. A fingerprint (SHA256 prefix) is printed for confirmation —
never the key itself.

Canonical env names (frozen):
    DEEPSEEK_API_KEY, DASHSCOPE_API_KEY, ARK_API_KEY,
    MOONSHOT_API_KEY, ZHIPUAI_API_KEY, MINIMAX_API_KEY
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
ENV_LOCAL = BACKEND_DIR / ".env.local"
ENV_LEGACY = BACKEND_DIR / ".env"

PROVIDERS = [
    ("deepseek", "DEEPSEEK_API_KEY", "DeepSeek"),
    ("qwen", "DASHSCOPE_API_KEY", "Alibaba Model Studio / Qwen"),
    ("doubao", "ARK_API_KEY", "Volcengine Ark / Doubao"),
    ("kimi", "MOONSHOT_API_KEY", "Moonshot / Kimi"),
    ("glm", "ZHIPUAI_API_KEY", "Zhipu / GLM"),
    ("minimax", "MINIMAX_API_KEY", "MiniMax"),
]

# Legacy alias fallbacks (read-only) so existing keys are not duplicated.
ALIASES = {
    "DEEPSEEK_API_KEY": ["DEEPSEEK_API_KEY"],
    "DASHSCOPE_API_KEY": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"],
    "ARK_API_KEY": ["ARK_API_KEY", "VOLCENGINE_API_KEY"],
    "MOONSHOT_API_KEY": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
    "ZHIPUAI_API_KEY": ["ZHIPUAI_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY"],
    "MINIMAX_API_KEY": ["MINIMAX_API_KEY"],
}


def _load_existing() -> dict[str, str]:
    """Read existing keys from backend/.env.local then backend/.env (legacy)."""
    existing: dict[str, str] = {}
    for path in (ENV_LOCAL, ENV_LEGACY):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and value and name not in existing:
                existing[name] = value
    return existing


def _resolve(existing: dict[str, str], name: str) -> str:
    for alias in ALIASES.get(name, [name]):
        if existing.get(alias):
            return existing[alias]
    return ""


def _fingerprint(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def main() -> int:
    print("智学AI — AI Provider Secret 配置（隐藏输入，绝不回显）\n")
    existing = _load_existing()
    out: dict[str, str] = {}

    for _provider, env_name, label in PROVIDERS:
        current = _resolve(existing, env_name)
        hint = f"（已配置 fingerprint={_fingerprint(current)}，留空保持不变）" if current else "（留空跳过）"
        prompt = f"[{label}] {env_name} {hint}\n输入 API Key（隐藏）: "
        try:
            entered = getpass.getpass(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return 1
        entered = entered.strip()
        if entered:
            out[env_name] = entered
        elif current:
            out[env_name] = current

    if not out:
        print("未输入任何新 key，未写入文件。")
        return 0

    # Write canonical keys entered/present, PRESERVING every other line of the file
    # (e.g. ARK_ENDPOINT_* — non-secret provider config lives here too).
    preserved: list[str] = []
    if ENV_LOCAL.exists():
        for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
            name = line.split("=", 1)[0].strip() if "=" in line else ""
            if name and name in out:
                continue
            preserved.append(line)

    lines = [f"{name}={value}" for name, value in out.items()]
    body = [ln for ln in preserved if ln.strip()] + lines
    ENV_LOCAL.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(f"\n已写入 {ENV_LOCAL}")
    print("确认指纹（SHA256 prefix，非 key）：")
    for name, value in out.items():
        print(f"  {name}: fingerprint={_fingerprint(value)}")
    print("\n注意：backend/.env.local 已被 .gitignore 忽略，请勿提交。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
