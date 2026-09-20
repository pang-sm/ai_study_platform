"""ACCEL_PRODUCT_S10 PART I — a manual-curation worklist for the unresolved 计算机网络 rows.

WHAT THIS IS
------------
A preparation artefact for a HUMAN. S9 measured 300 `computer_network` questions whose stored
concept id is not a canonical leaf of their module — 45 with an empty id, 255 whose column
holds a value that equals no leaf code. Every one of them is a question whose concept identity
can only be settled by reading it.

WHAT THIS IS NOT
----------------
Not a model, and not a mapping. It does NOT select a leaf for any row. The one field a curator
fills in — ``selected_leaf`` — is emitted as ``null`` for every row and asserted to be ``null``
before the file is written, so the artefact cannot be mistaken for a decision that was made.

The distinction matters because the tempting shortcut is real: a row whose stored id is
``4.2`` "obviously" belongs to leaf ``4.2``. But S8 measured exactly that case and found the
column collides numerically with a different chapter's code, which is why the write boundary
refuses it. Automated selection here would reproduce the fabrication S9 closed.

WHAT A CURATOR GETS PER ROW
---------------------------
  question_id            the row to re-key
  source_ref             the section the question came from, as ingested
  current_chapter        the canonical chapter the row is currently attributed to (may be none)
  current_level          how deep the stored id honestly reaches today
  reason                 why it is unresolved, as a stable code
  near_match_leaf_code   a candidate the resolver refused to accept, when one exists
  stem_excerpt           the first characters of the question, so it can be judged without a
                         second lookup — an excerpt, never the full item, and never the answer
  candidate_leaves       the canonical leaves OF THE ROW'S OWN CHAPTER, with titles. A row
                         whose chapter is unknown gets an empty set rather than the whole
                         module's leaves, because offering 32 candidates is not a shortlist.
  selected_leaf          null. Always.

Output is JSON (the full structure) and CSV (one row per question, for a spreadsheet).
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MODULE = "computer_network"
STEM_EXCERPT_CHARS = 80


def _stem_excerpt(stem: str | None) -> str:
    text = " ".join(str(stem or "").split())
    if len(text) <= STEM_EXCERPT_CHARS:
        return text
    return text[:STEM_EXCERPT_CHARS].rstrip() + "…"


def _candidates_for_chapter(chapter: str | None, concepts: dict) -> list[dict]:
    """The canonical leaves of ONE chapter, code + title, in code order.

    Limited to the row's own chapter on purpose: the shortlist has to be short enough to be a
    decision. A row whose chapter could not be established gets an empty list, because
    enumerating the whole module would be a search space, not a worklist.
    """
    if not chapter:
        return []
    chapter_of_leaf = concepts.get("chapter_of_leaf") or {}
    titles_by_leaf = {}
    for title, code in (concepts.get("titles") or {}).items():
        titles_by_leaf.setdefault(code, title)
    return [
        {"leaf_code": leaf, "leaf_title": titles_by_leaf.get(leaf, "")}
        for leaf, owner in sorted(chapter_of_leaf.items())
        if owner == chapter
    ]


def build_worklist(db_path: Path) -> dict:
    import database
    from science import concept_coverage
    import models

    session = database.SessionLocal()
    try:
        report = concept_coverage.unresolved_identity_report(session, MODULE)
        concepts = concept_coverage.load_module_concepts(MODULE)

        rows = []
        for record in report.get("records") or []:
            question = session.query(models.ExamQuestionBank).filter(
                models.ExamQuestionBank.id == record["question_id"]).first()
            chapter = record.get("current_chapter")
            rows.append({
                "question_id": record["question_id"],
                "source_ref": record.get("source_ref"),
                "stored_source_identity": record.get("stored_source_identity"),
                "current_canonical_chapter": chapter,
                "current_level": record.get("current_level"),
                "reason": record.get("reason"),
                "near_match_leaf_code": record.get("near_match_leaf_code"),
                "stem_excerpt": _stem_excerpt(getattr(question, "stem", None)),
                "candidate_leaves": _candidates_for_chapter(chapter, concepts),
                "selected_leaf": None,
            })
        return {"module_key": MODULE, "report": {k: v for k, v in report.items()
                                                if k != "records"}, "rows": rows}
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to the database to READ")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # `--db` is the explicit subject of this run, so it WINS. An inherited DATABASE_URL that
    # pointed somewhere else would otherwise be honoured silently and the worklist would
    # describe a different content set than the one asked for.
    import os
    target_url = f"sqlite:///{db_path.as_posix()}"
    inherited = os.environ.get("DATABASE_URL")
    if inherited and inherited != target_url:
        print(f"REFUSED: DATABASE_URL is already set to {inherited!r}, which is not the "
              f"--db this run was asked for ({target_url!r})", file=sys.stderr)
        return 1
    os.environ["DATABASE_URL"] = target_url

    worklist = build_worklist(db_path)
    rows = worklist["rows"]

    # The artefact must not contain a decision. Checked AFTER building, so a future rule that
    # started filling `selected_leaf` in would fail here rather than shipping a mapping.
    auto_selected = [r["question_id"] for r in rows if r["selected_leaf"] is not None]
    if auto_selected:
        print(f"REFUSED: {len(auto_selected)} rows carry a selected_leaf; this artefact is "
              f"preparation for human curation and must not select one", file=sys.stderr)
        return 1

    json_path = out_dir / "cn_unresolved_curation_worklist.json"
    json_path.write_text(json.dumps(worklist, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = out_dir / "cn_unresolved_curation_worklist.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["question_id", "current_canonical_chapter", "current_level", "reason",
                         "source_ref", "stored_source_identity", "near_match_leaf_code",
                         "candidate_count", "candidate_leaf_codes", "stem_excerpt",
                         "selected_leaf"])
        for row in rows:
            writer.writerow([
                row["question_id"], row["current_canonical_chapter"] or "",
                row["current_level"] or "", row["reason"] or "", row["source_ref"] or "",
                row["stored_source_identity"] or "", row["near_match_leaf_code"] or "",
                len(row["candidate_leaves"]),
                "|".join(c["leaf_code"] for c in row["candidate_leaves"]),
                row["stem_excerpt"], "",
            ])

    by_reason = worklist["report"].get("by_reason") or {}
    with_candidates = sum(1 for r in rows if r["candidate_leaves"])
    print(f"unresolved rows: {len(rows)}")
    print(f"by reason: {by_reason}")
    print(f"rows with a candidate shortlist (chapter established): {with_candidates}")
    print(f"rows with NO chapter (empty shortlist): {len(rows) - with_candidates}")
    print(f"auto-selected leaves: 0 (enforced)")
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
