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
    if payload.get("validated") is not True:
        raise RuntimeError("deployment snapshot is not marked validated=true; refusing seed")
    rows = payload.get("exercises")
    if not isinstance(rows, list) or len(rows) != 800:
        raise RuntimeError("deployment snapshot must contain exactly 800 exercises")
    counts = {language: sum(row.get("language") == language for row in rows) for language in EXPECTED_COUNT}
    if counts != EXPECTED_COUNT:
        raise RuntimeError(f"invalid snapshot language counts: {counts}")
    keys = [row.get("source_key") for row in rows]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise RuntimeError("deployment snapshot source_key values must be present and unique")
    not_approved = [row.get("source_key") for row in rows if row.get("quality_status") != "approved"]
    if not_approved:
        raise RuntimeError(
            "deployment snapshot contains non-approved exercises; refusing to re-enable archived data: "
            + ", ".join(str(key) for key in not_approved[:5])
        )
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
                if row.quality_status == "rejected" and data.get("quality_status") != "approved":
                    raise RuntimeError(f"refusing to re-enable rejected exercise: {row.source_key}")
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
        active = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.quality_status == "approved",
        ).count()
        result = {"inserted": inserted, "updated": updated, "deactivated": deactivated, "active": active}
        print(json.dumps(result, ensure_ascii=False))
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
