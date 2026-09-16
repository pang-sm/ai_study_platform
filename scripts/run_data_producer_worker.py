"""DataProducerWorker CLI (Phase 2B2 → STEP 7A).

Manual/--once execution, plus a lightweight --loop interval mode (STEP 7A).
Gated by DATA_PRODUCER_EXECUTION_ENABLED AND STUDENT_TWIN_MODE (default OFF).

Usage:
    python scripts/run_data_producer_worker.py --once [--limit N] [--event-id ID]
    python scripts/run_data_producer_worker.py --loop [--interval SECONDS] [--max-iterations N]
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
    ap.add_argument("--loop", action="store_true", help="run on an interval until interrupted")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--event-id", default="")
    ap.add_argument("--interval", type=float, default=30.0, help="loop sleep seconds (default 30)")
    ap.add_argument("--max-iterations", type=int, default=None,
                    help="stop after N passes (default: loop forever)")
    args = ap.parse_args()

    if args.once:
        report = worker.run_once(database.SessionLocal, limit=args.limit, event_id=args.event_id)
    elif args.loop:
        report = worker.run_loop(database.SessionLocal,
                                 interval_seconds=args.interval,
                                 max_iterations=args.max_iterations)
    else:
        print("specify --once or --loop")
        sys.exit(2)

    print("DataProducerWorker run:")
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
