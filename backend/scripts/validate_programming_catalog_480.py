"""Real compiler/runtime and content audit for the approved 480 catalog."""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from catalog_adapters import compile_starter  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402
from restore_high_quality_programming_catalog import run_standard_many  # noqa: E402

OUT = ROOT / "verification-results"
BANNED = ("# Instructions", "编程练习", "通用练习", "TODO", "待补充", "暂无题干", "请根据要求完成代码")


def flatten(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    return [item for group in data if isinstance(group, dict) for item in group.get("samples", []) if isinstance(item, dict)]


def file_content(raw: str, default: str) -> tuple[str, str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return default, ""
    item = data[0] if data and isinstance(data[0], dict) else {}
    return str(item.get("path") or default), str(item.get("content") or "")


def wrong_code(language: str) -> tuple[str, str]:
    if language == "Python": return "main.py", "print(0)\n"
    if language == "Java": return "Main.java", "public class Main { public static void main(String[] args) { System.out.println(0); } }\n"
    if language == "C++": return "main.cpp", "#include <iostream>\nint main(){std::cout<<0<<\"\\n\";}\n"
    return "main.c", "#include <stdio.h>\nint main(void){puts(\"0\");return 0;}\n"


def norm(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").rstrip("\n")


def audit_language(language: str) -> dict:
    ensure_database_schema(engine)
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(
        ProgrammingExercise.language == language,
        ProgrammingExercise.is_active.is_(True),
        ProgrammingExercise.quality_status == "approved",
    ).order_by(ProgrammingExercise.id.asc()).all()
    statements = [re.sub(r"\s+", "", str(row.statement_zh or "")) for row in rows]
    records = []
    for index, row in enumerate(rows):
        public, hidden = flatten(row.public_tests_json), flatten(row.hidden_tests_json)
        filename, reference = file_content(row.reference_files_json, "Main.java" if language == "Java" else "main.py" if language == "Python" else "main.cpp" if language == "C++" else "main.c")
        starter_name, starter = file_content(row.starter_files_json, filename)
        public_inputs = {json.dumps({k: v for k, v in item.items() if k not in {"id", "name", "visibility"}}, ensure_ascii=False, sort_keys=True) for item in public}
        hidden_inputs = {json.dumps({k: v for k, v in item.items() if k not in {"id", "name", "visibility"}}, ensure_ascii=False, sort_keys=True) for item in hidden}
        starter_valid = reference_passed = wrong_rejected = False
        failure = []
        candidate = {"language": language, "starter_code": starter, "reference_code": reference, "filename": starter_name or filename}
        try:
            starter_valid = bool(compile_starter(candidate))
            inputs = [str(item.get("stdin_text", item.get("stdin", ""))) for item in [*public, *hidden]]
            expected = [str(item.get("expected_stdout", item.get("expected", ""))) for item in [*public, *hidden]]
            actual = run_standard_many(language, reference, inputs)
            reference_passed = len(actual) == len(expected) and all(norm(a) == norm(b) for a, b in zip(actual, expected))
            _, wrong = wrong_code(language)
            wrong_actual = run_standard_many(language, wrong, [str(item.get("stdin_text", item.get("stdin", ""))) for item in hidden])
            wrong_rejected = any(norm(a) != norm(item.get("expected_stdout", item.get("expected", ""))) for a, item in zip(wrong_actual, hidden))
        except Exception as exc:
            failure.append(str(exc)[-600:])
        content_fields = ("title_zh", "summary_zh", "statement_zh", "input_format_zh", "output_format_zh", "constraints_zh", "background_knowledge_zh", "hints_zh")
        content_ok = all(str(getattr(row, field) or "").strip() and not any(marker in str(getattr(row, field) or "") for marker in BANNED) for field in content_fields)
        content_ok = content_ok and any("\u4e00" <= char <= "\u9fff" for char in str(row.title_zh or ""))
        mapping_ok = bool(row.learning_objective_id and row.learning_objective and row.curriculum_module and row.knowledge_point_ids and row.primary_knowledge_point_id and row.prerequisite_knowledge_point_ids is not None)
        duplicates = len(public_inputs & hidden_inputs)
        similarity = max((difflib.SequenceMatcher(None, statements[index], other).ratio() for pos, other in enumerate(statements) if pos != index), default=0.0)
        checks = {
            "content_quality_passed": content_ok,
            "curriculum_slot_covered": mapping_ok,
            "public_case_count": len(public) >= 3,
            "hidden_case_count": len(hidden) >= 5,
            "public_hidden_duplicate_count": duplicates == 0,
            "starter_valid": starter_valid,
            "reference_passed": reference_passed,
            "wrong_solution_rejected": wrong_rejected,
            "similarity_passed": similarity <= 0.78,
        }
        failure.extend(name for name, ok in checks.items() if not ok and name not in {"public_case_count", "hidden_case_count", "public_hidden_duplicate_count"})
        records.append({
            "language": language, "exercise_id": row.id, "source": row.source_repo, "source_key": row.source_key,
            "title_zh_present": bool(row.title_zh), "summary_zh_present": bool(row.summary_zh), "statement_zh_present": bool(row.statement_zh),
            "input_format_zh_present": bool(row.input_format_zh), "output_format_zh_present": bool(row.output_format_zh), "constraints_zh_present": bool(row.constraints_zh),
            "background_knowledge_zh_present": bool(row.background_knowledge_zh), "hints_zh_present": bool(row.hints_zh), "english_original_preserved": bool(row.title_en or row.title),
            "public_case_count": len(public), "hidden_case_count": len(hidden), "public_hidden_duplicate_count": duplicates,
            "starter_valid": starter_valid, "reference_passed": reference_passed, "wrong_solution_rejected": wrong_rejected,
            "hidden_not_serialized": None, "content_quality_passed": content_ok, "similarity_passed": similarity <= 0.78,
            "curriculum_slot_covered": mapping_ok, "difficulty": row.difficulty, "quality_status": row.quality_status,
            "quality_score": row.quality_score, "similarity_max": round(similarity, 4),
            "final_status": "passed" if all(checks.values()) else "failed", "failure_reason": "; ".join(failure),
        })
    db.close()
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "language": language, "approved_total": len(records), "passed": sum(x["final_status"] == "passed" for x in records), "failed": sum(x["final_status"] != "passed" for x in records), "difficulty": dict(Counter(x["difficulty"] for x in records)), "results": records}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"programming-catalog-480-{language.replace('+', 'p')}-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=("C", "C++", "Python", "Java"), required=True)
    args = parser.parse_args()
    result = audit_language(args.language)
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, ensure_ascii=False))


if __name__ == "__main__": main()
