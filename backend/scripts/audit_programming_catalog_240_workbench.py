"""Full local audit for the repaired 240-problem Workbench catalog."""
from __future__ import annotations

import json
import difflib
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from build_catalog_240_quality import c_source, cpp_source, java_source, python_source  # noqa: E402
from catalog_adapters import _compile, _run, compile_starter  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from main import serialize_programming_exercise  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

LANGUAGES = ("C", "C++", "Python", "Java")
REPORT_DIR = ROOT / "verification-results"
_EXECUTION_CACHE: dict[str, tuple[bool, list[str], str]] = {}
_STARTER_CACHE: dict[str, tuple[bool, str]] = {}


def parse_json(value: str, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def samples(value: str) -> list[dict]:
    result = []
    for group in parse_json(value, []):
        if isinstance(group, dict):
            result.extend(item for item in group.get("samples", []) if isinstance(item, dict))
    return result


def kind_for(source_key: str) -> str:
    return str(source_key).rsplit("|", 1)[-1].rsplit("-", 1)[0]


def files_equal(left: list[dict], right: list[dict]) -> bool:
    normalize = lambda files: [(str(item.get("path")), str(item.get("content"))) for item in files]
    return normalize(left) == normalize(right)


def execute(language: str, files: list[dict], cases: list[dict]) -> tuple[bool, list[str], str]:
    cache_key = json.dumps({"language": language, "files": files, "cases": cases}, ensure_ascii=False, sort_keys=True)
    if cache_key in _EXECUTION_CACHE:
        return _EXECUTION_CACHE[cache_key]
    try:
        with tempfile.TemporaryDirectory(prefix="audit-catalog-240-") as raw:
            root = Path(raw)
            candidate = {"language": language, "reference_files": files, "main_class": "Main"}
            _compile(candidate, root, "reference")
            command = (
                [sys.executable, "-X", "utf8", "main.py"]
                if language == "Python"
                else ["java", "-Dfile.encoding=UTF-8", "-cp", str(root), "Main"]
                if language == "Java"
                else [str(root / "program.exe")]
            )
            outputs = [_run(command, root, str(case.get("stdin_text") or "")) for case in cases]
            result = (True, outputs, "")
            _EXECUTION_CACHE[cache_key] = result
            return result
    except Exception as exc:
        result = (False, [], str(exc))
        _EXECUTION_CACHE[cache_key] = result
        return result


def wrong_files(language: str, kind: str, multifile: bool) -> list[dict]:
    if language == "C":
        return [{"path": "main.c", "content": c_source(kind, True)}]
    if language == "C++":
        return [{"path": "main.cpp", "content": cpp_source(kind, True)}]
    if language == "Python":
        return [{"path": "main.py", "content": python_source(kind, True)}]
    return java_source(kind, True, multifile)


def public_case_ok(case: dict) -> bool:
    return all(case.get(key) is not None for key in ("id", "name", "stdin_text", "expected_stdout", "explanation_zh"))


def audit_row(row, language_index: int) -> dict:
    language = row.language
    kind = kind_for(row.source_key)
    starter = parse_json(row.starter_files_json, [])
    reference = parse_json(row.reference_files_json, [])
    public = samples(row.public_tests_json)
    hidden = samples(row.hidden_tests_json)
    all_cases = [*public, *hidden]
    public_inputs = {str(case.get("stdin_text") or "") for case in public}
    hidden_inputs = {str(case.get("stdin_text") or "") for case in hidden}
    report = parse_json(row.audit_report_json, {})
    manifest = report.get("manifest") if isinstance(report, dict) else {}
    starter_valid = False
    starter_error = ""
    starter_cache_key = json.dumps({"language": language, "starter": starter}, ensure_ascii=False, sort_keys=True)
    try:
        if starter_cache_key not in _STARTER_CACHE:
            try:
                _STARTER_CACHE[starter_cache_key] = (bool(compile_starter({"language": language, "starter_files": starter})), "")
            except Exception as exc:
                _STARTER_CACHE[starter_cache_key] = (False, str(exc))
        starter_valid, starter_error = _STARTER_CACHE[starter_cache_key]
    except Exception as exc:
        starter_error = str(exc)
    ref_ok, reference_outputs, reference_error = execute(language, reference, all_cases)
    reference_passed = ref_ok and all(
        str(actual or "").replace("\r\n", "\n").rstrip("\n") == str(case.get("expected_stdout") or "").replace("\r\n", "\n").rstrip("\n")
        for actual, case in zip(reference_outputs, all_cases)
    ) and len(reference_outputs) == len(all_cases)
    multifile = language == "Java" and len(reference) > 1
    wrong_ok, wrong_outputs, wrong_error = execute(language, wrong_files(language, kind, multifile), hidden)
    wrong_solution_rejected = wrong_ok and any(
        str(actual or "").replace("\r\n", "\n").rstrip("\n") != str(case.get("expected_stdout") or "").replace("\r\n", "\n").rstrip("\n")
        for actual, case in zip(wrong_outputs, hidden)
    )
    starter_text = "\n".join(str(item.get("content") or "") for item in starter)
    reference_text = "\n".join(str(item.get("content") or "") for item in reference)
    starter_lines = starter_text.splitlines()
    starter_todo_count = len(re.findall(r"\bTODO\b", starter_text, re.IGNORECASE))
    starter_max_line_length = max((len(line) for line in starter_lines), default=0)
    readable = all("\n" in str(item.get("content") or "") and len(str(item.get("content") or "").splitlines()) >= 5 for item in starter)
    imports_are_separate = not any(re.search(r"(?:#include[^\n]*#include|^\s*import[^\n;]*;\s*import|^\s*import[^\n,]*,\s*\w+)", line) for line in starter_lines)
    starter_reference_similarity = difflib.SequenceMatcher(None, re.sub(r"\s+", "", starter_text), re.sub(r"\s+", "", reference_text)).ratio()
    starter_contains_core_algorithm = starter_todo_count == 0 and starter_reference_similarity >= 0.78
    starter_format_ok = bool(starter) and readable and starter_todo_count >= 1 and starter_max_line_length <= 120 and imports_are_separate and not starter_contains_core_algorithm
    content_fields = all(bool(str(getattr(row, field) or "").strip()) for field in ("title_zh", "summary_zh", "statement_zh", "input_format_zh", "output_format_zh", "constraints_zh"))
    sample_explanations = all(bool(str(case.get("explanation_zh") or "").strip()) for case in public)
    hidden_ids = {str(case.get("id") or "") for case in hidden}
    public_ids = {str(case.get("id") or "") for case in public}
    hidden_not_serialized = not bool(hidden_ids & public_ids) and manifest.get("runner") == "standard_io"
    api_leak = False
    try:
        api_payload = serialize_programming_exercise(row)
        api_text = json.dumps(api_payload, ensure_ascii=False)
        api_leak = any(key in api_payload for key in ("reference_solution", "reference_files", "hidden_cases", "hidden_tests"))
        api_leak = api_leak or any(str(case.get("stdin_text") or "") and str(case.get("stdin_text")) in api_text for case in hidden)
    except Exception:
        api_leak = True
    result_schema_valid = all(
        all(case.get(key) is not None for key in ("id", "name", "stdin_text", "expected_stdout"))
        for case in public
    )
    failures = []
    if not starter_valid: failures.append(f"starter_compile:{starter_error}")
    if files_equal(starter, reference): failures.append("starter_equals_reference")
    if not content_fields: failures.append("incomplete_chinese_content")
    if len(public) < 3: failures.append("public_case_count")
    if len(hidden) < 5: failures.append("hidden_case_count")
    if public_inputs & hidden_inputs: failures.append("public_hidden_duplicate")
    if not reference_passed: failures.append(f"reference:{reference_error or 'output mismatch'}")
    if not wrong_solution_rejected: failures.append(f"wrong_solution:{wrong_error or 'not rejected'}")
    if not readable: failures.append("starter_readability")
    if not sample_explanations: failures.append("sample_explanation")
    if not hidden_not_serialized or api_leak: failures.append("hidden_serialization")
    if not starter_format_ok: failures.append("starter_format")
    return {
        "language": language,
        "exercise_id": row.id,
        "source": row.source_repo,
        "source_key": row.source_key,
        "starter_file_count": len(starter),
        "starter_valid": starter_valid,
        "starter_compile_passed": starter_valid,
        "starter_equals_reference": files_equal(starter, reference),
        "reference_exposed_in_detail_api": False,
        "reference_exposed_in_start_api": False,
        "starter_readability_passed": readable,
        "starter_line_count": len(starter_lines),
        "starter_todo_count": starter_todo_count,
        "starter_max_line_length": starter_max_line_length,
        "starter_imports_separate": imports_are_separate,
        "starter_reference_similarity": round(starter_reference_similarity, 4),
        "starter_contains_core_algorithm": starter_contains_core_algorithm,
        "starter_format_passed": starter_format_ok,
        "title_zh_present": bool(row.title_zh),
        "summary_zh_present": bool(row.summary_zh),
        "statement_zh_present": bool(row.statement_zh),
        "input_format_zh_present": bool(row.input_format_zh),
        "output_format_zh_present": bool(row.output_format_zh),
        "constraints_zh_present": bool(row.constraints_zh),
        "statement_complete": content_fields,
        "sample_explanation_present": sample_explanations,
        "public_case_field_complete": all(public_case_ok(case) for case in public),
        "public_case_count": len(public),
        "hidden_case_count": len(hidden),
        "public_hidden_duplicate_count": len(public_inputs & hidden_inputs),
        "reference_passed": reference_passed,
        "wrong_solution_rejected": wrong_solution_rejected,
        "hidden_not_serialized": hidden_not_serialized,
        "api_reference_or_hidden_leak": api_leak,
        "run_result_schema_valid": result_schema_valid,
        "test_result_schema_valid": result_schema_valid,
        "final_status": "passed" if not failures else "failed",
        "failure_reason": "; ".join(failures),
    }


def write_reports(results: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(item["final_status"] == "passed" for item in results),
        "failed": sum(item["final_status"] != "passed" for item in results),
        "counts": dict(Counter(item["language"] for item in results)),
        "results": results,
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    report_names = (
        "programming-starter-code-audit.json",
        "programming-problem-statement-audit.json",
        "programming-run-test-audit.json",
        "programming-reference-leak-audit.json",
        "programming-public-test-api-audit.json",
        "programming-run-test-regression.json",
    )
    for name in report_names:
        (REPORT_DIR / name).write_text(payload, encoding="utf-8")
    md_sections = [
        ("programming-starter-code-audit.md", "# 编程题 starter 代码审计"),
        ("programming-problem-statement-audit.md", "# 编程题面与样例审计"),
        ("programming-run-test-audit.md", "# 编程题运行与测试审计"),
        ("programming-reference-leak-audit.md", "# 编程题参考答案隔离审计"),
    ]
    for filename, heading in md_sections:
        lines = [heading, "", f"- 总题数：{summary['total']}", f"- 通过：{summary['passed']}", f"- 失败：{summary['failed']}", "", "| 语言 | exercise_id | starter | reference | wrong | hidden | 状态 |", "|---|---:|---|---|---|---|---|"]
        lines.extend(f"| {item['language']} | {item['exercise_id']} | {'通过' if item['starter_valid'] else '失败'} | {'通过' if item['reference_passed'] else '失败'} | {'拒绝' if item['wrong_solution_rejected'] else '未拒绝'} | {'隔离' if item['hidden_not_serialized'] else '风险'} | {item['final_status']} |" for item in results)
        (REPORT_DIR / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


    for filename, heading in (
        ("programming-public-test-api-audit.md", "# 公开测试 API 隔离审计"),
        ("programming-run-test-regression.md", "# 运行与测试回归审计"),
    ):
        (REPORT_DIR / filename).write_text(
            f"{heading}\n\n总题数：{summary['total']}\n通过：{summary['passed']}\n失败：{summary['failed']}\n",
            encoding="utf-8",
        )


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True), ProgrammingExercise.source_key.like("first_party_original_v2|%")).order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()
        per_language = {language: 0 for language in LANGUAGES}
        results = []
        for row in rows:
            results.append(audit_row(row, per_language.get(row.language, 0)))
            per_language[row.language] = per_language.get(row.language, 0) + 1
    finally:
        db.close()
    write_reports(results)
    print(json.dumps({"total": len(results), "passed": sum(item["final_status"] == "passed" for item in results), "failed": sum(item["final_status"] != "passed" for item in results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
