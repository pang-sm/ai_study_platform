"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3A — Programming Debug Agent.

WHAT THESE TESTS HOLD
---------------------
1. the workflow is a BOUNDED loop: MAX_ITERATIONS / MAX_EXECUTIONS / MAX_MODEL_STEPS are hard
   caps, not targets, and a patch that never helps cannot make the agent run forever;
2. it really repairs: diagnose → patch → run the exercise's own tests → pass, with the
   baseline failure and the final result both reported;
3. it is scoped to the caller: another learner's project is a 404, and the model can only ever
   name a file that is already part of the run (no path, no other project's file);
4. a step that fails is RECORDED and SETTLED — the run reports what happened instead of
   hiding a partial workflow behind an error;
5. the trace is durable: one ``ai_requests`` row per model step (deterministic ids) plus the
   canonical started/completed events, whose payload carries a CODE-FREE per-step trace.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported. The execution seam is the ONLY thing stubbed: the agent, the orchestrator, usage and
events are real.
"""
import dataclasses
import json

from ai.gateway import GatewayError, GatewayErrorCategory
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from data_plane.models import LearningEvent
from learning.spaces.programming import agent as debug_agent
from models import CodeProject, CodeProjectFile, ProgrammingExercise, User
from usage.models import AIRequest

AGENT_DEBUG = "/programming/agent/debug"

ORIGINAL = "def solve(n):\n    return n + 1\n"
PATCHED = "def solve(n):\n    return n - 1\n"

FAIL_RESULT = {
    "status": "failed", "passed": False, "passed_count": 1, "total_count": 3,
    "duration_ms": 12, "tests_executed": "public_only",
    "cases": [{"id": "1", "name": "case_2", "status": "failed", "reason": "expected 3 got 4"}],
}
PASS_RESULT = {
    "status": "passed", "passed": True, "passed_count": 3, "total_count": 3,
    "duration_ms": 9, "tests_executed": "public_only", "cases": [],
}


class _AgentProvider(FakeProvider):
    """A provider that answers each STEP with the JSON that step expects."""

    def __init__(self, *, patched=PATCHED, file="solution.py", content=None, **kwargs):
        super().__init__(**kwargs)
        self._patched = patched
        self._file = file
        self._forced = content

    def complete(self, spec):
        text = "\n".join(m.content for m in spec.messages)
        if self._forced is not None:
            reply = self._forced
        elif "请诊断问题" in text:
            reply = json.dumps({"diagnosis": "边界条件写错了", "evidence": "用例 2 失败",
                                "fix_direction": "修正 n 的边界"}, ensure_ascii=False)
        elif "给出修复后的完整文件内容" in text:
            reply = json.dumps({"file": self._file, "content": self._patched,
                                "summary": "把 n+1 改为 n-1"}, ensure_ascii=False)
        else:
            reply = "原来错在边界条件，现在已修正。"
        return dataclasses.replace(super().complete(spec), content=reply)


class _BrokenPatchProvider(_AgentProvider):
    """The diagnose step works; the patch step fails at the provider (auth error)."""

    def complete(self, spec):
        text = "\n".join(m.content for m in spec.messages)
        if "给出修复后的完整文件内容" in text:
            raise GatewayError(GatewayErrorCategory.authentication, "no key", self.name)
        return super().complete(spec)


def _provider(factory_cls=_AgentProvider, **kwargs):
    def _make(name: str) -> FakeProvider:
        return factory_cls(provider=name, input_tokens=60, output_tokens=60, **kwargs)
    return _make


def _scripted_execution(results):
    """A stand-in for the execution backend: one scripted result per test run."""
    queue = list(results)

    def _run(db, user, exercise, project, files, *, submission=False):
        return queue.pop(0) if queue else results[-1]
    return _run


def _exercise(db, *, language="Python", title="两数之和") -> ProgrammingExercise:
    exercise = ProgrammingExercise(
        slug=f"p3a-agent-{title}-{language}".lower().replace(" ", "-"),
        title=title, language=language, difficulty="easy",
        description="实现一个函数", tags_json="[]", starter_files_json="[]",
        reference_files_json="[]", public_tests_json="[]", hidden_tests_json="[]",
        official_test_files_json="[]", source_repo="test-fixture",
        source_path="solution.py", source_commit="0" * 40, license="MIT",
        license_text="MIT", attribution="test", audit_report_json="{}",
        is_active=True, quality_status="approved")
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def _project(db, user, exercise, *, filename="solution.py", content=ORIGINAL):
    project = CodeProject(user_id=user.id, username=user.username,
                          course_id="programming", name="练习", language=exercise.language,
                          entry_file=filename, programming_exercise_id=exercise.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    db.add(CodeProjectFile(project_id=project.id, username=user.username,
                           relative_path=filename, filename=filename, content=content,
                           file_type="text"))
    db.commit()
    return project


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _body(exercise, **overrides):
    payload = {"exercise_id": exercise.id,
               "files": [{"filename": "solution.py", "content": ORIGINAL}]}
    payload.update(overrides)
    return payload


# ================================================================ 1. the repair loop


def test_the_agent_repairs_a_failing_submission(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_ok")
    grant_unified_tier(db_session, "p3a_agent_ok", "standard")
    exercise = _exercise(db_session)
    project = _project(db_session, _user(db_session, "p3a_agent_ok"), exercise)
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([FAIL_RESULT, PASS_RESULT]))
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    response = client.post(AGENT_DEBUG, json=_body(exercise, project_id=project.id))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "completed"
    assert body["stop_reason"] == "tests_passed"
    assert body["tests_before"]["passed"] is False
    assert body["tests_after"]["passed"] is True
    assert [step["action"] for step in body["steps"]] == [
        "tests_before", "diagnose", "propose_patch", "run_tests", "explain"]
    assert body["iterations_used"] == 1
    assert body["executions_used"] == 2
    assert body["patch_file"] == "solution.py"
    assert body["final_code"] == PATCHED
    assert "+def solve" in body["proposed_patch"] or "-    return n + 1" in body["proposed_patch"]
    assert body["explanation"]
    assert body["usage"]["model_steps"] == 3

    # the learner's OWN file was never modified — the agent repairs a copy
    from models import CodeProjectFile as _File
    stored = (db_session.query(_File)
              .filter(_File.project_id == project.id).one())
    assert stored.content == ORIGINAL


def test_the_agent_stops_at_its_hard_bounds(client, db_session, monkeypatch):
    """A patch that never helps hits the caps, not an infinite loop."""
    register_and_login(client, "p3a_agent_bounded")
    grant_unified_tier(db_session, "p3a_agent_bounded", "standard")
    exercise = _exercise(db_session, title="永不收敛")
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([FAIL_RESULT]))          # always fails
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    body = client.post(AGENT_DEBUG, json=_body(exercise)).json()
    assert body["status"] == "failed"
    assert body["iterations_used"] == debug_agent.MAX_ITERATIONS
    assert body["executions_used"] <= debug_agent.MAX_EXECUTIONS
    assert body["usage"]["model_steps"] <= debug_agent.MAX_MODEL_STEPS
    assert len(body["steps"]) <= debug_agent.MAX_MODEL_STEPS + debug_agent.MAX_EXECUTIONS
    # the trace says why it stopped instead of pretending it converged
    assert body["stop_reason"] in {"max_iterations", "budget_exhausted"}


def test_no_repair_is_attempted_when_the_tests_already_pass(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_passing")
    grant_unified_tier(db_session, "p3a_agent_passing", "standard")
    exercise = _exercise(db_session, title="已经通过")
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([PASS_RESULT]))
    calls = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: calls.append(name) or _AgentProvider(provider=name))

    body = client.post(AGENT_DEBUG, json=_body(exercise)).json()
    assert body["status"] == "no_repair_needed"
    assert body["reason"] == "tests_already_passing"
    assert calls == []                       # no model was called at all
    assert [step["action"] for step in body["steps"]] == ["tests_before"]


# ================================================================ 2. ownership & scope


def test_another_learners_project_is_a_404(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_stranger")
    grant_unified_tier(db_session, "p3a_agent_stranger", "standard")
    exercise = _exercise(db_session, title="别人的项目")
    other = _user(db_session, "p3a_agent_stranger")
    foreign_project = _project(db_session, other, exercise)

    register_and_login(client, "p3a_agent_caller")
    grant_unified_tier(db_session, "p3a_agent_caller", "standard")
    refused = client.post(AGENT_DEBUG, json=_body(exercise, project_id=foreign_project.id))
    assert refused.status_code == 404, refused.text


def test_the_model_cannot_name_a_file_outside_the_run(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_escape")
    grant_unified_tier(db_session, "p3a_agent_escape", "standard")
    exercise = _exercise(db_session, title="越权文件")
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([FAIL_RESULT, PASS_RESULT]))
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider(file="../other_project/main.py"))

    body = client.post(AGENT_DEBUG, json=_body(exercise)).json()
    assert body["status"] == "failed"
    assert body["stop_reason"] == "patch_not_applicable"
    patch_step = next(s for s in body["steps"] if s["action"] == "propose_patch")
    assert patch_step["status"] == "failed"
    assert patch_step["reason"] == "unusable_patch"
    assert body["proposed_patch"] is None
    assert body["executions_used"] == 1      # nothing was executed with an unknown file


def test_the_agent_is_gated_before_any_code_runs(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_free")
    exercise = _exercise(db_session, title="免费档")
    executions = []
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        lambda *a, **k: executions.append(1) or FAIL_RESULT)

    denied = client.post(AGENT_DEBUG, json=_body(exercise))
    assert denied.status_code == 403, denied.text
    assert executions == []


# ================================================================ 3. failure settlement


def test_a_failed_step_is_recorded_and_settled(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_partial")
    grant_unified_tier(db_session, "p3a_agent_partial", "standard")
    exercise = _exercise(db_session, title="中途失败")
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([FAIL_RESULT]))
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(_BrokenPatchProvider))

    response = client.post(AGENT_DEBUG, json=_body(exercise))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "failed"
    assert body["error_category"] == "http_502"
    actions = [(step["action"], step["status"]) for step in body["steps"]]
    assert actions == [("tests_before", "failed"), ("diagnose", "ok"),
                       ("propose_patch", "failed")]

    user = _user(db_session, "p3a_agent_partial")
    requests = db_session.query(AIRequest).filter(AIRequest.user_id == user.id).all()
    assert {row.capability for row in requests} == {"programming.agent"}
    # the step that really ran was SETTLED; the one that failed was RELEASED (no usage)
    assert sorted(row.status for row in requests) == ["released", "settled"]
    diagnose = next(row for row in requests if row.status == "settled")
    assert diagnose.request_id in {step.get("ai_request_id") for step in body["steps"]}


# ================================================================ 4. the durable trace


def test_the_workflow_trace_is_persisted_without_copying_code(client, db_session, monkeypatch):
    register_and_login(client, "p3a_agent_trace")
    grant_unified_tier(db_session, "p3a_agent_trace", "standard")
    exercise = _exercise(db_session, title="轨迹")
    monkeypatch.setattr("learning.spaces.programming.agent.execute_exercise_tests",
                        _scripted_execution([FAIL_RESULT, PASS_RESULT]))
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    body = client.post(AGENT_DEBUG, json=_body(exercise)).json()
    run_id = body["agent_run_id"]

    # one ai_requests row per model step, under the run's deterministic ids
    user = _user(db_session, "p3a_agent_trace")
    rows = (db_session.query(AIRequest)
            .filter(AIRequest.user_id == user.id,
                    AIRequest.request_id.like(f"{run_id}:%")).all())
    assert len(rows) == body["usage"]["model_steps"] == 3
    assert all(row.capability == "programming.agent" for row in rows)
    assert all(row.service_namespace == "programming" for row in rows)
    assert all(row.provider and row.model for row in rows)

    # the run's canonical facts, with a code-free per-step trace
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id,
                      LearningEvent.source_attempt_id == run_id).all())
    by_type = {event.event_type: event for event in events}
    assert set(by_type) == {"programming_agent_started", "programming_agent_completed"}
    assert all(event.service_key == "programming" for event in events)

    payload = json.loads(by_type["programming_agent_completed"].item_snapshot_json)
    assert payload["status"] == "completed"
    assert [step["action"] for step in payload["steps"]] == [
        "tests_before", "diagnose", "propose_patch", "run_tests", "explain"]
    assert payload["steps"][2]["patch"]["lines_added"] >= 1
    assert payload["steps"][3]["tests"]["passed"] is True

    # §34: the canonical stream carries no source code, no prompt and no model response
    snapshot = by_type["programming_agent_completed"].item_snapshot_json
    for forbidden in ("return n - 1", "return n + 1", "def solve", "请诊断问题"):
        assert forbidden not in snapshot, forbidden
    for step in payload["steps"]:
        assert "patch_text" not in step
        assert "content" not in step
