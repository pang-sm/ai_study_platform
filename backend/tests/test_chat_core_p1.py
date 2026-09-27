"""CHAT_CORE_P1 contracts: durable multi-turn context and scope isolation."""
from __future__ import annotations

import dataclasses

import pytest

from ai.providers import FakeProvider
from conftest import register_and_login
from models import ChatSession, User
from usage import service as usage_service


class RecordingProvider(FakeProvider):
    def __init__(self, calls: list, **kwargs):
        super().__init__(**kwargs)
        self.calls = calls

    def complete(self, spec):
        self.calls.append(spec)
        return dataclasses.replace(super().complete(spec), content="已收到")


@pytest.fixture
def provider(monkeypatch):
    calls: list = []

    def factory(name: str):
        return RecordingProvider(calls, provider=name, input_tokens=20, output_tokens=20)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", factory)
    return calls


def _activate(db_session, username: str):
    user = db_session.query(User).filter_by(username=username).one()
    usage_service.activate_subscription(db_session, user.id, "advanced", 30)
    user_id = user.id
    # The TestClient writes through another SessionLocal connection.  Release the
    # fixture's read transaction before exercising an event-emitting denial path.
    db_session.rollback()
    return user_id


def _declare(client, courses):
    """Give the learner the course, the way the product does (学习设置 → 我的课程).

    A course conversation is a surface of a course the learner HAS: since course Q&A now
    enforces that, a test that chats in a course has to own it first.
    """
    reply = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "",
        "selected_courses": list(courses), "recommended_courses": [],
        "material_types": [], "course_goals": {}, "onboarding_completed": True,
    })
    assert reply.status_code == 200, reply.text


def _exam_body(message: str, **more):
    return {
        "message": message,
        "service_key": "exam_11408",
        "exam_subject": "data_structure",
        "subject": "",
        "course": "",
        **more,
    }


def test_existing_session_sends_prior_turns_once_and_in_order(client, db_session, provider):
    register_and_login(client, "chat-p1-context")
    _activate(db_session, "chat-p1-context")

    first = client.post("/chat", json=_exam_body("请记住验证码是 7319。"))
    assert first.status_code == 200, first.text
    session_id = first.json()["session"]["id"]

    second = client.post("/chat", json=_exam_body("我刚才让你记住的验证码是什么？", session_id=session_id))
    assert second.status_code == 200, second.text

    messages = [(item.role, item.content) for item in provider[-1].messages]
    assert messages[0][0] == "system"
    assert messages[1:] == [
        ("user", "请记住验证码是 7319。"),
        ("assistant", "已收到"),
        ("user", "我刚才让你记住的验证码是什么？"),
    ]
    assert sum(content == "我刚才让你记住的验证码是什么？" for _, content in messages) == 1


def test_scoped_detail_requires_and_enforces_exam_scope(client, db_session, provider):
    register_and_login(client, "chat-p1-exam-scope")
    _activate(db_session, "chat-p1-exam-scope")
    created = client.post("/chat", json=_exam_body("解释链表"))
    assert created.status_code == 200, created.text
    session_id = created.json()["session"]["id"]

    assert client.get(f"/chat/sessions/{session_id}").status_code == 400
    assert client.get(f"/chat/sessions/{session_id}", params={"exam_subject": "operating_system"}).status_code == 404
    assert client.get(f"/chat/sessions/{session_id}", params={"exam_subject": "data_structure"}).status_code == 200


def test_course_session_cannot_be_loaded_or_deleted_from_another_course(client, db_session, provider):
    register_and_login(client, "chat-p1-course-scope")
    _activate(db_session, "chat-p1-course-scope")
    _declare(client, ["数据结构"])
    created = client.post("/chat", json={"message": "解释线性表", "course": "data_structure", "service_key": "course_learning"})
    assert created.status_code == 200, created.text
    session_id = created.json()["session"]["id"]

    assert client.get(f"/chat/sessions/{session_id}", params={"course": "operating_system"}).status_code == 404
    assert client.get(f"/chat/sessions/{session_id}", params={"course": "data_structure"}).status_code == 200
    assert client.delete(f"/chat/sessions/{session_id}", params={"course": "operating_system"}).status_code == 404


def test_new_session_persists_exactly_one_scope(client, db_session, provider):
    register_and_login(client, "chat-p1-new-scope")
    _activate(db_session, "chat-p1-new-scope")
    response = client.post("/chat", json={
        "message": "解释线性表", "course": "data_structure", "exam_subject": "operating_system",
        "service_key": "course_learning",
    })
    assert response.status_code == 400
    user_id = db_session.query(User).filter_by(username="chat-p1-new-scope").one().id
    assert db_session.query(ChatSession).filter_by(user_id=user_id).count() == 0


def test_model_id_reaches_explicit_router_path_and_returns_actual_model(client, db_session, provider):
    register_and_login(client, "chat-p1-model")
    _activate(db_session, "chat-p1-model")
    _declare(client, ["数据结构"])
    response = client.post("/chat", json={"message": "解释线性表", "course": "data_structure", "model_id": "qwen3.8-flash"})
    assert response.status_code == 200, response.text
    assert provider[-1].model == "qwen3.8-flash"
    assert response.json()["resolved_model"] == "qwen3.8-flash"


def test_invalid_model_id_never_silently_autoselects(client, db_session, provider, monkeypatch):
    register_and_login(client, "chat-p1-invalid-model")
    _activate(db_session, "chat-p1-invalid-model")
    _declare(client, ["数据结构"])
    # The denial path emits a best-effort data-plane fact through a separate SQLite
    # connection.  That cross-connection telemetry is covered elsewhere; keep this
    # contract focused on the HTTP/router boundary.
    monkeypatch.setattr("ai.orchestrator.AIOrchestrator._emit_ai_called", staticmethod(lambda *args, **kwargs: None))
    response = client.post("/chat", json={"message": "解释线性表", "course": "data_structure", "model_id": "not-a-qualified-model"})
    assert response.status_code in {403, 429, 502}
    assert provider == []


def test_deep_turn_stays_in_the_same_session_and_reaches_provider_thinking(client, db_session, provider):
    register_and_login(client, "chat-p2a-deep")
    _activate(db_session, "chat-p2a-deep")

    first = client.post("/chat", json=_exam_body("记住数字 31415。"))
    assert first.status_code == 200, first.text
    session_id = first.json()["session"]["id"]

    second = client.post("/chat", json=_exam_body(
        "我刚才让你记住什么数字？", session_id=session_id, thinking_mode="deep",
    ))
    assert second.status_code == 200, second.text
    assert provider[-1].thinking is True
    assert [(message.role, message.content) for message in provider[-1].messages][1:] == [
        ("user", "记住数字 31415。"),
        ("assistant", "已收到"),
        ("user", "我刚才让你记住什么数字？"),
    ]
