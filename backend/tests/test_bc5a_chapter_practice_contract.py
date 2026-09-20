"""FRONTEND_BLOCKER_BC5A — CS408 chapter-practice core contract closure.

Gates this file exists to prove:

  * the canonical chapter identity is the level-1 chapter code shared with the knowledge
    workspace, and it maps COMPLETELY: every chapter-practice row in all four CS408 modules
    belongs to exactly one canonical chapter (unmapped = 0, ambiguous = 0);
  * the six chapter-practice endpoints declare concrete OpenAPI request / response schemas
    instead of `unknown` and untyped records, and the live payload validates against them;
  * the chapter question list is PRE-SUBMIT: the correct answer and the explanation are not on
    the wire, so a learner cannot read the solution off the network response;
  * grading stays backend-side and deterministic with zero provider calls, big questions stay
    self-review, wrong records keep their existing semantics, and a correct answer never
    auto-marks knowledge mastered;
  * the real ``backend/app.db`` is never mutated by any of this.
"""
import hashlib
import inspect
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import register_and_login
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
SEED_DIR = BACKEND_DIR / "seed_data" / "knowledge_maps"

MODULES = ("data_structure", "computer_organization", "operating_system", "computer_network")
SEED_CHAPTERS = {"data_structure": 8, "computer_organization": 7, "operating_system": 5, "computer_network": 6}

QUESTION_ITEM_KEYS = {
    "id", "subject_key", "source_type", "visibility", "knowledge_point_id",
    "knowledge_point_name", "knowledge_point_path", "knowledge_points", "chapter_id",
    "chapter_name", "year", "question_number", "question_type", "stem", "options",
    "difficulty", "quality_status", "created_at", "practiced",
}
RESULT_KEYS = {
    "choice": {"question_id", "correct", "standard_answer", "user_answer", "stem",
               "options", "analysis", "question_type"},
    "big": {"question_id", "correct", "judge", "standard_answer", "user_answer", "stem",
            "options", "analysis", "question_type", "hint"},
}


# ---------------------------------------------------------------- fixtures / helpers

def _seed_chapter_bank(db, subject_key="data_structure"):
    """A deterministic small chapter bank: chapter 1 (1.1 / 1.2) plus chapter 2, one past paper."""
    rows = [
        # chapter 1
        dict(knowledge_point_id="1.1", stem="第一章选择一", question_type="choice",
             options_json=json.dumps({"A": "甲", "B": "乙", "C": "丙", "D": "丁"}),
             standard_answer="A", analysis=""),
        dict(knowledge_point_id="1.1", stem="第一章选择二", question_type="choice",
             options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="b", analysis=""),
        dict(knowledge_point_id="1.2", stem="第一章大题", question_type="big",
             options_json=json.dumps({}), standard_answer="参考答案文本", analysis=""),
        # chapter 2
        dict(knowledge_point_id="2.1", stem="第二章选择", question_type="choice",
             options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="A", analysis=""),
    ]
    created = []
    for row in rows:
        item = ExamQuestionBank(
            subject_key=subject_key, subject_name=subject_key, source_type="chapter",
            visibility="public", knowledge_point_name="知识点", knowledge_point_path="",
            **row,
        )
        db.add(item)
        created.append(item)
    # A past-paper row in the same module: chapter practice must never serve it.
    paper = ExamQuestionBank(
        subject_key=subject_key, subject_name=subject_key, source_type="past_paper",
        visibility="public", knowledge_point_id="", knowledge_point_name="",
        knowledge_point_path="", question_type="choice", stem="真题选择",
        options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="A",
        analysis="真题解析", year=2024, question_number=1,
    )
    db.add(paper)
    db.commit()
    for item in created:
        db.refresh(item)
    db.refresh(paper)
    return created, paper


