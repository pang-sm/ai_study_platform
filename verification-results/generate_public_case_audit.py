import json
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).parents[1] / "backend" / "app.db"
OUT = Path(__file__).parent
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
results = []
for row in con.execute("select * from programming_exercises order by language, id"):
    files = json.loads(row["public_tests_json"] or "[]")
    samples = [s for f in files if isinstance(f, dict) for s in (f.get("samples") or [])]
    checks = []
    for sample in samples:
        checks.append({
            "official_source_ok": bool(sample.get("source_test_name") or sample.get("test_path")) and bool(sample.get("selector")),
            # The API derives stdin_text/expected_stdout from the canonical
            # arguments/expected fields for legacy importer rows.
            "terminal_input_ok": "stdin_text" in sample or "input_display" in sample or "arguments" in sample,
            "output_format_ok": "expected_stdout" in sample or "expected" in sample,
            "json_parameter_leak": any(token in str(sample.get("input_display", "")) for token in ("{", "}")),
        })
    reasons = []
    if not samples: reasons.append("没有结构化公开样例")
    if any(not x["official_source_ok"] for x in checks): reasons.append("存在缺少官方测试标识的样例")
    if any(not x["terminal_input_ok"] or not x["output_format_ok"] for x in checks): reasons.append("存在缺少 stdin_text 或 expected_stdout 的样例")
    if any(x["json_parameter_leak"] for x in checks): reasons.append("样例输入仍疑似包含 JSON 参数")
    results.append({
        "language": row["language"], "exercise_id": row["id"],
        "public_case_count": len(samples), "input_format_ok": bool(samples) and all(x["terminal_input_ok"] for x in checks),
        "output_format_ok": bool(samples) and all(x["output_format_ok"] for x in checks),
        "official_source_ok": bool(samples) and all(x["official_source_ok"] for x in checks),
        "terminal_input_ok": False, "reference_cases_passed": False,
        "wrong_solution_rejected": False, "hidden_case_leakage": False,
        "final_status": "failed" if reasons else "not_executed",
        "failure_reasons": reasons or ["需要在隔离运行器中执行参考解、错误解和终端逐行输入审计"],
    })
OUT.joinpath("public-case-audit.json").write_text(json.dumps({"database": str(DB), "total": len(results), "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
counts = Counter(r["language"] for r in results)
passed = sum(r["final_status"] == "passed" for r in results)
failed = len(results) - passed
lines = ["# Public case audit", "", f"- Database: `{DB}`", f"- Exercises: {len(results)}", f"- Passed: {passed}", f"- Failed/not executed: {failed}", "", "| Language | Exercises | Public cases | Passed |", "|---|---:|---:|---:|"]
for lang in ("C", "C++", "Python", "Java"):
    group = [r for r in results if r["language"] == lang]
    lines.append(f"| {lang} | {len(group)} | {sum(r['public_case_count'] for r in group)} | {sum(r['final_status'] == 'passed' for r in group)} |")
lines += ["", "## Failed or not executed", ""]
for r in results:
    if r["final_status"] != "passed": lines.append(f"- {r['language']} #{r['exercise_id']}: {'; '.join(r['failure_reasons'])}")
OUT.joinpath("public-case-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
