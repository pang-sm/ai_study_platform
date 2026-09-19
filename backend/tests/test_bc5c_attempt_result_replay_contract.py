"""FRONTEND_BLOCKER_BC5C — submitted practice attempt authoritative result replay.

Gates this file exists to prove:

  * the authoritative per-question result is ALREADY persisted by submit into
    ``ExamPracticeAttempt.result_json``; the detail endpoint is a replay/read endpoint and gains
    nothing to grade;
  * after ``submitted``, ``GET .../attempts/{attempt_id}`` replays that persisted result verbatim,
    keyed by ``question_id``, as the exact ``ExamPracticeSubmitResult`` union the submit response
    uses — so the frontend never reconstructs correctness from ``user_answer`` vs
    ``standard_answer``;
  * before submission the payload still hides the answer, the explanation and every grading field;
  * the replay is read-only and idempotent: repeated GETs create no wrong record, no knowledge
    write and no learning event, and one user can never read another user's attempt.
"""
import hashlib
import inspect
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login
from data_plane.models import LearningEvent
from learning.practice.models import PracticeAttempt, PracticeSession
from learning.wrong_answers.models import WrongAnswerState
from models import (
    ExamPracticeAttempt,
    ExamQuestionBank,
    ExamQuestionDoneRecord,
    ExamWrongQuestion,
    UserKnowledgeProgress,
)
import main

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"
SUBJECT = "data_structure"

# Mirrors BC5A: the canonical result key set per question type, unchanged by the replay.
RESULT_KEYS = {
    "choice": {"question_id", "correct", "standard_answer", "user_answer", "stem",
               "options", "analysis", "question_type"},
    "big": {"question_id", "correct", "judge", "standard_answer", "user_answer", "stem",
            "options", "analysis", "question_type", "hint"},
}

# Every table the submit path can write. A read/replay endpoint must not move a single one.
SIDE_EFFECT_TABLES = (
    ExamWrongQuestion, ExamQuestionDoneRecord, UserKnowledgeProgress,
    PracticeSession, PracticeAttempt, LearningEvent, WrongAnswerState,
)


# ---------------------------------------------------------------- fixtures / helpers

@pytest.fixture
def bank(db_session):
    """A deterministic module bank: two choice questions plus one big question."""
    rows = [
        dict(knowledge_point_id="1.1", stem="BC5C 选择正确", question_type="choice",
             options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="A", analysis="这是解析"),
        dict(knowledge_point_id="1.1", stem="BC5C 选择错误", question_type="choice",
             options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="B", analysis=""),
        dict(knowledge_point_id="1.2", stem="BC5C 大题", question_type="big",
             options_json=json.dumps({}), standard_answer="参考答案文本", analysis=""),
    ]
    created = []
    for row in rows:
        item = ExamQuestionBank(subject_key=SUBJECT, subject_name=SUBJECT, source_type="chapter",
                                visibility="public", knowledge_point_name="知识点",
                                knowledge_point_path="", **row)
        db_session.add(item)
        created.append(item)
    db_session.commit()
    for item in created:
        db_session.refresh(item)
    ids = [q.id for q in created]
    try:
        yield {"chapter": created, "by_stem": {q.stem: q for q in created}}
    finally:
        db_session.query(ExamWrongQuestion).filter(
            ExamWrongQuestion.question_bank_id.in_(ids)).delete(synchronize_session=False)
        db_session.query(ExamQuestionDoneRecord).filter(
            ExamQuestionDoneRecord.question_bank_id.in_(ids)).delete(synchronize_session=False)
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.commit()


def _start(client, question_ids, subject_key=SUBJECT):
    response = client.post(f"/exam/11408/{subject_key}/chapter-practice/attempts",
                           json={"question_ids": question_ids})
    assert response.status_code == 200, response.text
    return response.json()["attempt_id"]


def _submit(client, attempt_id, answers, subject_key=SUBJECT):
    response = client.post(f"/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/submit",
                           json={"answers": answers})
    assert response.status_code == 200, response.text
    return response.json()