@pytest.fixture
def bank(db_session):
    """Seed a deterministic chapter bank and remove it again, so each test sees a clean module."""
    created, paper = _seed_chapter_bank(db_session)
    ids = [q.id for q in created] + [paper.id]
    try:
        yield {"chapter": created, "paper": paper,
               "by_stem": {q.stem: q for q in created + [paper]}}
    finally:
        db_session.query(ExamWrongQuestion).filter(
            ExamWrongQuestion.question_bank_id.in_(ids)).delete(synchronize_session=False)
        db_session.query(ExamQuestionDoneRecord).filter(
            ExamQuestionDoneRecord.question_bank_id.in_(ids)).delete(synchronize_session=False)
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.commit()


def _flow(client, subject_key="data_structure", answers=None):
    created = client.post(f"/exam/11408/{subject_key}/chapter-practice/attempts",
                          json={"question_ids": answers["question_ids"]}).json()
    aid = created["attempt_id"]
    if answers:
        client.post(f"/exam/11408/{subject_key}/chapter-practice/attempts/{aid}/answers",
                    json={"answers": answers.get("answers", {})})
    return aid


# ================================================================ A. chapter identity

class _Row:
    """The two attributes `_question_chapter_code` reads off a question-bank row."""

    def __init__(self, knowledge_point_id, source_ref=None):
        self.knowledge_point_id = knowledge_point_id
        self.source_ref = source_ref


def _real_chapter_rows(module):
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(
            "select distinct knowledge_point_id, knowledge_point_name, question_type, count(*) "
            "from exam_question_bank where source_type='chapter' and is_active=1 and subject_key=? "
            "group by 1,2,3", (module,)).fetchall()
    finally:
        con.close()


def _seed_chapter_codes(module):
    payload = json.loads((SEED_DIR / f"{module}_11408.json").read_text(encoding="utf-8"))
    return {str(c.get("code") or "").strip(): c for c in payload.get("chapters") or []}


@pytest.mark.parametrize("module", MODULES)
def test_every_chapter_practice_row_maps_to_exactly_one_canonical_chapter(module):
    """UNMAPPED = 0 and AMBIGUOUS = 0 for every module, using the runtime helper itself."""
    chapters = _seed_chapter_codes(module)
    groups = _real_chapter_rows(module)
    assert groups, "the real chapter bank must not be empty for this proof"

    mapped = {}
    for kp_id, _kp_name, _qtype, count in groups:
        code = main._question_chapter_code(_Row(kp_id))
        assert code, f"{module}: knowledge point {kp_id!r} has no canonical chapter"
        assert code in chapters, f"{module}: chapter {code!r} is not a knowledge-map chapter"
        mapped.setdefault(code, 0)
        mapped[code] += count

    assert not [kp for kp, *_ in groups if main._question_chapter_code(_Row(kp)) not in chapters]
    assert set(mapped) == set(chapters), f"{module}: chapters without questions {sorted(set(chapters) - set(mapped))}"


@pytest.mark.parametrize("module", MODULES)
def test_canonical_chapter_identity_is_url_safe_and_unique_within_the_module(module):
    chapters = _seed_chapter_codes(module)
    assert len(chapters) == SEED_CHAPTERS[module]

    by_group = {}
    for kp_id, *_ in _real_chapter_rows(module):
        code = main._question_chapter_code(_Row(kp_id))
        assert code.isdigit(), f"{module}: {code!r} is not URL-safe"
        assert code in chapters
        # the mapping is a function: one knowledge point never resolves to two chapters
        by_group.setdefault(kp_id, set()).add(code)
        assert len(by_group[kp_id]) == 1
        # `chapter_no` is the same stable value the knowledge workspace exposes
        assert int(code) == chapters[code].get("chapter_no")

    assert by_group, f"{module}: no chapter-practice rows to audit"


