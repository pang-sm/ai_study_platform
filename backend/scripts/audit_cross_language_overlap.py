"""Read-only audit of overlap between the approved programming catalog languages.

The report deliberately compares normalized task content, test protocols, and
reference structure.  It does not change exercise rows or quarantine anything;
the replacement plan is reviewed after this evidence is generated.
"""
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
from models import ProgrammingExercise  # noqa: E402


OUT = ROOT / "verification-results"
LANGUAGES = ("C", "C++", "Python", "Java")
TITLE_THRESHOLD = 0.82
STATEMENT_THRESHOLD = 0.78
SOLUTION_THRESHOLD = 0.88
TEST_THRESHOLD = 0.80
ALLOWED_SHARED_FAMILIES = {
    # These are deliberately small, language-independent foundations.  All
    # other shared families must be replaced by language-specific tasks.
    "catalog240-checksum-0",
    "catalog240-unique-0",
    "catalog240-words-0",
    "catalog240-brackets-0",
    "catalog240-coins-0",
    "catalog240-bfs-0",
}


def text(value: object) -> str:
    return str(value or "").strip()


def parse_json(value: str, default):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def samples(value: str) -> list[dict]:
    parsed = parse_json(value, [])
    result: list[dict] = []
    if isinstance(parsed, list):
        for group in parsed:
            if isinstance(group, dict) and isinstance(group.get("samples"), list):
                result.extend(item for item in group["samples"] if isinstance(item, dict))
    return result


def files(value: str) -> list[dict]:
    parsed = parse_json(value, [])
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def normalize(value: object, *, strip_numbers: bool = True) -> str:
    result = text(value).lower()
    result = re.sub(r"```.*?```", " ", result, flags=re.S)
    result = re.sub(r"https?://\S+", " ", result)
    if strip_numbers:
        result = re.sub(r"\d+", "#", result)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", result)


def solution_structure(value: str) -> str:
    parts = files(value)
    raw = "\n".join(text(item.get("content")) for item in parts)
    raw = re.sub(r"//.*|#.*|/\*.*?\*/", " ", raw, flags=re.S)
    raw = re.sub(r"\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'", "STR", raw)
    raw = re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", raw)
    raw = re.sub(r"\b[A-Za-z_]\w*\b", "ID", raw)
    return re.sub(r"\s+", "", raw)


