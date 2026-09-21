"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6 — operations & hardening.

WHAT THESE TESTS HOLD
---------------------
1. the AI operations contract is AGGREGATED and CORRECT, and leaks no learner identity,
   prompt, response or request identity;
2. the workflow operations contract reports per-workflow calls / outcomes / latency / credits
   / failure category, and the debug agent's iterations and executions — without source code;
3. the agent run detail read RECONSTRUCTS a run from durable stores only (restart recovery,
   detail read, audit, debugging) — which is the evidence for the §C decision that no per-step
   table is needed;
4. the feature flags really close a workflow on the NEXT request (OFF / INTERNAL), and TIER is
   the default that changes nothing;
5. ALL is a real grant of the ENTITLEMENT step and nothing else: the budget still settles, the
   recorded tier stays the learner's real tier, and the grant is recorded in the audit fact;
6. the new admin surfaces are admin-only and permission-gated.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json

import pytest

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import User
from ops import feature_flags

DEEP_STUDY = "/ai/deep-study"
REPORT = "/ai/learning-report"
REVIEW = "/review"
ADAPTIVE = "/adaptive/practice"
AI_OPS = "/admin/ai-operations/summary"
WF_OPS = "/admin/workflow-operations/summary"
RUN_DETAIL = "/admin/workflow-operations/agent-runs/{run_id}"
FLAGS = "/admin/feature-flags"
COURSE = "数据结构"
ANSWER = "虚拟内存是操作系统对物理内存的抽象。"


class _ScriptedProvider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=ANSWER)


def _provider(name: str) -> FakeProvider:
    return _ScriptedProvider(provider=name, input_tokens=60, output_tokens=40)


_ANALYSIS_JSON = {
    "error_category": "概念混淆",
    "reasoning_gap": "把顺序存储的下标访问当成了 O(n)",
    "correct_reasoning": "基址加下标可直接算出地址，是 O(1)",
    "next_action": "复习线性表的存储结构",
    "review_recommendation": "48 小时后重做该题",
}


class _AnalysisProvider(FakeProvider):
    """A model response shaped like the structured wrong-cause analysis."""

    def complete(self, spec):
        return dataclasses.replace(super().complete(spec),
                                   content=json.dumps(_ANALYSIS_JSON, ensure_ascii=False))


def _analysis_provider(name: str) -> FakeProvider:
    return _AnalysisProvider(provider=name, input_tokens=60, output_tokens=40)


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


@pytest.fixture(autouse=True)
def _reset_feature_flags(db_session):
    """Flag rows are GLOBAL in a shared test DB — one test must not re-mode the next one.

    The suite runs against ONE temp database (conftest), so a test that leaves
    ``adaptive_practice`` at INTERNAL would silently change what a later test can reach. The
    registry itself is untouched: the rows this suite wrote are removed afterwards.
    """
    yield
    from models import SystemSetting
    db_session.rollback()
    db_session.query(SystemSetting).filter(
        SystemSetting.key.like(f"{feature_flags.SETTING_KEY_PREFIX}%")
    ).delete(synchronize_session=False)
    db_session.commit()


def _make_admin(db, username, role="super_admin") -> None:
    user = _user(db, username)
    user.is_admin = 1
    user.admin_role = role
    db.commit()


def _one_deep_study(client, monkeypatch) -> str:
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    response = client.post(DEEP_STUDY, json={"question": "什么是虚拟内存？", "course_id": COURSE})
    assert response.status_code == 200, response.text
    return response.json()["request_id"]


# ================================================================ 1. AI operations


