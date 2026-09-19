"""Deterministic offline KT dataset exporter — PART J of ACCEL_SPRINT_S6.

Writes the CS408-native interaction dataset that a FUTURE knowledge-tracing model would be
trained from. It trains nothing, predicts nothing, and imports no model.

    DATABASE_URL=sqlite:///... python scripts/export_kt_dataset.py --out dataset.json

DETERMINISM IS THE CONTRACT
---------------------------
The same database snapshot and the same exporter version produce a BYTE-IDENTICAL file.
That is what makes an export auditable: a second run that differs is evidence that the
data changed, not evidence that the exporter is noisy. Three things make it hold, and each
is a decision rather than a default:

  * ordering is ``(occurred_at, event_id)`` inside a sequence and
    ``(learner_ref, concept_key)`` across sequences — never dict or query order;
  * the JSON is serialized canonically (sorted keys, fixed separators, no ASCII escaping);
  * the body carries NO wall clock. ``generated_at`` is deliberately absent: it would
    change every second and make the hash meaningless. A caller that wants a timestamp
    records it OUTSIDE the artifact.

The split assignment travels INSIDE the file but OUTSIDE the hashed body: it is a pure
function of the body, so including it in the hash would be redundant, and excluding it from
the file would force every consumer to re-implement it.

NO RANDOM SPLIT. The exporter never shuffles. Selecting a split is
``science.kt_dataset.user_grouped_split``, which is deterministic and learner-grouped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

EXPORTER_VERSION = "kt-export-v1"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_export(*, database_url: str, service_namespace: str | None = None,
                 user_id: int | None = None, event_types: tuple[str, ...] | None = None,
                 limit: int = 20000, with_split: bool = False) -> dict:
    from science import kt_dataset

    engine = create_engine(database_url)
    db = sessionmaker(bind=engine)()
    try:
        body = kt_dataset.build(db, service_namespace=service_namespace, user_id=user_id,
                                event_types=event_types, limit=limit)
    finally:
        db.close()

    export = {
        "exporter_version": EXPORTER_VERSION,
        "dataset_contract_version": body["dataset_contract_version"],
        "dataset": body,
        "split": kt_dataset.user_grouped_split(body) if with_split else None,
    }
    export["export_hash"] = _export_hash(export)
    return export


def _export_hash(export: dict) -> str:
    """sha256 over the artifact with the hash field removed. Stable under re-export."""
    import hashlib

    payload = {k: v for k, v in export.items() if k != "export_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="-",
                        help="output path, or - for stdout (default: -)")
    parser.add_argument("--database-url", default=None,
                        help="defaults to $DATABASE_URL")
    parser.add_argument("--service-namespace", default="exam_prep",
                        help="learning space to export; 'all' for every space")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--event-types", default=None,
                        help="comma-separated event types")
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--with-split", action="store_true",
                        help="include the deterministic user-grouped split assignment")
    parser.add_argument("--summary", action="store_true",
                        help="print only counts and hashes, never the rows")
    args = parser.parse_args(argv)

    database_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not database_url:
        print("export_kt_dataset: DATABASE_URL is required", file=sys.stderr)
        return 2

    namespace = None if args.service_namespace in ("", "all") else args.service_namespace
    event_types = tuple(t.strip() for t in args.event_types.split(",") if t.strip()) \
        if args.event_types else None

    export = build_export(database_url=database_url, service_namespace=namespace,
                          user_id=args.user_id, event_types=event_types,
                          limit=args.limit, with_split=args.with_split)

    dataset = export["dataset"]
    if args.summary:
        print(json.dumps({
            "exporter_version": export["exporter_version"],
            "dataset_contract_version": export["dataset_contract_version"],
            "dataset_hash": dataset["dataset_hash"],
            "export_hash": export["export_hash"],
            "sequence_count": dataset["sequence_count"],
            "interaction_count": dataset["interaction_count"],
            "excluded": dataset["excluded"],
            "concept_levels": dataset["concept_levels"],
            "exam_track_ids": dataset["scope"]["exam_track_ids"],
            "split_overlap_is_empty": (export["split"] or {}).get("overlap_is_empty"),
        }, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    text = canonical_json(export) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({len(text.encode('utf-8'))} bytes, "
              f"dataset_hash={dataset['dataset_hash'][:16]})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
