"""STEP 7H3: Exam AI runs on the unified boundary.

    Exam endpoint → authenticated user → canonical Exam LearningContext → execute_exam_ai
                  → AIOrchestrator → capability → router → estimate → reserve → gateway
                  → actual usage → settlement → domain postprocess

Never a live provider: the outbound call is replaced by ``FakeProvider`` while the real
permission / router / pool / estimate / reserve / settle lifecycle runs. The one declared
exception is ``qwen_parser`` OCR, which is PARSER_OCR infrastructure.
"""
import dataclasses
import inspect
import json
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from ai.providers import FakeProvider
from core.learning_context import ServiceNamespace
from data_plane.models import LearningEvent
from learning.spaces.exam_prep.ai import GradeOutputError, grade_big_answer
from learning.spaces.exam_prep.context import cs408_context
from models import ExamQuestionBank, PastPaperAttempt, User
from usage import service as usage_service
from usage.models import AICostRecord, AIRequest, UsageLedger
from conftest import register_and_login
import exam_paper_parser
import main

EXAM = ServiceNamespace.EXAM_PREP
CS408 = "cs_408"


# ---------------------------------------------------------------- doubles

class CountingProvider(FakeProvider):
    def __init__(self, calls: list, content: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._calls = calls
        self._content = content

    def complete(self, spec):
        self._calls.append((self.name, spec.model, spec.capability))
        response = super().complete(spec)
        if self._content is None:
            return response
        return dataclasses.replace(response, content=self._content)


def _factory(calls: list, content: str | None = None):
    def _make(name: str) -> FakeProvider:
        return CountingProvider(calls, content=content, provider=name,
                                input_tokens=50, output_tokens=50)
    return _make


@pytest.fixture
def provider(monkeypatch):
    calls: list = []

    def _install(content: str | None = None) -> list:
        monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                            _factory(calls, content))
        return calls

    return _install


