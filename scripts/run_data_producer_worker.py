"""DataProducerWorker CLI (Phase 2B2).

Manual/--once execution of scientific inference over persisted LearningEvents.
Gated by DATA_PRODUCER_EXECUTION_ENABLED (default false).  No automatic startup.

Usage:
    python scripts/run_data_producer_worker.py --once [--limit N] [--event-id ID]
"""
import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import database  # noqa: E402
from data_plane import worker  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="run a single pass")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--event-id", default="")
    args = ap.parse_args()

    if not args.once:
        print("specify --once (only manual single-pass mode is supported this phase)")
        sys.exit(2)

    report = worker.run_once(database.SessionLocal, limit=args.limit, event_id=args.event_id)
    print("DataProducerWorker run:")
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