def test_sub_chapter_groups_are_not_a_knowledge_map_identity():
    """Why only the chapter level can be canonical: computer_network sub-groups leave the map."""
    leaves = _seed_chapter_codes("computer_network")
    section_codes = set()
    payload = json.loads((SEED_DIR / "computer_network_11408.json").read_text(encoding="utf-8"))
    for chapter in payload["chapters"]:
        for section in chapter.get("children") or []:
            section_codes.add(str(section.get("code") or ""))
            for leaf in section.get("children") or []:
                section_codes.add(str(leaf.get("code") or ""))
    outside = 0
    for kp_id, *_ in _real_chapter_rows("computer_network"):
        code = (kp_id or "").split(" ", 1)[0].strip()
        if code and code not in section_codes and code not in leaves:
            outside += 1
    assert outside > 0, "the audit's key fact: 44 network groups sit outside the seed map"


# ================================================================ B. outline contract

def test_outline_exposes_the_canonical_chapter_catalog(client, bank):
    register_and_login(client, "bc5a_outline")
    body = client.get("/exam/11408/data_structure/chapter-practice/outline").json()

    assert set(body) == {"subject_key", "knowledge_points", "total", "chapters"}
    assert body["knowledge_points"] == {"1.1": 2, "1.2": 1, "2.1": 1}
    assert body["total"] == 4
    assert [c["chapter_code"] for c in body["chapters"]] == ["1", "2"]
    assert all(set(c) == {"chapter_code", "chapter_no", "chapter_title", "question_count"} for c in body["chapters"])
    assert {c["chapter_code"]: c["question_count"] for c in body["chapters"]} == {"1": 3, "2": 1}
    assert sum(c["question_count"] for c in body["chapters"]) == body["total"]


def test_outline_chapter_title_and_no_come_from_the_module_seed(client, bank):
    register_and_login(client, "bc5a_outline_seed")
    body = client.get("/exam/11408/data_structure/chapter-practice/outline").json()
    seed = _seed_chapter_codes("data_structure")
    for chapter in body["chapters"]:
        assert chapter["chapter_title"] == str(seed[chapter["chapter_code"]].get("title") or "")
        assert chapter["chapter_no"] == int(seed[chapter["chapter_code"]].get("chapter_no"))


def test_outline_response_validates_against_its_declared_model(client, bank):
    register_and_login(client, "bc5a_outline_model")
    body = client.get("/exam/11408/data_structure/chapter-practice/outline").json()
    main.ExamChapterPracticeOutlineResponse.model_validate(body)


# ================================================================ C. question list

def test_chapter_question_list_is_pre_submit_safe(client, bank):
    """PRE_SUBMIT_ANSWER_LEAK = 0 and PRE_SUBMIT_EXPLANATION_LEAK = 0."""
    register_and_login(client, "bc5a_leak")
    for url in ("/exam/11408/data_structure/chapter-practice/questions",
                "/exam/11408/data_structure/chapter-practice/questions?chapter_code=1",
                "/exam/11408/data_structure/chapter-practice/questions?knowledge_point_id=1.1"):
        items = client.get(url).json()["items"]
        assert items, url
        for item in items:
            assert "standard_answer" not in item, url
            assert "analysis" not in item, url
            assert "correct" not in item, url
            assert set(item) == QUESTION_ITEM_KEYS


def test_chapter_question_list_model_has_no_answer_field():
    """The pre-submit transport may not even declare a place to put the solution."""
    fields = set(main.ExamPracticeQuestion.model_fields)
    assert "standard_answer" not in fields
    assert "analysis" not in fields
    attempt_fields = set(main.ExamPracticeAttemptQuestion.model_fields)
    assert {"standard_answer", "analysis"} <= attempt_fields, "the attempt model is the post-submit surface"


def test_question_list_serves_chapter_rows_only(client, bank, db_session):
    register_and_login(client, "bc5a_source")
    subject = "data_structure"
    items = client.get(f"/exam/11408/{subject}/chapter-practice/questions").json()["items"]
    paper_id = bank["paper"].id
    assert items
    assert {i["source_type"] for i in items} == {"chapter"}
    assert paper_id not in {i["id"] for i in items}, "past-paper rows must not leak into chapter practice"


