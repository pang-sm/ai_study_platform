"""Repair deterministic metadata for the already validated 480 catalog.

No code or test field is changed here; this pass only replaces the first
draft's overly uniform Chinese statements with algorithm-specific prose.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402
from build_catalog_480_quality import LANGUAGE_OBJECTIVES, OPS, title_and_statement  # noqa: E402


def main() -> None:
    variant_names = ["基础边界", "反例与重复值", "规模与负数", "逆序输入", "稀疏数据", "峰值数据"]
    ensure_database_schema(engine)
    db = SessionLocal()
    changed = 0
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.source_key.like("first_party_catalog_480:%"),
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.quality_status == "approved",
        ).all()
        for row in rows:
            parts = str(row.source_key).split(":")
            if len(parts) != 4:
                continue
            _, language, op, serial_text = parts
            serial = int(serial_text)
            item = next(item for item in OPS if item[0] == op)
            variant = serial % 6
            _, title, _, _, _, _ = item
            objective = next(x[1] for x in LANGUAGE_OBJECTIVES[language] if x[0] == row.learning_objective_id)
            title_zh, statement, _ = title_and_statement(language, op, variant, title, objective)
            row.title = title_zh
            row.title_zh = title_zh
            row.statement_zh = statement
            row.summary_zh = f"围绕{title}训练{row.core_skill}，重点覆盖{variant_names[variant]}。"
            row.description = row.summary_zh
            if serial < 30:
                row.difficulty, row.difficulty_score, row.estimated_minutes = "入门", 35, 20
            elif serial < 70:
                row.difficulty, row.difficulty_score, row.estimated_minutes = "基础", 50, 30
            elif serial < 75:
                row.difficulty, row.difficulty_score, row.estimated_minutes = "中等", 65, 40
            else:
                row.difficulty, row.difficulty_score, row.estimated_minutes = "进阶", 78, 50
            changed += 1
        for language in ("C", "C++", "Python", "Java"):
            recovery = db.query(ProgrammingExercise).filter(
                ProgrammingExercise.language == language,
                ProgrammingExercise.source_key.like("recovery-2026:%"),
                ProgrammingExercise.is_active.is_(True),
                ProgrammingExercise.quality_status == "approved",
            ).order_by(ProgrammingExercise.id.asc()).all()
            for index, row in enumerate(recovery):
                row.difficulty = "挑战" if index >= 25 else "进阶" if index >= 20 else "中等"
                row.difficulty_score = 90 if index >= 25 else 78 if index >= 20 else 65
                row.estimated_minutes = 60 if index >= 25 else 50 if index >= 20 else 40
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print({"changed": changed})


if __name__ == "__main__":
    main()