def test_ai_operations_summary_is_aggregated_and_correct(client, db_session, monkeypatch):
    """DELTAS, not absolutes: the suite shares ONE temp database (conftest), so every window
    total already contains the other tests' calls and only the movement is assertable."""
    register_and_login(client, "p6_ops_member")
    grant_unified_tier(db_session, "p6_ops_member", "standard")
    assert client.get(AI_OPS).status_code == 403           # not an admin → no ops view
    _make_admin(db_session, "p6_ops_member")
    before = client.get(AI_OPS, params={"window_days": 7}).json()

    request_ids = [_one_deep_study(client, monkeypatch) for _ in range(3)]
    client.post("/ai/feedback", json={"request_id": request_ids[0], "rating": "down",
                                      "reason": "too_verbose"})

    body = client.get(AI_OPS, params={"window_days": 7}).json()
    assert body["scope"] == "platform"
    assert body["window_days"] == 7

    def moved(*path):
        """Movement of one metric. A bucket an earlier state simply did not have counts 0."""
        node, previous = body, before
        for step in path:
            node = node.get(step, 0) if isinstance(node, dict) else 0
            previous = previous.get(step, 0) if isinstance(previous, dict) else 0
        return (node or 0) - (previous or 0)

    def bucket_moved(kind, key, field):
        return (body[kind].get(key, {}).get(field, 0)
                - before[kind].get(key, {}).get(field, 0))

    assert moved("requests", "total") == 3
    assert moved("requests", "success") == 3
    assert moved("requests", "failure") == 0
    assert moved("requests", "by_status", "settled") == 3
    assert moved("latency", "samples") == 3 and body["latency"]["avg_ms"] is not None
    assert moved("credits", "actual_total") > 0
    assert bucket_moved("by_capability", "tutor.strong_reasoning", "requests") == 3
    assert bucket_moved("by_tier", "standard", "requests") == 3
    assert body["by_provider"] and body["by_model"]
    # router facts come from the ai_called audit stream and say so
    assert body["router"]["source"] == "learning_events:ai_called"
    assert moved("router", "event_count") == 3
    assert moved("router", "fallback_count") == 0
    # feedback is read through the EXISTING aggregate, not a second one
    assert moved("feedback", "down") == 1
    assert moved("feedback", "by_reason", "too_verbose") == 1
    # degraded availability is reported with its scope
    assert body["availability"]["scope"] == "process_local"
    assert body["availability"]["tracked_models"] >= 1


def test_ai_operations_never_leaks_learner_identity_or_content(client, db_session, monkeypatch):
    register_and_login(client, "p6_ops_privacy")
    grant_unified_tier(db_session, "p6_ops_privacy", "standard")
    request_id = _one_deep_study(client, monkeypatch)
    _make_admin(db_session, "p6_ops_privacy")

    body = client.get(AI_OPS).json()
    # the `privacy` block DECLARES what is never returned, so it is excluded from the scan
    declaration = json.dumps(body["privacy"], ensure_ascii=False)
    payload = json.dumps({key: value for key, value in body.items() if key != "privacy"},
                         ensure_ascii=False)

    assert "p6_ops_privacy" not in payload
    assert request_id not in payload
    assert ANSWER not in payload                       # no response text
    assert "什么是虚拟内存" not in payload               # no prompt text
    assert "prompt" not in payload and "response_text" not in payload
    assert "secret" not in payload.lower() and "api_key" not in payload.lower()
    assert "C:\\" not in payload and "/var/" not in payload
    assert "user_id" not in payload and "username" not in payload
    assert "prompt" in declaration                     # …and the declaration is still there
    assert body["privacy"]["aggregate_only"] is True
    assert "user_id" in body["privacy"]["never_returns"]


def test_ai_operations_requires_the_ai_logs_permission(client, db_session):
    register_and_login(client, "p6_ops_perm")
    _make_admin(db_session, "p6_ops_perm", role="operator")
    assert client.get(AI_OPS).status_code == 200        # operator holds ai_logs.view

    user = _user(db_session, "p6_ops_perm")
    user.admin_role = "none"
    db_session.commit()
    assert client.get(AI_OPS).status_code == 403        # role revoked → no access


# ================================================================ 2. workflow operations


def test_workflow_operations_reports_every_workflow(client, db_session, monkeypatch):
    """DELTAS, not absolutes: the suite shares ONE temp database (conftest), so a window
    total is cumulative across tests and only the movement this test caused is assertable."""
    register_and_login(client, "p6_wf_member")
    grant_unified_tier(db_session, "p6_wf_member", "advanced")
    _make_admin(db_session, "p6_wf_member")
    before = client.get(WF_OPS, params={"window_days": 7}).json()["workflows"]

    _one_deep_study(client, monkeypatch)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    report = client.post(REPORT, json={"service_key": "course_learning", "period_days": 7,
                                       "course_id": COURSE, "include_narrative": True})
    assert report.status_code == 200, report.text

    body = client.get(WF_OPS, params={"window_days": 7}).json()
    workflows = body["workflows"]
    assert set(workflows) == {"deep_study", "programming_agent", "learning_report",
                              "wrong_analysis", "plan_adjustment"}

    def at(snapshot, workflow, *path):
        node = snapshot[workflow]
        for step in path:
            node = node[step]
        return node

    def moved(workflow, *path):
        return at(workflows, workflow, *path) - at(before, workflow, *path)

    assert moved("deep_study", "calls", "requests") == 1
    assert moved("deep_study", "calls", "success") == 1
    assert moved("deep_study", "activity", "strong_reasoning_requested") == 1
    assert moved("deep_study", "activity", "strong_reasoning_completed") == 1
    assert moved("learning_report", "activity", "report_generated") == 1
    assert workflows["programming_agent"]["activity"]["agent"]["iterations"] >= 0
    assert workflows["programming_agent"]["activity"]["agent"]["executions"] >= 0
    # failure detail is a NORMALIZED category, never a provider body
    assert workflows["deep_study"]["failure_by_category"] == {}
    assert body["privacy"]["aggregate_only"] is True
    assert "source_code" in body["privacy"]["never_returns"]