def test_question_list_chapter_code_binds_to_exactly_one_chapter(client, bank):
    register_and_login(client, "bc5a_chapter_filter")
    body = client.get("/exam/11408/data_structure/chapter-practice/questions?chapter_code=1").json()
    assert body["total"] == 3
    assert {i["chapter_id"] for i in body["items"]} == {"1"}
    assert {i["knowledge_point_id"] for i in body["items"]} == {"1.1", "1.2"}

    other = client.get("/exam/11408/data_structure/chapter-practice/questions?chapter_code=2").json()
    assert other["total"] == 1
    assert {i["chapter_id"] for i in other["items"]} == {"2"}

    empty = client.get("/exam/11408/data_structure/chapter-practice/questions?chapter_code=99").json()
    assert empty["total"] == 0


def test_question_list_response_validates_against_its_declared_model(client, bank):
    register_and_login(client, "bc5a_qlist_model")
    body = client.get("/exam/11408/data_structure/chapter-practice/questions").json()
    main.ExamChapterPracticeQuestionsResponse.model_validate(body)


def test_question_type_is_a_closed_set(client, bank, db_session):
    register_and_login(client, "bc5a_qtype")
    items = client.get("/exam/11408/data_structure/chapter-practice/questions").json()["items"]
    assert {i["question_type"] for i in items} <= {"choice", "big"}
    # the whole question bank only ever holds those two values, so the union is genuinely closed
    kinds = {r[0] for r in db_session.query(ExamQuestionBank.question_type).distinct()}
    assert kinds <= {"choice", "big"}


def test_question_payload_never_exposes_filesystem_paths(client, bank):
    register_and_login(client, "bc5a_paths")
    items = client.get("/exam/11408/data_structure/chapter-practice/questions").json()["items"]
    for item in items:
        blob = json.dumps(item, ensure_ascii=False)
        assert "C:\\" not in blob and "\\\\" not in blob
        assert "\\upload" not in blob and "/uploads/" not in blob


# ================================================================ D. attempt lifecycle

def test_attempt_create_response_is_concrete(client, bank):
    register_and_login(client, "bc5a_create")
    ids = [q.id for q in bank["chapter"] if q.knowledge_point_id == "1.1"]
    # ACCEL_PRODUCT_S9: `knowledge_point_id` is now a VALIDATED canonical concept slot, so it
    # is only accepted together with questions that genuinely carry it. BC5A sent the whole
    # chapter here; that payload declared concept 1.1 over questions of 1.2 and 2.1 and is
    # now a 422 (see tests/test_s9_concept_identity.py). This test's own subject — that the
    # create response is concrete — is unchanged.
    response = client.post("/exam/11408/data_structure/chapter-practice/attempts",
                           json={"question_ids": ids, "knowledge_point_id": "1.1"})
    assert response.status_code == 200
    body = response.json()
    main.ExamPracticeAttemptCreateResponse.model_validate(body)
    assert set(body) == {"attempt_id", "status", "total_questions"}
    assert body["status"] == "in_progress"
    assert body["total_questions"] == len(ids)


def test_attempt_create_without_a_concept_still_declares_none(client, bank):
    """The BC5A shape with NO concept: the whole chapter, and the concept slot stays NULL."""
    register_and_login(client, "bc5a_create_no_concept")
    ids = [q.id for q in bank["chapter"]]
    response = client.post("/exam/11408/data_structure/chapter-practice/attempts",
                           json={"question_ids": ids})
    assert response.status_code == 200
    main.ExamPracticeAttemptCreateResponse.model_validate(response.json())
    assert response.json()["total_questions"] == len(ids)


def test_attempt_create_without_question_ids_keeps_its_400(client, bank):
    register_and_login(client, "bc5a_no_ids")
    assert client.post("/exam/11408/data_structure/chapter-practice/attempts",
                       json={}).status_code == 400
    assert client.post("/exam/11408/data_structure/chapter-practice/attempts",
                       json={"question_ids": []}).status_code == 400