@pytest.fixture(autouse=True)
def no_legacy_exam_provider(monkeypatch):
    """Any exam path that still reaches the legacy client fails loudly."""
    monkeypatch.setattr(main, "call_deepseek", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Exam AI reached the legacy direct provider client")))


def _user(session, username, tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        usage_service.activate_subscription(session, u.id, tier, 30)
    return u


def _activate(username, tier):
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        usage_service.activate_subscription(db, user.id, tier, 30)


def _fresh_request(username):
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        return (db.query(AIRequest).filter(AIRequest.user_id == user.id)
                .order_by(AIRequest.id.desc()).first())


# ---------------------------------------------------------------- B15 tier matrix

FREE_ALLOWED = ("tutor.chat", "material.qa", "question.explain")
FREE_DENIED = ("question.generate", "planning.generate", "report.generate", "answer.grade")
STANDARD_EXTRA = ("question.generate", "planning.generate", "answer.grade")


@pytest.mark.parametrize("capability", FREE_ALLOWED)
def test_free_exam_capabilities_pass(db_session, provider, capability):
    u = _user(db_session, f"h3_free_{capability.replace('.', '_')}")
    calls = provider()
    from learning.spaces.exam_prep.ai import execute_exam_ai
    result = execute_exam_ai(db_session, u, capability,
                             [{"role": "user", "content": "hi"}],
                             learning_context=cs408_context(u, module_key="data_structure"),
                             max_tokens=200)
    assert result.status == "settled"
    assert len(calls) == 1


@pytest.mark.parametrize("capability", FREE_DENIED)
def test_free_exam_capabilities_are_denied_before_the_provider(db_session, provider, capability):
    u = _user(db_session, f"h3_freed_{capability.replace('.', '_')}")
    calls = provider()
    from learning.spaces.exam_prep.ai import execute_exam_ai
    with pytest.raises(HTTPException) as exc:
        execute_exam_ai(db_session, u, capability, [{"role": "user", "content": "hi"}],
                        learning_context=cs408_context(u, module_key="data_structure"),
                        max_tokens=200)
    assert exc.value.status_code == 403
    assert calls == []
    assert db_session.query(AIRequest).filter(AIRequest.user_id == u.id).count() == 0


@pytest.mark.parametrize("capability", STANDARD_EXTRA)
def test_standard_exam_capabilities_pass(db_session, provider, capability):
    u = _user(db_session, f"h3_std_{capability.replace('.', '_')}", tier="standard")
    calls = provider()
    from learning.spaces.exam_prep.ai import execute_exam_ai
    result = execute_exam_ai(db_session, u, capability,
                             [{"role": "user", "content": "hi"}],
                             learning_context=cs408_context(u, module_key="operating_system"),
                             max_tokens=200)
    assert result.status == "settled"
    assert len(calls) == 1


def test_standard_is_denied_report_generate(db_session, provider):
    u = _user(db_session, "h3_std_report", tier="standard")
    calls = provider()
    from learning.spaces.exam_prep.ai import execute_exam_ai
    with pytest.raises(HTTPException) as exc:
        execute_exam_ai(db_session, u, "report.generate", [{"role": "user", "content": "hi"}],
                        learning_context=cs408_context(u, module_key="data_structure"),
                        max_tokens=200)
    assert exc.value.status_code == 403
    assert calls == []


def test_advanced_may_use_report_generate(db_session, provider):
    u = _user(db_session, "h3_adv_report", tier="advanced")
    calls = provider()
    from learning.spaces.exam_prep.ai import execute_exam_ai
    result = execute_exam_ai(db_session, u, "report.generate",
                             [{"role": "user", "content": "hi"}],
                             learning_context=cs408_context(u, module_key="data_structure"),
                             max_tokens=200)
    assert result.status == "settled"
    assert len(calls) == 1


def test_budget_exhaustion_denies_before_the_provider(db_session, provider):
    u = _user(db_session, "h3_budget", tier="standard")
    calls = provider()
    budget = usage_service.get_or_create_budget(db_session, u.id, "daily")
    budget.settled_amount = budget.budget_amount
    db_session.commit()
    from learning.spaces.exam_prep.ai import execute_exam_ai
    with pytest.raises(HTTPException) as exc:
        execute_exam_ai(db_session, u, "answer.grade", [{"role": "user", "content": "hi"}],
                        learning_context=cs408_context(u, module_key="data_structure"),
                        max_tokens=200)
    assert exc.value.status_code == 429
    assert calls == []



@pytest.fixture
def synthetic_paper(monkeypatch):
    """One subjective question, so the AI grading path is reachable without a docx.

    BC6: the normalized adapter and the grading parser must read the SAME document source. The
    adapter resolves questions through ``document_questions`` (cache first, parser second) while
    grading goes through ``get_year_questions``, so the cache lookup is redirected too — otherwise
    the real repository cache would answer the adapter while the patch answered the grader.
    """
    def _install(subject_key="data_structure", year=2022):
        monkeypatch.setattr(exam_paper_parser, "get_year_questions",
                            lambda *a, **k: {"questions": [
                                {"id": "1", "type": "大题", "number": 45,
                                 "content": "简述进程与线程的区别",
                                 "answer": "进程是资源分配单位，线程是调度单位"},
                            ], "subject_name": subject_key})
        monkeypatch.setattr(exam_paper_parser, "_ocr_cache_path",
                            lambda *a, **k: Path(tempfile.gettempdir()) / "bc6-no-such-cache.json")
    return _install


# ---------------------------------------------------------------- B16 answer.grade

_GRADE_JSON = json.dumps({"score": 8, "feedback": "思路正确，第三步可再展开。"},
                         ensure_ascii=False)


def test_grade_big_answer_returns_validated_score(db_session, provider):
    u = _user(db_session, "h3_grade", tier="standard")
    calls = provider(content=_GRADE_JSON)
    score, feedback = grade_big_answer(
        db_session, u, learning_context=cs408_context(u, module_key="operating_system"),
        stem="简述进程与线程的区别", standard_answer="进程是资源分配单位…",
        user_answer="进程有独立地址空间", subject_name="操作系统", question_number=45)
    assert score == 8
    assert "思路正确" in feedback
    assert len(calls) == 1
    assert calls[0][2] == "answer.grade"


def test_grade_big_answer_rejects_out_of_range_score(db_session, provider):
    u = _user(db_session, "h3_grade_bad", tier="standard")
    calls = provider(content=json.dumps({"score": 99, "feedback": "x"}))
    with pytest.raises(GradeOutputError):
        grade_big_answer(db_session, u,
                         learning_context=cs408_context(u, module_key="operating_system"),
                         stem="s", standard_answer="a", user_answer="b")
    # the provider call DID happen and already settled its measured usage
    assert len(calls) == 1
    req = _fresh_request("h3_grade_bad")
    assert db_session.query(AICostRecord).filter(
        AICostRecord.request_id == req.request_id).count() == 1
    assert req.status == "settled"


def test_grade_big_answer_rejects_non_json_output(db_session, provider):
    u = _user(db_session, "h3_grade_nj", tier="standard")
    provider(content="抱歉，我无法评分。")
    with pytest.raises(GradeOutputError):
        grade_big_answer(db_session, u,
                         learning_context=cs408_context(u, module_key="operating_system"),
                         stem="s", standard_answer="a", user_answer="b")


def test_grade_context_equivalence(db_session, provider):
    """AIRequest / ai_called / UsageLedger carry ONE canonical exam context."""
    u = _user(db_session, "h3_grade_ctx", tier="standard")
    provider(content=_GRADE_JSON)
    ctx = cs408_context(u, module_key="computer_network")
    score, _ = grade_big_answer(db_session, u, learning_context=ctx, stem="s",
                                standard_answer="a", user_answer="b",
                                subject_name="计算机网络", question_number=47)
    assert score == 8
    db_session.expire_all()

    req = _fresh_request("h3_grade_ctx")
    assert req.service_namespace == "exam_prep"
    assert req.capability == "answer.grade"
    assert req.context_json["exam_subject_id"] == CS408
    assert req.context_json["exam_module_id"] == "computer_network"
    assert req.context_json["subject_key"] == "computer_network"

    ledger = (db_session.query(UsageLedger)
              .filter(UsageLedger.request_id == req.request_id).all())
    assert ledger and {row.service_namespace for row in ledger} == {"exam_prep"}

    event = (db_session.query(LearningEvent)
             .filter(LearningEvent.source_attempt_id == req.request_id,
                     LearningEvent.event_type == "ai_called").one())
    assert event.service_key == "exam_prep"
    assert event.subject_key == CS408
    assert json.loads(event.knowledge_point_ref_json)["exam_module_id"] == "computer_network"


# ---------------------------------------------------------------- B5.2 / B5 parser

def test_parser_module_owns_no_provider_client():
    src = Path(exam_paper_parser.__file__).read_text(encoding="utf-8")
    assert "OpenAI(" not in src
    assert "chat.completions" not in src
    assert "DEEPSEEK_API_KEY" not in src
    assert not hasattr(exam_paper_parser, "_grade_big_question")


def test_grade_submission_without_an_injected_grader_never_reaches_a_provider(monkeypatch):
    """The parser's default path is provider-free (it is the injected grader that calls AI)."""
    monkeypatch.setattr(exam_paper_parser, "get_year_questions",
                        lambda *a, **k: {"questions": [
                            {"id": "1", "type": "大题", "number": 45, "content": "题干",
                             "answer": "参考答案内容"}]})
    monkeypatch.setattr(main, "call_deepseek", lambda *a, **k: pytest.fail(
        "parser reached a provider"))
    result = exam_paper_parser.grade_submission("operating_system", 2022,
                                                [{"question_id": "1",
                                                  "user_answer": "参考答案内容"}])
    assert result["results"][0]["feedback"] == "AI暂不可用,基础评分"


def _seed_bank_paper(db_session, *, subject_key="computer_network", year=2022,
                     with_rows=True):
    if with_rows:
        db_session.add(ExamQuestionBank(
            subject_key=subject_key, subject_name="计算机网络", source_type="past_paper",
            year=year, question_number=33, question_type="choice", stem="题干",
            standard_answer="A", is_active=True, source_ref="past_paper:2022-Q33"))
        db_session.commit()


def _past_paper_attempt(db_session, user, *, subject_key="computer_network", year=2022):
    row = PastPaperAttempt(
        username=user.username, mode="11408", subject_key=subject_key,
        subject_name=subject_key, year=year, attempt_no=1, status="in_progress",
        total_questions=1, answers_json="{}", result_json="{}")
    db_session.add(row)
    db_session.commit()
    return row


def test_deterministic_grade_path_makes_zero_provider_calls(client, provider, monkeypatch):
    """Bank rows exist → every question is graded without a model."""
    register_and_login(client, "h3_det")
    _activate("h3_det", "standard")
    calls = provider()
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == "h3_det").one()
        _seed_bank_paper(db, with_rows=True)
        attempt = _past_paper_attempt(db, user)
        attempt_id = attempt.id
        assert db.query(ExamQuestionBank).filter(
            ExamQuestionBank.year == 2022, ExamQuestionBank.is_active == True).count() == 1

    # BC6: answers are keyed by the public question number, not a source-specific id.
    r = client.post(f"/exam/11408/computer_network/past-paper-attempts/{attempt_id}/submit",
                    json={"username": "h3_det", "answers": {"33": "B"}})
    assert r.status_code == 200, r.text
    assert r.json()["answer_grade"]["applied"] is False
    assert r.json()["answer_grade"]["reason"] == "deterministic_bank_grading"
    assert calls == [], "the deterministic path must not invoke a provider"

    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == "h3_det").one()
        reqs = db.query(AIRequest).filter(AIRequest.user_id == user.id).count()
    assert reqs == 0


