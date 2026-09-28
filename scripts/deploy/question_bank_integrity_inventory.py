"""Read-only integrity inventory for the CS408 question bank — SECURITY_S1B follow-up.

SECURITY_S1B closed the endpoint that let any authenticated learner write
``visibility=public, source_type=chapter`` rows into the shared bank. The remaining question is
historical: were any such rows actually written before the fix?

This answers it with counts only. Its guarantees:

* **Read-only at the connection level.** The database is opened with SQLite ``mode=ro``, so the
  process cannot write a row even if a query were wrong.
* **No input of any kind.** No argv, no environment-driven SQL, no filters. Every query below is
  a fixed literal.
* **No content and no identity.** It prints counts and category labels. It never prints
  ``owner_username``, a stem, an answer or an analysis — an owner's name is exactly the thing a
  report should not carry.

Ownership is the authoritative signal, not role: the offline importers that build the bank
(``chapter_question_upsert`` / ``past_paper_upsert``) never set ``owner_username``, so **any**
row carrying an owner came from the HTTP authoring path rather than the official pipeline.
Role-based classification of owners is deliberately not attempted — see
``OWNER_ROLE_CLASSIFICATION`` below.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/question_bank_integrity_inventory.py

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
sys.path.insert(0, str(REPO_ROOT / "backend"))

VALID_VISIBILITIES = ("public", "private")
VALID_SOURCE_TYPES = ("chapter", "past_paper")

TABLE = "exam_question_bank"


def _database_path(url: str) -> str:
    """The on-disk path for a sqlite URL.

    ``sqlite:////var/lib/app.db`` -> ``/var/lib/app.db`` (Linux deployment form)
    ``sqlite:///C:/app.db``       -> ``C:/app.db``      (Windows absolute form)
    """
    if not url.startswith("sqlite:"):
        raise SystemExit("[integrity] only sqlite database URLs are supported")
    path = url.split("sqlite://", 1)[1] if "sqlite://" in url else url[len("sqlite:"):]
    while path.startswith("//"):
        path = path[1:]
    # Windows drive-letter absolute: the URL adds a leading slash the OS does not want.
    if len(path) > 2 and path[0] == "/" and path[1].isalpha() and path[2] == ":":
        path = path[1:]
    if not path or path == ":memory:":
        raise SystemExit("[integrity] refusing to inspect an in-memory or empty database path")
    return path


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[integrity] DATABASE_URL is required (never assume the default database)")
        return 2

    path = _database_path(url)
    if not Path(path).exists():
        print(f"[integrity] database not found: {path}")
        return 2

    # mode=ro is the guarantee: this connection cannot write, whatever the queries say.
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cur = con.cursor()

        def count(where: str) -> int:
            return cur.execute(f"select count(*) from {TABLE} where {where}").fetchone()[0]

        owned = "trim(coalesce(owner_username, '')) <> ''"
        total = cur.execute(f"select count(*) from {TABLE}").fetchone()[0]
        public = count("visibility = 'public'")
        private = count("visibility = 'private'")
        other_visibility = count("visibility is not null and visibility not in ('public', 'private')")
        invalid_visibility = count("visibility is null or visibility not in ('public', 'private')")
        invalid_source = count("source_type is null or source_type not in ('chapter', 'past_paper')")
        ownerless = count("owner_username is null or trim(owner_username) = ''")

        owned_public = count(f"visibility = 'public' and {owned}")
        owned_private = count(f"visibility = 'private' and {owned}")
        owned_chapter = count(f"source_type = 'chapter' and {owned}")
        owned_past_paper = count(f"source_type = 'past_paper' and {owned}")

        # Category labels only — a source_type or visibility value is not content.
        source_distribution = cur.execute(
            f"select source_type, count(*) from {TABLE} group by source_type order by 2 desc").fetchall()
        visibility_distribution = cur.execute(
            f"select visibility, count(*) from {TABLE} group by visibility order by 2 desc").fetchall()
    finally:
        con.close()

    line = "[integrity]"
    print(f"{line} === totals ===")
    print(f"{line} TOTAL_QUESTIONS             = {total}")
    print(f"{line} PUBLIC_ROWS                 = {public}")
    print(f"{line} PRIVATE_ROWS                = {private}")
    print(f"{line} OTHER_VISIBILITY_ROWS       = {other_visibility}")
    print(f"{line} OWNERLESS_ROWS              = {ownerless}")
    print(f"{line} === rows carrying an owner (written outside the official importers) ===")
    print(f"{line} OWNED_PUBLIC_ROWS           = {owned_public}")
    print(f"{line} OWNED_PRIVATE_ROWS          = {owned_private}")
    print(f"{line} OWNED_CHAPTER_ROWS          = {owned_chapter}")
    print(f"{line} OWNED_PAST_PAPER_ROWS       = {owned_past_paper}")
    print(f"{line} === out-of-domain values ===")
    print(f"{line} INVALID_VISIBILITY_ROWS     = {invalid_visibility}"
          f"   (OTHER_VISIBILITY_ROWS plus any NULL visibility)")
    print(f"{line} INVALID_SOURCE_TYPE_ROWS    = {invalid_source}")
    print(f"{line} source_type distribution    = "
          + ", ".join(f"{value!r}:{n}" for value, n in source_distribution))
    print(f"{line} visibility distribution     = "
          + ", ".join(f"{value!r}:{n}" for value, n in visibility_distribution))
    print(f"{line} === ownership role classification ===")
    print(f"{line} OWNER_ROLE_CLASSIFICATION   = NOT_AVAILABLE")
    print(f"{line}   (an account can be both an administrator and a learner, and a row's owner may no")
    print(f"{line}    longer exist, so a role-based split would be a guess. OWNED_* is the honest")
    print(f"{line}    signal: the importers never set an owner, so any owned row is a deviation.)")

    review = owned_public > 0 or owned_chapter > 0 or invalid_visibility > 0 or invalid_source > 0
    print(f"{line} CONTENT_INTEGRITY_REVIEW_REQUIRED = {'YES' if review else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