def test_signature(value: str) -> str:
    rows = []
    for item in samples(value):
        rows.append({
            "stdin": normalize(item.get("stdin_text", item.get("input", "")), strip_numbers=False),
            "stdout": normalize(item.get("expected_stdout", item.get("expected_output", "")), strip_numbers=False),
        })
    return json.dumps(rows, ensure_ascii=False, sort_keys=True)


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def language_value(row: ProgrammingExercise) -> dict:
    code = "\n".join(text(item.get("content")) for item in files(row.reference_files_json))
    lowered = code.lower()
    markers = {
        # Include the language's actual I/O and standard-library idioms.  A
        # task is still reported as specific only when at least two markers
        # are present; a language name in metadata alone is never sufficient.
        "C": ("scanf", "printf", "&", "char[", "malloc", "free(", "struct", "->", "fopen"),
        "C++": ("ios::sync_with_stdio", "cin", "cout", "vector<", "unordered_map", "priority_queue", "sort(", "rotate(", "stable_partition"),
        "Python": ("sys.stdin", "list(map", "dict.fromkeys", "sorted(", "bisect", "math.", "set(", "for x in", "yield"),
        "Java": ("scanner", "system.out", "arrays.", "arraylist", "hashmap", "deque", "comparator", "stream()", "optional", "record "),
    }[row.language]
    matched = [marker for marker in markers if marker.lower() in lowered]
    return {
        "language": row.language,
        "markers_found": matched,
        "language_specific_value": len(matched) >= 2 or len(files(row.reference_files_json)) >= 3,
    }


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.quality_status == "approved",
        ).order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()
    finally:
        db.close()

    by_language = defaultdict(list)
    for row in rows:
        by_language[row.language].append(row)

    pair_records: list[dict] = []
    related: dict[int, list[dict]] = defaultdict(list)
    for left_language_index, left_language in enumerate(LANGUAGES):
        for right_language in LANGUAGES[left_language_index + 1:]:
            for left in by_language[left_language]:
                left_statement = normalize(" ".join((left.statement_zh, left.input_format_zh, left.output_format_zh, left.constraints_zh)))
                left_solution = solution_structure(left.reference_files_json)
                left_tests = test_signature(left.public_tests_json)
                for right in by_language[right_language]:
                    right_statement = normalize(" ".join((right.statement_zh, right.input_format_zh, right.output_format_zh, right.constraints_zh)))
                    right_solution = solution_structure(right.reference_files_json)
                    right_tests = test_signature(right.public_tests_json)
                    metrics = {
                        "title_similarity": similarity(normalize(left.title_zh or left.title), normalize(right.title_zh or right.title)),
                        "statement_similarity": similarity(left_statement, right_statement),
                        "solution_similarity": similarity(left_solution, right_solution),
                        "test_similarity": similarity(left_tests, right_tests),
                    }
                    same_family = text(left.problem_family_id) and text(left.problem_family_id) == text(right.problem_family_id)
                    duplicate = same_family or (
                        metrics["title_similarity"] >= TITLE_THRESHOLD
                        and metrics["statement_similarity"] >= STATEMENT_THRESHOLD
                    ) or (
                        metrics["statement_similarity"] >= 0.90
                        and metrics["solution_similarity"] >= SOLUTION_THRESHOLD
                    ) or (
                        metrics["test_similarity"] >= TEST_THRESHOLD
                        and metrics["solution_similarity"] >= SOLUTION_THRESHOLD
                    )
                    if not duplicate:
                        continue
                    record = {
                        "left": {"language": left.language, "exercise_id": left.id, "source_key": left.source_key},
                        "right": {"language": right.language, "exercise_id": right.id, "source_key": right.source_key},
                        "problem_family_id": left.problem_family_id if same_family else None,
                        **{key: round(value, 4) for key, value in metrics.items()},
                        "same_problem_family": same_family,
                        "shared_allowed": same_family and text(left.problem_family_id) in ALLOWED_SHARED_FAMILIES,
                    }
                    pair_records.append(record)
                    related[left.id].append(record)
                    related[right.id].append(record)

    records = []
    for row in rows:
        pairs = related.get(row.id, [])
        duplicates = sorted({
            item["right"]["language"] if item["left"]["exercise_id"] == row.id else item["left"]["language"]
            for item in pairs
        })
        strongest = max(pairs, key=lambda item: (
            item["same_problem_family"], item["statement_similarity"], item["solution_similarity"]
        ), default=None)
        family = text(row.problem_family_id)
        keep = not duplicates or family in ALLOWED_SHARED_FAMILIES
        value = language_value(row)
        records.append({
            "language": row.language,
            "exercise_id": row.id,
            "source_key": row.source_key,
            "problem_family_id": family,
            "duplicate_languages": duplicates,
            "title_similarity": strongest["title_similarity"] if strongest else 0.0,
            "statement_similarity": strongest["statement_similarity"] if strongest else 0.0,
            "solution_similarity": strongest["solution_similarity"] if strongest else 0.0,
            "test_similarity": strongest["test_similarity"] if strongest else 0.0,
            "language_specific_value": value["language_specific_value"],
            "language_markers_found": value["markers_found"],
            "keep_or_replace": "keep" if keep else "replace",
            "replacement_reason": "保留在六个共享基础题族名额内。" if keep else "跨语言任务协议、题意或参考实现重合，需替换为独立语言特性题。",
        })

    counts = {}
    for language in LANGUAGES:
        lang_rows = [item for item in records if item["language"] == language]
        shared = [item for item in lang_rows if item["duplicate_languages"]]
        kept_shared = [item for item in shared if item["keep_or_replace"] == "keep"]
        specific = [item for item in lang_rows if item["language_specific_value"]]
        counts[language] = {
            "total": len(lang_rows),
            "shared_candidates": len(shared),
            "shared_kept": len(kept_shared),
            "shared_ratio_after_plan": round(len(kept_shared) / len(lang_rows), 4) if lang_rows else 0.0,
            "language_specific_candidates": len(specific),
            "language_specific_ratio": round(len(specific) / len(lang_rows), 4) if lang_rows else 0.0,
            "replace_candidates": len(lang_rows) - len(kept_shared),
        }

    family_counts = Counter(
        text(row.problem_family_id)
        for row in rows
        if any(item["same_problem_family"] for item in related.get(row.id, []))
    )
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "read_only": True,
        "thresholds": {
            "title_similarity": TITLE_THRESHOLD,
            "statement_similarity": STATEMENT_THRESHOLD,
            "solution_similarity": SOLUTION_THRESHOLD,
            "test_similarity": TEST_THRESHOLD,
        },
        "allowed_shared_families": sorted(ALLOWED_SHARED_FAMILIES),
        "summary": {
            "approved_active_total": len(rows),
            "pair_overlap_count": len(pair_records),
            "shared_family_count": len(family_counts),
            "shared_families": dict(family_counts),
            "per_language": counts,
        },
        "records": records,
        "pair_overlaps": pair_records,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cross-language-overlap-matrix.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 四语言编程题跨语言重合审计",
        "",
        f"审计范围：启用且 approved 的 {len(rows)} 道题；本审计只读，不修改数据库。",
        "",
        "## 结论",
        "",
        f"- 判定为跨语言重合的题对：{len(pair_records)} 对。",
        f"- 共享题族：{len(family_counts)} 个；允许保留：{len(ALLOWED_SHARED_FAMILIES)} 个。",
    ]
    for language in LANGUAGES:
        item = counts[language]
        lines.append(
            f"- {language}：{item['total']} 道；当前重合候选 {item['shared_candidates']} 道；"
            f"计划保留共享 {item['shared_kept']} 道；计划替换 {item['replace_candidates']} 道；"
            f"语言特性候选 {item['language_specific_candidates']} 道。"
        )
    lines.extend(["", "## 共享题族", ""])
    for family, count in sorted(family_counts.items()):
        lines.append(f"- `{family}`：涉及 {count} 道跨语言成员；{'保留' if family in ALLOWED_SHARED_FAMILIES else '替换'}。")
    lines.extend(["", "## 处理规则", "", "- `keep` 仅表示进入六个共享基础题族名额，不代表已经完成最终质量审计。", "- `replace` 表示必须设计新任务、稳定 source_key、真实参考解、公开/隐藏测试并重新验证。", "- 逐题详细字段和题对指标见 `cross-language-overlap-matrix.json`。", ""])
    (OUT / "cross-language-overlap-audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
