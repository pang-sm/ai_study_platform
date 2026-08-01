"""Idempotently merge the validated 480-exercise deployment snapshot."""

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


SNAPSHOT = ROOT / "backend" / "data" / "programming_catalog_480.json.gz"
LANGUAGES = ("C", "C++", "Python", "Java")
EXPECTED_COUNT = {language: 120 for language in LANGUAGES}
IMMUTABLE_FIELDS = {"id", "created_at", "updated_at"}


def load_snapshot() -> list[dict]:
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("exercises")
    if payload.get("validated") is not True:
        raise RuntimeError("deployment snapshot is not marked validated=true; refusing seed")
    if payload.get("catalog") != "programming-480":
        raise RuntimeError("deployment snapshot catalog marker is not programming-480")
    if not isinstance(rows, list) or len(rows) != 480:
        raise RuntimeError("deployment snapshot must contain exactly 480 exercises")
    counts = {language: sum(row.get("language") == language for row in rows) for language in LANGUAGES}
    if counts != EXPECTED_COUNT:
        raise RuntimeError(f"invalid snapshot language counts: {counts}")
    keys = [row.get("source_key") for row in rows]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise RuntimeError("deployment snapshot source_key values must be present and unique")
    invalid = [
        row.get("source_key")
        for row in rows
        if row.get("quality_status") != "approved" or row.get("is_active") is not True
    ]
    if invalid:
        raise RuntimeError(
            "deployment snapshot contains inactive or non-approved exercises: "
            + ", ".join(str(key) for key in invalid[:5])
        )
    return rows


def seed(*, dry_run: bool = False) -> dict:
    ensure_database_schema(engine)
    rows = load_snapshot()
    if dry_run:
        result = {
            "dry_run": True,
            "validated": True,
            "snapshot_rows": len(rows),
            "counts": EXPECTED_COUNT,
            "written": 0,
        }
        print(json.dumps(result, ensure_ascii=False))
        return result

    db = SessionLocal()
    try:
        keys = {row["source_key"] for row in rows}
        existing = {
            row.source_key: row
            for row in db.query(ProgrammingExercise)
            .filter(ProgrammingExercise.source_key.in_(keys))
            .all()
        }
        inserted = 0
        updated = 0
        for data in rows:
            source_key = data["source_key"]
            row = existing.get(source_key)
            if row is not None and row.quality_status == "rejected":
                raise RuntimeError(
                    f"refusing to re-enable rejected exercise with source_key={source_key}"
                )
            if row is None:
                row = ProgrammingExercise()
                db.add(row)
                inserted += 1
            changed = False
            for field, value in data.items():
                if field in IMMUTABLE_FIELDS:
                    continue
                if getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
            if row in db.new:
                continue
            if changed:
                updated += 1

        deactivated = (
            db.query(ProgrammingExercise)
            .filter(ProgrammingExercise.is_active.is_(True))
            .filter(~ProgrammingExercise.source_key.in_(keys))
            .update({"is_active": False}, synchronize_session=False)
        )
        db.commit()
        active_rows = (
            db.query(ProgrammingExercise)
            .filter(
                ProgrammingExercise.is_active.is_(True),
                ProgrammingExercise.quality_status == "approved",
            )
            .all()
        )
        counts = {language: sum(row.language == language for row in active_rows) for language in LANGUAGES}
        if counts != EXPECTED_COUNT or len(active_rows) != 480:
            raise RuntimeError(f"post-seed approved active counts are invalid: {counts}")
        result = {
            "dry_run": False,
            "inserted": inserted,
            "updated": updated,
            "deactivated": deactivated,
            "written": inserted + updated + deactivated,
            "active_approved_total": len(active_rows),
            "counts": counts,
        }
        print(json.dumps(result, ensure_ascii=False))
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
