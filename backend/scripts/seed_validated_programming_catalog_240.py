"""Idempotently merge the validated 240-row deployment snapshot."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

SNAPSHOT = ROOT / "backend/data/programming_catalog_240.json.gz"
LANGUAGES = ("C", "C++", "Python", "Java")
EXPECTED = {language: 60 for language in LANGUAGES}
IMMUTABLE = {"id", "created_at", "updated_at"}


def load() -> list[dict]:
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("exercises")
    if payload.get("catalog") != "programming-240" or payload.get("validated") is not True or not isinstance(rows, list) or len(rows) != 240:
        raise RuntimeError("refusing non-validated 240 snapshot")
    counts = {language: sum(row.get("language") == language for row in rows) for language in LANGUAGES}
    if counts != EXPECTED or len({row.get("source_key") for row in rows}) != 240:
        raise RuntimeError(f"invalid snapshot counts or keys: {counts}")
    if any(row.get("quality_status") != "approved" or row.get("is_active") is not True for row in rows):
        raise RuntimeError("snapshot contains inactive or non-approved row")
    return rows


def seed(dry_run: bool = False) -> dict:
    ensure_database_schema(engine)
    rows = load()
    if dry_run:
        result = {"dry_run": True, "validated": True, "snapshot_rows": 240, "counts": EXPECTED, "written": 0}
        print(json.dumps(result, ensure_ascii=False)); return result
    db = SessionLocal()
    try:
        keys = {row["source_key"] for row in rows}
        existing = {row.source_key: row for row in db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key.in_(keys)).all()}
        inserted = updated = 0
        for data in rows:
            row = existing.get(data["source_key"])
            if row is not None and row.quality_status == "rejected":
                raise RuntimeError(f"refusing to re-enable rejected row {row.source_key}")
            if row is None:
                row = ProgrammingExercise(); db.add(row); inserted += 1
            changed = False
            for field, value in data.items():
                if field in IMMUTABLE: continue
                if getattr(row, field) != value: setattr(row, field, value); changed = True
            if row not in db.new and changed: updated += 1
        deactivated = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.source_repo == "first_party_original",
            ~ProgrammingExercise.source_key.in_(keys),
        ).update({"is_active": False}, synchronize_session=False)
        db.commit()
        active = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.is_active.is_(True),
            ProgrammingExercise.quality_status == "approved",
        ).all()
        counts = {language: sum(row.language == language for row in active) for language in LANGUAGES}
        if counts != EXPECTED or len(active) != 240: raise RuntimeError(f"post-seed counts invalid: {counts}")
        result = {"dry_run": False, "inserted": inserted, "updated": updated, "deactivated": deactivated, "written": inserted + updated + deactivated, "active_approved_total": len(active), "counts": counts}
        print(json.dumps(result, ensure_ascii=False)); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--dry-run", action="store_true")
    seed(parser.parse_args().dry_run)