def _detail(client, attempt_id, subject_key=SUBJECT):
    response = client.get(f"/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _table_counts(db_session):
    return {model.__tablename__: db_session.query(model).count() for model in SIDE_EFFECT_TABLES}


def _attempt_row(attempt_id):
    from database import SessionLocal

    session = SessionLocal()
    try:
        return session.query(ExamPracticeAttempt).filter(ExamPracticeAttempt.id == attempt_id).first()
    finally:
        session.close()


def _mutate_persisted_result(attempt_id, mutate):
    """Rewrite the stored blob, then detach it, so assertions see committed state only."""
    from database import SessionLocal

    session = SessionLocal()
    try:
        attempt = session.query(ExamPracticeAttempt).filter(ExamPracticeAttempt.id == attempt_id).first()
        blob = json.loads(attempt.result_json)
        mutate(blob)
        attempt.result_json = json.dumps(blob, ensure_ascii=False)
        session.commit()
    finally:
        session.close()


# ================================================================ A. pre-submit is still sealed

def test_pre_submit_detail_leaks_no_answer_explanation_or_result(client, bank):
    register_and_login(client, "bc5c_pre")
    ids = [q.id for q in bank["chapter"]]
    attempt_id = _start(client, ids)
    client.post(f"/exam/11408/{SUBJECT}/chapter-practice/attempts/{attempt_id}/answers",
                json={"answers": {str(ids[0]): "A"}})

    pre = _detail(client, attempt_id)

    assert sorted(pre) == ["attempt", "questions", "saved_answers"]
    for question in pre["questions"]:
        assert "standard_answer" not in question
        assert "analysis" not in question
        assert "correct" not in question
        assert "judge" not in question
    assert pre["attempt"]["status"] == "in_progress"
    # the pre-submit draft answer is still served, so the desk can restore the form
    assert pre["saved_answers"] == {str(ids[0]): "A"}


# ================================================================ B. choice replay

def test_submitted_detail_replays_the_correct_choice_result(client, bank):
    register_and_login(client, "bc5c_choice_ok")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])
    submitted = _submit(client, attempt_id, {str(good.id): "A"})

    post = _detail(client, attempt_id)

    assert post["attempt"]["status"] == "submitted"
    assert set(post) == {"attempt", "questions", "saved_answers", "results"}
    assert post["results"] == submitted["results"]
    assert post["results"][0]["question_id"] == good.id
    assert post["results"][0]["correct"] is True
    assert set(post["results"][0]) == RESULT_KEYS["choice"]


def test_submitted_detail_replays_the_incorrect_choice_result(client, bank):
    register_and_login(client, "bc5c_choice_bad")
    bad = bank["by_stem"]["BC5C 选择错误"]
    attempt_id = _start(client, [bad.id])
    # standard is "B"; answer "A" is wrong and must stay wrong after the reload
    submitted = _submit(client, attempt_id, {str(bad.id): "A"})

    post = _detail(client, attempt_id)
    result = post["results"][0]

    assert post["results"] == submitted["results"]
    assert result["correct"] is False
    assert result["standard_answer"] == "B"
    assert result["user_answer"] == "A"


def test_replayed_grading_matches_the_case_folded_verdict_decided_at_submit(client, bank):
    """Case folding happens at submit; the reload carries that decision, it does not redo it."""
    register_and_login(client, "bc5c_case")
    good, bad = bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 选择错误"]
    attempt_id = _start(client, [good.id, bad.id])
    submitted = _submit(client, attempt_id, {str(good.id): "a", str(bad.id): "b"})

    graded = {r["question_id"]: r["correct"] for r in submitted["results"]}
    assert graded[good.id] is True      # "a" vs standard "A"
    assert graded[bad.id] is True       # "b" vs standard "B"

    post = _detail(client, attempt_id)
    replayed = {r["question_id"]: r for r in post["results"]}

    # the raw lower-case answers are preserved verbatim, and the folded verdict is replayed
    assert replayed[good.id]["user_answer"] == "a"
    assert replayed[good.id]["correct"] is True
    assert replayed[bad.id]["user_answer"] == "b"
    assert replayed[bad.id]["correct"] is True
    assert post["results"] == submitted["results"]


# ================================================================ C. big-question self review

def test_submitted_detail_replays_big_question_self_review(client, bank):
    register_and_login(client, "bc5c_big")
    big = bank["by_stem"]["BC5C 大题"]
    attempt_id = _start(client, [big.id])
    submitted = _submit(client, attempt_id, {str(big.id): "我的作答文本"})

    post = _detail(client, attempt_id)
    result = post["results"][0]

    assert post["results"] == submitted["results"]
    assert set(result) == RESULT_KEYS["big"]
    assert result["question_id"] == big.id
    assert result["correct"] is None
    assert result["judge"] == "self_review"
    assert result["question_type"] == "big"
    assert result["user_answer"] == "我的作答文本"
    assert result["standard_answer"] == "参考答案文本"
    # never auto-graded: no boolean sneaks into the big-question replay
    assert not isinstance(result["correct"], bool)


