"""Every past-paper question the product serves is covered by the content audit.

The audit exists because the served 11408 content is machine-extracted (OCR + regex parsers) from
scanned papers, and it had drifted from the papers in ways nobody could see from the database: a
stem that stopped before its statement list, options that repeated their own letter, a question
standing where another year's question belonged.

These tests hold two things:

  * the audit covers EXACTLY the questions the runtime serves — so adding a question without
    auditing it fails here rather than shipping unverified content;
  * the audit's own totals are internally consistent.

The enumeration reads the same artifacts the runtime does, not the audit file, so it cannot be
satisfied by editing the audit alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

RESOURCES = Path(__file__).resolve().parents[1] / "exam_resources" / "11408"
AUDIT_FILE = RESOURCES / "question_content_audit.json"
CACHE_11408 = Path(__file__).resolve().parents[1] / "cache" / "exam_papers" / "11408"

AUDIT = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
ENTRIES = AUDIT["entries"]
AUDITED = {e["question_id"] for e in ENTRIES}


def _served_question_ids() -> set[str]:
    """The public identity of every past-paper question the runtime can serve today.

    ``data_structure`` has no bank rows: it is projected from the OCR cache. The other three
    subjects are bank-backed, and their checked files are the builder output the bank is loaded
    from — regenerating one is part of changing its source text.
    """
    ids: set[str] = set()

    for year in range(2022, 2027):
        cache = CACHE_11408 / "data_structure" / f"{year}.ocr.json"
        if not cache.exists():
            continue
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


def test_the_past_paper_set_is_the_size_this_audit_measured():
    """235 = 数据结构 65 + 计算机组成原理 65 + 操作系统 60 + 计算机网络 45."""
    assert len(SERVED) == 235, f"served past-paper count moved to {len(SERVED)}"
    assert AUDIT["total_questions"] == len(SERVED)


def test_every_served_question_has_been_audited():
    """A new question must enter the audit before it can be served."""
    unaudited = sorted(SERVED - AUDITED)
    assert unaudited == [], f"served but never audited: {unaudited}"


def test_the_audit_covers_nothing_that_is_no_longer_served():
    stale = sorted(AUDITED - SERVED)
    assert stale == [], f"audited but no longer served: {stale}"


def test_no_question_appears_twice():
    assert len(ENTRIES) == len(AUDITED), "duplicate question_id in the audit"


def test_every_entry_states_a_status_and_its_evidence():
    allowed = {"PASS", "FIXED", "BLOCKED"}
    for entry in ENTRIES:
        assert entry["status"] in allowed, entry
        assert entry["verified"] is True, entry
        assert entry["issues"] == [] if entry["status"] == "PASS" else entry["issues"], entry
        if entry["status"] in {"FIXED", "BLOCKED"}:
            assert entry["note"], f"{entry['question_id']} states no reason"


def test_the_declared_counts_match_the_entries():
    counts = AUDIT["counts"]
    for status, key in (("PASS", "pass"), ("FIXED", "fixed"), ("BLOCKED", "blocked")):
        assert counts[key] == sum(1 for e in ENTRIES if e["status"] == status), status
    assert counts["total"] == len(ENTRIES)

    by_type: dict[str, int] = {}
    for entry in ENTRIES:
        for issue in entry["issues"]:
            by_type[issue] = by_type.get(issue, 0) + 1
    assert AUDIT["issues_by_type"] == dict(sorted(by_type.items()))


@pytest.mark.parametrize("subject", ["data_structure", "computer_organization",
                                     "operating_system", "computer_network"])
def test_each_subject_is_audited_across_all_five_papers(subject):
    years = {e["paper_year"] for e in ENTRIES if e["subject"] == subject}
    assert years == {2022, 2023, 2024, 2025, 2026}, years
