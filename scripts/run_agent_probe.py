"""AGENT_CAPABILITY_PROBE runner — separate from the general calibration benchmark.

A coding/agent-oriented model is not eliminated for failing general pedagogy cases.
This screens it on programming explanation, non-trivial debugging and strict structured
output instead, using the same deterministic scoring as the general benchmark.

Usage:
    python scripts/run_agent_probe.py doubao-agent
Optionally also run the general 6-case benchmark for the same model (reported under a
separate label so the two results are never conflated):
    python scripts/run_agent_probe.py doubao-agent --also-general
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

from ai import benchmark  # noqa: E402
from ai.pricing import compute_cost_cny, get_pricing  # noqa: E402
from run_calibration_benchmark import run_model  # noqa: E402

PROVIDER = "doubao"


def _report(label: str, provider: str, model: str, cases, r: dict) -> None:
    s = r["score"]
    pricing = get_pricing(provider, model)
    cny = compute_cost_cny(pricing, r["in_tok"], r["out_tok"]) if pricing else 0.0
    price_note = "priced" if pricing else "NO_PRICING_ENTRY"
    lats = [v for v in r["lat"].values() if v >= 0]
    lat_s = f"{sum(lats) // len(lats)}ms" if lats else "-"
    print(f"[{label}] {provider}/{model}: {s['passed']}/{s['total']} passed · "
          f"max_tokens={r['max_tokens']} · in={r['in_tok']} out={r['out_tok']} "
          f"(reasoning={r['reasoning_tok']}) · ~¥{cny:.4f} [{price_note}] · avg_lat={lat_s}")
    for c in s["results"]:
        print(f"    {'PASS' if c['passed'] else 'FAIL'} {c['id']} ({c['method']})")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    also_general = "--also-general" in sys.argv
    model = args[0] if args else "doubao-agent"

    print(f"{benchmark.AGENT_PROBE_VERSION} · {model} · "
          f"{len(benchmark.AGENT_PROBE_CASES)} probe cases\n")
    _report("AGENT_CAPABILITY_PROBE", PROVIDER, model,
            benchmark.AGENT_PROBE_CASES, run_model(PROVIDER, model, benchmark.AGENT_PROBE_CASES))

    if also_general:
        print()
        _report("GENERAL_BENCHMARK", PROVIDER, model,
                benchmark.CASES, run_model(PROVIDER, model, benchmark.CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
