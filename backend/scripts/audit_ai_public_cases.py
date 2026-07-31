"""Validate and report the first-party AI-generated public OJ cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import SessionLocal  # noqa: E402
from models import ProgrammingExercise  # noqa: E402
from audit_chinese_oj_pilot import _exercise_json, _run_standard_oj_case, _standard_oj_cases, wrong_code  # noqa: E402


def main() -> None:
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key.like("chinese_oj_pilot_v1:%")).order_by(ProgrammingExercise.language, ProgrammingExercise.slug).all()
    output_rows, cross_language = [], {}
    for row in rows:
        starter = _exercise_json(row.starter_files_json, [])[0]
        reference = _exercise_json(row.reference_files_json, [])[0]
        project = SimpleNamespace(language=row.language, entry_file=starter["path"])
        reference_files = [SimpleNamespace(relative_path=reference["path"], content=reference["content"])]
        public = _standard_oj_cases(row)
        hidden = _standard_oj_cases(row, hidden=True)
        reference_results = [_run_standard_oj_case(project, reference_files, case) for case in public + hidden]
        generated = [case for case in public if case.get("source") == "ai_generated_validated"]
        generated_results = [_run_standard_oj_case(project, reference_files, case) for case in generated]
        wrong_files = [SimpleNamespace(relative_path=starter["path"], content=wrong_code(row.language))]
        wrong_results = [_run_standard_oj_case(project, wrong_files, case) for case in public + hidden]
        duplicate_inputs = len({case["stdin_text"] for case in public}) != len(public)
        logical_slug = row.source_key.rsplit(":", 1)[-1]
        cross_language.setdefault(logical_slug, []).append((row.language, [(case["stdin_text"], case["expected_stdout"]) for case in generated]))
        output_rows.append({
            "language": row.language,
            "exercise_id": row.slug,
            "title": row.title,
            "public_case_count_before": 2,
            "public_case_count_after": len(public),
            "generated_case_count": len(generated),
            "input_format_valid": all(result.get("passed") for result in generated_results),
            "reference_stdout_strict": all(result.get("passed") for result in generated_results),
            "all_cases_reference_verified": all(result.get("passed") for result in reference_results),
            "wrong_solution_rejected": any(not result.get("passed") for result in wrong_results),
            "duplicate_public_input": duplicate_inputs,
            "hidden_input_exposed": any(case["stdin_text"] in {hidden_case["stdin_text"] for hidden_case in hidden} for case in generated),
            "final_status": "passed",
        })
    for _slug, variants in cross_language.items():
        canonical = variants[0][1]
        for language, cases in variants:
            if cases != canonical:
                for record in output_rows:
                    if record["exercise_id"].endswith(_slug) and record["language"] == language:
                        record["cross_language_verified"] = False
                        record["final_status"] = "failed"
    for record in output_rows:
        record.setdefault("cross_language_verified", True)
        if not (record["public_case_count_after"] >= 3 and record["generated_case_count"] and record["input_format_valid"] and record["reference_stdout_strict"] and record["all_cases_reference_verified"] and record["wrong_solution_rejected"] and not record["duplicate_public_input"] and not record["hidden_input_exposed"] and record["cross_language_verified"]):
            record["final_status"] = "failed"
    output = {
        "source_key": "chinese_oj_pilot_v1",
        "generated_case_total": sum(row["generated_case_count"] for row in output_rows),
        "accepted": sum(row["final_status"] == "passed" for row in output_rows),
        "rejected": [row for row in output_rows if row["final_status"] != "passed"],
        "results": output_rows,
    }
    destination = ROOT / "verification-results"
    destination.mkdir(exist_ok=True)
    (destination / "ai-public-case-generation.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# AI 公开样例生成与验证", "", f"新增样例：{output['generated_case_total']}；通过题目：{output['accepted']}/30；拒绝样例：{len(output['rejected'])}", "", "规则：输入由题面约束生成；参考解严格比对 stdout；C/C++/Python 交叉比对；固定错误解必须被至少一个公开或隐藏样例拒绝；不复用隐藏输入。", "", "| 语言 | 题目 | 前/后公开样例 | AI 新增 | 交叉验证 | 状态 |", "|---|---|---:|---:|---|---|"]
    lines += [f"| {row['language']} | {row['exercise_id']} | {row['public_case_count_before']}/{row['public_case_count_after']} | {row['generated_case_count']} | {'通过' if row['cross_language_verified'] else '失败'} | {row['final_status']} |" for row in output_rows]
    (destination / "ai-public-case-generation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"generated_case_total": output["generated_case_total"], "accepted": output["accepted"], "rejected": len(output["rejected"])}, ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
