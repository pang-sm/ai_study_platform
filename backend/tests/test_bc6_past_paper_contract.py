"""FRONTEND_BLOCKER_BC6 — CS408 past-paper product contract normalization.

Gates this file exists to prove:

  * one public identity ``(subject_key, year, question_number)`` over BOTH real sources, with no
    unmapped, ambiguous or duplicate public keys;
  * neither source can leak an answer, an explanation or a grading result before submission, and
    no answer-bearing read is served anonymously;
  * a submitted attempt replays the authoritative results submit already persisted, keyed on the
    public identity, and the read path never grades;
  * a subjective answer is self-review when no authoritative grade was applied — never a fabricated
    midpoint score — while a real AI grade is preserved distinctly;
  * figures resolve to one safe application-relative URL, and traversal is rejected.
"""
import inspect
import json
from pathlib import Path

import pytest

from conftest import register_and_login
from models import ExamQuestionBank, PastPaperAttempt, PastPaperWrongQuestion, UserKnowledgeProgress
import exam_paper_parser
import exam_past_paper
import main

SUBJECT = "computer_organization"
YEAR = 2022
DOCUMENT_SUBJECT = "data_structure"

# Fields that must never appear on a pre-submit payload, from either source.
PROTECTED = ("standard_answer", "answer", "analysis", "review_notes", "correct", "judge", "score")


def _bank_rows(db, subject_key=SUBJECT, year=YEAR):
    return db.query(ExamQuestionBank).filter(
        ExamQuestionBank.subject_key == subject_key,
        ExamQuestionBank.source_type == "past_paper",
        ExamQuestionBank.year == year,
        ExamQuestionBank.is_active == True,  # noqa: E712
    ).all()


@pytest.fixture
def bank_paper(db_session):
    """A deterministic bank-backed paper: two choice questions and one big question."""
    rows = [
        ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理", source_type="past_paper",
                         visibility="public", year=YEAR, question_number=601, question_type="choice",
                         stem="BC6 选择题一", options_json=json.dumps({"A": "甲", "B": "乙"}),
                         standard_answer="A", analysis="BC6 解析一", is_active=True,
                         source_ref="past_paper:2022-Q601"),
        ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理", source_type="past_paper",
                         visibility="public", year=YEAR, question_number=602, question_type="choice",
                         stem="BC6 选择题二", options_json=json.dumps({"A": "甲", "B": "乙"}),
                         standard_answer="B", analysis="", is_active=True,
                         source_ref="past_paper:2022-Q602"),
        ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理", source_type="past_paper",
                         visibility="public", year=YEAR, question_number=603, question_type="big",
                         stem="BC6 大题", options_json="{}",
                         standard_answer="BC6 参考答案", analysis="BC6 大题解析", is_active=True,
                         source_ref="past_paper:2022-Q603"),
    ]
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
            PastPaperWrongQuestion.standard_answer.in_(["A", "B", "BC6 参考答案"])).delete(
            synchronize_session=False)
        db_session.query(ExamQuestionBank).filter(ExamQuestionBank.id.in_(ids)).delete(
            synchronize_session=False)
        db_session.commit()


def _flow(client, subject_key=SUBJECT, year=YEAR, answers=None):
    created = client.post(f"/exam/11408/{subject_key}/past-paper-attempts", json={"year": year})
    assert created.status_code == 200, created.text
    attempt_id = created.json()["attempt_id"]
    if answers is not None:
        client.post(f"/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers",
                    json={"answers": answers})
    return attempt_id


def _submit(client, attempt_id, answers, subject_key=SUBJECT):
    return client.post(f"/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit",
                       json={"answers": answers})


def _walk_protected(payload):
    """Every protected key present anywhere in a payload, with its value."""
    found = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in PROTECTED:
                    found.append((f"{path}.{key}", value))
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload)
    return found


def _has_document_source(subject_key=DOCUMENT_SUBJECT, year=YEAR):
    return exam_paper_parser._ocr_cache_path(subject_key, year).exists()


# ================================================================ A. identity