def test_ai_grade_path_uses_the_result_and_settles_it(client, provider, synthetic_paper):
    """No bank rows → the model grades, and its score is what the learner gets."""
    synthetic_paper()
    register_and_login(client, "h3_aig")
    _activate("h3_aig", "standard")
    calls = provider(content=_GRADE_JSON)
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == "h3_aig").one()
        attempt = _past_paper_attempt(db, user, subject_key="data_structure")
        attempt_id = attempt.id

    r = client.post("/exam/11408/data_structure/past-paper-attempts/{}/submit".format(attempt_id),
                    json={"username": "h3_aig", "answers": {"45": "我的作答"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer_grade"]["applied"] is True
    assert len(calls) == 1
    assert calls[0][2] == "answer.grade"
    assert body["results"][0]["score"] == 8, "the AI score must be USED, not discarded"
    assert "思路正确" in body["results"][0]["feedback"]

    with database.SessionLocal() as db:
        req = (db.query(AIRequest).filter(AIRequest.capability == "answer.grade")
               .order_by(AIRequest.id.desc()).first())
        assert req.service_namespace == "exam_prep"
        assert db.query(AICostRecord).filter(
            AICostRecord.request_id == req.request_id).count() == 1
        ledger = db.query(UsageLedger).filter(UsageLedger.request_id == req.request_id).all()
        assert {r.service_namespace for r in ledger} == {"exam_prep"}


def test_free_user_submission_survives_a_denied_ai_grade(client, provider, synthetic_paper):
    """The submission is the durable fact; a refused AI grade must not lose it."""
    synthetic_paper()
    register_and_login(client, "h3_freedenied")
    calls = provider(content=_GRADE_JSON)
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == "h3_freedenied").one()
        attempt = _past_paper_attempt(db, user, subject_key="data_structure")
        attempt_id = attempt.id

    r = client.post("/exam/11408/data_structure/past-paper-attempts/{}/submit".format(attempt_id),
                    json={"username": "h3_freedenied", "answers": {"45": "作答"}})
    assert r.status_code == 200, r.text
    assert r.json()["answer_grade"]["applied"] is False
    assert r.json()["answer_grade"]["reason"] == "answer_grade_unavailable_403"
    assert calls == [], "a denied capability must not invoke a provider"

    import database as _db
    with _db.SessionLocal() as db:
        assert db.query(PastPaperAttempt).filter(
            PastPaperAttempt.id == attempt_id).one().status == "submitted"


# ---------------------------------------------------------------- B17 reachability

EXAM_AI_ENDPOINT_FUNCTIONS = (
    "generate_exam_ai_questions", "generate_question_analysis", "submit_attempt",
    "get_past_paper_questions", "chat", "handle_material_upload",
    "structure_practice_paper_text", "refine_question_analysis_with_ai",
    "_repair_json_with_ai", "_generate_plan_preview_core",
)


def test_exam_endpoints_reach_the_exam_boundary():
    src = inspect.getsource(main)
    for fn in EXAM_AI_ENDPOINT_FUNCTIONS:
        body = _function_source(src, fn)
        assert body, fn
        assert ("_exam_ai_content" in body or "_scoped_ai_content" in body
                or "execute_exam_ai" in body or "GradeOutputError" in body
                or "_paper_big_answer_grader" in body
                # BC6: past-paper reads delegate to the shared normalization adapter instead of
                # touching a source parser directly.
                or "exam_past_paper" in body
                or "get_year_questions" in body), f"{fn} does not reach the exam boundary"


def _function_source(src, name):
    import ast
    tree = ast.parse(src)
    lines = src.split("\n")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    return ""


def test_no_exam_ai_path_uses_a_legacy_quota_gate():
    """EXAM_AI_LEGACY_AUTH_OWNER = 0: the legacy exam quota no longer decides AI."""
    src = inspect.getsource(main)
    assert "check_exam_408_usage_limit(" not in src.replace(
        "def check_exam_408_usage_limit(user: models.User, feature: str, db: Session):", "")


def test_ocr_stays_infrastructure():
    """PARSER_OCR is deliberately NOT migrated to the orchestrator."""
    import qwen_parser
    src = Path(qwen_parser.__file__).read_text(encoding="utf-8")
    assert "OpenAI(" in src, "OCR keeps its own vision client — it is not learning AI"


# ---------------------------------------------------------------- B19 cross-space

def test_course_exam_and_programming_stay_apart(client, provider):
    register_and_login(client, "h3_cross")
    _activate("h3_cross", "standard")
    calls = provider(content=json.dumps({"items": [{"title": "x"}]}))

    exam = client.post("/knowledge-points/generate-preview",
                       json={"username": "h3_cross", "course_id": "data_structure_11408",
                             "course_name": "11408 数据结构", "mode": "course_name"})
    assert exam.status_code == 200, exam.text
    req = _fresh_request("h3_cross")
    assert req.service_namespace == "exam_prep", "course_id=data_structure is a MODULE here"

    course = client.post("/knowledge-points/generate-preview",
                         json={"username": "h3_cross", "course_id": "data_structure",
                               "course_name": "数据结构", "mode": "course_name"})
    assert course.status_code == 200, course.text
    req2 = _fresh_request("h3_cross")
    assert req2.service_namespace == "course_learning"
    assert req2.request_id != req.request_id
