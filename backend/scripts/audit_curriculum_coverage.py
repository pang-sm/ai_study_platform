"""Report approved catalog coverage against the language curriculum blueprint."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

BLUEPRINT = ROOT / "backend/data/programming_catalog/curriculum_blueprint.json"
OUT = ROOT / "verification-results"


def main() -> None:
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.quality_status == "approved",
        ).all()
        approved_by_language = Counter(row.language for row in rows)
        objective_counts = Counter(row.learning_objective_id for row in rows if row.learning_objective_id)
        covered = {}
        for language, objectives in blueprint["languages"].items():
            covered[language] = []
            for objective in objectives:
                count = objective_counts[objective["objective_id"]]
                covered[language].append({
                    "objective_id": objective["objective_id"],
                    "objective": objective["objective"],
                    "approved_count": count,
                    "status": "covered" if count else "uncovered",
                })
        result = {
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "blueprint": str(BLUEPRINT.relative_to(ROOT)),
            "approved_total": len(rows),
            "approved_by_language": dict(approved_by_language),
            "covered_objectives": sum(item["status"] == "covered" for items in covered.values() for item in items),
            "total_objectives": sum(len(items) for items in covered.values()),
            "languages": covered,
        }
    finally:
        db.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "curriculum-coverage-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Curriculum Coverage Audit", "", f"- Approved exercises: `{result['approved_total']}`", f"- Approved by language: `{result['approved_by_language']}`", f"- Objectives covered: `{result['covered_objectives']}/{result['total_objectives']}`", ""]
    for language, items in covered.items():
        lines.append(f"## {language}")
        lines.extend(f"- `{item['objective_id']}`: {item['status']} ({item['approved_count']})" for item in items)
        lines.append("")
    (OUT / "curriculum-coverage-audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
