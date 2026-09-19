"""ZHIXUE_MODEL_POOL_CALIBRATION_V1 Stage 2 runner with cost accounting.

Runs the fixed benchmark over a Stage-1 shortlist, reports per-model pass/fail +
latency + token cost (estimated from the pricing registry). No raw keys printed.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402
for env_path in (BACKEND_DIR / ".env.local", BACKEND_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path)

from ai import benchmark, cost  # noqa: E402
from ai.gateway import AIRequestSpec, ChatMessage  # noqa: E402
from ai.orchestrator import default_provider_factory  # noqa: E402
from ai.pricing import compute_cost_cny, get_pricing  # noqa: E402

MAX_OUTPUT = 200
# Thinking models spend their budget on hidden reasoning before emitting content; at
# max_tokens=200 the content came back empty for every thinking model, so they are
# measured at 800 (identical policy for every model — fair, not per-model tuning).
MAX_OUTPUT_THINKING = 800
CASE_INTERVAL_SECONDS = 3  # courtesy spacing; Kimi org rate-limits tight loops

THINKING_MODELS = {
    ("deepseek", "deepseek-v4-pro"),
    ("kimi", "kimi-k2.6"),
    ("kimi", "kimi-k2.7-code"),
    ("glm", "glm-5"),
    ("minimax", "MiniMax-M3"),
    ("doubao", "doubao-general"),
    ("doubao", "doubao-agent"),
}


def max_output_for(provider: str, model: str) -> int:
    return MAX_OUTPUT_THINKING if (provider, model) in THINKING_MODELS else MAX_OUTPUT


SHORTLIST = [
    ("deepseek", "deepseek-flash"),
    ("deepseek", "deepseek-v4-pro"),
    ("qwen", "qwen3.8-flash"),
    ("qwen", "qwen3.8-max"),
    ("kimi", "kimi-k2.6"),
    ("kimi", "kimi-k2.7-code"),
    ("glm", "glm-5.3-flash"),
    ("glm", "glm-5.3"),
    ("glm", "glm-5"),
    ("minimax", "MiniMax-M3"),
    ("minimax", "MiniMax-M2.7-highspeed"),
    ("doubao", "doubao-general"),
]


def run_model(provider: str, model: str, cases=None,
              thinking: bool | None = None, max_tokens: int | None = None) -> dict:
    import time
    cases = cases if cases is not None else benchmark.CASES
    max_tokens = max_tokens if max_tokens is not None else max_output_for(provider, model)
    adapter = default_provider_factory(provider)
    responses = {}
    lat = {}
    in_tok = out_tok = reasoning_tok = 0
    for i, case in enumerate(cases):
        if i:
            time.sleep(CASE_INTERVAL_SECONDS)
        spec = AIRequestSpec(messages=(ChatMessage(role="user", content=case["prompt"]),),
                             model=model, temperature=None, max_tokens=max_tokens,
                             thinking=thinking)
        try:
            resp = adapter.complete(spec)
            responses[case["id"]] = resp.content or ""
            lat[case["id"]] = resp.latency_ms
            in_tok += resp.usage.input_tokens or 0
            out_tok += resp.usage.output_tokens or 0
            reasoning_tok += resp.usage.reasoning_tokens or 0
        except Exception as exc:
            responses[case["id"]] = ""
            lat[case["id"]] = -1
    score = benchmark.score_all(responses, cases)
    return {"score": score, "lat": lat, "in_tok": in_tok, "out_tok": out_tok,
            "reasoning_tok": reasoning_tok, "max_tokens": max_tokens,
            "thinking": thinking, "responses": responses}


def main() -> int:
    # Optional filters: `... run_calibration_benchmark.py doubao-general` runs one model.
    filters = [a.lower() for a in sys.argv[1:] if not a.startswith("-")]
    shortlist = [t for t in SHORTLIST
                 if not filters or any(f in t[1].lower() or f == t[0] for f in filters)]
    label = "GENERAL_BENCHMARK"
    print(f"{label} {benchmark.BENCHMARK_VERSION} · "
          f"{len(shortlist)} models × {len(benchmark.CASES)} cases\n")
    total_cost = 0.0
    for provider, model in shortlist:
        r = run_model(provider, model)
        s = r["score"]
        pricing = get_pricing(provider, model)
        cny = 0.0
        if pricing:
            cny = compute_cost_cny(pricing, r["in_tok"], r["out_tok"])
        total_cost += cny
        lats = [v for v in r["lat"].values() if v >= 0]
        lat_s = f"{sum(lats) // len(lats)}ms" if lats else "-"
        print(f"{provider}/{model}: {s['passed']}/{s['total']} passed · "
              f"max_tokens={r['max_tokens']} · in={r['in_tok']} out={r['out_tok']} "
              f"(reasoning={r['reasoning_tok']}) · ~¥{cny:.4f} · avg_lat={lat_s}")
        for c in s["results"]:
            print(f"    {'PASS' if c['passed'] else 'FAIL'} {c['id']}")
    print(f"\nTOTAL_ESTIMATED_COST ≈ ¥{total_cost:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