# ================================================================ D. payload restoration

def test_user_answer_survives_reload_for_every_question_type(client, bank):
    register_and_login(client, "bc5c_user_answer")
    good, big = bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 大题"]
    attempt_id = _start(client, [good.id, big.id])
    _submit(client, attempt_id, {str(good.id): "A", str(big.id): "手写作答"})

    replayed = {r["question_id"]: r["user_answer"] for r in _detail(client, attempt_id)["results"]}

    assert replayed == {good.id: "A", big.id: "手写作答"}


def test_standard_answer_and_analysis_appear_only_after_submission(client, bank):
    register_and_login(client, "bc5c_reveal")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])

    pre = _detail(client, attempt_id)
    assert "standard_answer" not in pre["questions"][0]
    assert "analysis" not in pre["questions"][0]

    _submit(client, attempt_id, {str(good.id): "A"})
    post = _detail(client, attempt_id)

    assert post["questions"][0]["standard_answer"] == "A"
    assert post["questions"][0]["analysis"] == "这是解析"
    assert post["results"][0]["standard_answer"] == "A"
    assert post["results"][0]["analysis"] == "这是解析"


def test_empty_analysis_is_preserved_as_empty_not_manufactured(client, bank):
    register_and_login(client, "bc5c_analysis")
    bad, big = bank["by_stem"]["BC5C 选择错误"], bank["by_stem"]["BC5C 大题"]   # both analysis=""
    attempt_id = _start(client, [bad.id, big.id])
    _submit(client, attempt_id, {str(bad.id): "A", str(big.id): "作答"})

    post = _detail(client, attempt_id)

    assert {r["question_id"]: r["analysis"] for r in post["results"]} == {bad.id: "", big.id: ""}
    for question in post["questions"]:
        assert question["analysis"] == ""


# ================================================================ E. identity, not position

def test_results_are_keyed_by_question_id_not_array_position(client, bank):
    register_and_login(client, "bc5c_identity")
    good, bad, big = (bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 选择错误"],
                      bank["by_stem"]["BC5C 大题"])
    attempt_id = _start(client, [big.id, good.id, bad.id])
    _submit(client, attempt_id, {str(good.id): "A", str(bad.id): "A", str(big.id): "作答"})

    by_id = {r["question_id"]: r for r in _detail(client, attempt_id)["results"]}

    assert set(by_id) == {good.id, bad.id, big.id}
    assert (by_id[good.id]["user_answer"], by_id[good.id]["correct"]) == ("A", True)
    assert (by_id[bad.id]["user_answer"], by_id[bad.id]["correct"]) == ("A", False)
    assert (by_id[big.id]["user_answer"], by_id[big.id]["correct"]) == ("作答", None)
    # every replayed record carries its own identity explicitly
    assert all(isinstance(r["question_id"], int) for r in _detail(client, attempt_id)["results"])


def test_reordering_the_stored_questions_does_not_rebind_answers(client, bank):
    register_and_login(client, "bc5c_reorder")
    good, bad, big = (bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 选择错误"],
                      bank["by_stem"]["BC5C 大题"])
    attempt_id = _start(client, [good.id, bad.id, big.id])
    _submit(client, attempt_id, {str(good.id): "A", str(bad.id): "B", str(big.id): "作答"})

    def _binding(detail):
        return {r["question_id"]: (r["user_answer"], r["correct"]) for r in detail["results"]}

    baseline = _binding(_detail(client, attempt_id))

    # shuffle both the attempt's question list and the persisted result list
    session_ids = [bad.id, big.id, good.id]
    from database import SessionLocal

    session = SessionLocal()
    try:
        attempt = session.query(ExamPracticeAttempt).filter(ExamPracticeAttempt.id == attempt_id).first()
        attempt.question_ids_json = json.dumps(session_ids)
        session.commit()
    finally:
        session.close()
    _mutate_persisted_result(attempt_id, lambda blob: blob["results"].reverse())

    assert _binding(_detail(client, attempt_id)) == baseline


# ================================================================ F. no second grader on GET

