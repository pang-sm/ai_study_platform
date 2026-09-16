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
]


def run_model(provider: str, model: str) -> dict:
    adapter = default_provider_factory(provider)
    responses = {}
    lat = {}
    in_tok = out_tok = 0
    for case in benchmark.CASES:
        spec = AIRequestSpec(messages=(ChatMessage(role="user", content=case["prompt"]),),
                             model=model, temperature=None, max_tokens=MAX_OUTPUT)
        try:
            resp = adapter.complete(spec)
            responses[case["id"]] = resp.content or ""
            lat[case["id"]] = resp.latency_ms
            in_tok += resp.usage.input_tokens or 0
            out_tok += resp.usage.output_tokens or 0
        except Exception as exc:
            responses[case["id"]] = ""
            lat[case["id"]] = -1
    score = benchmark.score_all(responses)
    return {"score": score, "lat": lat, "in_tok": in_tok, "out_tok": out_tok}


def main() -> int:
    print(f"Benchmark {benchmark.BENCHMARK_VERSION} · {len(SHORTLIST)} models × {len(benchmark.CASES)} cases\n")
    total_cost = 0.0
    for provider, model in SHORTLIST:
        r = run_model(provider, model)
        s = r["score"]
        pricing = get_pricing(provider, model)
        cny = 0.0
        if pricing:
            cny = compute_cost_cny(pricing, r["in_tok"], r["out_tok"])
        total_cost += cny
        avg_lat = sum(v for v in r["lat"].values() if v >= 0)
        n_lat = sum(1 for v in r["lat"].values() if v >= 0)
        lat_s = f"{avg_lat // n_lat}ms" if n_lat else "-"
        print(f"{provider}/{model}: {s['passed']}/{s['total']} passed · "
              f"in={r['in_tok']} out={r['out_tok']} · ~¥{cny:.4f} · avg_lat={lat_s}")
        for c in s["results"]:
            print(f"    {'PASS' if c['passed'] else 'FAIL'} {c['id']}")
    print(f"\nTOTAL_ESTIMATED_COST ≈ ¥{total_cost:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
