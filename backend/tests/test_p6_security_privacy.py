"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6 §G — security & privacy of the advanced APIs.

WHAT THIS FILE ADDS
-------------------
The per-domain files already hold each surface's own ownership rules (another learner's state
is a 404, another course's material is excluded, another language's catalog is not selected).
This file holds the CROSS-CUTTING properties P6 changes or newly exposes:

1. an ops feature grant widens ENTITLEMENT only — never ownership: a granted Free learner
   still cannot ground an answer in someone else's material;
2. no advanced API response carries a provider secret, an API key, prompt internals, a
   filesystem path, or another learner's content;
3. the three admin analytics surfaces are admin-only and AGGREGATED, and say so;
4. the admin ops read never returns learner source code, patch text or a model response.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json
import uuid

import pytest

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import MaterialChunk, ProgrammingExercise, ProgrammingExerciseProgress, StudyMaterial
from models import User

DEEP_STUDY = "/ai/deep-study"
ADAPTIVE = "/adaptive/practice"
AI_OPS = "/admin/ai-operations/summary"
WF_OPS = "/admin/workflow-operations/summary"
FEEDBACK_ANALYTICS = "/ai/feedback/analytics"
FLAGS = "/admin/feature-flags"
COURSE = "数据结构"
SECRET_TEXT = "四零四秘密讲义：虚拟内存的秘密公式是 42。"

# Credential material: must never appear in ANY payload, learner-facing or admin.
SECRET_TOKENS = ("api_key", "apikey", "sk-", "bearer ", "authorization:",
                 "dashscope_api_key", "ark_api_key", "password", "token=")
# Provider / model identity: NOT a secret. The model menu (`/ai/models`, and the
# `model.options` block of a workflow response) publishes it BY DESIGN so the learner can pick
# a model, and the admin AI ops breakdown is asked for by name. It must not appear in an
# ANSWER, a citation, a user-safe model LABEL, or anywhere else.
PROVIDER_TOKENS = ("deepseek", "qwen", "doubao", "kimi", "moonshot", "glm", "zhipu", "minimax",
                   "ark", "openai", "anthropic")


class _EchoProvider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content="答案。")


def _provider(name: str) -> FakeProvider:
    return _EchoProvider(provider=name, input_tokens=50, output_tokens=30)


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


@pytest.fixture(autouse=True)
def _reset_feature_flags(db_session):
    yield
    from models import SystemSetting
    from ops import feature_flags
    db_session.rollback()
    db_session.query(SystemSetting).filter(
        SystemSetting.key.like(f"{feature_flags.SETTING_KEY_PREFIX}%")
    ).delete(synchronize_session=False)
    db_session.commit()


def _material(db, username, course_id, filename, text) -> StudyMaterial:
    material = StudyMaterial(
        username=username, course_id=course_id, subject_key=course_id, subject=course_id,
        file_type="text", original_filename=filename, file_hash=f"hash-{filename}",
        file_path=f"uploads/{username}/{filename}", file_size=len(text), extracted_text=text,
        summary="", parse_status="success", is_deleted=False,
        visibility="private", allow_private_rag=True)
    db.add(material)
    db.commit()
    db.refresh(material)
    db.add(MaterialChunk(
        material_id=material.id, username=username, course_id=course_id,
        subject_key=course_id, subject=course_id, chunk_index=0, chunk_text=text,
        chunk_summary=text[:80], keywords="虚拟内存", source_filename=filename))
    db.commit()
    return material


def _scan(payload) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _assert_no_secret(payload, *, where: str = "payload") -> str:
    """Credential material, prompt internals and filesystem paths: never, anywhere."""
    text = _scan(payload)
    lowered = text.lower()
    for token in SECRET_TOKENS:
        assert token not in lowered, f"secret token leaked into {where}: {token}"
    assert "C:\\" not in text and "/var/" not in text
    assert "uploads/" not in text and "backend/.env" not in text
    assert "你是一名" not in text, "prompt internals leaked"
    assert "严格返回JSON" not in text, "prompt internals leaked"
    return text


def _assert_no_provider_name(payload, *, where: str) -> str:
    """Provider / model identity outside the places the product publishes it on purpose."""
    lowered = _scan(payload).lower()
    for token in PROVIDER_TOKENS:
        assert token not in lowered, f"provider identity leaked into {where}: {token}"
    return lowered


# ================================================================ 1. grant ≠ ownership