# ================================================================ 3. agent run detail (§C)


def _agent_events(db, run_id: str, *, steps: list) -> None:
    """Write the two canonical events a finished agent run leaves behind."""
    from learning.records import producers
    producers.emit_programming_agent_started(
        user_id=1, agent_run_id=run_id, exercise_id=7, language="C",
        max_iterations=3, max_executions=4, occurred_at=None)
    producers.emit_programming_agent_completed(
        user_id=1, agent_run_id=run_id, status="completed", language="C", steps=steps,
        tests_before={"passed": False, "passed_count": 1, "total_count": 3},
        tests_after={"passed": True, "passed_count": 3, "total_count": 3},
        occurred_at=None)


def test_agent_run_detail_is_reconstructable_from_durable_stores(client, db_session):
    """§C EVIDENCE: restart recovery / detail read / audit / debugging, without a new table.

    The events and the per-step ``ai_requests`` rows are written independently, then read back
    through the ops contract exactly as a restarted process would read them.
    """
    from usage.models import AIRequest
    from datetime import datetime

    register_and_login(client, "p6_agent_admin")
    _make_admin(db_session, "p6_agent_admin")
    run_id = "run-p6-detail"
    steps = [
        {"index": 0, "action": "tests_before", "status": "failed", "latency_ms": 120,
         "tests": {"passed": False, "passed_count": 1, "total_count": 3}},
        {"index": 1, "action": "diagnose", "status": "ok", "latency_ms": 900,
         "credits": 3, "ai_request_id": f"{run_id}:1:diagnose"},
        {"index": 2, "action": "propose_patch", "status": "ok", "latency_ms": 1100,
         "credits": 4, "ai_request_id": f"{run_id}:2:propose_patch",
         "file": "main.c", "patch": {"patch_chars": 40, "lines_added": 2, "lines_removed": 1}},
        {"index": 3, "action": "run_tests", "status": "ok", "latency_ms": 200,
         "tests": {"passed": True, "passed_count": 3, "total_count": 3}},
    ]
    _agent_events(db_session, run_id, steps=steps)
    now = datetime.utcnow()
    for step_index, action, credits in ((1, "diagnose", 3), (2, "propose_patch", 4)):
        db_session.add(AIRequest(
            request_id=f"{run_id}:{step_index}:{action}", user_id=1,
            capability="programming.agent", status="settled", tier="standard",
            estimated_credits=credits, actual_credits=credits,
            provider="deepseek", model="deepseek-chat",
            started_at=now, finished_at=now))
    db_session.commit()

    # RESTART RECOVERY, stated as a fact: both halves are on disk, so a reader that shares
    # nothing with the writer — which is what a restarted backend process is — sees them.
    from database import SessionLocal
    fresh = SessionLocal()
    try:
        assert fresh.query(AIRequest).filter(
            AIRequest.request_id.like(f"{run_id}:%")).count() == 2
    finally:
        fresh.close()

    detail = client.get(RUN_DETAIL.format(run_id=run_id)).json()
    assert detail["found"] is True
    assert detail["run_status"] == "completed"
    assert detail["exercise_id"] == 7 and detail["language"] == "C"
    assert len(detail["trace"]) == 4
    assert detail["model_steps"] == 2
    assert sum(1 for s in detail["steps"] if s["status"] == "settled") == 2
    assert {s["request_id"] for s in detail["steps"]} == {
        f"{run_id}:1:diagnose", f"{run_id}:2:propose_patch"}
    assert detail["durable_sources"] == ["learning_events:programming_agent_*", "ai_requests"]
    # the trace that IS durable carries no source code and no prompt
    assert json.dumps(detail, ensure_ascii=False).find("def ") == -1
    # per-execution test results survive restart, per step
    assert detail["trace"][3]["tests"]["passed"] is True

    assert client.get(RUN_DETAIL.format(run_id="missing-run")).status_code == 404


