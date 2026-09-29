"""The score a learner is graded against is the one the PAPER prints.

Before SCORE_S1 the denominator was hard-coded (2 per choice question, 10 per 综合应用题), so a
2022 组成原理 Q43 — worth 15 — could never be scored out of 15, and its attempt's ``max_score``
was 5 points short of the paper. These tests hold the whole chain end to end:

    canonical table → served payload → submission → grading → persisted attempt → report
"""
import json

import pytest

from conftest import register_and_login
from models import ExamQuestionBank, PastPaperAttempt, PastPaperWrongQuestion
import exam_paper_scores
import main

SUBJECT = "computer_organization"
YEAR = 2022
# Real numbers from that paper, so the canonical table answers for them: 2022 组成原理 Q43 = 15 分,
# and every objective question is 2 分.
CHOICE_NUMBERS = (12, 13)
BIG_NUMBER = 43
BIG_SCORE = 15


@pytest.fixture
def scored_paper(db_session):
    """Two objective questions and the 15-point 综合应用题, under their REAL question numbers."""
    rows = [ExamQuestionBank(
        subject_key=SUBJECT, subject_name="计算机组成原理", source_type="past_paper",
        visibility="public", year=YEAR, question_number=number, question_type="choice",
        stem=f"评分选择题 {number}", options_json=json.dumps({"A": "甲", "B": "乙"}),
        standard_answer="A", analysis="", is_active=True, source_ref=f"past_paper:{YEAR}-Q{number}")
        for number in CHOICE_NUMBERS]
    rows.append(ExamQuestionBank(
        subject_key=SUBJECT, subject_name="计算机组成原理", source_type="past_paper",
        visibility="public", year=YEAR, question_number=BIG_NUMBER, question_type="big",
        stem="评分综合应用题", options_json="{}", standard_answer="参考答案",
        analysis="", is_active=True, source_ref=f"past_paper:{YEAR}-Q{BIG_NUMBER}"))
    for row in rows:
        db_session.add(row)
    db_session.commit()
    for row in rows:
        db_session.refresh(row)
    ids = [row.id for row in rows]
    try:
        yield {row.question_number: row for row in rows}
    finally:
        db_session.query(PastPaperWrongQuestion).filter(
            PastPaperWrongQuestion.standard_answer.in_(["A", "参考答案"])).delete(
            synchronize_session=False)
        db_session.query(ExamQuestionBank).filter(ExamQuestionBank.id.in_(ids)).delete(
            synchronize_session=False)
        db_session.commit()


def _submit(client, username, answers):
    login = register_and_login(client, username)
    assert login is not None
    created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts", json={"year": YEAR})
    assert created.status_code == 200, created.text
    attempt_id = created.json()["attempt_id"]
    submitted = client.post(
        f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}/submit",
        json={"answers": answers})
    assert submitted.status_code == 200, submitted.text
    return attempt_id, submitted.json()


def test_the_served_question_carries_the_paper_s_score(scored_paper):
    assert exam_paper_scores.full_score(SUBJECT, YEAR, BIG_NUMBER, "big") == BIG_SCORE
    assert exam_paper_scores.full_score(SUBJECT, YEAR, CHOICE_NUMBERS[0], "choice") == 2


def test_the_pre_submit_payload_never_promises_the_wrong_denominator(client, db_session,
                                                                     scored_paper):
    register_and_login(client, "score_payload")
    body = client.get(f"/exam/11408/{SUBJECT}/past-paper-questions?year={YEAR}").json()
    served = {q["question_number"]: q for q in body["questions"]}
    assert served[BIG_NUMBER]["full_score"] == BIG_SCORE
    for number in CHOICE_NUMBERS:
        assert served[number]["full_score"] == 2


def test_grading_and_the_persisted_attempt_use_the_paper_s_denominator(client, db_session,
                                                                      scored_paper):
    register_and_login(client, "score_grade")
    created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts", json={"year": YEAR})
    attempt_id = created.json()["attempt_id"]

    answers = {str(number): "A" for number in CHOICE_NUMBERS}
    answers[str(BIG_NUMBER)] = "我的作答"
    submitted = client.post(
        f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}/submit",
        json={"answers": answers})
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()

    per_question = {r["question_number"]: r for r in result["results"]}
    assert per_question[BIG_NUMBER]["full_score"] == BIG_SCORE, "the big question is out of 15"
    # 2 objective questions × 2 分 + the 15-point 综合应用题. Under the old rule this was 14.
    assert result["max_score"] == 2 * 2 + BIG_SCORE
    assert result["total_score"] == 2 * 2

    db_session.expire_all()
    attempt = db_session.query(PastPaperAttempt).filter(PastPaperAttempt.id == attempt_id).one()
    assert attempt.max_score == 2 * 2 + BIG_SCORE
    assert attempt.total_score == 2 * 2


