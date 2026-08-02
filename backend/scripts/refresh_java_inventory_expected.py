"""Refresh the three Java inventory rows after fixing subprocess encoding."""
from __future__ import annotations

import json

from repair_programming_catalog_240 import all_samples, parse_json, run_reference, sync_snapshot
from database import SessionLocal
from models import ProgrammingExercise


def main() -> None:
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(
        ProgrammingExercise.source_key.like("first_party_original_v2|Java|inventory-%")
    ).all()
    for row in rows:
        public = all_samples(row.public_tests_json)
        hidden = all_samples(row.hidden_tests_json)
        outputs = run_reference("Java", parse_json(row.reference_files_json, []), public + hidden)
        cursor = len(public)
        groups = parse_json(row.hidden_tests_json, [])
        for group in groups:
            for sample in group.get("samples", []):
                sample["expected_stdout"] = outputs[cursor]
                cursor += 1
        row.hidden_tests_json = json.dumps(groups, ensure_ascii=False, separators=(",", ":"))
    db.commit()
    db.close()
    sync_snapshot()
    print(json.dumps({"updated": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
