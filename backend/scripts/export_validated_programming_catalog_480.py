"""Export the already audited 480-exercise catalog for deployment.

The snapshot is a derived deployment input.  It contains programming exercise
rows only; users, submissions, progress, and the local SQLite database never
enter the artifact.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402


OUTPUT = ROOT / "backend" / "data" / "programming_catalog_480.json.gz"
LANGUAGES = ("C", "C++", "Python", "Java")
EXPECTED_COUNT = {language: 120 for language in LANGUAGES}
EXCLUDED_FIELDS = {"id", "created_at", "updated_at"}


def main() -> None:
    ensure_database_schema(engine)
    fields = [
        column.name
        for column in ProgrammingExercise.__table__.columns
        if column.name not in EXCLUDED_FIELDS
    ]
    db = SessionLocal()
    try:
        rows = (
            db.query(ProgrammingExercise)
            .filter(
                ProgrammingExercise.is_active.is_(True),
                ProgrammingExercise.quality_status == "approved",
            )
            .order_by(ProgrammingExercise.language, ProgrammingExercise.id)
            .all()
        )
        counts = {language: sum(row.language == language for row in rows) for language in LANGUAGES}
        if counts != EXPECTED_COUNT or len(rows) != 480:
            raise RuntimeError(f"expected 480 approved active records, got {counts}")
        if any(not row.source_key for row in rows):
            raise RuntimeError("approved active catalog contains a record without source_key")
        if len({row.source_key for row in rows}) != len(rows):
            raise RuntimeError("approved active catalog contains duplicate source_key values")
        if any(row.quality_status != "approved" or not row.is_active for row in rows):
            raise RuntimeError("snapshot contains an inactive or non-approved record")
        if any(not row.reference_verified or not row.starter_verified for row in rows):
            raise RuntimeError("approved active catalog contains an unvalidated exercise")
        payload = {
            "schema_version": 3,
            "catalog": "programming-480",
            "validated": True,
            "counts": counts,
            "exercises": [
                {field: getattr(row, field) for field in fields}
                for row in rows
            ],
        }
    finally:
        db.close()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(
        json.dumps(
            {"output": str(OUTPUT), "counts": counts, "bytes": OUTPUT.stat().st_size},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
