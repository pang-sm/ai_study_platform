"""FRONTEND_BLOCKER_BC5B — Exam `question.explain` contract closure.

Closes the EXAM question.explain route only:

    POST /exam/11408/{subject_key}/question-analysis
      → generate_question_analysis
      → execute_exam_ai(db, user, "question.explain", …)
      → AIOrchestrator → capability permission → router → estimate → reserve
      → gateway → actual usage → settle

What this suite locks down:
  * the OpenAPI request/response are CONCRETE (no unknown body, no unknown 2xx);
  * the route reaches the orchestrator with capability ``question.explain`` and never a
    direct provider HTTP client;
  * typing the transport did not change runtime bytes for a valid caller;
  * the endpoint is answer-BLIND: it reads no question row, so it cannot disclose an
    authoritative standard answer pre-submit;
  * no side effect outside the unified AI accounting (grade / wrong record / knowledge
    status / learner state / attempt / static analysis all stay untouched);
  * one billable lifecycle per call.

No live provider is ever contacted: the outbound call is replaced at the orchestrator's
provider factory, so permission / router / pool / estimate / reserve / settle all run for
real against a deterministic double.
"""
import dataclasses
import inspect
import json

import pytest
from fastapi import HTTPException

from ai.gateway import GatewayError, GatewayErrorCategory
from ai.orchestrator import OrchestratorResult
from ai.providers import FakeProvider
from conftest import register_and_login
import database
import main
import models
from usage.models import AICostRecord, AIRequest, UsageLedger

ROUTE = "/exam/11408/{subject_key}/question-analysis"
SUBJECT = "data_structure"
CAPABILITY = "question.explain"

# The 200 body the route returned before BC5B typed it (raw `dict` handler, untyped 2xx).
PRE_TYPING_SUCCESS_KEYS = ["analysis", "generated_at", "model", "request_id"]


# ---------------------------------------------------------------- doubles

@pytest.fixture
def provider(monkeypatch):
    """Deterministic provider double installed at the orchestrator's provider factory."""
    calls: list = []

    def _factory(name: str) -> FakeProvider:
        def _complete(spec):
            calls.append({"provider": name, "model": spec.model,
                          "capability": spec.capability, "stream": spec.stream})
            return FakeProvider(provider=name, model=spec.model or "fake-model",
                                input_tokens=50, output_tokens=50).complete(spec)
        instance = FakeProvider(provider=name, model="fake-model",
                                input_tokens=50, output_tokens=50)
        instance.complete = _complete
        return instance

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _factory)
    return calls


