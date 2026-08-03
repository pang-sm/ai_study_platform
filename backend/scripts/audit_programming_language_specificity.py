"""Generate the final language-specificity, curriculum, and content reports."""
from __future__ import annotations

import datetime as dt
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from main import serialize_programming_exercise  # noqa: E402
from models import ProgrammingExercise  # noqa: E402


OUT = ROOT / "verification-results"
LANGUAGES = ("C", "C++", "Python", "Java")
BANNED_CONTENT = ("# Instructions", "编程练习", "通用练习", "TODO", "待补充", "暂无题干", "请根据要求完成代码")
TITLE_BANNED = ("练习", "通用校验器", "基础边界", "规模与负数", "稀疏数据")
ALLOWED_SHARED_FAMILIES = {
    "catalog240-checksum-0", "catalog240-unique-0", "catalog240-words-0",
    "catalog240-brackets-0", "catalog240-coins-0", "catalog240-bfs-0",
}


def parse(raw: str, default):
    try:
        return json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        return default


def samples(raw: str) -> list[dict]:
    return [item for group in parse(raw, []) if isinstance(group, dict) for item in group.get("samples", []) if isinstance(item, dict)]


def files(raw: str) -> list[dict]:
    return [item for item in parse(raw, []) if isinstance(item, dict) and item.get("path") and item.get("content") is not None]