# ================================================================ 4. feature flags


def test_flags_default_to_tier_and_are_admin_manageable(client, db_session, monkeypatch):
    register_and_login(client, "p6_flag_member")
    grant_unified_tier(db_session, "p6_flag_member", "standard")

    # TIER is the default: an unset flag changes NOTHING about the existing policy
    assert client.get(FLAGS).status_code == 403
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    assert client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE}).status_code == 200

    _make_admin(db_session, "p6_flag_member", role="operator")
    assert client.get(FLAGS).status_code == 403          # operator lacks feature_flags.manage
    user = _user(db_session, "p6_flag_member")
    user.admin_role = "super_admin"
    db_session.commit()

    listed = client.get(FLAGS).json()
    assert listed["default_mode"] == "TIER"
    assert {item["feature"] for item in listed["items"]} == {
        "deep_study", "programming_agent", "learning_report", "wrong_analysis",
        "dynamic_planning", "adaptive_practice", "intelligent_review"}
    assert all(item["mode"] == "TIER" and item["stored"] is False
               for item in listed["items"])


def test_off_closes_the_workflow_on_the_next_request(client, db_session, monkeypatch):
    register_and_login(client, "p6_flag_off")
    grant_unified_tier(db_session, "p6_flag_off", "standard")
    _make_admin(db_session, "p6_flag_off")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)

    assert client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE}).status_code == 200

    update = client.put(FLAGS, json={"flags": {"deep_study": "OFF"}})
    assert update.status_code == 200, update.text
    assert update.json()["previous"]["deep_study"] == "TIER"

    closed = client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE})
    assert closed.status_code == 403
    assert closed.json()["detail"]["code"] == "feature_disabled"
    assert closed.json()["detail"]["mode"] == "OFF"

    # …and it reopens on the next request, without a restart
    client.put(FLAGS, json={"flags": {"deep_study": "TIER"}})
    assert client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE}).status_code == 200


def test_internal_closes_non_admin_members_only(client, db_session, monkeypatch):
    register_and_login(client, "p6_flag_internal")
    grant_unified_tier(db_session, "p6_flag_internal", "standard")
    _make_admin(db_session, "p6_flag_internal")
    client.put(FLAGS, json={"flags": {"adaptive_practice": "INTERNAL"}})

    # the ADMIN reaches it (canary), a plain member does not
    params = {"service_key": "course_learning", "course_id": COURSE}
    assert client.get(ADAPTIVE, params=params).status_code == 200
    user = _user(db_session, "p6_flag_internal")
    user.is_admin = 0
    user.admin_role = "none"
    db_session.commit()
    denied = client.get(ADAPTIVE, params=params)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "feature_internal_only"


def test_flag_rejects_unknown_keys_and_modes(client, db_session):
    register_and_login(client, "p6_flag_validate")
    _make_admin(db_session, "p6_flag_validate")
    before = feature_flags.get_modes(db_session)
    assert client.put(FLAGS, json={"flags": {"nope": "OFF"}}).status_code == 400
    assert client.put(FLAGS, json={"flags": {"deep_study": "MAYBE"}}).status_code == 400
    assert client.put(FLAGS, json={"flags": {}}).status_code == 422
    # a rejected batch writes NOTHING (validate-all-before-write)
    assert feature_flags.get_modes(db_session) == before


# ================================================================ 5. ALL is a grant, not a giveaway


def test_all_grants_entitlement_but_the_budget_still_settles(client, db_session, monkeypatch):
    register_and_login(client, "p6_flag_all_free")     # Free tier: strong reasoning DENIED
    _make_admin(db_session, "p6_flag_all_free")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    from usage.models import AIRequest
    from usage.capabilities import check_capability_permission
    assert check_capability_permission("free", "tutor.strong_reasoning")["allowed"] is False

    denied = client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE})
    assert denied.status_code == 403                   # the policy answers first

    client.put(FLAGS, json={"flags": {"deep_study": "ALL"}})
    granted = client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE})
    assert granted.status_code == 200, granted.text
    request_id = granted.json()["request_id"]

    db_session.expire_all()
    row = db_session.query(AIRequest).filter(AIRequest.request_id == request_id).one()
    # the ENTITLEMENT step was widened; the accounting chain was NOT
    assert row.status == "settled"
    assert row.tier == "free"                           # the REAL tier is recorded
    assert row.actual_credits is not None               # the call was still billed
    from usage.models import UsageLedger
    ledger = (db_session.query(UsageLedger)
              .filter(UsageLedger.request_id == request_id).all())
    assert ledger, "a granted call still settles through the usage ledger"

    # the grant is recorded in the call's own audit fact
    from data_plane.models import LearningEvent
    event = (db_session.query(LearningEvent)
             .filter(LearningEvent.event_type == "ai_called",
                     LearningEvent.source_attempt_id == request_id).one())
    payload = json.loads(event.item_snapshot_json)
    assert payload["entitlement_grant"] == "ALL"
    assert payload["status"] == "succeeded"


