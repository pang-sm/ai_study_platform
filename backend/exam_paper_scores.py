"""How many points each 11408 past-paper question is worth — the ONE place that answers it.

WHY THIS MODULE EXISTS. The score used to be hard-coded at each site that needed one: the two
projections into ``ResolvedQuestion``, the two grading paths, and the AI grader's rubric each
said "2 for a choice question, 10 for a 综合应用题". No paper uses 10 for every big question —
2022 组成原理 Q43 is worth 15, and the 操作系统 pair is worth 7 and 8 — so the denominator a
learner was graded against was simply not the paper's.

The authority is ``exam_resources/11408/question_scores.json``, whose every value was read from
that question's own 原卷截图 (and cross-checked against the official syllabus, which fixes the
objective section at 40 × 2 = 80 and the paper at 150). ``question_score_audit.json`` records
that reading per question, and a test fails if any served question is missing here.

Deliberately dependency-free: ``exam_paper_parser``, ``exam_past_paper``, ``main`` and the Exam AI
boundary all need this, and none of them should have to import the others to get it.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SCORES_PATH = Path(__file__).resolve().parent / "exam_resources" / "11408" / "question_scores.json"

# The pre-audit values, kept ONLY as a last-resort fallback so an unknown question can never turn
# a learner's request into a 500. They are not a source of truth: the audit test asserts this
# module's table covers every question the product serves, so reaching them is a bug, not a case.
LEGACY_CHOICE_FULL_SCORE = 2
LEGACY_BIG_FULL_SCORE = 10


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(SCORES_PATH.read_text(encoding="utf-8"))


def choice_full_score() -> int:
    """Every objective question is worth this — 40 of them make the paper's 80."""
    return int(_table().get("choice_full_score", LEGACY_CHOICE_FULL_SCORE))


def big_full_score(subject_key: str, year: int, question_number: int) -> int | None:
    """The printed score of one 综合应用题, or None when this table has never heard of it."""
    entry = (_table().get("big", {}).get(str(subject_key), {})
             .get(str(int(year)), {}).get(str(int(question_number))))
    if isinstance(entry, dict) and isinstance(entry.get("score"), int):
        return int(entry["score"])
    return None


def full_score(subject_key: str, year: int, question_number: int, question_type: str) -> int:
    """The score of one past-paper question, whichever kind it is.

    ``question_type`` is the resolved kind ("big" / "choice"), not the raw paper label.
    """
    if str(question_type or "").strip() != "big":
        return choice_full_score()
    found = big_full_score(subject_key, year, question_number)
    return LEGACY_BIG_FULL_SCORE if found is None else found


def known_big_questions() -> dict[tuple[str, int, int], int]:
    """Every (subject, year, question_number) this table carries — what the audit covers."""
    out: dict[tuple[str, int, int], int] = {}
    for subject, years in (_table().get("big") or {}).items():
        for year, numbers in years.items():
            for number, entry in numbers.items():
                out[(subject, int(year), int(number))] = int(entry["score"])
    return out