def test_public_identity_is_unique_and_complete_on_both_sources(db_session):
    seen = {}
    for subject_key in exam_past_paper.SUBJECT_NAMES:
        for paper in exam_past_paper.available_papers(db_session, subject_key):
            resolved = exam_past_paper.resolve_paper(db_session, subject_key, paper.year)
            keys = [q.question_number for q in resolved.questions]
            assert keys, f"{subject_key} {paper.year} has no questions"
            assert len(keys) == len(set(keys)), f"duplicate public keys in {subject_key} {paper.year}"
            assert all(isinstance(k, int) and k > 0 for k in keys), f"unmapped key in {subject_key}"
            for number in keys:
                key = (subject_key, paper.year, number)
                assert key not in seen, f"key claimed by two sources: {key} ({seen[key]} / {resolved.source})"
                seen[key] = resolved.source
    assert seen, "no papers resolved at all"


def test_both_real_sources_are_exercised(db_session, bank_paper):
    sources = set()
    for subject_key in exam_past_paper.SUBJECT_NAMES:
        for paper in exam_past_paper.available_papers(db_session, subject_key):
            sources.add(exam_past_paper.resolve_paper(db_session, subject_key, paper.year).source)
    assert "bank" in sources, "the bank source must own at least one real paper"
    assert "document" in sources, "the document source must own at least one real paper"


def test_paper_index_reports_factual_availability(client, bank_paper, db_session):
    register_and_login(client, "bc6_index")
    body = client.get(f"/exam/11408/{SUBJECT}/past-papers").json()
    entry = next(p for p in body["papers"] if p["year"] == YEAR)
    assert entry["question_count"] == len(_bank_rows(db_session))
    assert entry["source"] == "bank"
    assert entry["choice_count"] + entry["big_count"] == entry["question_count"]
    # availability is factual: nothing is advertised without real questions
    assert all(p["question_count"] > 0 for p in body["papers"])
    assert all(p["source"] in ("bank", "document") for p in body["papers"])


# ================================================================ B. security


def test_anonymous_reads_are_refused(client):
    anon = client
    for path in (f"/exam/11408/{SUBJECT}/past-papers",
                 f"/exam/11408/{SUBJECT}/past-paper-questions?year={YEAR}"):
        assert anon.get(path).status_code == 401, path


def test_pre_submit_question_list_leaks_nothing(client, bank_paper):
    register_and_login(client, "bc6_list")
    body = client.get(f"/exam/11408/{SUBJECT}/past-paper-questions?year={YEAR}").json()
    assert body["questions"]
    assert _walk_protected(body) == [], _walk_protected(body)[:3]


def test_pre_submit_attempt_detail_leaks_nothing(client, bank_paper):
    register_and_login(client, "bc6_pre")
    attempt_id = _flow(client)
    body = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    assert body["attempt"]["status"] == "in_progress"
    assert "results" not in body
    assert _walk_protected(body) == [], _walk_protected(body)[:3]


@pytest.mark.skipif(not _has_document_source(), reason="no document source in this checkout")
def test_document_source_leaks_nothing_before_submit(client):
    register_and_login(client, "bc6_doc_pre")
    body = client.get(f"/exam/11408/{DOCUMENT_SUBJECT}/past-paper-questions?year={YEAR}").json()
    assert body["source"] == "document"
    assert body["questions"]
    assert _walk_protected(body) == [], _walk_protected(body)[:3]
    attempt_id = _flow(client, DOCUMENT_SUBJECT)
    detail = client.get(f"/exam/11408/{DOCUMENT_SUBJECT}/past-paper-attempts/{attempt_id}").json()
    assert _walk_protected(detail) == [], _walk_protected(detail)[:3]


def test_generated_schema_cannot_express_a_pre_submit_answer():
    fields = set(exam_past_paper.PastPaperQuestion.model_fields)
    assert fields.isdisjoint(PROTECTED), fields & set(PROTECTED)
    assert set(exam_past_paper.PastPaperQuestionsResponse.model_fields) == {
        "subject_key", "subject_name", "year", "source", "questions"}


# ================================================================ C. grading semantics


