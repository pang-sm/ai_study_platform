"""P6.1 §A/§B — AI request identity + feedback ownership on the code surfaces.

WHAT THESE TESTS HOLD
---------------------
1. `/code/analyze` returns the REAL ``ai_requests`` identity of the row that produced the
   answer, on BOTH branches — including the programming branch, which used to call the
   provider directly and therefore had no identity at all;
2. `/code/diagnose` performs no AI request, so it returns no request_id — and the test states
   that as a contract instead of inventing one;
3. `POST /chat` returns the real identity of its unified branch (its own frontend already
   reads ``data.request_id``);
4. that identity is OWNED: it round-trips through ``POST /ai/feedback`` for its owner and is a
   404 for anyone else — the owner check was not weakened;
5. the Debug Agent keeps ``agent_run_id`` as its workflow identity and does NOT promote any
   step's request id to a top-level one; each STEP id is a real, ratable request.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import AiUsageLog, CodeProject, CodeProjectFile, ProgrammingExercise, User
from usage.models import AIRequest

ANALYZE = "/code/analyze"
DIAGNOSE = "/code/diagnose"
CHAT = "/chat"
FEEDBACK = "/ai/feedback"
AGENT_DEBUG = "/programming/agent/debug"

ANSWER = "这段代码的边界条件有问题：n 为 0 时返回 1。"
ORIGINAL = "def solve(n):\n    return n + 1\n"
PATCHED = "def solve(n):\n    return n - 1\n"

FAIL_RESULT = {"status": "failed", "passed": False, "passed_count": 1, "total_count": 3,
               "duration_ms": 12, "tests_executed": "public_only",
               "cases": [{"id": "1", "name": "case_2", "status": "failed", "reason": "x"}]}
PASS_RESULT = {"status": "passed", "passed": True, "passed_count": 3, "total_count": 3,
               "duration_ms": 9, "tests_executed": "public_only", "cases": []}


class _Provider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=ANSWER)


class _AgentProvider(FakeProvider):
    """Answers each agent step with the JSON that step expects."""

    def complete(self, spec):
        text = "\n".join(m.content for m in spec.messages)
        if "请诊断问题" in text:
            reply = json.dumps({"diagnosis": "边界条件写错了", "evidence": "用例失败",
                                "fix_direction": "修正边界"}, ensure_ascii=False)
        elif "给出修复后的完整文件内容" in text:
            reply = json.dumps({"file": "solution.py", "content": PATCHED,
                                "summary": "改为 n-1"}, ensure_ascii=False)
        else:
            reply = "原来错在边界条件。"
        return dataclasses.replace(super().complete(spec), content=reply)


def _provider(name: str) -> FakeProvider:
    return _Provider(provider=name, input_tokens=50, output_tokens=40)


def _agent_provider(name: str) -> FakeProvider:
    return _AgentProvider(provider=name, input_tokens=60, output_tokens=60)


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _scripted_execution(results):
    queue = list(results)

    def _run(db, user, exercise, project, files, *, submission=False):
        return queue.pop(0) if queue else results[-1]
    return _run


def _exercise(db, *, language="Python", title="两数之和") -> ProgrammingExercise:
    exercise = ProgrammingExercise(
        slug=f"p61-agent-{title}-{language}".lower(), title=title, language=language,
        difficulty="easy", description="实现一个函数", tags_json="[]", starter_files_json="[]",
        reference_files_json="[]", public_tests_json="[]", hidden_tests_json="[]",
        official_test_files_json="[]", source_repo="test-fixture", source_path="solution.py",
        source_commit="0" * 40, license="MIT", license_text="MIT", attribution="test",
        audit_report_json="{}", is_active=True, quality_status="approved")
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def _project(db, user, exercise) -> CodeProject:
    project = CodeProject(user_id=user.id, username=user.username, course_id="programming",
                          name="练习", language=exercise.language, entry_file="solution.py",
                          programming_exercise_id=exercise.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    db.add(CodeProjectFile(project_id=project.id, username=user.username,
                           relative_path="solution.py", filename="solution.py",
                           content=ORIGINAL, file_type="text"))
    db.commit()
    return project


def _owned_request(db, request_id: str, user_id: int):
    """The identity contract, checked against the store itself."""
    return (db.query(AIRequest)
            .filter(AIRequest.request_id == request_id, AIRequest.user_id == user_id).first())


# ================================================================ 1. code/analyze


def test_code_analyze_returns_a_real_owned_request_id(client, db_session, monkeypatch):
    register_and_login(client, "p61_analyze_course")
    grant_unified_tier(db_session, "p61_analyze_course", "standard")
    user = _user(db_session, "p61_analyze_course")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)

    body = client.post(ANALYZE, json={"username": "", "course_id": "", "language": "python",
                                      "code": ORIGINAL, "question": "这段代码对吗？"}).json()
    request_id = body.get("request_id")
    assert request_id, "the response must carry the real identity of the AI request"

    db_session.expire_all()
    row = _owned_request(db_session, request_id, user.id)
    assert row is not None, "the id must be an actual ai_requests row of the CALLER"
    assert row.capability == "programming.explain"
    assert row.status == "settled"

    # …and it is genuinely ratable: the feedback round trip closes the loop
    rated = client.post(FEEDBACK, json={"request_id": request_id, "rating": "up"})
    assert rated.status_code == 200, rated.text
    assert rated.json()["capability"] == "programming.explain"
    assert rated.json()["trains_router_online"] is False


def test_code_analyze_programming_branch_runs_on_the_unified_stack(client, db_session,
                                                                  monkeypatch):
    """The programming branch no longer calls a provider directly.

    Before P6.1 it created NO ``ai_requests`` row, took no capability/permission decision and
    logged to the legacy ``ai_usage_logs`` table. Now it is one ordinary request on the same
    capability → usage → router → gateway → ``ai_requests`` chain as everything else.
    """
    register_and_login(client, "p61_analyze_prog")
    grant_unified_tier(db_session, "p61_analyze_prog", "standard")
    user = _user(db_session, "p61_analyze_prog")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)

    db_session.expire_all()
    legacy_before = db_session.query(AiUsageLog).count()

    response = client.post(ANALYZE, json={"username": "", "course_id": "programming",
                                          "language": "python", "code": ORIGINAL,
                                          "question": "这段代码对吗？"})
    assert response.status_code == 200, response.text
    request_id = response.json()["request_id"]

    db_session.expire_all()
    row = _owned_request(db_session, request_id, user.id)
    assert row is not None
    assert row.capability == "programming.explain"
    assert row.service_namespace == "programming"      # the canonical space, not a guess
    assert row.context_json and row.context_json.get("programming_language")
    assert db_session.query(AiUsageLog).count() == legacy_before, \
        "the legacy usage logger must not be written on the unified path"

    assert client.post(FEEDBACK, json={"request_id": request_id, "rating": "up",
                                       "reason": None}).status_code == 200


def test_a_borrowed_request_id_is_still_a_404(client, db_session, monkeypatch):
    register_and_login(client, "p61_owner")
    grant_unified_tier(db_session, "p61_owner", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    mine = client.post(ANALYZE, json={"username": "", "course_id": "", "language": "python",
                                      "code": ORIGINAL, "question": "对吗？"}).json()["request_id"]

    register_and_login(client, "p61_other")
    stolen = client.post(FEEDBACK, json={"request_id": mine, "rating": "up"})
    assert stolen.status_code == 404, "the feedback owner check must not be weakened"
    assert client.post(ANALYZE, json={"username": "p61_owner", "course_id": "",
                                      "language": "python", "code": ORIGINAL,
                                      "question": "?"}).status_code == 403


# ================================================================ 2. code/diagnose


def test_code_diagnose_makes_no_ai_request_and_returns_no_id(client, db_session):
    """§A2 decision, held as a contract: diagnose is DETERMINISTIC.

    It compiles the code with the local interpreter — no model, no ``ai_requests`` row — so
    there is no identity to expose. Inventing one, or turning a syntax check into a billed
    model call, would be a new AI feature; the response therefore says nothing about AI.
    """
    register_and_login(client, "p61_diagnose")
    user = _user(db_session, "p61_diagnose")

    db_session.expire_all()
    before = (db_session.query(AIRequest)
              .filter(AIRequest.user_id == user.id).count())

    ok = client.post(DIAGNOSE, json={"language": "python", "code": "x = 1\n"})
    assert ok.status_code == 200 and ok.json()["status"] == "ok"
    assert "request_id" not in ok.json(), "a deterministic check has no AI identity"

    broken = client.post(DIAGNOSE, json={"language": "python", "code": "def f(:\n"})
    assert broken.status_code == 200 and broken.json()["status"] == "error"
    assert "request_id" not in broken.json()

    unsupported = client.post(DIAGNOSE, json={"language": "rust", "code": "fn main() {}"})
    assert unsupported.json()["status"] == "unsupported"

    db_session.expire_all()
    assert (db_session.query(AIRequest).filter(AIRequest.user_id == user.id).count()
            == before), "diagnose must not create an ai_requests row"


# ================================================================ 3. chat


def test_chat_returns_the_real_request_id_of_its_answer(client, db_session, monkeypatch):
    register_and_login(client, "p61_chat")
    grant_unified_tier(db_session, "p61_chat", "standard")
    user = _user(db_session, "p61_chat")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)

    response = client.post(CHAT, json={"message": "什么是分页？", "course_id": "数据结构",
                                       "course": "数据结构", "service_key": "course_learning"})
    assert response.status_code == 200, response.text
    request_id = response.json()["request_id"]
    assert request_id, "the course chat answer has a real ai_requests identity"

    db_session.expire_all()
    row = _owned_request(db_session, request_id, user.id)
    assert row is not None and row.capability in ("tutor.chat", "material.qa")
    assert row.service_namespace == "course_learning"

    assert client.post(FEEDBACK, json={"request_id": request_id, "rating": "up"}
                       ).status_code == 200


# ================================================================ 4. debug agent identity


def test_the_debug_agent_keeps_agent_run_id_and_exposes_only_real_step_ids(
        client, db_session, monkeypatch):
    """§A3: no fabricated workflow-level request id.

    The agent has no workflow-level ``ai_requests`` row (each model STEP has its own), so the
    top level carries ``agent_run_id`` — a workflow id, never dressed up as a request id — and
    every step carries the REAL id of the request that served it, which is ratable.
    """
    register_and_login(client, "p61_agent")
    grant_unified_tier(db_session, "p61_agent", "standard")
    user = _user(db_session, "p61_agent")
    exercise = _exercise(db_session)
    _project(db_session, user, exercise)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _agent_provider)
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([FAIL_RESULT, PASS_RESULT]))

    body = client.post(AGENT_DEBUG, json={"exercise_id": exercise.id,
                                          "files": [{"filename": "solution.py",
                                                     "content": ORIGINAL}]}).json()
    assert body["status"] == "completed", body
    assert "request_id" not in body, \
        "the workflow must NOT claim a top-level request id it does not have"

    step_ids = [step["ai_request_id"] for step in body["steps"] if step.get("ai_request_id")]
    assert step_ids, "each model step carries its own real request id"
    assert body["agent_run_id"] not in step_ids, "the run id is not a request id"

    db_session.expire_all()
    for step_id in step_ids:
        row = _owned_request(db_session, step_id, user.id)
        assert row is not None and row.capability == "programming.agent"
        # a step id IS ratable — the trace already exposes it, so feedback stays possible
        assert client.post(FEEDBACK, json={"request_id": step_id, "rating": "up"}
                           ).status_code == 200