@pytest.fixture(autouse=True)
def no_legacy_direct_provider(monkeypatch):
    """A direct provider client on this route is a semantic blocker, not a style issue."""
    monkeypatch.setattr(main, "call_deepseek", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Exam question.explain reached a legacy direct provider client")))


def _orchestrator_returning(monkeypatch, **kwargs):
    """Refuse at the orchestrator boundary without touching permission/router/gateway."""
    class _Stub:
        def execute(self, *_a, **_kw):
            return OrchestratorResult(request_id="stub-request", capability=CAPABILITY,
                                      tier=kwargs.pop("tier", "free"), **kwargs)

    monkeypatch.setattr("learning.spaces.exam_prep.ai.AIOrchestrator", _Stub)


def _post(client, monkeypatch, **body):
    """Post the route with the legacy-shaped payload, outside the double's lifecycle."""
    with monkeypatch.context() as ctx:
        ctx.setattr("ai.orchestrator.default_provider_factory",
                    lambda name: FakeProvider(provider=name, model="deepseek-flash"))
        return client.post(ROUTE.format(subject_key=SUBJECT), json=body)


def _attempt_fixture(client, username):
    """A real submitted chapter-practice attempt: one choice question, answered WRONG."""
    register_and_login(client, username)
    with database.SessionLocal() as db:
        db.add(models.ExamQuestionBank(
            subject_key=SUBJECT, subject_name="数据结构", source_type="chapter_practice",
            question_type="choice",
            stem="线性表的顺序存储与链式存储，哪个支持 O(1) 随机访问？",
            options_json=json.dumps({"A": "顺序存储", "B": "链式存储"}, ensure_ascii=False),
            standard_answer="A", analysis="静态解析：顺序存储下标直接寻址。",
            is_active=True, source_ref=f"{username}:Q1"))
        db.commit()
        bank_id = (db.query(models.ExamQuestionBank)
                   .filter(models.ExamQuestionBank.source_ref == f"{username}:Q1")
                   .one().id)

    created = client.post(f"/exam/11408/{SUBJECT}/chapter-practice/attempts",
                          json={"question_ids": [bank_id]})
    assert created.status_code == 200, created.text
    attempt_id = created.json()["attempt_id"]
    submitted = client.post(
        f"/exam/11408/{SUBJECT}/chapter-practice/attempts/{attempt_id}/submit",
        json={"answers": {str(bank_id): "B"}})
    assert submitted.status_code == 200, submitted.text
    return bank_id, attempt_id, submitted.json()["results"][0]


def _side_effect_snapshot(username):
    """Everything section 14 forbids this route from writing."""
    with database.SessionLocal() as db:
        return {
            "attempts": [(a.id, a.status, a.correct_count, a.wrong_count, a.accuracy,
                          a.result_json, a.answers_json)
                         for a in db.query(models.ExamPracticeAttempt)
                         .filter(models.ExamPracticeAttempt.username == username).all()],
            "wrong": [(w.id, w.status, w.user_answer, w.mastered, w.review_count,
                       w.standard_answer_snapshot, w.analysis_snapshot)
                      for w in db.query(models.ExamWrongQuestion)
                      .filter(models.ExamWrongQuestion.username == username).all()],
            "done": [(d.id, d.is_correct, d.done_count)
                     for d in db.query(models.ExamQuestionDoneRecord)
                     .filter(models.ExamQuestionDoneRecord.username == username).all()],
            "bank": [(q.id, q.stem, q.standard_answer, q.analysis)
                     for q in db.query(models.ExamQuestionBank).all()],
            "knowledge": [(k.id, k.status, k.mastery_score, k.learned_at,
                           k.review_interval_days)
                          for k in db.query(models.UserKnowledgeProgress)
                          .filter(models.UserKnowledgeProgress.username == username).all()],
            "knowledge_events": db.query(models.KnowledgeProgressEvent).count(),
            "learning_records": db.query(models.LearningRecord).count(),
            "ai_requests": db.query(AIRequest).count(),
        }


# ---------------------------------------------------------------- 1-2 OpenAPI concrete

def test_request_schema_is_concrete(client):
    spec = client.get("/openapi.json").json()
    body = spec["paths"][ROUTE]["post"]["requestBody"]
    schema = body["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/ExamQuestionAnalysisRequest"}

    props = spec["components"]["schemas"]["ExamQuestionAnalysisRequest"]["properties"]
    assert set(props) == {"stem", "options", "standard_answer", "user_answer",
                          "question_type", "context"}
    assert props["options"] == {"additionalProperties": {"type": "string"}, "type": "object",
                                "title": "Options"}
    assert props["stem"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    # no transport field is a free-form `Any` / bare object
    for name, prop in props.items():
        assert prop.get("title") != "Any", name
        assert prop.get("type") != "object" or name == "options", name


def test_success_response_is_concrete(client):
    spec = client.get("/openapi.json").json()
    resp = spec["paths"][ROUTE]["post"]["responses"]["200"]
    assert resp["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ExamQuestionAnalysisResponse"}
    schema = spec["components"]["schemas"]["ExamQuestionAnalysisResponse"]
    assert schema["required"] == ["analysis", "generated_at", "model", "request_id"]
    assert schema["properties"]["analysis"] == {"type": "string", "title": "Analysis"}


def test_handler_no_longer_declares_a_bare_dict_body():
    src = inspect.getsource(main.generate_question_analysis)
    assert "req.get(" not in src, "the handler must read the typed model, not a raw dict"
    sig = inspect.signature(main.generate_question_analysis)
    assert sig.parameters["req"].annotation is main.ExamQuestionAnalysisRequest


# ---------------------------------------------------------------- 3-4 generated TS types

def test_generated_typescript_exposes_the_typed_transport():
    """The compile-level probe lives in frontend; this pins the source it reads."""
    from pathlib import Path
    api_ts = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "api.ts"
    if not api_ts.exists():
        pytest.skip("frontend tree not present in this checkout")
    text = api_ts.read_text(encoding="utf-8")
    anchor = "generate_question_analysis_exam_11408__subject_key__question_analysis_post: {"
    assert anchor in text, "the operation is missing from the generated client"
    operation = text.split(anchor, 1)[1].split("\n    };", 1)[0]

    assert 'components["schemas"]["ExamQuestionAnalysisRequest"]' in operation
    assert 'components["schemas"]["ExamQuestionAnalysisResponse"]' in operation
    assert "[key: string]: unknown;" not in operation, "request body is still untyped"
    assert '"application/json": unknown;' not in operation, "2xx is still untyped"


# ---------------------------------------------------------------- 5-7 orchestrator route

def test_route_uses_the_orchestrator_with_capability_question_explain(client, provider):
    register_and_login(client, "bc5b_cap")
    r = client.post(ROUTE.format(subject_key=SUBJECT),
                    json={"stem": "什么是线性表？", "question_type": "选择题",
                          "standard_answer": "A", "user_answer": "B",
                          "options": {"A": "顺序存储", "B": "链式存储"}})
    assert r.status_code == 200, r.text
    assert len(provider) == 1
    assert provider[0]["capability"] == CAPABILITY
    assert provider[0]["stream"] is False, "question.explain is JSON transport, not SSE"

    with database.SessionLocal() as db:
        req = (db.query(AIRequest).filter(AIRequest.capability == CAPABILITY)
               .order_by(AIRequest.id.desc()).first())
        assert req.service_namespace == "exam_prep"
        assert req.context_json["exam_module_id"] == SUBJECT


def test_route_source_holds_no_provider_client_or_model_name():
    src = inspect.getsource(main.generate_question_analysis)
    for forbidden in ("OpenAI(", "call_deepseek", "chat.completions", "DEEPSEEK_API_KEY",
                      "deepseek-", "qwen-", "doubao-", "kimi-", "glm-", "minimax-"):
        assert forbidden not in src, f"{forbidden} leaked into the exam explain route"


def test_direct_provider_calls_in_exam_question_explain_is_zero(client, provider):
    """The double is the ONLY thing that runs; the legacy client would have raised."""
    register_and_login(client, "bc5b_direct")
    r = client.post(ROUTE.format(subject_key="operating_system"), json={"stem": "进程与线程"})
    assert r.status_code == 200, r.text
    assert len(provider) == 1


# ---------------------------------------------------------------- 8-9 denial mapping

def test_entitlement_denial_is_403_and_never_reaches_a_provider(client, monkeypatch, provider):
    register_and_login(client, "bc5b_403")
    _orchestrator_returning(monkeypatch, ok=False, status="denied",
                            error_category="permission_denied", error_message="tier_not_permitted")
    r = client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干"})
    assert r.status_code == 403, r.text
    assert provider == []
    assert "AI capability unavailable" in r.json()["detail"]


def test_budget_rejection_is_429_and_never_reaches_a_provider(client, monkeypatch, provider):
    register_and_login(client, "bc5b_429")
    _orchestrator_returning(monkeypatch, ok=False, status="denied",
                            error_category="budget_reserve_failed",
                            error_message="daily budget exhausted")
    r = client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干"})
    assert r.status_code == 429, r.text
    assert provider == []


def test_no_qualified_model_is_502_not_403(client, monkeypatch, provider):
    register_and_login(client, "bc5b_502route")
    _orchestrator_returning(monkeypatch, ok=False, status="denied",
                            error_category="no_qualified_model_available")
    r = client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干"})
    assert r.status_code == 502, r.text


def test_question_explain_is_allowed_on_the_free_tier(client, provider):
    """The route's fixed capability is free-tier; a tier 403 is therefore unreachable here."""
    register_and_login(client, "bc5b_free")
    r = client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干"})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------- 10-15 side effects

def test_post_submit_explanation_touches_no_learning_state(client, provider):
    bank_id, attempt_id, result = _attempt_fixture(client, "bc5b_side")
    before = _side_effect_snapshot("bc5b_side")

    r = client.post(ROUTE.format(subject_key=SUBJECT), json={
        "stem": result["stem"], "options": result["options"],
        "standard_answer": result["standard_answer"],
        "user_answer": result["user_answer"],
        "question_type": result["question_type"], "context": "错题复盘"})
    assert r.status_code == 200, r.text

    after = _side_effect_snapshot("bc5b_side")
    for key in before:
        if key == "ai_requests":
            continue
        assert before[key] == after[key], f"question.explain altered {key}"
    assert after["ai_requests"] - before["ai_requests"] == 1


def test_attempt_row_is_byte_identical_after_explain(client, provider):
    _bank_id, attempt_id, _result = _attempt_fixture(client, "bc5b_attempt")
    with database.SessionLocal() as db:
        row = db.query(models.ExamPracticeAttempt).filter_by(id=attempt_id).one()
        frozen = (row.status, row.correct_count, row.wrong_count, row.accuracy,
                  row.result_json, row.answers_json, row.submitted_at)
    client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干", "standard_answer": "A"})
    with database.SessionLocal() as db:
        row = db.query(models.ExamPracticeAttempt).filter_by(id=attempt_id).one()
        assert (row.status, row.correct_count, row.wrong_count, row.accuracy,
                row.result_json, row.answers_json, row.submitted_at) == frozen


def test_static_bank_analysis_is_never_overwritten(client, provider):
    bank_id, _attempt_id, _result = _attempt_fixture(client, "bc5b_static")
    with database.SessionLocal() as db:
        row = db.query(models.ExamQuestionBank).filter_by(id=bank_id).one()
        frozen = (row.stem, row.standard_answer, row.analysis)
    client.post(ROUTE.format(subject_key=SUBJECT),
                json={"stem": "题干", "standard_answer": "B", "user_answer": "C"})
    with database.SessionLocal() as db:
        row = db.query(models.ExamQuestionBank).filter_by(id=bank_id).one()
        assert (row.stem, row.standard_answer, row.analysis) == frozen
        assert row.analysis == "静态解析：顺序存储下标直接寻址。"


def test_no_learner_state_or_knowledge_write_happens(client, provider):
    _bank_id, _attempt_id, _result = _attempt_fixture(client, "bc5b_learner")
    before = _side_effect_snapshot("bc5b_learner")
    client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干"})
    after = _side_effect_snapshot("bc5b_learner")
    assert before["knowledge"] == after["knowledge"]
    assert before["knowledge_events"] == after["knowledge_events"]
    assert before["learning_records"] == after["learning_records"]


# ---------------------------------------------------------------- 16 failure isolation

def test_provider_failure_is_502_and_grade_survives(client, monkeypatch):
    _bank_id, attempt_id, _result = _attempt_fixture(client, "bc5b_fail")
    before = _side_effect_snapshot("bc5b_fail")

    def _boom(name):
        raise GatewayError(GatewayErrorCategory.provider_unavailable,
                           "upstream down", provider=name, retriable=False)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _boom)
    r = client.post(ROUTE.format(subject_key=SUBJECT), json={"stem": "题干"})
    assert r.status_code == 502, r.text

    after = _side_effect_snapshot("bc5b_fail")
    assert before["attempts"] == after["attempts"], "the graded attempt must survive"
    assert before["wrong"] == after["wrong"]
    with database.SessionLocal() as db:
        assert db.query(models.ExamPracticeAttempt).filter_by(
            id=attempt_id).one().status == "submitted"


def test_missing_stem_keeps_the_handler_400_not_a_422(client):
    register_and_login(client, "bc5b_400")
    body = client.post(ROUTE.format(subject_key=SUBJECT),
                       json={"stem": ""}).json()
    assert client.post(ROUTE.format(subject_key=SUBJECT),
                       json={"stem": ""}).status_code == 400
    assert body["detail"] == "stem is required"


def test_unauthenticated_call_is_401(anon_client):
    assert anon_client.post(ROUTE.format(subject_key=SUBJECT),
                            json={"stem": "题干"}).status_code == 401


@pytest.fixture
def anon_client():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


# ---------------------------------------------------------------- 17-18 pre-submit / binding

def test_endpoint_accepts_no_question_or_attempt_identity(client, provider):
    """There is no server-side binding to bind to: the route is stateless by construction."""
    register_and_login(client, "bc5b_ident")
    with database.SessionLocal() as db:
        db.add(models.ExamQuestionBank(
            subject_key=SUBJECT, subject_name="数据结构", question_type="choice",
            stem="题干", options_json='{"A":"a","B":"b"}', standard_answer="A",
            analysis="静态解析", is_active=True, source_ref="bc5b_ident:Q1"))
        db.commit()
        qid = db.query(models.ExamQuestionBank).filter_by(
            source_ref="bc5b_ident:Q1").one().id

    r = client.post(ROUTE.format(subject_key=SUBJECT),
                    json={"question_id": qid, "attempt_id": 1})
    assert r.status_code == 400, "identities are not part of this contract"
    assert r.json()["detail"] == "stem is required"
    assert provider == [], "a rejected request must not be billed"


def test_pre_submit_answer_leak_is_zero(client, provider):
    """The 200 body carries model prose only — there is no field that can carry a stored answer."""
    register_and_login(client, "bc5b_leak")
    with database.SessionLocal() as db:
        db.add(models.ExamQuestionBank(
            subject_key=SUBJECT, subject_name="数据结构", question_type="choice",
            stem="机密题干", options_json='{"A":"a","B":"b"}',
            standard_answer="CONFIDENTIAL-REFERENCE-KEY", analysis="静态解析",
            is_active=True, source_ref="bc5b_leak:Q1"))
        db.commit()

    r = client.post(ROUTE.format(subject_key=SUBJECT),
                    json={"stem": "机密题干", "options": {"A": "a", "B": "b"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == set(PRE_TYPING_SUCCESS_KEYS)
    serialized = json.dumps(body, ensure_ascii=False)
    assert "CONFIDENTIAL-REFERENCE-KEY" not in serialized
    assert "静态解析" not in serialized, "static analysis must never ride along"


def test_pre_submit_attempt_view_strips_answer_material(client):
    """The practice attempt itself, not the explain route, is where post-submit gating lives."""
    register_and_login(client, "bc5b_preview")
    with database.SessionLocal() as db:
        db.add(models.ExamQuestionBank(
            subject_key=SUBJECT, subject_name="数据结构", question_type="choice",
            stem="题干", options_json='{"A":"a","B":"b"}', standard_answer="A",
            analysis="静态解析", is_active=True, source_ref="bc5b_preview:Q1"))
        db.commit()
        qid = db.query(models.ExamQuestionBank).filter_by(
            source_ref="bc5b_preview:Q1").one().id
    attempt_id = client.post(f"/exam/11408/{SUBJECT}/chapter-practice/attempts",
                             json={"question_ids": [qid]}).json()["attempt_id"]
    pre = client.get(f"/exam/11408/{SUBJECT}/chapter-practice/attempts/{attempt_id}").json()
    assert "standard_answer" not in pre["questions"][0]
    assert "analysis" not in pre["questions"][0]


# ---------------------------------------------------------------- 19-20 accounting / equivalence

def test_one_billable_lifecycle_per_call_no_double_billing(client, provider):
    register_and_login(client, "bc5b_billing")
    with database.SessionLocal() as db:
        baseline = (db.query(AIRequest).count(), db.query(AICostRecord).count(),
                    db.query(UsageLedger).count())

    for _ in range(2):
        assert client.post(ROUTE.format(subject_key=SUBJECT),
                           json={"stem": "题干"}).status_code == 200

    with database.SessionLocal() as db:
        requests = db.query(AIRequest).order_by(AIRequest.id.desc()).limit(2).all()
        assert len({r.request_id for r in requests}) == 2, "each call is its own request_id"
        assert {r.status for r in requests} == {"settled"}
        for req in requests:
            assert db.query(AICostRecord).filter(
                AICostRecord.request_id == req.request_id).count() == 1, "one cost row per call"
            ledger = db.query(UsageLedger).filter(
                UsageLedger.request_id == req.request_id).all()
            assert ledger, "a settled request has ledger facts"
            assert {row.service_namespace for row in ledger} == {"exam_prep"}
        assert db.query(AIRequest).count() == baseline[0] + 2
        assert db.query(AICostRecord).count() == baseline[1] + 2


def test_no_legacy_exam_quota_owner_on_this_route():
    src = inspect.getsource(main.generate_question_analysis)
    assert "check_exam_408_usage_limit" not in src
    assert "check_usage_limit" not in src


def test_retry_is_a_new_billable_call_not_a_cache(client, provider):
    """Current semantics: the route holds no cache, so a retry is a second billed call."""
    register_and_login(client, "bc5b_retry")
    for _ in range(3):
        assert client.post(ROUTE.format(subject_key=SUBJECT),
                           json={"stem": "同一道题"}).status_code == 200
    assert len(provider) == 3
    assert len({c["capability"] for c in provider}) == 1


def test_runtime_response_equivalence_for_the_typed_transport(client, provider):
    """Typing is a transport change only: a valid caller sees the same 200 bytes."""
    register_and_login(client, "bc5b_equiv")
    typed = main.ExamQuestionAnalysisRequest(
        stem="什么是线性表？", question_type="选择题", standard_answer="A",
        user_answer="B", options={"A": "顺序存储", "B": "链式存储"})

    r = client.post(ROUTE.format(subject_key=SUBJECT), json=typed.model_dump())
    assert r.status_code == 200, r.text
    body = r.json()
    assert sorted(body) == PRE_TYPING_SUCCESS_KEYS
    assert isinstance(body["analysis"], str) and body["analysis"]
    assert isinstance(body["request_id"], str) and body["request_id"]
    assert isinstance(body["generated_at"], str) and body["generated_at"]


def test_unknown_extra_fields_are_still_ignored_like_the_old_dict_body(client, provider):
    register_login_ok = register_and_login(client, "bc5b_extra")
    assert register_login_ok
    r = client.post(ROUTE.format(subject_key=SUBJECT),
                    json={"stem": "题干", "username": "someone-else",
                          "model": "deepseek-reasoner", "anything": [1, 2, 3]})
    assert r.status_code == 200, r.text
    # caller-supplied provider/model hints must not steer routing
    assert provider[0]["capability"] == CAPABILITY
    assert provider[0]["model"] != "deepseek-reasoner"
