"""Audit and quarantine low-quality generated programming exercises.

This is intentionally conservative for approval and aggressive for obvious
template spam. It never deletes rows or user-linked records.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import and_, or_

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402


REPORT_DIR = ROOT / "verification-results"
FORBIDDEN_TITLE_MARKERS = (
    "add", "sub", "mul", "max", "min", "basic", "variant", "generated",
    "编程练习", "基础练习", "综合练习",
)
QUALITY_STATUSES = {"approved", "needs_review", "rejected"}


def text(value) -> str:
    return str(value or "").strip()


def normalize(value: str, remove_numbers: bool = True) -> str:
    value = text(value).lower()
    if remove_numbers:
        value = re.sub(r"\d+", "#", value)
    return re.sub(r"[^\w\u4e00-\u9fff#]+", "", value)


def json_text(value) -> str:
    try:
        return json.dumps(json.loads(value or ""), ensure_ascii=False, sort_keys=True)
    except (TypeError, json.JSONDecodeError):
        return text(value)


def solution_structure(value: str) -> str:
    value = json_text(value).lower()
    value = re.sub(r"//.*|#.*|/\*.*?\*/", "", value, flags=re.S)
    value = re.sub(r"\"[^\"]*\"|'[^']*'", "STR", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", value)
    value = re.sub(r"\b[a-z_]\w*\b", "ID", value)
    return re.sub(r"\s+", "", value)


def marker_reasons(title: str) -> list[str]:
    lowered = text(title).lower()
    reasons = []
    if re.search(r"练习\s*\d+", lowered):
        reasons.append("numbered_template_title")
    if any(marker in lowered for marker in FORBIDDEN_TITLE_MARKERS):
        reasons.append("internal_template_or_operation_marker")
    if "双整数" in lowered:
        reasons.append("generic_two_integer_template")
    return reasons


def pairwise_max(values: list[str], threshold: float) -> list[float]:
    result = [0.0] * len(values)
    for index, current in enumerate(values):
        if not current:
            continue
        for other_index in range(index):
            other = values[other_index]
            if not other:
                continue
            score = difflib.SequenceMatcher(None, current, other).ratio()
            result[index] = max(result[index], score)
            result[other_index] = max(result[other_index], score)
    return result


def audit(apply: bool) -> dict:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = (
            db.query(ProgrammingExercise)
            .filter(or_(
                ProgrammingExercise.is_active.is_(True),
                and_(
                    ProgrammingExercise.quality_status == "rejected",
                    ProgrammingExercise.reviewed_at.isnot(None),
                ),
            ))
            .order_by(ProgrammingExercise.language, ProgrammingExercise.id)
            .all()
        )
        title_values = [normalize(row.title_zh or row.title) for row in rows]
        statement_values = [normalize(" ".join((row.statement_zh, row.input_format_zh, row.output_format_zh, row.constraints_zh))) for row in rows]
        reference_values = [solution_structure(row.reference_files_json) for row in rows]
        title_similarity = pairwise_max(title_values, 0.78)
        statement_similarity = pairwise_max(statement_values, 0.78)
        reference_similarity = pairwise_max(reference_values, 0.85)
        family_counts = Counter((row.language, text(row.problem_family_id)) for row in rows)
        objective_counts = Counter((row.language, text(row.learning_objective_id)) for row in rows if text(row.learning_objective_id))

        records = []
        for index, row in enumerate(rows):
            reasons = marker_reasons(row.title_zh or row.title)
            if title_similarity[index] >= 0.78:
                reasons.append("title_similarity_above_threshold")
            if statement_similarity[index] >= 0.78:
                reasons.append("statement_similarity_above_threshold")
            if reference_similarity[index] >= 0.85:
                reasons.append("reference_structure_similarity_above_threshold")
            if family_counts[(row.language, text(row.problem_family_id))] > 3:
                reasons.append("problem_family_over_language_limit")
            if objective_counts[(row.language, text(row.learning_objective_id))] > 2 and text(row.learning_objective_id):
                reasons.append("learning_objective_over_language_limit")
            required_objective_fields = (row.learning_objective_id, row.learning_objective, row.prerequisites, row.core_skill, row.novelty_reason)
            if not all(text(value) for value in required_objective_fields):
                reasons.append("missing_teaching_objective_fields")
            reasons = sorted(set(reasons))
            status = "approved" if not reasons else "rejected"
            score = max(0, 100 - len(reasons) * 15)
            record = {
                "language": row.language,
                "exercise_id": row.id,
                "source_key": row.source_key,
                "title": row.title_zh or row.title,
                "quality_status": status,
                "quality_score": score,
                "quality_failure_reasons": reasons,
                "title_similarity": round(title_similarity[index], 4),
                "statement_similarity": round(statement_similarity[index], 4),
                "reference_structure_similarity": round(reference_similarity[index], 4),
                "problem_family_id": row.problem_family_id,
                "learning_objective_id": row.learning_objective_id,
                "is_active_before": bool(row.is_active),
            }
            records.append(record)
            if apply:
                row.quality_status = status
                row.quality_score = score
                row.quality_failure_reasons = json.dumps(reasons, ensure_ascii=False)
                row.reviewed_at = dt.datetime.now(dt.timezone.utc).isoformat()
                if status != "approved":
                    row.is_active = False
        if apply:
            db.commit()
    finally:
        db.close()

    counts = Counter(record["quality_status"] for record in records)
    reason_counts = Counter(reason for record in records for reason in record["quality_failure_reasons"])
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "applied": apply,
        "audited_record_count": len(records),
        "original_active_count": sum(record["is_active_before"] for record in records),
        "previously_reviewed_rejected_count": sum(
            record["quality_status"] == "rejected" and not record["is_active_before"]
            for record in records
        ),
        "status_counts": dict(counts),
        "failure_reason_counts": dict(reason_counts),
        "language_counts": dict(Counter(record["language"] for record in records)),
        "records": records,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "programming-catalog-quality-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rejected = [record for record in records if record["quality_status"] == "rejected"]
    (REPORT_DIR / "rejected-generated-problems.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Programming Catalog Quality Audit", "", f"- Applied: `{apply}`", f"- Original active: `{len(records)}`", f"- Status counts: `{dict(counts)}`", "", "## Failure reasons", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(reason_counts.items()))
    (REPORT_DIR / "programming-catalog-quality-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(apply=args.apply and not args.dry_run), ensure_ascii=False))