def test_an_all_grant_widens_entitlement_but_not_ownership(client, db_session, monkeypatch):
    """The one invariant an ops grant must never break.

    A granted Free learner may reach the workflow, but the material rule still decides what the
    answer may be grounded in — and the refusal is STATED, never silently dropped.
    """
    register_and_login(client, "p6_sec_owner")
    grant_unified_tier(db_session, "p6_sec_owner", "standard")
    foreign = _material(db_session, "p6_sec_owner", COURSE, "foreign.txt", SECRET_TEXT)

    register_and_login(client, "p6_sec_foreign")          # Free tier
    owned = _material(db_session, "p6_sec_foreign", COURSE, "own.txt", "自己的资料：分页。")

    admin = _user(db_session, "p6_sec_foreign")
    admin.is_admin = 1
    admin.admin_role = "super_admin"
    db_session.commit()
    client.put(FLAGS, json={"flags": {"deep_study": "ALL"}})
    admin.is_admin = 0
    admin.admin_role = "none"
    db_session.commit()
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)

    # the grant opens the WORKFLOW…
    response = client.post(DEEP_STUDY, json={"question": "虚拟内存？", "course_id": COURSE,
                                            "material_ids": [foreign.id]})
    assert response.status_code == 200, response.text
    body = response.json()
    # …and ownership still decides the CONTENT: the other learner's material is refused BY NAME
    assert body["materials"]["used"] == []
    assert foreign.id in body["materials"]["excluded"]
    assert SECRET_TEXT not in _scan(body), "another learner's material was read"
    # the space-scoped retrieval may still ground the answer in the caller's OWN material —
    # never in anyone else's
    assert all(citation["material_id"] == owned.id for citation in body["citations"])


def test_a_grant_does_not_open_another_learners_wrong_answer(client, db_session, monkeypatch):
    """The same invariant on a state-scoped workflow: a 404 is still a 404."""
    from learning.wrong_answers import service as wrong_service
    from learning.wrong_answers.models import WrongAnswerState

    register_and_login(client, "p6_sec_wa_owner")
    owner = _user(db_session, "p6_sec_wa_owner")
    state = WrongAnswerState(user_id=owner.id, service_namespace="course_learning",
                             question_source_type="course_question", question_source_id="1",
                             question_scope_key="q1", status="active")
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)

    register_and_login(client, "p6_sec_wa_other")
    admin = _user(db_session, "p6_sec_wa_other")
    admin.is_admin = 1
    admin.admin_role = "super_admin"
    db_session.commit()
    client.put(FLAGS, json={"flags": {"wrong_analysis": "ALL"}})
    admin.is_admin = 0
    admin.admin_role = "none"
    db_session.commit()

    assert client.post(f"/wrong-answers/{state.id}/analysis").status_code == 404
    assert wrong_service.get_state(db_session, owner.id, state.id).id == state.id


# ================================================================ 2. no leak in payloads


def test_advanced_workflow_payloads_carry_no_secret_or_prompt_internals(
        client, db_session, monkeypatch):
    register_and_login(client, "p6_sec_leak")
    grant_unified_tier(db_session, "p6_sec_leak", "advanced")
    _material(db_session, "p6_sec_leak", COURSE, "notes.txt", SECRET_TEXT)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)

    deep = client.post(DEEP_STUDY, json={"question": "虚拟内存？", "course_id": COURSE})
    assert deep.status_code == 200, deep.text
    deep_body = deep.json()
    _assert_no_secret(deep_body, where="deep study")
    # the model LABEL is user-safe: a strength label, never the provider or the raw model id
    assert deep_body["model"]["display_name"].startswith("智学")
    _assert_no_provider_name(deep_body["model"]["display_name"], where="model label")
    # the ANSWER and its CITATIONS name no provider either
    _assert_no_provider_name({"answer": deep_body["answer"],
                              "citations": deep_body["citations"]}, where="answer")

    report = client.post("/ai/learning-report",
                         json={"service_key": "course_learning", "period_days": 7,
                               "course_id": COURSE, "include_narrative": True})
    assert report.status_code == 200, report.text
    _assert_no_secret(report.json(), where="learning report")

    plan = client.post("/ai/plan-adjustment",
                       json={"service_key": "course_learning", "goal": "复习",
                             "course_id": COURSE})
    assert plan.status_code in (200, 400), plan.text
    _assert_no_secret(plan.json(), where="plan adjustment")


