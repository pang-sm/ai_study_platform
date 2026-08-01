"""Export the approved 240-row catalog as the deployment artifact."""
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

OUTPUT = ROOT / "backend/data/programming_catalog_240.json.gz"
LANGUAGES = ("C", "C++", "Python", "Java")
EXPECTED = {language: 60 for language in LANGUAGES}
EXCLUDED = {"id", "created_at", "updated_at"}


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.quality_status == "approved",
            ProgrammingExercise.source_key.like("first_party_original_v2|%"),
        ).order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()
        counts = {language: sum(row.language == language for row in rows) for language in LANGUAGES}
        if counts != EXPECTED or len(rows) != 240:
            raise RuntimeError(f"invalid approved 240 counts: {counts}")
        keys = [row.source_key for row in rows]
        if any(not key for key in keys) or len(set(keys)) != len(keys):
            raise RuntimeError("source_key must be present and unique")
        if any(not row.reference_verified or not row.starter_verified for row in rows):
            raise RuntimeError("snapshot contains an unverified row")
        fields = [column.name for column in ProgrammingExercise.__table__.columns if column.name not in EXCLUDED]
        payload = {"schema_version": 4, "catalog": "programming-240", "validated": True, "counts": counts, "exercises": [{field: getattr(row, field) for field in fields} for row in rows]}
    finally:
        db.close()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"output": str(OUTPUT), "counts": counts, "bytes": OUTPUT.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
