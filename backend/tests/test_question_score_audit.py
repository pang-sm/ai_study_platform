"""Every served past-paper question's score is audited, and the papers still add up.

The score audit exists because the product graded every 综合应用题 out of a hard-coded 10 —
which no paper uses for all of them (2022 组成原理 Q43 is worth 15; the 操作系统 pair is worth
7 and 8). A learner's denominator was therefore not the paper's.

What these tests hold:

  * the audit covers EXACTLY the questions the runtime serves, so a newly added question fails
    here rather than being graded out of a guessed number;
  * the canonical table (``exam_paper_scores``) covers every big question — reaching its legacy
    fallback at all is a bug;
  * each year's four subjects still add up to the paper's own 150, and its big section to 70.
"""
from __future__ import annotations

import json
from pathlib import Path

import exam_paper_scores

RESOURCES = Path(__file__).resolve().parents[1] / "exam_resources" / "11408"
CACHE_11408 = Path(__file__).resolve().parents[1] / "cache" / "exam_papers" / "11408"

AUDIT = json.loads((RESOURCES / "question_score_audit.json").read_text(encoding="utf-8"))
ENTRIES = {e["question_id"]: e for e in AUDIT["entries"]}

SUBJECTS = ("data_structure", "computer_organization", "operating_system", "computer_network")
# Which objective questions each subject owns in the 408 paper: 11 + 11 + 10 + 8 = the paper's 40.
CHOICE_COUNT = {"data_structure": 11, "computer_organization": 11,
                "operating_system": 10, "computer_network": 8}


def _served_question_ids() -> set[str]:
    """The public identity of every past-paper question the runtime can serve today."""
    ids: set[str] = set()
    for year in range(2022, 2027):
        cache = CACHE_11408 / "data_structure" / f"{year}.ocr.json"
        if cache.exists():
            for question in json.loads(cache.read_text(encoding="utf-8"))["questions"]:
                ids.add(f"data_structure/{year}/Q{int(question['number'])}")
    co = RESOURCES / "computer_organization" / "past_papers" / "checked" / "parsed_ready_text_all.json"
    for question in json.loads(co.read_text(encoding="utf-8")):
        ids.add(f"computer_organization/{int(question['year'])}/Q{int(question['question_number'])}")
    for subject in ("operating_system", "computer_network"):
        checked = RESOURCES / subject / "past_papers" / "checked" / "parsed_ready_past_papers.json"
        for question in json.loads(checked.read_text(encoding="utf-8")):
            ids.add(f"{subject}/{int(question['year'])}/Q{int(question['question_number'])}")
    return ids


SERVED = _served_question_ids()


def test_every_served_question_has_a_score_audit_entry():
    assert len(SERVED) == 235
    assert sorted(SERVED - set(ENTRIES)) == [], "served but never score-audited"


def test_the_audit_covers_nothing_that_is_no_longer_served():
    assert sorted(set(ENTRIES) - SERVED) == []


def test_nothing_is_left_to_fix():
    """FIXED records a question that WAS wrong; nothing may still be awaiting a fix."""
    outstanding = sorted(key for key, entry in ENTRIES.items()
                         if entry["status"] not in {"PASS", "FIXED"})
    assert outstanding == [], f"score still wrong for: {outstanding}"

    counts = AUDIT["counts"]
    assert counts["fix_required"] == 0, "a question is still waiting to be corrected"
    assert counts["blocked"] == 0
    assert counts["total"] == len(ENTRIES) == 235
    assert counts["fixed"] == 28, "exactly the 28 big questions the papers price above/below 10"
    assert counts["pass"] == 207

    # Every FIXED entry carries the before AND the after, so the defect is auditable.
    for key, entry in ENTRIES.items():
        if entry["status"] == "FIXED":
            assert entry["current_full_score"] != entry["source_full_score"], key
            assert entry["question_type"] == "big", key


def test_the_canonical_table_covers_every_big_question_it_must():
    """Reaching ``LEGACY_BIG_FULL_SCORE`` is a bug, so the table has to be complete."""
    big = {key for key, entry in ENTRIES.items() if entry["question_type"] == "big"}
    assert len(big) == 35
    missing = []
    for key in big:
        subject, year, number = key.split("/")
        if exam_paper_scores.big_full_score(subject, int(year), int(number[1:])) is None:
            missing.append(key)
    assert missing == [], f"a big question would fall back to 10: {missing}"

    assert set(exam_paper_scores.known_big_questions()) == {
        (s, int(y), int(n[1:])) for s, y, n in (k.split("/") for k in big)}


def test_every_objective_question_is_worth_the_paper_s_objective_score():
    choice = {key: entry for key, entry in ENTRIES.items() if entry["question_type"] == "choice"}
    assert len(choice) == 200
    assert {entry["source_full_score"] for entry in choice.values()} == {
        exam_paper_scores.choice_full_score()}
    assert exam_paper_scores.choice_full_score() == 2


def test_each_year_is_the_paper_it_claims_to_be():
    """150 = 40 objective × 2 + 70 of 综合应用题, and each subject's share is a real slice."""
    for year in range(2022, 2027):
        total = 0
        big = 0
        for subject in SUBJECTS:
            total += CHOICE_COUNT[subject] * exam_paper_scores.choice_full_score()
            for key, entry in ENTRIES.items():
                if entry["subject"] == subject and entry["paper_year"] == year \
                        and entry["question_type"] == "big":
                    total += entry["source_full_score"]
                    big += entry["source_full_score"]
        assert (total, big) == (150, 70), f"{year}: total={total} big={big}"

    assert AUDIT["total_score_consistency"] == "PASS"
    assert all(entry["consistency"] == "PASS" for entry in AUDIT["per_year"].values())


def test_the_score_values_read_off_the_papers_are_the_ones_served():
    """The regressions this phase exists for, named one by one."""
    assert exam_paper_scores.big_full_score("computer_organization", 2022, 43) == 15
    assert exam_paper_scores.big_full_score("computer_organization", 2026, 44) == 15
    assert exam_paper_scores.big_full_score("computer_organization", 2025, 44) == 11
    assert exam_paper_scores.big_full_score("computer_network", 2024, 47) == 9
    assert exam_paper_scores.big_full_score("computer_network", 2026, 47) == 8
    assert exam_paper_scores.big_full_score("data_structure", 2023, 41) == 13
    assert exam_paper_scores.big_full_score("operating_system", 2025, 45) == 7
    assert exam_paper_scores.big_full_score("operating_system", 2025, 46) == 8

    # A question the table does not know keeps the shape of every other resolved question
    # (never None, never an exception) — the audit above is what stops that from shipping.
    assert exam_paper_scores.full_score("computer_organization", 2022, 603, "big") == 10
    assert exam_paper_scores.full_score("computer_organization", 2022, 603, "choice") == 2
