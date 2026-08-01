"""Full compiler, runtime, content and API audit for the approved 240 catalog."""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/scripts"))
from catalog_adapters import _compile, _run  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from main import serialize_programming_exercise  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

OUT = ROOT / "verification-results"
LANGUAGES = ("C", "C++", "Python", "Java")
BLUEPRINT = json.loads((ROOT / "backend/data/programming_catalog/curriculum_blueprint.json").read_text(encoding="utf-8"))
BANNED = ("# Instructions", "编程练习", "通用练习", "TODO", "待补充", "暂无题干", "请根据要求完成代码", "练习 66")


def flatten(raw: str) -> list[dict]:
    try: data = json.loads(raw or "[]")
    except Exception: return []
    return [item for group in data if isinstance(group, dict) for item in group.get("samples", []) if isinstance(item, dict)]


def source_files(raw: str) -> list[dict]:
    try: data = json.loads(raw or "[]")
    except Exception: return []
    return [item for item in data if isinstance(item, dict) and item.get("path") and item.get("content") is not None]


def norm(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").rstrip("\n")


def wrong_files(language: str) -> list[dict]:
    code = {
        "Python": "print(0)\n",
        "Java": "public class Main { public static void main(String[] args) { System.out.println(0); } }\n",
        "C++": "#include <iostream>\nint main(){std::cout<<0<<\"\\n\";}\n",
        "C": "#include <stdio.h>\nint main(void){puts(\"0\");return 0;}\n",
    }[language]
    path = "main.py" if language == "Python" else "Main.java" if language == "Java" else "main.cpp" if language == "C++" else "main.c"
    return [{"path": path, "content": code}]


def run_many(language: str, files: list[dict], tests: list[dict]) -> list[str]:
    candidate = {"language": language, "reference_files": files, "main_class": "Main"}
    with tempfile.TemporaryDirectory(prefix="catalog-240-audit-") as raw:
        root = Path(raw)
        _compile(candidate, root, "reference")
        command = [sys.executable, "main.py"] if language == "Python" else ["java", "-cp", str(root), "Main"] if language == "Java" else [str(root / "program.exe")]
        return [_run(command, root, str(item.get("stdin_text", item.get("stdin", "")))) for item in tests]


def write_pair(stem: str, title: str, payload: dict) -> None:
    (OUT / f"{stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = payload.get("summary", payload)
    (OUT / f"{stem}.md").write_text(f"# {title}\n\n```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n", encoding="utf-8")


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True), ProgrammingExercise.quality_status == "approved", ProgrammingExercise.source_key.like("first_party_original_v2|%" )).order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()
    records = []
    try:
        for row in rows:
            public, hidden = flatten(row.public_tests_json), flatten(row.hidden_tests_json)
            starter, reference = source_files(row.starter_files_json), source_files(row.reference_files_json)
            all_tests = public + hidden
            public_inputs = {str(x.get("stdin_text", x.get("stdin", ""))) for x in public}
            hidden_inputs = {str(x.get("stdin_text", x.get("stdin", ""))) for x in hidden}
            starter_valid = reference_passed = wrong_rejected = False
            failure = []
            try:
                _compile({"language": row.language, "starter_files": starter}, Path(tempfile.mkdtemp(prefix="catalog-240-starter-")), "starter")
                starter_valid = True
                actual = run_many(row.language, reference, all_tests)
                reference_passed = len(actual) == len(all_tests) and all(norm(a) == norm(x.get("expected_stdout", x.get("expected", ""))) for a, x in zip(actual, all_tests))
                wrong_actual = run_many(row.language, wrong_files(row.language), hidden)
                wrong_rejected = any(norm(a) != norm(x.get("expected_stdout", x.get("expected", ""))) for a, x in zip(wrong_actual, hidden))
            except Exception as exc:
                failure.append(str(exc)[-700:])
            fields = ("title_zh", "summary_zh", "statement_zh", "input_format_zh", "output_format_zh", "constraints_zh", "learning_objective", "language_fit_reason", "problem_family_id")
            content_ok = all(str(getattr(row, field) or "").strip() and not any(marker in str(getattr(row, field) or "") for marker in BANNED) for field in fields)
            content_ok = content_ok and any("\u4e00" <= char <= "\u9fff" for char in str(row.title_zh or "")) and not re.search(r"(?:练习|题目)\s*\d+$", str(row.title_zh or ""))
            objective_ids = {item["objective_id"] for item in BLUEPRINT["languages"][row.language]}
            curriculum_ok = row.learning_objective_id in objective_ids and bool(row.primary_knowledge_point_id) and bool(row.curriculum_module)
            duplicate_count = len(public_inputs & hidden_inputs)
            try:
                api_payload = serialize_programming_exercise(row)
                hidden_not_serialized = "hidden_tests" not in api_payload and "hidden_samples" not in api_payload and all(str(x.get("stdin_text", "")) not in json.dumps(api_payload, ensure_ascii=False) for x in hidden)
            except Exception as exc:
                hidden_not_serialized = False; failure.append(f"API serialization: {exc}")
            records.append({
                "language": row.language, "exercise_id": row.id, "source": row.source_repo, "source_key": row.source_key,
                "title_zh_present": bool(row.title_zh), "summary_zh_present": bool(row.summary_zh), "statement_zh_present": bool(row.statement_zh), "input_format_zh_present": bool(row.input_format_zh), "output_format_zh_present": bool(row.output_format_zh), "constraints_zh_present": bool(row.constraints_zh), "english_original_preserved": bool(row.title_en or row.title),
                "public_case_count": len(public), "hidden_case_count": len(hidden), "public_hidden_duplicate_count": duplicate_count, "starter_valid": starter_valid, "reference_passed": reference_passed, "wrong_solution_rejected": wrong_rejected, "hidden_not_serialized": hidden_not_serialized,
                "content_quality_passed": content_ok, "similarity_passed": True, "curriculum_slot_covered": curriculum_ok, "quality_status": row.quality_status, "quality_score": row.quality_score, "difficulty": row.difficulty, "curriculum_module": row.curriculum_module, "java_multifile": row.language == "Java" and len(reference) > 1, "final_status": "passed", "failure_reason": "; ".join(failure),
            })
    finally:
        db.close()
    # Similarity is computed after every row has been collected, per language.
    for language in LANGUAGES:
        lang_rows = [r for r in records if r["language"] == language]
        statements = []
        db2 = SessionLocal()
        try:
            statements = [re.sub(r"\s+", "", str(x.statement_zh or "")) for x in db2.query(ProgrammingExercise).filter(ProgrammingExercise.language == language, ProgrammingExercise.is_active.is_(True), ProgrammingExercise.source_key.like("first_party_original_v2|%" )).order_by(ProgrammingExercise.id).all()]
        finally: db2.close()
        for i, record in enumerate(lang_rows):
            maximum = max((difflib.SequenceMatcher(None, statements[i], other).ratio() for j, other in enumerate(statements) if i != j), default=0.0)
            record["similarity_max"] = round(maximum, 4); record["similarity_passed"] = maximum <= 0.78
            checks = [record["title_zh_present"], record["summary_zh_present"], record["statement_zh_present"], record["input_format_zh_present"], record["output_format_zh_present"], record["constraints_zh_present"], record["public_case_count"] >= 3, record["hidden_case_count"] >= 5, record["public_hidden_duplicate_count"] == 0, record["starter_valid"], record["reference_passed"], record["wrong_solution_rejected"], record["hidden_not_serialized"], record["content_quality_passed"], record["similarity_passed"], record["curriculum_slot_covered"]]
            if not all(checks): record["final_status"] = "failed"; record["failure_reason"] += "; failed quality gate"
    passed = sum(x["final_status"] == "passed" for x in records)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "total": len(records), "passed": passed, "failed": len(records) - passed, "counts": dict(Counter(x["language"] for x in records)), "difficulty": dict(Counter(x["difficulty"] for x in records)), "modules": dict(Counter(x["curriculum_module"] for x in records))}
    write_pair("programming-catalog-240-quality-audit", "240 题质量审计", {"summary": summary, "results": records})
    objectives = {}
    for language in LANGUAGES:
        seen = Counter(x["curriculum_slot_covered"] for x in records if x["language"] == language)
        ids = {x["learning_objective_id"] for x in []}
        db3 = SessionLocal()
        try: ids = {x.learning_objective_id for x in db3.query(ProgrammingExercise).filter(ProgrammingExercise.language == language, ProgrammingExercise.is_active.is_(True), ProgrammingExercise.source_key.like("first_party_original_v2|%" )).all()}
        finally: db3.close()
        objectives[language] = {item["objective_id"]: {"objective": item["objective"], "covered": item["objective_id"] in ids, "count": sum(1 for r in records if r["language"] == language and r["curriculum_slot_covered"])} for item in BLUEPRINT["languages"][language]}
    write_pair("programming-curriculum-60-audit", "四语言课程目标覆盖", {"summary": {"objective_total": 32, "covered": sum(sum(x["covered"] for x in v.values()) for v in objectives.values())}, "languages": objectives})
    java = [x for x in records if x["language"] == "Java"]
    write_pair("programming-multifile-java-audit", "Java 多文件审计", {"summary": {"java_total": len(java), "multifile": sum(x["java_multifile"] for x in java), "multifile_valid": sum(x["java_multifile"] and x["starter_valid"] and x["reference_passed"] for x in java)}, "results": java})
    write_pair("programming-test-coverage-240", "240 题测试覆盖", {"summary": {"total": len(records), "public_at_least_3": sum(x["public_case_count"] >= 3 for x in records), "hidden_at_least_5": sum(x["hidden_case_count"] >= 5 for x in records), "references_passed": sum(x["reference_passed"] for x in records), "wrong_rejected": sum(x["wrong_solution_rejected"] for x in records)}, "results": records})
    write_pair("programming-overlap-240", "240 题重叠审计", {"summary": {"public_hidden_duplicate_total": sum(x["public_hidden_duplicate_count"] for x in records), "similarity_failures": [x["source_key"] for x in records if not x["similarity_passed"]], "source_key_duplicates": len(records) - len({x["source_key"] for x in records})}})
    print(json.dumps({"total": len(records), "passed": passed, "failed": len(records) - passed, "counts": dict(Counter(x["language"] for x in records))}, ensure_ascii=False))
    if passed != 240:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
