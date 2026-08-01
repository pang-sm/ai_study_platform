"""Refresh the ten Java multi-file rows after a runner/source change."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/scripts"))
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402
from build_catalog_240_quality import java_source  # noqa: E402


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(
        ProgrammingExercise.language == "Java",
        ProgrammingExercise.source_key.like("first_party_original_v2|Java|%"),
        ProgrammingExercise.is_active.is_(True),
    ).order_by(ProgrammingExercise.id).all()
    changed = 0
    try:
        for index, row in enumerate(rows[:10]):
            kind = str(row.source_key).rsplit("|", 1)[-1].rsplit("-", 1)[0]
            files = java_source(kind, False, True)
            row.starter_files_json = json.dumps(files, ensure_ascii=False, separators=(",", ":"))
            row.reference_files_json = json.dumps(files, ensure_ascii=False, separators=(",", ":"))
            changed += 1
        db.commit()
    finally:
        db.close()
    print(json.dumps({"java_multifile_rows_updated": changed, "expected": 10}, ensure_ascii=False))


if __name__ == "__main__": main()