def test_objective_question_is_graded_deterministically_by_the_backend(client, bank_paper):
    register_and_login(client, "bc6_grade")
    attempt_id = _flow(client)
    body = _submit(client, attempt_id, {"601": "A", "602": "A"}).json()
    by_number = {r["question_number"]: r for r in body["results"]}
    assert by_number[601]["correct"] is True and by_number[601]["judge"] is None
    assert by_number[602]["correct"] is False and by_number[602]["judge"] is None
    assert by_number[601]["score"] == 2 and by_number[602]["score"] == 0
    assert body["choice_correct"] == 1
    assert body["answer_grade"] == {"applied": False, "reason": "deterministic_bank_grading"}


def test_unavailable_ai_grade_becomes_self_review_and_never_a_midpoint_score(client, bank_paper):
    """The provider-free bank path must not invent a subjective score."""
    register_and_login(client, "bc6_selfreview")
    attempt_id = _flow(client)
    body = _submit(client, attempt_id, {"603": "我的作答"}).json()
    big = next(r for r in body["results"] if r["question_number"] == 603)
    assert big["judge"] == "self_review"
    assert big["correct"] is None
    assert big["score"] is None, "an ungraded subjective answer must not carry a score"
    assert big["full_score"] == 10, "full_score is factual paper metadata"
    assert big["standard_answer"] == "BC6 参考答案", "the reference answer is post-submit material"
    assert big["feedback"] == "请自行对照参考答案"
    assert body["self_review_count"] == 1 and body["ai_graded_count"] == 0
    assert body["total_score"] == 0
    assert str(body["total_score"]) != "5", "no fabricated midpoint"


def test_an_ungraded_subjective_answer_is_not_a_wrong_answer(client, bank_paper):
    register_and_login(client, "bc6_notwrong")
    attempt_id = _flow(client)
    _submit(client, attempt_id, {"601": "B", "603": "我的作答"})
    from database import SessionLocal
    session = SessionLocal()
    try:
        wrong = session.query(PastPaperWrongQuestion).filter(
            PastPaperWrongQuestion.year == YEAR).all()
        numbers = {w.question_number for w in wrong}
    finally:
        session.close()
    assert 601 in numbers, "a wrong objective answer is still a wrong answer"
    assert 603 not in numbers, "an ungraded subjective answer is not a wrong answer"


def test_static_analysis_is_optional_and_never_manufactured(client, bank_paper):
    register_and_login(client, "bc6_analysis")
    attempt_id = _flow(client)
    body = _submit(client, attempt_id, {"601": "A", "602": "A", "603": "作答"}).json()
    by_number = {r["question_number"]: r for r in body["results"]}
    assert by_number[601]["analysis"] == "BC6 解析一"
    assert by_number[602]["analysis"] is None, "an empty analysis stays absent, not invented"


# ================================================================ D. replay


def test_submitted_detail_replays_the_persisted_result(client, bank_paper):
    register_and_login(client, "bc6_replay")
    attempt_id = _flow(client)
    submitted = _submit(client, attempt_id, {"601": "A", "603": "作答"}).json()
    detail = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    assert detail["attempt"]["status"] == "submitted"
    assert detail["results"] == submitted["results"]
    assert {r["question_number"] for r in detail["results"]} == {601, 602, 603}


def test_detail_never_regrades(client, bank_paper, monkeypatch):
    """Flip the persisted verdict: only a replay can answer with the flipped value."""
    register_and_login(client, "bc6_noregrade")
    attempt_id = _flow(client)
    _submit(client, attempt_id, {"601": "A"})

    from database import SessionLocal
    session = SessionLocal()
    try:
        attempt = session.query(PastPaperAttempt).filter(PastPaperAttempt.id == attempt_id).one()
        blob = json.loads(attempt.result_json)
        for result in blob["results"]:
            if str(result.get("type")) == "选择题":
                result["correct"] = not result["correct"]
        attempt.result_json = json.dumps(blob, ensure_ascii=False)
        session.commit()
    finally:
        session.close()

    def _explode(*_args, **_kwargs):
        raise AssertionError("the submit grading path must not run on a read")

    monkeypatch.setattr(exam_paper_parser, "grade_submission", _explode)
    detail = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    flipped = next(r for r in detail["results"] if r["question_number"] == 601)
    assert flipped["correct"] is False, "the replay must return the stored verdict"


def test_no_regrade_helper_is_called_on_the_read_path():
    source = inspect.getsource(main.get_past_paper_attempt)
    assert "grade_submission" not in source
    assert "grade_big" not in source
    assert "submit_attempt" not in source