def test_attempt_detail_hides_the_answer_until_submission(client, bank):
    register_and_login(client, "bc5a_detail")
    ids = [q.id for q in bank["chapter"]]
    aid = _flow(client, answers={"question_ids": ids, "answers": {str(ids[0]): "A"}})

    pre = client.get(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}").json()
    main.ExamPracticeAttemptDetailResponse.model_validate(pre)
    assert set(pre["questions"][0]) == QUESTION_ITEM_KEYS - {"practiced"}
    for question in pre["questions"]:
        assert "standard_answer" not in question
        assert "analysis" not in question
    assert pre["saved_answers"] == {str(ids[0]): "A"}

    client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                json={"answers": {str(ids[0]): "A"}})
    post = client.get(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}").json()
    main.ExamPracticeAttemptDetailResponse.model_validate(post)
    assert post["attempt"]["status"] == "submitted"
    for question in post["questions"]:
        assert "standard_answer" in question and "analysis" in question


def test_attempt_reload_restores_the_question_set_and_saved_answers(client, bank):
    register_and_login(client, "bc5a_reload")
    ids = [q.id for q in bank["chapter"]]
    aid = _flow(client, answers={"question_ids": ids, "answers": {str(ids[1]): "B"}})

    detail = client.get(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}").json()
    assert {q["id"] for q in detail["questions"]} == set(ids)
    assert detail["saved_answers"] == {str(ids[1]): "B"}
    assert detail["attempt"]["id"] == aid
    assert detail["attempt"]["total_questions"] == len(ids)

    # the attempt identity is the existing ExamPracticeAttempt — no new session entity
    columns = ExamPracticeAttempt.__table__.columns
    assert "question_ids_json" in columns
    assert "answers_json" in columns


def test_answer_save_response_is_concrete(client, bank):
    register_and_login(client, "bc5a_save")
    ids = [q.id for q in bank["chapter"]]
    aid = _flow(client, answers={"question_ids": ids})
    body = client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/answers",
                       json={"answers": {str(ids[0]): "A"}}).json()
    main.ExamPracticeAnswerSaveResponse.model_validate(body)
    assert body == {"success": True}


def test_answer_save_is_refused_after_submission(client, bank):
    register_and_login(client, "bc5a_save_after")
    ids = [q.id for q in bank["chapter"]]
    aid = _flow(client, answers={"question_ids": ids})
    client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit", json={"answers": {}})
    assert client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/answers",
                       json={"answers": {}}).status_code == 404


# ================================================================ E. grading

def test_choice_grading_is_deterministic_case_insensitive_and_provider_free(client, bank, monkeypatch):
    def _explode(*_a, **_kw):
        raise AssertionError("chapter grading must not reach the AI boundary")

    monkeypatch.setattr(main, "_exam_ai_content", _explode)
    register_and_login(client, "bc5a_grade")
    by_stem = bank["by_stem"]
    ids = [by_stem["第一章选择一"].id, by_stem["第一章选择二"].id, by_stem["第二章选择"].id]
    aid = _flow(client, answers={"question_ids": ids})

    response = client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                           json={"answers": {str(by_stem["第一章选择一"].id): "a",   # exact, lowercased
                                             str(by_stem["第一章选择二"].id): "B",   # standard is "b"
                                             str(by_stem["第二章选择"].id): "D"}})   # wrong
    assert response.status_code == 200
    body = response.json()
    main.ExamPracticeSubmitResponse.model_validate(body)
    assert set(body) == {"total_questions", "choice_total", "big_count", "correct_count",
                         "wrong_count", "accuracy", "mistake_saved_count", "results"}
    assert (body["correct_count"], body["wrong_count"], body["choice_total"]) == (2, 1, 3)
    graded = {r["question_id"]: r["correct"] for r in body["results"]}
    assert graded[by_stem["第一章选择一"].id] is True
    assert graded[by_stem["第一章选择二"].id] is True
    assert graded[by_stem["第二章选择"].id] is False
    for result in body["results"]:
        assert set(result) == RESULT_KEYS[result["question_type"]]
        assert result["question_type"] != "choice" or "judge" not in result


