"""Export a temporary local-only map used to type audited reference files in the UI."""
from __future__ import annotations

import json
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "verification-results/programming-workbench-random-40-sample.json"
SNAPSHOT = ROOT / "backend/data/programming_catalog_240.json.gz"
OUTPUT = ROOT / "verification-results/.workbench-reference-map.json"


def parse(value: str | None):
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    if "--all" in sys.argv[1:]:
        source_keys = [str(row["source_key"]) for row in snapshot.get("exercises", [])]
    else:
        source_keys = [str(item["source_key"]) for item in sample["exercises"]]
    rows = [row for row in snapshot.get("exercises", []) if row.get("source_key") in source_keys]
    by_id = {
        str(row["source_key"]): {
            "exercise_id": row.get("id"),
            "language": row.get("language"),
            "title": row.get("title") or row.get("title_zh"),
            "starter_files": parse(row.get("starter_files_json")),
            "reference_files": parse(row.get("reference_files_json")),
            "public_tests": parse(row.get("public_tests_json")),
        }
        for row in rows
    }
    missing = sorted(set(source_keys) - set(by_id))
    if missing:
        raise RuntimeError(f"missing local reference rows: {missing}")
    OUTPUT.write_text(json.dumps(by_id, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"rows": len(by_id), "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