def test_detail_get_replays_persistence_instead_of_regrading(client, bank):
    """The decisive no-regrade proof: flip the stored verdict and watch it survive a reload.

    A GET that compared ``user_answer`` against ``standard_answer`` again would answer ``True``
    here — the learner really did answer "A" and the standard really is "A". Only a replay of the
    persisted fact can answer ``False``.
    """
    register_and_login(client, "bc5c_regrade")
    good = bank["by_stem"]["BC5C 选择正确"]      # standard "A"
    attempt_id = _start(client, [good.id])
    assert _submit(client, attempt_id, {str(good.id): "A"})["results"][0]["correct"] is True
    assert _attempt_row(attempt_id).result_json is not None

    _mutate_persisted_result(
        attempt_id, lambda blob: [r.update(correct=not r["correct"]) for r in blob["results"]])

    replayed = _detail(client, attempt_id)["results"][0]

    assert replayed["user_answer"] == "A"
    assert replayed["correct"] is False   # the stored verdict — not a fresh comparison


def test_detail_get_sources_its_results_from_the_persisted_decode(client, bank, monkeypatch):
    """Narrow-boundary spy: the results are produced by the persistence decoder, nothing else."""
    calls = []
    real = main._persisted_attempt_results

    def spy(attempt):
        calls.append(attempt.id)
        return real(attempt)

    monkeypatch.setattr(main, "_persisted_attempt_results", spy)
    register_and_login(client, "bc5c_spy")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])
    _submit(client, attempt_id, {str(good.id): "A"})

    post = _detail(client, attempt_id)

    assert calls == [attempt_id]
    assert post["results"][0]["correct"] is True


def test_detail_get_never_reaches_the_ai_boundary(client, bank, monkeypatch):
    def _explode(*_args, **_kwargs):
        raise AssertionError("attempt detail must not reach the AI boundary")

    monkeypatch.setattr(main, "_exam_ai_content", _explode)
    register_and_login(client, "bc5c_ai")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])
    _submit(client, attempt_id, {str(good.id): "A"})

    assert _detail(client, attempt_id)["results"][0]["correct"] is True


def test_detail_handler_compares_no_answers():
    """Permanent source guard: the replay handler holds no comparison primitive of its own."""
    source = inspect.getsource(main.get_chapter_practice_attempt)
    assert ".upper()" not in source
    assert ".strip()" not in source


# ================================================================ G. read-only replay

def test_repeated_detail_get_on_submitted_attempt_writes_nothing(client, bank, db_session):
    register_and_login(client, "bc5c_idempotent")
    good, bad, big = (bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 选择错误"],
                      bank["by_stem"]["BC5C 大题"])
    attempt_id = _start(client, [good.id, bad.id, big.id])
    _submit(client, attempt_id, {str(good.id): "A", str(bad.id): "A", str(big.id): "作答"})

    before = _table_counts(db_session)
    first = _detail(client, attempt_id)
    second = _detail(client, attempt_id)
    third = _detail(client, attempt_id)
    after = _table_counts(db_session)

    assert first == second == third
    assert after == before, {t: (before[t], after[t]) for t in before if before[t] != after[t]}
    # named gates: no wrong record, no knowledge write, no new learning event on the read path
    assert after[ExamWrongQuestion.__tablename__] == before[ExamWrongQuestion.__tablename__]
    assert after[UserKnowledgeProgress.__tablename__] == before[UserKnowledgeProgress.__tablename__]
    assert after[LearningEvent.__tablename__] == before[LearningEvent.__tablename__]
    assert after[WrongAnswerState.__tablename__] == before[WrongAnswerState.__tablename__]
    assert after[PracticeAttempt.__tablename__] == before[PracticeAttempt.__tablename__]


def test_pre_submit_detail_get_is_also_read_only(client, bank, db_session):
    register_and_login(client, "bc5c_pre_idem")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])

    before = _table_counts(db_session)
    assert _detail(client, attempt_id) == _detail(client, attempt_id)
    after = _table_counts(db_session)

    assert after == before


# ================================================================ H. ownership

def test_one_user_cannot_read_another_users_submitted_result(client, bank):
    register_and_login(client, "bc5c_owner_a")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])
    _submit(client, attempt_id, {str(good.id): "A"})
    assert _detail(client, attempt_id)["results"][0]["correct"] is True

    with TestClient(main.app) as other:
        register_and_login(other, "bc5c_owner_b")
        detail = other.get(f"/exam/11408/{SUBJECT}/chapter-practice/attempts/{attempt_id}")
        submit = other.post(f"/exam/11408/{SUBJECT}/chapter-practice/attempts/{attempt_id}/submit",
                            json={"answers": {}})
        assert detail.status_code == 404
        assert submit.status_code == 404


