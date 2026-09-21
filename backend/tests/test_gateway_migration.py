"""STEP 7C: representative endpoint migrated through the orchestrator (no live API)."""
from unittest.mock import patch

from ai.providers import FakeProvider
from conftest import register_and_login
import main


def test_question_analysis_uses_orchestrator(client):
    register_and_login(client, "mig_1")
    with patch("ai.orchestrator.default_provider_factory",
               return_value=FakeProvider(provider="deepseek", model="deepseek-chat")):
        r = client.post(
            "/exam/11408/operating_system/question-analysis",
            json={"stem": "什么是进程？", "question_type": "选择题",
                  "standard_answer": "A", "user_answer": "B",
                  "options": {"A": "进程", "B": "线程"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["analysis"] == "fake response"
    assert body.get("request_id")
    assert body.get("model") == "deepseek-flash"


def test_question_analysis_requires_stem(client):
    register_and_login(client, "mig_2")
    r = client.post("/exam/11408/operating_system/question-analysis", json={"stem": ""})
    assert r.status_code == 400


def test_course_material_summary_uses_course_orchestrator_boundary(monkeypatch):
    """Upload-time Course summaries cannot fall back to the legacy provider client."""
    captured = {}

    def fake_course_ai(db, user, capability, messages, **kwargs):
        captured.update(
            db=db, user=user, capability=capability, messages=messages, kwargs=kwargs)
        return "统一 AI 摘要"

    monkeypatch.setattr(main, "_course_ai_content", fake_course_ai)
    monkeypatch.setattr(main, "call_deepseek", lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError("Course summary reached legacy direct provider")))

    user = object()
    assert main.summarize_material("data_structure", "线性表支持随机访问。", object(), user) == "统一 AI 摘要"
    assert captured["capability"] == "material.qa"
    assert captured["kwargs"]["course_id"] == "data_structure"


def test_course_code_analysis_uses_course_orchestrator_boundary(client, monkeypatch):
    register_and_login(client, "mig-course-code")
    captured = {}

    class _StubResult:
        """The boundary now returns the whole result (P6.1) so the endpoint can expose the
        real ``ai_requests`` identity; the assertion below is about WHICH boundary it takes."""

        content = "统一 AI 代码讲解"
        request_id = "stub-course-request"

    def fake_course_ai(_db, _user, capability, _messages, **kwargs):
        captured.update(capability=capability, kwargs=kwargs)
        return _StubResult()

    monkeypatch.setattr(main, "_course_ai_result", fake_course_ai)
    monkeypatch.setattr(main, "call_deepseek", lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError("Course code analysis reached legacy direct provider")))
    response = client.post("/code/analyze", json={
        "username": "mig-course-code", "course_id": "data_structure",
        "language": "Python", "code": "print('ok')", "question": "解释代码作用",
    })
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == "统一 AI 代码讲解"
    assert captured["capability"] == "programming.explain"
    assert captured["kwargs"]["course_id"] == "data_structure"


def test_course_paper_structuring_and_json_repair_use_orchestrator_boundary(monkeypatch):
    captured = []

    def fake_course_ai(_db, _user, capability, _messages, **kwargs):
        captured.append((capability, {k: v for k, v in kwargs.items()
                                       if k != 'exam_scope_values' and v not in (None, (), [], {})}))
        if capability == "question.generate":
            return '{"questions":[{"content":"题干","answer":"A"}]}'
        return '{"items":[]}'

    monkeypatch.setattr(main, "_course_ai_content", fake_course_ai)
    monkeypatch.setattr(main, "get_user_by_username", lambda *_a: object())
    monkeypatch.setattr(main, "check_usage_limit", lambda *_a, **_kw: None)
    monkeypatch.setattr(main, "call_deepseek", lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError("Course helper reached legacy direct provider")))
    result, _elapsed = main.structure_practice_paper_text(
        "第一题内容", {}, "paper.txt", "data_structure", None,
        username="owner", db=object())
    assert result["drafts"]
    assert main._repair_json_with_ai("{bad", "invalid", object(), object(), "course_learning",
                                     course_id="data_structure") == '{"items":[]}'
    assert captured == [
        ("question.generate", {"course_id": "data_structure"}),
        ("planning.generate", {"course_id": "data_structure", "max_tokens": 1000}),
    ]


def test_course_plan_preview_uses_course_orchestrator_boundary(client, monkeypatch):
    register_and_login(client, "mig-course-plan")
    captured = {}

    def fake_course_ai(_db, _user, capability, _messages, **kwargs):
        captured.update(capability=capability,
                        kwargs={k: v for k, v in kwargs.items()
                                if k != 'exam_scope_values' and v not in (None, (), [], {})})
        return '{"plan_title":"学习计划","summary":"按课程安排","items":[]}'

    # STEP7H3: the shared dispatcher is the boundary now; `_course_ai_content` is its
    # course side, so intercept that.
    monkeypatch.setattr(main, "_scoped_ai_content", fake_course_ai)
    monkeypatch.setattr(main, "call_deepseek", lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError("Course plan preview reached legacy direct provider")))
    response = client.post("/learning/plans/generate-preview", json={
        "username": "mig-course-plan", "course_id": "data_structure", "days": 3,
    })
    assert response.status_code == 200, response.text
    assert captured == {
        "capability": "planning.generate",
        "kwargs": {"course_id": "data_structure"},
    }
