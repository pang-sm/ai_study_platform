"""STEP 7C-P: benchmark harness (deterministic scoring, no live calls)."""
from ai.benchmark import CASES, BENCHMARK_VERSION, score_all, score_case


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