def test_off_is_stronger_than_all(client, db_session, monkeypatch):
    """A closed workflow stays closed even for an admin, and OFF never grants."""
    register_and_login(client, "p6_flag_off_wins")
    _make_admin(db_session, "p6_flag_off_wins")
    client.put(FLAGS, json={"flags": {"deep_study": "OFF"}})
    assert feature_flags.capability_entitlement_grant(
        db_session, _user(db_session, "p6_flag_off_wins").id,
        "tutor.strong_reasoning")["granted"] is False
    denied = client.post(DEEP_STUDY, json={"question": "q", "course_id": COURSE})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "feature_disabled"


# ================================================================ 6. storage decisions (§D)


def _wrong_state(db, username):
    """ONE real wrong-answer state for the caller, through the practice core."""
    from core.learning_context import ServiceNamespace
    from learning.practice import service as practice_service
    from learning.practice.refs import QuestionRef, QuestionSourceType
    from learning.spaces.course_learning.context import build_course_context
    from learning.wrong_answers import service as wrong_service
    from models import AIGeneratedQuestion, CourseLearningPreference

    db.add(CourseLearningPreference(username=username, course_id=COURSE,
                                    display_name=COURSE, is_started=True))
    db.commit()
    user = _user(db, username)
    question = AIGeneratedQuestion(
        username=username, subject_key=COURSE, subject_name=COURSE, question_type="选择题",
        stem="顺序存储的线性表按下标访问的时间复杂度是？",
        options_json=json.dumps({"A": "O(1)", "B": "O(n)"}, ensure_ascii=False),
        standard_answer="A", analysis="顺序存储按下标计算地址。", quality_status="unchecked",
        generation_mode="ai")
    db.add(question)
    db.commit()
    db.refresh(question)

    context = build_course_context(user, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="p6_storage",
        source_session_key=f"p6:{COURSE}", mode="p6", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=None,
        context=context,
        source=self_source(user, question.id)).attempt
    return wrong_service.list_states(db, user.id, service_namespace="course_learning")[0]


def self_source(user, question_id):
    from learning.practice import service as practice_service
    return practice_service.SourceIdentity("p6_storage_attempt", f"q{question_id}", "0")


def test_the_wrong_analysis_gap_is_stated_and_never_written_into_a_learner_fact(
        client, db_session, monkeypatch):
    """§D, as a held contract: the analysis text has NO owned store this round, and the
    deterministic learner fact is never overwritten with an AI hypothesis.

    Re-opening the same wrong answer therefore CANNOT restore the previous analysis — it
    produces a NEW request. That gap is asserted here so it cannot change silently, and so the
    closed `persistence` block keeps telling the truth until a store is authorized.
    """
    register_and_login(client, "p6_storage_member")
    grant_unified_tier(db_session, "p6_storage_member", "standard")
    state = _wrong_state(db_session, "p6_storage_member")
    deterministic = state.id

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _analysis_provider)
    first = client.post(f"/wrong-answers/{deterministic}/analysis")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["analysis_origin"] == "ai" and body["fact_origin"] == "deterministic"
    assert body["persistence"] == {
        "stored": False,
        "reason": "no_owned_store_for_ai_analysis_text",
        "durable_facts": ["ai_requests", "learning_events:wrong_analysis_generated"],
    }

    # re-opening produces a NEW request: there is no retrieval path, and the response says so
    second = client.post(f"/wrong-answers/{deterministic}/analysis")
    assert second.status_code == 200, second.text
    assert second.json()["request_id"] != body["request_id"]

    # the AI hypothesis never became the learner's own deterministic record
    record = client.get(f"/wrong-answers/{deterministic}").json()
    assert record["error_analysis"] != body["analysis"]
    assert "reasoning_gap" not in json.dumps(record, ensure_ascii=False)
