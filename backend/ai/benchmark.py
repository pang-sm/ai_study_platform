"""ZHIXUE_MODEL_POOL_CALIBRATION_V1 — small, fixed, provider-neutral benchmark.

Purpose: screen out clearly unsuitable models and seed the initial qualified pool
(NOT a benchmark paper). Deterministic scoring where possible (exact answer / JSON
validity / required fields); qualitative teaching-quality is a separate rubric.

Run LIVE via scripts/run_benchmark.py only after smoke tests pass (Stage 1). This
round ships the harness; live Stage 2 execution is cost-controlled and not run by
default.
"""
from __future__ import annotations

BENCHMARK_VERSION = "v1"

# (capability, prompt, check) — check is a deterministic scorer callable.
CASES = [
    {
        "capability": "tutor.chat",
        "id": "tutor-basic-1",
        "prompt": "请用一句话解释什么是操作系统中的进程。",
        "check": "contains",
        "expect": "程序",
    },
    {
        "capability": "question.explain",
        "id": "explain-11408-1",
        "prompt": "在计算机系统中，进程和线程的根本区别是什么？用不超过50字回答。",
        "check": "contains_any",
        "expect": ["资源", "调度", "独立"],
    },
    {
        "capability": "material.qa",
        "id": "qa-1",
        "prompt": "二分查找的时间复杂度是多少？",
        "check": "contains_any",
        "expect": ["O(log", "log n", "对数"],
    },
    {
        "capability": "question.generate",
        "id": "gen-json-1",
        "prompt": "生成一道关于「栈」的单选题，严格输出 JSON：{\"stem\":...,\"options\":[4项],\"answer\":\"A\",\"analysis\":...}",
        "check": "json_valid",
    },
    {
        "capability": "programming.explain",
        "id": "prog-explain-1",
        "prompt": "用中文解释下面 Python 代码的作用：`x = [i for i in range(10) if i % 2 == 0]`",
        "check": "contains_any",
        "expect": ["偶数", "even", "0, 2", "0,2"],
    },
    {
        "capability": "programming.debug",
        "id": "prog-debug-1",
        "prompt": "下面代码报 IndexError，指出错误原因：\n```python\nl = [1,2,3]\nprint(l[3])\n```",
        "check": "contains_any",
        "expect": ["越界", "索引", "index", "3"],
    },
]

# AGENT_CAPABILITY_PROBE — separate from the general 6-case benchmark. A coding/agent
# model must not be eliminated for failing general pedagogy cases; it is screened on
# programming explanation, non-trivial debugging, and strict structured output.
# Same deterministic scoring (contains_any / json_fields), no model-as-judge.
AGENT_PROBE_VERSION = "v1"

AGENT_PROBE_CASES = [
    {
        "capability": "programming.explain",
        "id": "agent-explain-1",
        "prompt": ("用中文解释下面 Python 代码的求值过程，并说明它为什么是惰性的：\n"
                   "```python\ndef fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n"
                   "        yield a\n        a, b = b, a + b\n```"),
        "check": "contains_any",
        "expect": ["生成器", "generator", "yield", "惰性"],
    },
    {
        "capability": "programming.debug",
        "id": "agent-debug-1",
        "prompt": ("下面代码两次调用的输出结果不是预期的 `[1]` 和 `[2]`，指出根本原因：\n"
                   "```python\ndef add(item, lst=[]):\n    lst.append(item)\n    return lst\n\n"
                   "print(add(1))\nprint(add(2))\n```"),
        "check": "contains_any",
        "expect": ["默认参数", "可变", "mutable", "共享", "同一个", "同一", "持久"],
    },
    {
        "capability": "programming.debug",
        "id": "agent-structured-1",
        "prompt": ("只输出一个 JSON 对象，不要 markdown 代码块、不要任何解释文字。\n"
                   "它必须包含且仅包含三个字段：`line`（整数，出错行号）、`cause`（字符串，根本原因）、"
                   "`fix`（字符串，最小修复方案）。\n"
                   "待分析代码：\n```python\ndef add(item, lst=[]):\n    lst.append(item)\n    return lst\n```"),
        "check": "json_fields",
        "expect": ["line", "cause", "fix"],
    },
]


def _json_valid(text: str) -> bool:
    import json
    try:
        json.loads(text[text.find("{"):text.rfind("}") + 1])
        return True
    except Exception:
        return False


def _json_fields(text: str, fields: list[str]) -> bool:
    """Valid JSON object carrying every required field (extras allowed)."""
    import json
    try:
        obj = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except Exception:
        return False
    return isinstance(obj, dict) and all(f in obj for f in fields)


def score_case(text: str, case: dict) -> dict:
    """Return {passed, method, detail}. Deterministic where possible."""
    check = case["check"]
    if check == "contains":
        passed = case["expect"] in text
    elif check == "contains_any":
        passed = any(e in text for e in case["expect"])
    elif check == "json_valid":
        passed = _json_valid(text)
    elif check == "json_fields":
        passed = _json_fields(text, case["expect"])
    else:
        passed = False
    return {"id": case["id"], "capability": case["capability"],
            "passed": passed, "method": check}


def score_all(responses: dict[str, str], cases: list[dict] | None = None) -> dict:
    """responses: case id → model output. Returns per-case + aggregate."""
    by_id = {c["id"]: c for c in (cases if cases is not None else CASES)}
    results = []
    for case_id, text in responses.items():
        case = by_id.get(case_id)
        if case is None:
            continue
        results.append(score_case(text or "", case))
    passed = sum(1 for r in results if r["passed"])
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "total": len(results),
        "passed": passed,
        "results": results,
    }
