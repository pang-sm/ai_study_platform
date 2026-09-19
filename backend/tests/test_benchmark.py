"""STEP 7C-P: benchmark harness (deterministic scoring, no live calls)."""
from ai.benchmark import (
    AGENT_PROBE_CASES, AGENT_PROBE_VERSION, BENCHMARK_VERSION, CASES, score_all,
    score_case,
)


def test_benchmark_version():
    assert BENCHMARK_VERSION == "v1"


def test_contains_scoring():
    case = next(c for c in CASES if c["id"] == "tutor-basic-1")
    assert score_case("进程是运行中的程序", case)["passed"] is True
    assert score_case("完全无关的回答", case)["passed"] is False


def test_json_valid_scoring():
    case = next(c for c in CASES if c["id"] == "gen-json-1")
    good = '{"stem":"x","options":["a","b","c","d"],"answer":"A","analysis":"y"}'
    assert score_case(good, case)["passed"] is True
    assert score_case("不是 json", case)["passed"] is False


def test_score_all_aggregate():
    responses = {c["id"]: ("进程是运行中的程序" if c["id"] == "tutor-basic-1" else "")
                 for c in CASES}
    r = score_all(responses)
    assert r["benchmark_version"] == "v1"
    assert r["total"] == len(CASES)
    assert 0 <= r["passed"] <= r["total"]


# ---- AGENT_CAPABILITY_PROBE (separate from the general benchmark) ----

def test_agent_probe_is_separate_from_general_cases():
    general_ids = {c["id"] for c in CASES}
    probe_ids = {c["id"] for c in AGENT_PROBE_CASES}
    assert probe_ids and probe_ids.isdisjoint(general_ids)
    assert AGENT_PROBE_VERSION == "v1"


def test_agent_probe_covers_required_capabilities():
    caps = {c["capability"] for c in AGENT_PROBE_CASES}
    assert {"programming.explain", "programming.debug"} <= caps
    # structured instruction following is expressed as a strict JSON-output case
    assert any(c["check"] == "json_fields" for c in AGENT_PROBE_CASES)


def test_json_fields_scoring():
    case = next(c for c in AGENT_PROBE_CASES if c["check"] == "json_fields")
    assert score_case('{"line": 1, "cause": "c", "fix": "f"}', case)["passed"] is True
    # extras are allowed, missing required fields are not
    assert score_case('{"line": 1, "cause": "c", "fix": "f", "note": "n"}',
                      case)["passed"] is True
    assert score_case('{"line": 1, "cause": "c"}', case)["passed"] is False
    assert score_case('not json at all', case)["passed"] is False


def test_agent_probe_uses_same_scoring_engine():
    r = score_all({c["id"]: "" for c in AGENT_PROBE_CASES}, AGENT_PROBE_CASES)
    assert r["total"] == len(AGENT_PROBE_CASES)
    assert r["passed"] == 0