def test_big_question_is_self_review_and_never_auto_graded(client, bank):
    register_and_login(client, "bc5a_big")
    big = bank["by_stem"]["第一章大题"]
    aid = _flow(client, answers={"question_ids": [big.id]})
    body = client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                       json={"answers": {str(big.id): "我的作答"}}).json()

    assert body["big_count"] == 1
    assert body["choice_total"] == 0
    assert body["accuracy"] == 0
    result = body["results"][0]
    assert set(result) == RESULT_KEYS["big"]
    assert result["correct"] is None
    assert result["judge"] == "self_review"
    assert result["user_answer"] == "我的作答"
    assert result["standard_answer"] == "参考答案文本"
    assert result["hint"] == "请自行对照参考答案"
    # a big question never becomes a wrong record
    assert body["mistake_saved_count"] == 0


def test_submit_is_one_time(client, bank):
    register_and_login(client, "bc5a_once")
    ids = [q.id for q in bank["chapter"]]
    aid = _flow(client, answers={"question_ids": ids})
    assert client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                       json={"answers": {}}).status_code == 200
    assert client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                       json={"answers": {}}).status_code == 404


# ================================================================ F. wrong records

def test_incorrect_choice_creates_exactly_one_active_wrong_record(client, bank, db_session):
    register_and_login(client, "bc5a_wrong")
    target = bank["by_stem"]["第一章选择一"]
    aid = _flow(client, answers={"question_ids": [target.id]})
    body = client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                       json={"answers": {str(target.id): "D"}}).json()

    rows = db_session.query(ExamWrongQuestion).filter(
        ExamWrongQuestion.question_bank_id == target.id,
        ExamWrongQuestion.status == "active").all()
    assert len(rows) == 1
    assert rows[0].user_answer == "D"
    assert rows[0].review_count in (0, None) or rows[0].review_count == 0
    assert body["mistake_saved_count"] == 1


def test_repeated_wrong_answer_updates_review_count_instead_of_duplicating(client, bank, db_session):
    register_and_login(client, "bc5a_wrong_twice")
    target = bank["by_stem"]["第一章选择一"]
    for _ in range(2):
        aid = _flow(client, answers={"question_ids": [target.id]})
        client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                    json={"answers": {str(target.id): "D"}})

    rows = db_session.query(ExamWrongQuestion).filter(
        ExamWrongQuestion.question_bank_id == target.id,
        ExamWrongQuestion.status == "active").all()
    assert len(rows) == 1
    assert rows[0].review_count == 1


def test_submit_does_not_promise_uncontracted_wrong_record_fields(client, bank, db_session):
    """The submit payload guarantees counts, not `wrong_recorded` / `resolved`."""
    register_and_login(client, "bc5a_wrong_fields")
    target = bank["by_stem"]["第一章选择一"]
    aid = _flow(client, answers={"question_ids": [target.id]})
    body = client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                       json={"answers": {str(target.id): "D"}}).json()
    assert "wrong_recorded" not in body
    assert "resolved" not in body
    assert "wrong_recorded" not in body["results"][0]
    assert "resolved" not in body["results"][0]
    # the wrong book was written by submit alone — no second mutation endpoint is needed
    assert db_session.query(ExamWrongQuestion).filter(
        ExamWrongQuestion.question_bank_id == target.id).count() == 1


# ================================================================ G. knowledge boundary

def test_correct_answer_never_auto_marks_knowledge_mastered(client, bank, db_session):
    register_and_login(client, "bc5a_no_mastery")
    target = bank["by_stem"]["第一章选择一"]
    aid = _flow(client, answers={"question_ids": [target.id]})
    body = client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                       json={"answers": {str(target.id): target.standard_answer}}).json()
    assert body["correct_count"] == 1
    assert db_session.query(UserKnowledgeProgress).count() == 0


