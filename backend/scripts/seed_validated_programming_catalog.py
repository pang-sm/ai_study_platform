"""Idempotently merge the validated 800-exercise deployment snapshot."""

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


SNAPSHOT = ROOT / "backend" / "data" / "programming_catalog_800.json.gz"
EXPECTED_COUNT = {"C": 200, "C++": 200, "Python": 200, "Java": 200}
IMMUTABLE_FIELDS = {"id", "created_at", "updated_at"}


def load_snapshot() -> list[dict]:
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("exercises")
    if not isinstance(rows, list) or len(rows) != 800:
        raise RuntimeError("deployment snapshot must contain exactly 800 exercises")
    counts = {language: sum(row.get("language") == language for row in rows) for language in EXPECTED_COUNT}
    if counts != EXPECTED_COUNT:
        raise RuntimeError(f"invalid snapshot language counts: {counts}")
    keys = [row.get("source_key") for row in rows]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise RuntimeError("deployment snapshot source_key values must be present and unique")
    return rows


def seed() -> dict:
    ensure_database_schema(engine)
    rows = load_snapshot()
    db = SessionLocal()
    try:
        keys = {row["source_key"] for row in rows}
        existing = {
            row.source_key: row
            for row in db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key.in_(keys)).all()
        }
        inserted = 0
        updated = 0
        for data in rows:
            row = existing.get(data["source_key"])
            if row is None:
                row = ProgrammingExercise()
                db.add(row)
                inserted += 1
            else:
                updated += 1
            for field, value in data.items():
                if field not in IMMUTABLE_FIELDS:
                    setattr(row, field, value)

        deactivated = (
            db.query(ProgrammingExercise)
            .filter(ProgrammingExercise.is_active.is_(True))
            .filter(~ProgrammingExercise.source_key.in_(keys))
            .update({"is_active": False}, synchronize_session=False)
        )
        db.commit()
        result = {"inserted": inserted, "updated": updated, "deactivated": deactivated, "active": 800}
        print(json.dumps(result, ensure_ascii=False))
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