def test_submitted_detail_of_an_unsubmitted_attempt_has_no_results(client, bank_paper):
    register_and_login(client, "bc6_nosubmit")
    attempt_id = _flow(client)
    body = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    assert "results" not in body


# ================================================================ E. resources


def test_resource_url_is_application_relative_and_leaks_no_path(client, bank_paper):
    register_and_login(client, "bc6_resource")
    client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts", json={"year": YEAR})
    questions = client.get(f"/exam/11408/{SUBJECT}/past-paper-questions?year={YEAR}").json()["questions"]
    for question in questions:
        for resource in question["resources"]:
            url = resource["url"]
            assert url.startswith("/exam/11408/past-paper-images/"), url
            assert ":" not in url and "\\" not in url, f"filesystem leaked: {url}"
            assert ".." not in url


def test_existing_figure_is_reachable_over_http(client, bank_paper):
    register_and_login(client, "bc6_figure")
    resolved_any = False
    for subject_key in exam_past_paper.SUBJECT_NAMES:
        for year in (2022,):
            candidates = exam_past_paper._scan_asset_filenames(subject_key, year, 12) or []
            for name in candidates[:1]:
                if exam_past_paper.resolve_resource_file(subject_key, year, name) is None:
                    continue
                response = client.get(f"/exam/11408/past-paper-images/{subject_key}/{year}/{name}")
                assert response.status_code == 200, f"{subject_key}/{year}/{name}"
                assert response.headers["content-type"].startswith("image/")
                resolved_any = True
    if not resolved_any:
        pytest.skip("no figure assets in this checkout")


def test_traversal_and_bad_filenames_are_rejected(client, bank_paper):
    register_and_login(client, "bc6_traversal")
    for bad in ("..%2F..%2Fapp.db", "....%2F%2Fapp.db", "main.py", "not-an-image.txt", "a/b.jpg"):
        response = client.get(f"/exam/11408/past-paper-images/{SUBJECT}/{YEAR}/{bad}")
        assert response.status_code == 404, f"{bad} -> {response.status_code}"
    assert exam_past_paper.resolve_resource_file(SUBJECT, YEAR, "../../app.db") is None
    assert exam_past_paper.resolve_resource_file("../../etc", YEAR, "x.jpg") is None


# ------------------------------------------------ assets: reachability + honest missing state


def test_every_advertised_resource_actually_serves(client, bank_paper, db_session):
    """The contract must never hand the frontend a URL that 404s."""
    register_and_login(client, "bc6_advertised")
    checked = 0
    for subject_key in exam_past_paper.SUBJECT_NAMES:
        for paper in exam_past_paper.available_papers(db_session, subject_key):
            resolved = exam_past_paper.resolve_paper(db_session, subject_key, paper.year)
            for question in resolved.questions:
                public = exam_past_paper.public_question(question, subject_key, paper.year)
                assert public.missing_resources == [], (
                    f"{subject_key} {paper.year} Q{question.question_number} "
                    f"-> {public.missing_resources}")
                for resource in public.resources:
                    filename = resource.url.rsplit("/", 1)[-1]
                    response = client.get(
                        f"/exam/11408/past-paper-images/{subject_key}/{paper.year}/{filename}")
                    assert response.status_code == 200, resource.url
                    checked += 1
    assert checked > 0, "no resource was exercised"


def test_missing_resources_surfaces_a_reference_that_cannot_resolve(bank_paper):
    """A broken reference is reported, never silently dropped."""
    question = exam_past_paper.ResolvedQuestion(
        question_number=901, question_type="big", stem="如题 901 图所示",
        options={}, standard_answer="参考答案", analysis="",
        full_score=10, resource_filenames=["definitely_absent_901_0.jpg"])
    public = exam_past_paper.public_question(question, SUBJECT, YEAR)
    assert public.resources == []
    assert public.missing_resources == ["definitely_absent_901_0.jpg"]


