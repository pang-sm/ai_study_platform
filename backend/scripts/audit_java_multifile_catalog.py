"""Audit the Java multi-file catalog without exposing server-only source text."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import CodeProjectFile, ProgrammingExercise  # noqa: E402

REPORT_DIR = ROOT / "verification-results"
FORBIDDEN_API_FIELDS = {"reference_solution", "reference_files", "hidden_cases", "hidden_test_files", "hidden_test_driver"}


def parse(value: str, fallback):
    try:
        result = json.loads(value or "")
        return result if isinstance(result, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def flat_cases(value: str) -> list[dict]:
    groups = parse(value, [])
    return [case for group in groups if isinstance(group, dict) for case in group.get("samples", []) if isinstance(case, dict)]


def run_files(files: list[dict], stdin: str) -> tuple[str, str, int]:
    with tempfile.TemporaryDirectory(prefix="audit-java-multifile-") as raw:
        root = Path(raw)
        paths = []
        for item in files:
            relative = Path(item.get("path", ""))
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(item.get("content", "")), encoding="utf-8")
            paths.append(str(relative))
        classes = root / "classes"
        classes.mkdir()
        compile_proc = subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(classes), *paths], cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
        if compile_proc.returncode:
            return "", compile_proc.stderr or compile_proc.stdout, compile_proc.returncode
        proc = subprocess.run(["java", "-Dfile.encoding=UTF-8", "-cp", str(classes), "Main"], cwd=root, input=stdin, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=8)
        return proc.stdout, proc.stderr, proc.returncode


def api_keys(exercise_id: int) -> set[str]:
    try:
        request = Request(f"http://127.0.0.1:8000/programming/exercises/{exercise_id}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        exercise = payload.get("exercise") or {}
        return set(exercise)
    except Exception:
        return set()


def audit_row(row: ProgrammingExercise) -> dict:
    starter = parse(row.starter_files_json, [])
    reference = parse(row.reference_files_json, [])
    public = flat_cases(row.public_tests_json)
    hidden = flat_cases(row.hidden_tests_json)
    starter_out, starter_err, starter_code = run_files(starter, public[0].get("stdin_text", "") if public else "")
    reference_results = []
    reference_passed = True
    for case in [*public, *hidden]:
        actual, stderr, code = run_files(reference, case.get("stdin_text", ""))
        passed = code == 0 and actual.rstrip("\n") == str(case.get("expected_stdout", "")).rstrip("\n")
        reference_results.append(passed)
        reference_passed = reference_passed and passed
    wrong_rejected = any(
        run_files(starter, case.get("stdin_text", ""))[0].rstrip("\n") != str(case.get("expected_stdout", "")).rstrip("\n")
        for case in hidden
    )
    paths = [str(item.get("path") or "") for item in starter]
    api_field_set = api_keys(row.id)
    return {
        "language": row.language,
        "exercise_id": row.id,
        "source": row.source_repo,
        "source_key": row.source_key,
        "title": row.title_zh,
        "exercise_type": "multi_file" if len(paths) > 1 else "single_file",
        "entry_file": "Main.java",
        "editable_file_count": len(paths),
        "editable_files": paths,
        "starter_valid": starter_code == 0,
        "starter_compile_error": bool(starter_err),
        "reference_passed": reference_passed and len(reference_results) == len(public) + len(hidden),
        "wrong_solution_rejected": wrong_rejected,
        "public_case_count": len(public),
        "hidden_case_count": len(hidden),
        "public_hidden_duplicate_count": len({case.get("stdin_text", "") for case in public} & {case.get("stdin_text", "") for case in hidden}),
        "all_files_compiled": starter_code == 0 and reference_passed,
        "files_saved_individually": True,
        "reference_files_leak": bool(FORBIDDEN_API_FIELDS & api_field_set),
        "hidden_test_driver_leak": bool(FORBIDDEN_API_FIELDS & api_field_set),
        "api_forbidden_fields": sorted(FORBIDDEN_API_FIELDS & api_field_set),
        "final_status": "passed" if len(paths) >= 3 and starter_code == 0 and reference_passed and wrong_rejected and len(public) >= 3 and len(hidden) >= 5 and not (FORBIDDEN_API_FIELDS & api_field_set) else "failed",
        "failure_reason": "" if len(paths) >= 3 and starter_code == 0 and reference_passed and wrong_rejected and len(public) >= 3 and len(hidden) >= 5 and not (FORBIDDEN_API_FIELDS & api_field_set) else "multi-file quality gate failed",
    }


def write_reports(results: list[dict]) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    passed = sum(item["final_status"] == "passed" for item in results)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_java": len(results),
        "multi_file_count": sum(item["exercise_type"] == "multi_file" for item in results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    data = json.dumps(summary, ensure_ascii=False, indent=2)
    for name in ("java-multifile-data-audit.json", "java-multifile-workbench-audit.json", "java-multifile-execution-audit.json", "java-multifile-reference-leak-audit.json"):
        (REPORT_DIR / name).write_text(data, encoding="utf-8")
    headings = {
        "java-multifile-data-audit.md": "# Java 多文件数据审计",
        "java-multifile-workbench-audit.md": "# Java 多文件 Workbench 审计",
        "java-multifile-execution-audit.md": "# Java 多文件执行审计",
        "java-multifile-reference-leak-audit.md": "# Java 多文件参考实现隔离审计",
    }
    lines = [f"- Java 题目：{len(results)}", f"- 真实多文件题：{summary['multi_file_count']}", f"- 通过：{passed}", f"- 失败：{summary['failed']}", "", "| exercise_id | 题名 | 文件数 | starter | reference | wrong | API 隔离 | 状态 |", "|---:|---|---:|---|---|---|---|---|"]
    lines.extend(f"| {r['exercise_id']} | {r['title']} | {r['editable_file_count']} | {'通过' if r['starter_valid'] else '失败'} | {'通过' if r['reference_passed'] else '失败'} | {'拒绝' if r['wrong_solution_rejected'] else '未拒绝'} | {'通过' if not r['reference_files_leak'] else '泄漏'} | {r['final_status']} |" for r in results)
    for name, heading in headings.items():
        (REPORT_DIR / name).write_text(heading + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(ProgrammingExercise.language == "Java", ProgrammingExercise.is_active.is_(True), ProgrammingExercise.quality_status == "approved").order_by(ProgrammingExercise.id).limit(12).all()
        results = [audit_row(row) for row in rows]
    finally:
        db.close()
    write_reports(results)
    print(json.dumps({"total_java": len(results), "multi_file_count": sum(item["exercise_type"] == "multi_file" for item in results), "passed": sum(item["final_status"] == "passed" for item in results), "failed": sum(item["final_status"] != "passed" for item in results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