def test_anonymous_read_of_an_attempt_is_refused(client, bank):
    register_and_login(client, "bc5c_anon")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])
    _submit(client, attempt_id, {str(good.id): "A"})

    with TestClient(main.app) as anon:
        assert anon.get(
            f"/exam/11408/{SUBJECT}/chapter-practice/attempts/{attempt_id}").status_code == 401


def test_unknown_attempt_still_answers_404(client, bank):
    register_and_login(client, "bc5c_404")
    assert client.get(
        f"/exam/11408/{SUBJECT}/chapter-practice/attempts/999999").status_code == 404


# ================================================================ I. typed transport

def test_detail_response_model_is_concrete_and_reuses_the_submit_result_union():
    schemas = main.app.openapi()["components"]["schemas"]
    detail = schemas["ExamPracticeAttemptDetailResponse"]

    union = detail["properties"]["results"]["items"]
    assert detail["properties"]["results"]["type"] == "array"
    assert "oneOf" in union and "additionalProperties" not in union
    assert union["discriminator"] == {
        "propertyName": "question_type",
        "mapping": {"big": "#/components/schemas/ExamBigPracticeResult",
                    "choice": "#/components/schemas/ExamChoicePracticeResult"},
    }
    # one canonical result schema shared by submit and detail — not two subtly different ones
    assert schemas["ExamPracticeSubmitResponse"]["properties"]["results"]["items"] == union
    # additive only: the pre-existing required keys are untouched
    assert sorted(detail["required"]) == ["attempt", "questions", "saved_answers"]
    assert main.ExamPracticeAttemptDetailResponse.model_fields["results"].annotation == \
        list[main.ExamPracticeSubmitResult]


def test_live_detail_payload_validates_against_the_declared_model(client, bank):
    register_and_login(client, "bc5c_validate")
    good, big = bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 大题"]
    attempt_id = _start(client, [good.id, big.id])

    main.ExamPracticeAttemptDetailResponse.model_validate(_detail(client, attempt_id))

    _submit(client, attempt_id, {str(good.id): "A", str(big.id): "作答"})
    validated = main.ExamPracticeAttemptDetailResponse.model_validate(_detail(client, attempt_id))

    assert sorted(r.question_id for r in validated.results) == sorted([good.id, big.id])


def test_decoded_replay_matches_the_persisted_blob_exactly(client, bank):
    register_and_login(client, "bc5c_blob")
    good, bad, big = (bank["by_stem"]["BC5C 选择正确"], bank["by_stem"]["BC5C 选择错误"],
                      bank["by_stem"]["BC5C 大题"])
    attempt_id = _start(client, [good.id, bad.id, big.id])
    _submit(client, attempt_id, {str(good.id): "A", str(bad.id): "A", str(big.id): "作答"})

    persisted = json.loads(_attempt_row(attempt_id).result_json)

    assert _detail(client, attempt_id)["results"] == persisted["results"]


def test_a_submitted_attempt_with_nothing_persisted_replays_empty_not_invented(client, bank):
    """No persisted result means nothing to replay — never a freshly computed verdict."""
    register_and_login(client, "bc5c_empty")
    good = bank["by_stem"]["BC5C 选择正确"]
    attempt_id = _start(client, [good.id])
    _submit(client, attempt_id, {str(good.id): "A"})

    from database import SessionLocal

    session = SessionLocal()
    try:
        attempt = session.query(ExamPracticeAttempt).filter(ExamPracticeAttempt.id == attempt_id).first()
        attempt.result_json = None
        session.commit()
    finally:
        session.close()

    assert _detail(client, attempt_id)["results"] == []


# ================================================================ J. real DB is untouched

def _real_db_fingerprint():
    if not APP_DB.exists():
        return None
    return {
        "sha256": hashlib.sha256(APP_DB.read_bytes()).hexdigest(),
        "mtime": APP_DB.stat().st_mtime,
        "attempts": _read_attempt_count(),
    }


def _read_attempt_count():
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("select count(*) from exam_practice_attempts").fetchone()[0]
    finally:
        con.close()


_REAL_DB_BASELINE = _real_db_fingerprint()


def test_real_app_db_is_never_mutated_by_this_suite():
    if _REAL_DB_BASELINE is None:
        pytest.skip("no real app.db in this checkout")
    assert _real_db_fingerprint() == _REAL_DB_BASELINE
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()
