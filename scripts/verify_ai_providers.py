"""Lightweight internal AI-provider health check (STEP 7C-P).

Run locally (no public endpoint):
    cd backend && ..\\.venv\\Scripts\\python.exe -m scripts.verify_ai_providers
or:
    python scripts/verify_ai_providers.py

Prints account matrix (configured + fingerprint only), then model discovery + a
minimal smoke test per configured provider. NO raw keys are ever printed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

for env_path in (BACKEND_DIR / ".env.local", BACKEND_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path)

from ai import discovery  # noqa: E402
from ai.secrets import ALL_PROVIDERS, provider_status  # noqa: E402

# Probe models: canonical aliases used ONLY as a smoke-test entry point. Live
# discovery / the candidate registry is the source of truth for real model IDs.
PROBE_MODELS = {
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
    "doubao": None,   # Ark may require endpoint-id; smoke skipped unless mapped
    "kimi": None,     # discovered via /models where supported
    "glm": None,
    "minimax": None,
}


def _masked_fingerprint(status: dict) -> str:
    return status.get("fingerprint") or "-"


def main() -> int:
    print("=== AI Provider Account Matrix ===\n")
    for p in ALL_PROVIDERS:
        s = provider_status(p)
        cfg = "configured" if s["configured"] else "NOT_CONFIGURED"
        print(f"  {p:<10} {s['label']:<34} {cfg:<16} fingerprint={_masked_fingerprint(s)}")

    print("\n=== Live discovery + smoke test ===\n")
    for p in ALL_PROVIDERS:
        s = provider_status(p)
        if not s["configured"]:
            print(f"[{p}] SKIPPED (not configured)")
            continue
        listing = discovery.list_models(p)
        if listing["ok"]:
            models = listing["models"]
            print(f"[{p}] model discovery: {len(models)} models "
                  f"(first: {', '.join(models[:5])})")
        else:
            print(f"[{p}] model discovery: UNSUPPORTED/FAILED ({listing['error']})")

        probe = PROBE_MODELS.get(p)
        if probe:
            r = discovery.smoke_test(p, probe)
            if r["ok"]:
                print(f"[{p}] smoke {probe}: OK latency={r['latency_ms']}ms "
                      f"in={r['input_tokens']} out={r['output_tokens']} "
                      f"usage={r['usage_source']} finish={r['finish_reason']}")
            else:
                print(f"[{p}] smoke {probe}: {r['status']} ({r.get('error')})")
        else:
            print(f"[{p}] smoke: SKIPPED (no probe model mapped)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