def test_the_replayed_result_keeps_the_paper_s_denominator(client, db_session, scored_paper):
    register_and_login(client, "score_replay")
    created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts", json={"year": YEAR})
    attempt_id = created.json()["attempt_id"]
    answers = {str(number): "A" for number in CHOICE_NUMBERS}
    answers[str(BIG_NUMBER)] = "我的作答"
    client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}/submit",
                json={"answers": answers})

    detail = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    replayed = {r["question_number"]: r for r in detail["results"]}
    assert replayed[BIG_NUMBER]["full_score"] == BIG_SCORE


def test_the_report_denominator_is_the_papers_not_a_fixed_ten(client, db_session, scored_paper):
    """``practice/stats`` computes accuracy from total_score / max_score — the same numbers."""
    attempt_id, result = _submit(client, "score_report", {
        str(number): "A" for number in CHOICE_NUMBERS
    } | {str(BIG_NUMBER): "我的作答"})
    stats = client.get(f"/exam/11408/{SUBJECT}/practice/stats").json()
    # 4 of 19: the two objective questions score 2 each, and the 15-point question is self-review
    # here — so it is not in total_score, but its 15 points ARE in the denominator.
    assert result["max_score"] == 19
    assert stats["accuracy"] == round(4 / 19 * 100)


def test_the_ai_grader_is_asked_for_the_paper_s_maximum(monkeypatch, db_session):
    """The rubric's maximum is the question's score, not GRADE_MAX_SCORE."""
    from learning.spaces.exam_prep import ai as exam_ai

    captured = {}

    class _Result:
        content = '{"score": 12, "feedback": "不错"}'

    def _fake_execute(db, user, capability, messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return _Result()

    monkeypatch.setattr(exam_ai, "execute_exam_ai", _fake_execute)
    score, feedback = exam_ai.grade_big_answer(
        None, None, learning_context=None, stem="题干", standard_answer="参考",
        user_answer="作答", question_number=BIG_NUMBER, max_score=BIG_SCORE)

    assert score == 12
    assert f"满分{BIG_SCORE}分" in captured["prompt"], captured["prompt"][:60]
    assert "满分10分" not in captured["prompt"]

    # …and a score above the QUESTION's maximum is refused, not silently clamped to the old 10.
    monkeypatch.setattr(exam_ai, "execute_exam_ai",
                        lambda *a, **k: type("R", (), {"content": '{"score": 16}'})())
    with pytest.raises(exam_ai.GradeOutputError):
        exam_ai.grade_big_answer(None, None, learning_context=None, stem="题干",
                                 standard_answer="参考", user_answer="作答",
                                 question_number=BIG_NUMBER, max_score=BIG_SCORE)


def test_the_provisional_grader_scales_to_the_question_not_to_ten():
    import exam_paper_parser

    score, feedback = exam_paper_parser._ungraded_big_answer("甲 乙", "甲 乙 丙 丁", 15)
    assert 0 < score <= 15
    assert feedback
    # The same overlap against the same reference cannot exceed the question's own maximum.
    assert exam_paper_parser._ungraded_big_answer("甲 乙", "甲 乙 丙 丁", 7)[0] <= 7


def test_an_unanswered_question_is_still_worth_its_points_in_the_denominator(client, db_session,
                                                                             scored_paper):
    """Blank is not zero: it scores nothing, but the paper still counts its marks."""
    register_and_login(client, "score_blank")
    created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts", json={"year": YEAR})
    attempt_id = created.json()["attempt_id"]
    submitted = client.post(
        f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}/submit",
        json={"answers": {str(CHOICE_NUMBERS[0]): "A"}})
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()

    assert result["total_score"] == 2, "only the one answered question scores"
    assert result["max_score"] == 2 * 2 + BIG_SCORE, "but both objective questions and the big one count"
    unanswered = next(r for r in result["results"] if r["question_number"] == CHOICE_NUMBERS[1])
    assert unanswered["correct"] is None, "an unanswered objective question carries no verdict"
    assert unanswered["score"] == 0
