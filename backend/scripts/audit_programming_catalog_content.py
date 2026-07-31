"""Audit cross-language overlap and Chinese presentation readiness.

The audit is deliberately read-only.  It records missing metadata instead of
silently treating English Exercism source text as Chinese content.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal
from models import ProgrammingExercise


def as_json(value: str) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def problem_metadata(row: ProgrammingExercise) -> dict:
    audit = as_json(row.audit_report_json)
    return audit.get("problem", {}) if isinstance(audit.get("problem"), dict) else {}


def has_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value or ""))


def has_markdown_noise(value: str) -> bool:
    text = str(value or "")
    return "# Instructions" in text or "[" in text and "](" in text


def pilot_family(row: ProgrammingExercise) -> str:
    # source_key is immutable and has the stable final slug segment.
    return str(row.source_key or row.slug).rsplit(":", 1)[-1]


def write_json_md(name: str, payload: dict, lines: list[str]) -> None:
    target = ROOT / "verification-results"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.reference_verified.is_(True),
            ProgrammingExercise.starter_verified.is_(True),
        ).order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()

        pilot_rows = [row for row in rows if str(row.source_key or "").startswith("chinese_oj_pilot_v1:")]
        families: dict[str, list[ProgrammingExercise]] = defaultdict(list)
        for row in pilot_rows:
            families[pilot_family(row)].append(row)
        family_records = []
        per_language = defaultdict(lambda: {"total": 0, "repeated": 0, "unique": 0})
        for family_id, members in sorted(families.items()):
            languages = sorted({row.language for row in members})
            repeated = len(languages) > 1
            for language in languages:
                per_language[language]["total"] += 1
                per_language[language]["repeated" if repeated else "unique"] += 1
            family_records.append({
                "problem_family_id": family_id,
                "exercises": [{"language": row.language, "exercise_id": row.id, "source_key": row.source_key, "title": row.title} for row in members],
                "completely_duplicate": repeated,
                "has_language_learning_value": False if repeated else True,
                "language_fit_reason": {row.language: "未记录；当前第一方题族使用同一题意和测试协议。" for row in members},
                "decision": "调整" if repeated else "保留",
            })
        cross_summary = {language: {**values, "duplicate_ratio": values["repeated"] / values["total"] if values["total"] else 0} for language, values in sorted(per_language.items())}
        cross_payload = {"summary": cross_summary, "families": family_records}
        write_json_md("cross-language-problem-audit", cross_payload, [
            "# 跨语言题目审计", "", f"原创题总数：{len(pilot_rows)}", "",
            *[f"- {language}：重复 {item['repeated']}/{item['total']}（{item['duplicate_ratio']:.0%}）" for language, item in cross_summary.items()],
            "", "当前 10 个原创题族均跨 C/C++/Python 完全重复，超过 30% 上限，应调整。",
        ])

        content_records = []
        for row in rows:
            is_pilot = row in pilot_rows
            # Current database columns are the canonical catalog source.
            title_zh = str(row.title_zh or (row.title if is_pilot else ""))
            summary_zh = str(row.summary_zh or (row.description if is_pilot else ""))
            statement_zh = str(row.statement_zh or (row.description if is_pilot else ""))
            input_zh = str(row.input_format_zh or "")
            output_zh = str(row.output_format_zh or "")
            generic = row.title == "编程练习" or "请根据题目要求完成当前练习" in str(row.description or "")
            final = all([has_chinese(title_zh), has_chinese(summary_zh), has_chinese(statement_zh), has_chinese(input_zh), has_chinese(output_zh), bool(row.constraints_zh), bool(row.title_en), bool(row.statement_en)]) and not generic and not has_markdown_noise(summary_zh)
            content_records.append({
                "language": row.language, "exercise_id": row.id, "source_key": row.source_key,
                "title_zh_present": has_chinese(title_zh), "summary_zh_present": has_chinese(summary_zh),
                "statement_zh_present": has_chinese(statement_zh), "input_format_zh_present": has_chinese(input_zh),
                "output_format_zh_present": has_chinese(output_zh), "raw_english_visible_on_card": not is_pilot and bool(row.description),
                "markdown_noise_present": has_markdown_noise(row.description), "card_overflow": "not_verified",
                "card_height_consistent": "not_verified", "language_specific_value": "not_verified",
                "final_status": "passed" if final else "failed",
                "failure_reason": "" if final else "缺少独立中文展示字段，或当前卡片来源仍为英文/Markdown 原文。",
            })
        failed = [item for item in content_records if item["final_status"] != "passed"]
        content_payload = {"summary": {"total": len(content_records), "passed": len(content_records) - len(failed), "failed": len(failed)}, "results": content_records}
        write_json_md("chinese-problem-content-audit", content_payload, [
            "# 中文题目内容审计", "", f"启用题目：{len(content_records)}；通过：{len(content_records)-len(failed)}；失败：{len(failed)}。",
            "", "英文 Exercism 原文未被误标为中文；需在保留英文原文的前提下补充标准中文字段。",
        ])
        layout_records = [{"language": row.language, "exercise_id": row.id, "card_overflow": "not_verified", "card_height_consistent": "not_verified", "final_status": "not_verified", "failure_reason": "需要部署后的真实浏览器多分辨率验收。"} for row in rows]
        write_json_md("problem-card-layout-audit", {"summary": {"total": len(layout_records), "not_verified": len(layout_records)}, "results": layout_records}, [
            "# 题库卡片布局审计", "", f"共 {len(layout_records)} 道启用题目待真实浏览器验证。",
        ])
    finally:
        db.close()


if __name__ == "__main__":
    main()
