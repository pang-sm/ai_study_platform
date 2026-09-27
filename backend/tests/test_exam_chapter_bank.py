"""章节练习 reads the module's own CHAPTER question bank — and nothing else in it.

The 408 question bank holds chapter questions, past-paper questions and retired rows in one
table. 章节练习 must count only what it can actually serve: `source_type="chapter"` rows that
are `is_active`. This file is the guard on that boundary — the numbers a learner reads on the
chapter chooser have to be the questions behind it, so a past-paper row or a retired row
leaking into the counts is a wrong number, not a rounding difference.

The DB is shared with the rest of the session, so every expectation here is derived from the
bank the test itself wrote (compared against the whole table), never from a hard-coded count.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login
import models

MODULE = "operating_system"
OTHER_MODULE = "computer_network"


def _question(subject_key, *, kp, stem, source_type="chapter", active=True, chapter="1",
              year=None, question_number=None):
    """ONE bank row.

    A past-paper row carries the year and question number a real one does: the shared temp DB
    holds every test's rows at once, and a shapeless past paper here would fail the contract
    another suite guards (`test_exam_practice_records`).
    """
    return models.ExamQuestionBank(
        subject_key=subject_key, subject_name=subject_key, source_type=source_type,
        visibility="public", knowledge_point_id=kp, knowledge_point_name=kp,
        year=year, question_number=question_number,
        question_type="choice", stem=stem, options_json='{"A": "1", "B": "2"}',
        standard_answer="A", analysis="解析",
        source_ref=f'{{"chapter_id": "{chapter}"}}', is_active=active,
    )


@pytest.fixture
def bank(db_session):
    """This module's bank, plus one row of every shape that must NOT be served."""
    mark = uuid.uuid4().hex[:8]
    rows = {
        "chapter_a": _question(MODULE, kp="1.1.1", stem=f"进程状态 {mark}"),
        "chapter_b": _question(MODULE, kp="2.1", stem=f"页面置换 {mark}", chapter="2"),
        "past_paper": _question(MODULE, kp="1.1.1", stem=f"真题：进程 {mark}",
                                source_type="past_paper", year=2023, question_number=1),
        "retired": _question(MODULE, kp="1.1.1", stem=f"已退役的题 {mark}", active=False),
        "other_module": _question(OTHER_MODULE, kp="1.1", stem=f"网络体系结构 {mark}"),
    }
    db_session.add_all(rows.values())
    db_session.commit()
    return rows


def _live_chapter_ids(db_session, subject_key=MODULE):
    return {
        row.id for row in db_session.query(models.ExamQuestionBank).filter(
            models.ExamQuestionBank.subject_key == subject_key,
            models.ExamQuestionBank.source_type == "chapter",
            models.ExamQuestionBank.is_active.is_(True),
        )
    }


def test_the_outline_counts_exactly_the_live_chapter_questions(client: TestClient, bank, db_session):
    register_and_login(client, "chapter-bank-counts")

    payload = client.get(f"/exam/11408/{MODULE}/chapter-practice/outline").json()

    # EVERY live chapter row of this module, and nothing else — whatever else the shared DB holds.
    live = _live_chapter_ids(db_session)
    assert sum(c["question_count"] for c in payload["chapters"]) == len(live)
    assert payload["total"] == len(live)
    # The two rows this test wrote are both counted, and filed under their own chapters.
    counts = {c["chapter_code"]: c["question_count"] for c in payload["chapters"]}
    assert counts.get("1", 0) >= 1 and counts.get("2", 0) >= 1


def test_a_past_paper_question_is_never_reachable_from_chapter_practice(client: TestClient, bank, db_session):
    register_and_login(client, "chapter-bank-past-paper")

    past_paper = bank["past_paper"]
    # It is in the bank, active, and filed under chapter 1 — and it is still not chapter practice.
    assert past_paper.is_active is True
    questions = client.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                           params={"chapter_code": "1"}).json()
    served = {item["id"] for item in questions["items"]}
    assert served, "the chapter itself still serves its live questions"
    assert past_paper.id not in served


def test_a_retired_row_is_not_served_either(client: TestClient, bank, db_session):
    register_and_login(client, "chapter-bank-retired")

    retired = bank["retired"]
    assert retired.is_active is False
    questions = client.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                           params={"chapter_code": "1"}).json()
    served = {item["id"] for item in questions["items"]}
    assert retired.id not in served
    assert all(item["stem"] != retired.stem for item in questions["items"])


def test_the_outline_never_leaks_another_module(client: TestClient, bank, db_session):
    register_and_login(client, "chapter-bank-modules")

    questions = client.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                           params={"chapter_code": "1"}).json()
    assert bank["other_module"].id not in {item["id"] for item in questions["items"]}

    other = client.get(f"/exam/11408/{OTHER_MODULE}/chapter-practice/outline").json()
    ours = _live_chapter_ids(db_session, OTHER_MODULE)
    assert sum(c["question_count"] for c in other["chapters"]) == len(ours)
