"""ZHIXUE_MODEL_POOL_CALIBRATION_V1 live runner (Stage 2, cost-controlled).

Run only AFTER Stage 1 smoke tests pass. Each candidate runs each case ONCE with
max_tokens capped; total cost is minimal. Prints per-model pass/fail + latency/usage.
No raw keys are printed.

Usage:
    python scripts/run_benchmark.py [provider model ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

for env_path in (BACKEND_DIR / ".env.local", BACKEND_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path)

from ai import benchmark  # noqa: E402
from ai import discovery  # noqa: E402

MAX_OUTPUT = 200


def run_model(provider: str, model: str) -> dict:
    responses = {}
    for case in benchmark.CASES:
        from ai.gateway import AIRequestSpec, ChatMessage
        from ai.orchestrator import default_provider_factory
        adapter = default_provider_factory(provider)
        spec = AIRequestSpec(messages=(ChatMessage(role="user", content=case["prompt"]),),
                             model=model, temperature=None, max_tokens=MAX_OUTPUT)
        try:
            resp = adapter.complete(spec)
            responses[case["id"]] = resp.content
        except Exception as exc:
            responses[case["id"]] = f"[ERROR] {type(exc).__name__}"
    return benchmark.score_all(responses)


def main(argv: list[str]) -> int:
    pairs = []
    if len(argv) >= 2:
        for i in range(0, len(argv) - 1, 2):
            pairs.append((argv[i], argv[i + 1]))
    else:
        # default shortlist (smoke-passed candidates)
        pairs = [("deepseek", "deepseek-flash"), ("deepseek", "deepseek-v4-pro"),
                 ("qwen", "qwen-flash"), ("qwen", "qwen-plus")]

    for provider, model in pairs:
        r = run_model(provider, model)
        print(f"{provider}/{model}: {r['passed']}/{r['total']} passed")
        for case in r["results"]:
            mark = "PASS" if case["passed"] else "FAIL"
            print(f"   {mark} {case['id']} ({case['method']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