def test_recovered_operating_system_2022_q46_figure_is_reachable(client, bank_paper):
    """The one figure BC6 initially reported absent: recovered from the document source.

    The bank row for `operating_system` 2022 Q46 had no mapping entry and no `2022_46_*` asset,
    while the same paper's OCR cache references `.../2022/img_14.jpg`, which exists on disk. It is
    now part of the curated mapping and served through the one resource route.
    """
    register_and_login(client, "bc6_q46")
    names = exam_past_paper._bank_resources("operating_system", 2022, 46)
    if not names:
        pytest.skip("operating_system 2022 Q46 has no asset in this checkout")
    assert "img_14.jpg" in names
    assert exam_past_paper.resolve_resource_file("operating_system", 2022, "img_14.jpg") is not None

    response = client.get("/exam/11408/past-paper-images/operating_system/2022/img_14.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert len(response.content) > 1000, "a real figure, not a placeholder"

    mapping = json.loads(
        (exam_past_paper.EXAM_RESOURCES_DIR / "operating_system" / "past_papers"
         / "image_mapping.json").read_text(encoding="utf-8"))
    assert "2022-46" in mapping, "the recovered figure must be recorded in the curated mapping"


# ================================================================ F. boundaries


def test_paper_source_isolation_holds(client, bank_paper, db_session):
    register_and_login(client, "bc6_isolation")
    attempt_id = _flow(client)
    detail = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    numbers = [q["question_number"] for q in detail["questions"]]
    assert set(numbers) == set(bank_paper)
    assert all(q["question_type"] in ("choice", "big") for q in detail["questions"])


def test_wrong_records_belong_to_the_backend_and_no_mastery_is_written(client, bank_paper):
    register_and_login(client, "bc6_wrong")
    attempt_id = _flow(client)
    _submit(client, attempt_id, {"601": "B"})
    from database import SessionLocal
    session = SessionLocal()
    try:
        rows = session.query(PastPaperWrongQuestion).filter(
            PastPaperWrongQuestion.attempt_id == attempt_id).all()
        assert rows and all(r.username == "bc6_wrong" for r in rows)
        assert session.query(UserKnowledgeProgress).filter(
            UserKnowledgeProgress.username == "bc6_wrong").count() == 0
    finally:
        session.close()


def test_attempt_ownership_is_enforced(client, bank_paper):
    register_and_login(client, "bc6_owner")
    attempt_id = _flow(client)
    client.post("/logout")
    register_and_login(client, "bc6_intruder")
    assert client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").status_code == 404
    assert _submit(client, attempt_id, {"601": "A"}).status_code == 404


def test_answers_are_keyed_by_public_question_number(client, bank_paper):
    register_and_login(client, "bc6_keying")
    questions = client.get(f"/exam/11408/{SUBJECT}/past-paper-questions?year={YEAR}").json()
    attempt_id = _flow(client, answers={"601": "A"})
    detail = client.get(f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}").json()
    assert detail["saved_answers"] == {"601": "A"}
    # no source-specific id ever reaches the client
    assert all("id" not in q for q in questions["questions"])
    assert all(isinstance(q["question_number"], int) for q in questions["questions"])


# ================================================================ G. OpenAPI


def test_every_required_endpoint_is_concretely_typed():
    schemas = main.app.openapi()["components"]["schemas"]
    paths = main.app.openapi()["paths"]
    required = {
        ("/exam/11408/{subject_key}/past-papers", "get"): "PastPaperIndexResponse",
        ("/exam/11408/{subject_key}/past-paper-questions", "get"): "PastPaperQuestionsResponse",
        ("/exam/11408/{subject_key}/past-paper-attempts", "post"): "PastPaperAttemptCreateResponse",
        ("/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}", "get"): "PastPaperAttemptDetailResponse",
        ("/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers", "post"): "PastPaperAnswerSaveResponse",
        ("/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit", "post"): "PastPaperSubmitResponse",
    }
    for (path, method), model in required.items():
        schema = paths[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema.get("$ref", "").endswith(model), f"{path} -> {schema}"
        assert model in schemas

    for path in ("/exam/11408/{subject_key}/past-paper-attempts",
                 "/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers",
                 "/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit"):
        body = paths[path]["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert body.get("$ref"), f"{path} request body is untyped: {body}"

    image = paths["/exam/11408/past-paper-images/{subject_key}/{year}/{filename}"]["get"]
    assert "image/jpeg" in image["responses"]["200"]["content"]
