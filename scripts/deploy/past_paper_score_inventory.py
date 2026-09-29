"""Read-only inventory of persisted past-paper SCORE facts — SCORE_S1 follow-up.

WHY THIS EXISTS. Every past-paper attempt was graded with a per-question ``full_score`` the
product had hard-coded (2 for a choice question, 10 for a 综合应用题) rather than read from the
paper. The papers do not use 10 for every big question, so any submitted attempt may hold a
``max_score`` whose denominator never matched the paper. Before changing the canonical scores,
this counts how many attempts that actually affects — and whether their raw answers are still
present, so a correction could be recomputed rather than invented.

Its guarantees (the same ones ``question_bank_integrity_inventory.py`` makes):

* **Read-only at the connection level.** The database is opened with SQLite ``mode=ro``, so the
  process cannot write a row even if a query were wrong.
* **No input of any kind.** No argv, no environment-driven SQL, no filters. Every query below is
  a fixed literal.
* **No content and no identity.** It prints counts and category labels — never a username, a
  stem, an answer or an analysis.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/past_paper_score_inventory.py

Exit codes:
    0  the inventory ran (the verdict is in the output, not the exit code)
    2  the inventory could not run (no DATABASE_URL, unreadable database)
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _database_path(url: str) -> str:
    """The on-disk path for a sqlite URL (deployment and Windows absolute forms)."""
    if not url.startswith("sqlite:"):
        raise SystemExit("[score-inventory] only sqlite database URLs are supported")
    path = url.split("sqlite://", 1)[1] if "sqlite://" in url else url[len("sqlite:"):]
    while path.startswith("//"):
        path = path[1:]
    if len(path) > 2 and path[0] == "/" and path[1].isalpha() and path[2] == ":":
        path = path[1:]
    if not path or path == ":memory:":
        raise SystemExit("[score-inventory] refusing an in-memory or empty database path")
    return os.path.expanduser(path)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("[score-inventory] DATABASE_URL is required")
        return 2
    path = _database_path(url)
    if not Path(path).exists():
        print("[score-inventory] database not found")
        return 2

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        print(f"[score-inventory] read-only inventory of past_paper_attempts  (sqlite mode=ro)")

        if not _table_exists(conn, "past_paper_attempts"):
            print("PAST_PAPER_ATTEMPTS_TABLE = ABSENT")
            return 0

        # ── how much persisted grading is there at all ────────────────────────────────
        print("ATTEMPTS_BY_STATUS = " + repr(dict(conn.execute(
            "SELECT status, COUNT(*) FROM past_paper_attempts GROUP BY status").fetchall())))
        print("SUBMITTED_TOTAL = " + repr(conn.execute(
            "SELECT COUNT(*) FROM past_paper_attempts WHERE status='submitted'").fetchone()[0]))
        print("SUBMITTED_DISTINCT_LEARNERS = " + repr(conn.execute(
            "SELECT COUNT(DISTINCT username) FROM past_paper_attempts WHERE status='submitted'"
        ).fetchone()[0]))
        print("SUBMITTED_WITH_MAX_SCORE = " + repr(conn.execute(
            "SELECT COUNT(*) FROM past_paper_attempts "
            "WHERE status='submitted' AND max_score IS NOT NULL").fetchone()[0]))

        # ── which papers are affected, without naming anyone ──────────────────────────
        # A submitted attempt holds a graded denominator only for the papers the product has
        # been used on; this pairs each such (subject, year) with how many attempts it holds,
        # so the caller can intersect it with the papers that have a non-10 big question.
        print("SUBMITTED_BY_PAPER = " + repr(sorted(conn.execute(
            "SELECT subject_key, year, COUNT(*), COUNT(DISTINCT username) "
            "FROM past_paper_attempts WHERE status='submitted' "
            "GROUP BY subject_key, year").fetchall())))

        # The distinct denominators actually persisted, with how often each occurs. A value the
        # canonical table can no longer produce is a row computed under the old rule.
        print("MAX_SCORE_DISTRIBUTION = " + repr(sorted(conn.execute(
            "SELECT max_score, COUNT(*) FROM past_paper_attempts "
            "WHERE status='submitted' AND max_score IS NOT NULL "
            "GROUP BY max_score").fetchall())))

        # ── can the facts be recomputed, or only replaced ─────────────────────────────
        # A recomputation needs the RAW ANSWERS, which live in the attempt's result_json. This
        # counts how many submitted attempts still carry it (A: recomputable) versus how many
        # hold only a final score (B: keep as history).
        print("SUBMITTED_WITH_RESULT_JSON = " + repr(conn.execute(
            "SELECT COUNT(*) FROM past_paper_attempts "
            "WHERE status='submitted' AND result_json IS NOT NULL AND result_json != ''"
        ).fetchone()[0]))
        print("SUBMITTED_ANSWER_ROWS = " + repr(conn.execute(
            "SELECT COUNT(*) FROM past_paper_attempt_answers").fetchone()[0])
            if _table_exists(conn, "past_paper_attempt_answers") else "SUBMITTED_ANSWER_ROWS = TABLE_ABSENT")

        # ── the canonical mirror, if the practice core holds score facts too ──────────
        if _table_exists(conn, "practice_attempts"):
            print("PRACTICE_ATTEMPTS_WITH_MAX_SCORE = " + repr(conn.execute(
                "SELECT COUNT(*) FROM practice_attempts WHERE max_score IS NOT NULL").fetchone()[0]))
            print("PRACTICE_MAX_SCORE_DISTRIBUTION = " + repr(sorted(conn.execute(
                "SELECT max_score, COUNT(*) FROM practice_attempts "
                "WHERE max_score IS NOT NULL GROUP BY max_score").fetchall())))
        else:
            print("PRACTICE_ATTEMPTS_WITH_MAX_SCORE = TABLE_ABSENT")

        print("[score-inventory] done (nothing was written)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
