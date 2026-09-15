"""Backfill historical course_practice attempts into LearningEvents.

Dry-run by default.  Pass --apply to write.  Idempotent (INSERT OR IGNORE on event_id).

Usage:
    python scripts/backfill_learning_events.py [--apply] [--limit N] [--before ISO_DATETIME]
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import models  # noqa: E402
import database  # noqa: E402
from data_plane import backfill as dp_backfill  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write (default dry-run)")
    ap.add_argument("--limit", type=int, default=0, help="max attempts to scan (0 = all)")
    ap.add_argument("--before", default="", help="only attempts with submitted_at < this ISO datetime")
    args = ap.parse_args()

    session = database.SessionLocal()
    try:
        q = session.query(models.AIQuestionAttempt).filter(
            models.AIQuestionAttempt.mode == "course_learning",
            models.AIQuestionAttempt.status == "submitted",
        ).order_by(models.AIQuestionAttempt.submitted_at)
        if args.before:
            try:
                cutoff = datetime.fromisoformat(args.before)
                q = q.filter(models.AIQuestionAttempt.submitted_at < cutoff)
            except ValueError:
                print(f"invalid --before datetime: {args.before}")
                sys.exit(2)
        if args.limit > 0:
            q = q.limit(args.limit)
        attempts = q.all()

        usernames = {a.username for a in attempts}
        users = session.query(models.User).filter(models.User.username.in_(usernames)).all() if usernames else []
        user_map = {u.username: u.id for u in users}

        report = dp_backfill.backfill(attempts, database.SessionLocal, user_map, apply=args.apply)
    finally:
        session.close()

    print(f"mode={'apply' if args.apply else 'DRY-RUN'}")
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