def text(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    return re.sub(r"\s+", "", text(value).lower())


def feature_value(row: ProgrammingExercise) -> bool:
    code = "\n".join(text(item.get("content")) for item in files(row.reference_files_json)).lower()
    markers = {
        "C": ("scanf", "printf", "&", "malloc", "struct", "fopen"),
        "C++": ("ios::sync_with_stdio", "cin", "cout", "vector<", "map<", "sort(", "priority_queue"),
        "Python": ("sys.stdin", "list(map", "sorted(", "bisect", "math.", "set(", "yield", "dict.fromkeys"),
        "Java": ("scanner", "system.out", "arraylist", "hashmap", "deque", "comparator", "stream()", "optional", "record "),
    }[row.language]
    return sum(marker in code for marker in markers) >= 2 or len(files(row.reference_files_json)) >= 3


def audit_report(row: ProgrammingExercise) -> dict:
    return parse(row.audit_report_json, {})


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True), ProgrammingExercise.quality_status == "approved",
        ).order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()
    finally:
        db.close()

    records = []
    title_by_language = defaultdict(list)
    for row in rows:
        title_by_language[row.language].append(norm(row.title_zh or row.title))
    for row in rows:
        public, hidden = samples(row.public_tests_json), samples(row.hidden_tests_json)
        starter, reference = files(row.starter_files_json), files(row.reference_files_json)
        public_inputs = {text(item.get("stdin_text", item.get("input", ""))) for item in public}
        hidden_inputs = {text(item.get("stdin_text", item.get("input", ""))) for item in hidden}
        audit = audit_report(row)
        title = text(row.title_zh or row.title)
        content_fields = (row.title_zh, row.summary_zh, row.statement_zh, row.input_format_zh, row.output_format_zh, row.constraints_zh)
        content_quality = all(text(value) and not any(marker in text(value) for marker in BANNED_CONTENT) for value in content_fields)
        title_quality = bool(re.search(r"[\u4e00-\u9fff]", title)) and not any(marker in title for marker in TITLE_BANNED) and not re.search(r"\d+$", title)
        starter_text = "\n".join(text(item.get("content")) for item in starter)
        reference_text = "\n".join(text(item.get("content")) for item in reference)
        starter_lines = starter_text.splitlines()
        starter_valid = bool(row.starter_verified) and bool(starter) and all(len(line) <= 120 for line in starter_lines) and len(starter_lines) >= 4
        starter_todo = "TODO" in starter_text
        starter_reference_similarity = difflib.SequenceMatcher(None, norm(starter_text), norm(reference_text)).ratio()
        first_explanation = bool(public and text(public[0].get("explanation_zh")))
        try:
            api_payload = serialize_programming_exercise(row)
            api_text = json.dumps(api_payload, ensure_ascii=False)
            hidden_not_serialized = not any(key in api_payload for key in ("hidden_tests", "hidden_samples", "reference_solution", "reference_files"))
        except Exception:
            hidden_not_serialized = False
        ref_passed = bool(audit.get("reference_passed", row.reference_verified))
        wrong_rejected = bool(audit.get("wrong_solution_rejected", False))
        multi = row.language == "Java" and (text(row.problem_family_id).startswith("java-multifile-") or audit.get("exercise_type") == "multi_file")
        shared_exception = text(row.problem_family_id) in ALLOWED_SHARED_FAMILIES
        checks = {
            "title_quality": title_quality,
            "content_quality_passed": content_quality,
            "starter_valid": starter_valid,
            "starter_todo_present": starter_todo,
            "starter_not_reference": starter_text != reference_text and starter_reference_similarity < 0.97,
            "reference_passed": ref_passed,
            "wrong_solution_rejected": wrong_rejected,
            "public_coverage_passed": len(public) >= 3,
            "hidden_coverage_passed": len(hidden) >= 5,
            "public_hidden_duplicate_count": len(public_inputs & hidden_inputs) == 0,
            "sample_explanation_complete": first_explanation,
            "hidden_not_serialized": hidden_not_serialized,
            "language_specific_value": feature_value(row) or shared_exception,
            "quality_status_approved": row.quality_status == "approved" and bool(row.is_active),
        }
        records.append({
            "language": row.language, "exercise_id": row.id, "source": row.source_repo, "source_key": row.source_key,
            "title_zh": title, "problem_family_id": row.problem_family_id, "difficulty": row.difficulty,
            "curriculum_module": row.curriculum_module, "learning_objective_id": row.learning_objective_id,
            "java_multifile": multi, "public_case_count": len(public), "hidden_case_count": len(hidden),
            "public_hidden_duplicate_count": len(public_inputs & hidden_inputs),
            "starter_line_count": len(starter_lines), "starter_max_line_length": max((len(line) for line in starter_lines), default=0),
            "starter_todo_count": starter_text.count("TODO"), "starter_reference_similarity": round(starter_reference_similarity, 4),
            **checks,
            "final_status": "passed" if all(checks.values()) else "failed",
            "failure_reason": "" if all(checks.values()) else "; ".join(key for key, value in checks.items() if not value),
        })

    per_language = {}
    for language in LANGUAGES:
        values = [record for record in records if record["language"] == language]
        per_language[language] = {
            "total": len(values), "passed": sum(x["final_status"] == "passed" for x in values),
            "language_specific": sum(x["language_specific_value"] for x in values),
            "specific_ratio": round(sum(x["language_specific_value"] for x in values) / len(values), 4) if values else 0,
            "difficulty": dict(Counter(x["difficulty"] for x in values)),
            "modules": dict(Counter(x["curriculum_module"] for x in values)),
        }
    all_source_keys = [row["source_key"] for row in records]
    title_failures = [row for row in records if not row["title_quality"]]
    specificity = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "summary": {
            "total": len(records), "counts": {language: per_language[language]["total"] for language in LANGUAGES},
            "passed": sum(x["final_status"] == "passed" for x in records), "failed": sum(x["final_status"] == "failed" for x in records),
            "shared_family_limit": 6, "language_specific_minimum": 0.80,
            "source_key_duplicates": len(all_source_keys) - len(set(all_source_keys)),
            "title_failures": len(title_failures), "java_multifile": sum(x["java_multifile"] for x in records),
        }, "per_language": per_language, "records": records,
    }
    (OUT / "programming-language-specificity-audit.json").write_text(json.dumps(specificity, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 编程语言特性审计", "", f"总题数：{len(records)}；全量门禁通过：{specificity['summary']['passed']}/{len(records)}。", ""]
    for language in LANGUAGES:
        item = per_language[language]
        lines.append(f"- {language}：{item['total']} 道，语言特性 {item['language_specific']}/{item['total']}（{item['specific_ratio']:.0%}），执行门禁 {item['passed']}/{item['total']}。")
    lines.extend(["", "共享题族和题对指标详见 `cross-language-overlap-matrix.json`；旧重复题已归档，Java 多文件题保留。", ""])
    (OUT / "programming-language-specificity-audit.md").write_text("\n".join(lines), encoding="utf-8")

    overlap = parse((OUT / "cross-language-overlap-matrix.json").read_text(encoding="utf-8"), {})
    (OUT / "programming-cross-language-overlap.json").write_text(json.dumps(overlap, ensure_ascii=False, indent=2), encoding="utf-8")

    objectives = {}
    blueprint = parse((ROOT / "backend/data/programming_catalog/curriculum_blueprint.json").read_text(encoding="utf-8"), {})
    for language in LANGUAGES:
        language_rows = [row for row in records if row["language"] == language]
        seen = Counter(row["learning_objective_id"] for row in language_rows)
        objectives[language] = [{"objective_id": item["objective_id"], "objective": item["objective"], "count": seen[item["objective_id"]], "covered": seen[item["objective_id"]] > 0} for item in blueprint["languages"][language]]
    curriculum = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "objective_total": 32, "covered_total": sum(item["covered"] for values in objectives.values() for item in values), "all_covered": all(item["covered"] for values in objectives.values() for item in values), "languages": objectives}
    (OUT / "programming-curriculum-final.json").write_text(json.dumps(curriculum, ensure_ascii=False, indent=2), encoding="utf-8")

    content = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "summary": {
        "starter_format_passed": sum(x["starter_valid"] for x in records), "starter_not_reference": sum(x["starter_not_reference"] for x in records),
        "sample_explanation_complete": sum(x["sample_explanation_complete"] for x in records), "public_cases_at_least_3": sum(x["public_case_count"] >= 3 for x in records),
        "hidden_cases_at_least_5": sum(x["hidden_case_count"] >= 5 for x in records), "reference_passed": sum(x["reference_passed"] for x in records),
        "wrong_rejected": sum(x["wrong_solution_rejected"] for x in records), "hidden_leak_free": sum(x["hidden_not_serialized"] for x in records),
    }, "records": records}
    (OUT / "programming-content-quality-final.json").write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "programming-content-quality-final.md").write_text("# 编程题库最终内容质量审计\n\n" + json.dumps(content["summary"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"specificity": specificity["summary"], "curriculum": {"covered_total": curriculum["covered_total"], "all_covered": curriculum["all_covered"]}, "content": content["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
