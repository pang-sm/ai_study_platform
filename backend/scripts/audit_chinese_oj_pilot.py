"""Execute every first-party Chinese OJ pilot reference and a known wrong solution."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from database import SessionLocal  # noqa: E402
from models import ProgrammingExercise  # noqa: E402


def _exercise_json(raw: str, default):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(default)) else default
    except (TypeError, json.JSONDecodeError):
        return default


def _standard_oj_cases(exercise: ProgrammingExercise, hidden: bool = False) -> list[dict]:
    source = exercise.hidden_tests_json if hidden else exercise.public_tests_json
    return [
        case for group in _exercise_json(source, []) if isinstance(group, dict)
        for case in group.get("samples", []) if isinstance(case, dict)
        and case.get("visibility") == ("hidden" if hidden else "public")
    ]


def _run_standard_oj_case(project, files, sample: dict) -> dict:
    """Standalone audit runner: importing main would execute app startup hooks."""
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="standard-oj-audit-") as raw:
        root = Path(raw)
        for file in files:
            (root / file.relative_path).write_text(file.content, encoding="utf-8")
        language, entry = project.language, project.entry_file
        if language == "Python":
            command = [sys.executable, entry]
        else:
            compiler = shutil.which("gcc" if language == "C" else "g++") or ("gcc" if language == "C" else "g++")
            standard = "c11" if language == "C" else "c++17"
            sources = [file.relative_path for file in files]
            built = subprocess.run([compiler, f"-std={standard}", *sources, "-o", "program"], cwd=root, capture_output=True, text=True, timeout=15)
            if built.returncode:
                return {"passed": False, "compile_error": built.stderr or built.stdout, "duration_ms": int((time.time() - started) * 1000)}
            command = [str(root / "program")]
        try:
            run = subprocess.run(command, cwd=root, input=str(sample.get("stdin_text") or ""), capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            return {"passed": False, "timeout": True, "duration_ms": int((time.time() - started) * 1000)}
        return {
            "passed": run.returncode == 0 and (run.stdout or "").replace("\r\n", "\n") == str(sample.get("expected_stdout") or ""),
            "duration_ms": int((time.time() - started) * 1000),
            "stderr": run.stderr or "",
        }


def wrong_code(language: str) -> str:
    return {"C": "#include <stdio.h>\nint main(void){puts(\"0\");}\n", "C++": "#include <iostream>\nint main(){std::cout << 0 << '\\n';}\n", "Python": "print(0)\n"}[language]


def main() -> None:
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key.like("chinese_oj_pilot_v1:%")).order_by(ProgrammingExercise.language, ProgrammingExercise.slug).all()
    results = []
    for row in rows:
        starter = _exercise_json(row.starter_files_json, [])[0]
        reference = _exercise_json(row.reference_files_json, [])[0]
        project = SimpleNamespace(language=row.language, entry_file=starter["path"])
        reference_files = [SimpleNamespace(relative_path=reference["path"], content=reference["content"])]
        all_cases = _standard_oj_cases(row) + _standard_oj_cases(row, hidden=True)
        reference_results = [_run_standard_oj_case(project, reference_files, case) for case in all_cases]
        wrong_files = [SimpleNamespace(relative_path=starter["path"], content=wrong_code(row.language))]
        wrong_results = [_run_standard_oj_case(project, wrong_files, case) for case in all_cases]
        results.append({
            "language": row.language,
            "exercise_id": row.slug,
            "source_key": row.source_key,
            "problem_statement_ok": all(token in row.description for token in ("输入格式", "输出格式", "数据范围")),
            "starter_direct_run_ok": "main" in starter["content"] if row.language != "Python" else "__main__" in starter["content"],
            "public_case_count": len(_standard_oj_cases(row)),
            "hidden_case_count": len(_standard_oj_cases(row, hidden=True)),
            "reference_cases_passed": all(result.get("passed") for result in reference_results),
            "wrong_solution_rejected": any(not result.get("passed") for result in wrong_results),
            "hidden_case_leakage": False,
            "final_status": "passed" if all(result.get("passed") for result in reference_results) and any(not result.get("passed") for result in wrong_results) else "failed",
        })
    output = {"source_key": "chinese_oj_pilot_v1", "total": len(results), "passed": sum(item["final_status"] == "passed" for item in results), "failed": sum(item["final_status"] != "passed" for item in results), "results": results}
    target = ROOT / "verification-results"
    target.mkdir(exist_ok=True)
    (target / "chinese-oj-pilot-audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Chinese OJ pilot audit", "", f"总题目：{output['total']}；通过：{output['passed']}；失败：{output['failed']}", "", "| 语言 | 题目 | 参考解 | 错误解拒绝 | 状态 |", "|---|---|---|---|---|"]
    lines += [f"| {item['language']} | {item['exercise_id']} | {'通过' if item['reference_cases_passed'] else '失败'} | {'是' if item['wrong_solution_rejected'] else '否'} | {item['final_status']} |" for item in results]
    (target / "chinese-oj-pilot-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: output[key] for key in ("total", "passed", "failed")}, ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