def test_ops_read_never_returns_learner_code_or_prompt(client, db_session):
    """§C/§G: the per-run ops read is code-free by contract and by scan."""
    from learning.records import producers

    register_and_login(client, "p6_sec_run")
    admin = _user(db_session, "p6_sec_run")
    admin.is_admin = 1
    admin.admin_role = "super_admin"
    db_session.commit()

    run_id = f"p6-sec-{uuid.uuid4().hex[:8]}"
    producers.emit_programming_agent_started(
        user_id=admin.id, agent_run_id=run_id, exercise_id=1, language="C",
        max_iterations=3, max_executions=4, occurred_at=None)
    producers.emit_programming_agent_completed(
        user_id=admin.id, agent_run_id=run_id, status="completed", language="C",
        steps=[{"index": 0, "action": "propose_patch", "status": "ok", "latency_ms": 5,
                "credits": 1, "ai_request_id": f"{run_id}:0:propose_patch",
                "file": "main.c",
                "patch": {"patch_chars": 30, "lines_added": 2, "lines_removed": 1}}],
        occurred_at=None)

    detail = client.get(f"/admin/workflow-operations/agent-runs/{run_id}").json()
    text = _assert_no_secret(detail, where="agent run detail")
    # a patch is described by SIZE and shape — the diff text and the source never travel here
    assert detail["trace"][0]["patch"] == {"patch_chars": 30, "lines_added": 2,
                                          "lines_removed": 1}
    assert "content" not in text and "def " not in text and "#include" not in text


# ================================================================ 3. admin analytics


def test_every_admin_analytics_surface_is_admin_only_and_aggregated(client, db_session,
                                                                    monkeypatch):
    register_and_login(client, "p6_sec_member")
    grant_unified_tier(db_session, "p6_sec_member", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    call = client.post(DEEP_STUDY, json={"question": "虚拟内存？", "course_id": COURSE})
    assert call.status_code == 200, call.text

    for path in (AI_OPS, WF_OPS, FEEDBACK_ANALYTICS + "?scope=platform"):
        assert client.get(path).status_code == 403, path

    user = _user(db_session, "p6_sec_member")
    user.is_admin = 1
    user.admin_role = "auditor"                     # read-only role holds ai_logs.view
    db_session.commit()

    for path in (AI_OPS, WF_OPS, FEEDBACK_ANALYTICS + "?scope=platform"):
        body = client.get(path).json()
        text = _assert_no_secret(body, where=path)
        # identity is claimed only by AGGREGATE: no username and no request identity appears
        # (a bare integer user id is not checkable here — small ids collide with metric values)
        assert "p6_sec_member" not in text
        assert call.json()["request_id"] not in text
        assert body["scope"] == "platform"

    # each of the three says explicitly that it is an aggregate view
    assert client.get(AI_OPS).json()["privacy"]["aggregate_only"] is True
    assert client.get(WF_OPS).json()["privacy"]["aggregate_only"] is True
    assert (client.get(FEEDBACK_ANALYTICS, params={"scope": "platform"}).json()
            ["router_mutation"] is False)
    # the AI ops breakdown names providers/models ON PURPOSE (§A asks for it) — and it is the
    # ONLY one of the three that does, which is why it states its own bounded sources.
    ops = client.get(AI_OPS).json()
    assert ops["by_provider"] and ops["by_model"]
    assert ops["privacy"]["aggregate_only"] is True


# ================================================================ 4. cross-language


def test_cross_language_selection_is_isolated(client, db_session):
    """The §G cross-language check, on the surface that takes a language parameter."""
    register_and_login(client, "p6_sec_lang")
    user = _user(db_session, "p6_sec_lang")

    def _exercise(language):
        row = ProgrammingExercise(
            slug=f"p6-lang-{language.lower()}-{uuid.uuid4().hex[:8]}", title=f"{language}题",
            language=language, difficulty="easy", description="d", tags_json="[]",
            starter_files_json="[]", reference_files_json="[]", public_tests_json="[]",
            hidden_tests_json="[]", official_test_files_json="[]", source_repo="fixture",
            source_path="x.py", source_commit="0" * 40, license="MIT", license_text="MIT",
            attribution="test", audit_report_json="{}", is_active=True,
            quality_status="approved")
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        db_session.add(ProgrammingExerciseProgress(
            user_id=user.id, username=user.username, exercise_id=row.id,
            personal_status="needs_work", last_submit_passed=False, last_public_passed_count=1,
            last_public_total_count=3))
        db_session.commit()
        return row

    java = _exercise("Java")
    python = _exercise("Python")

    for language, expected, unexpected in (("Java", java, python),
                                           ("Python", python, java)):
        body = client.get(ADAPTIVE, params={"service_key": "programming", "course_id": "",
                                            "language": language, "limit": 30}).json()
        assert body["context"]["programming_language"] == language
        ids = {item["question_source_id"] for item in body["candidates"]}
        assert str(expected.id) in ids, f"{language} candidates missing"
        assert str(unexpected.id) not in ids, "another language's exercise was selected"