# ================================================================ H. typing / errors

def test_practice_write_requests_are_concrete_models():
    for name in ("ExamPracticeAttemptCreateRequest", "ExamPracticeWriteRequest"):
        model = getattr(main, name)
        assert not any(f.annotation is dict for f in model.model_fields.values() if isinstance(f.annotation, type))
        assert getattr(model, "__annotations__", None)
    source = inspect.getsource(main.create_chapter_practice_attempt)
    assert "req: ExamPracticeAttemptCreateRequest" in source
    assert "req: dict" not in source
    for handler in (main.get_chapter_practice_questions, main.get_chapter_practice_attempt,
                    main.save_chapter_attempt_answers, main.submit_chapter_attempt,
                    main.get_chapter_practice_outline):
        text = inspect.getsource(handler)
        assert "response_model=" in text, handler.__name__
        assert "req: dict" not in text


def test_write_requests_preserve_the_legacy_body_shape(client, bank):
    register_and_login(client, "bc5a_body")
    ids = [q.id for q in bank["chapter"]]
    # the legacy `username` echo is still accepted, and so is a bare answers object
    created = client.post("/exam/11408/data_structure/chapter-practice/attempts",
                          json={"question_ids": ids, "username": "bc5a_body"})
    assert created.status_code == 200
    aid = created.json()["attempt_id"]
    assert client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/answers",
                       json={"answers": {"1": "A"}, "username": "bc5a_body"}).status_code == 200
    assert client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/answers",
                       json={}).status_code == 200


def test_error_semantics_are_unchanged(client, bank):
    register_and_login(client, "bc5a_errors")
    assert client.get("/exam/11408/not_a_module/chapter-practice/outline").status_code == 400
    assert client.get("/exam/11408/not_a_module/chapter-practice/questions").status_code == 400
    assert client.get("/exam/11408/data_structure/chapter-practice/attempts/999999").status_code == 404
    assert client.post("/exam/11408/data_structure/chapter-practice/attempts/999999/answers",
                       json={"answers": {}}).status_code == 404
    assert client.post("/exam/11408/data_structure/chapter-practice/attempts",
                       json={"question_ids": [10 ** 9]}).status_code == 400
    assert client.post("/exam/11408/data_structure/chapter-practice/attempts",
                       json={"question_ids": "not-a-list"}).status_code == 422


def test_chapter_discovery_is_public_and_writes_are_authenticated(client, bank):
    # module/chapter discovery carries no entitlement today, so it stays reachable unauthenticated
    assert client.get("/exam/11408/data_structure/chapter-practice/outline").status_code == 200
    assert client.get("/exam/11408/data_structure/chapter-practice/questions").status_code in (401, 403)
    assert client.post("/exam/11408/data_structure/chapter-practice/attempts",
                       json={"question_ids": [1]}).status_code in (401, 403)


# ================================================================ I. real DB safety

def test_the_real_app_db_is_never_mutated(client, bank):
    before = hashlib.sha256(APP_DB.read_bytes()).hexdigest()
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
                  for t in ("exam_question_bank", "programming_exercises", "knowledge_points")}
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        tables = con.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]
    finally:
        con.close()
    assert counts == {"exam_question_bank": 9333, "programming_exercises": 1923, "knowledge_points": 32}
    assert integrity == "ok"

    register_and_login(client, "bc5a_db_safety")
    ids = [q.id for q in bank["chapter"]]
    aid = _flow(client, answers={"question_ids": ids})
    client.post(f"/exam/11408/data_structure/chapter-practice/attempts/{aid}/submit",
                json={"answers": {str(ids[0]): "A"}})

    assert hashlib.sha256(APP_DB.read_bytes()).hexdigest() == before
    assert tables == 72
