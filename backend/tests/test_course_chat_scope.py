"""P3: a course conversation belongs to ONE course, and it can be found under that course.

The course Q&A tab sends the course as the canonical `course_id` and leaves the legacy display
fields empty. Reading only the display fields left every course conversation with NO course on it:
invisible in that course's own history, indistinguishable from another course's, and ungrounded.
These tests pin the identity, the isolation and the capability rule that go with it.
"""
from __future__ import annotations

import pytest

from ai.providers import FakeProvider
from conftest import register_and_login
from models import ChatSession, StudyMaterial, User
from usage import service as usage_service
from usage.models import AIRequest

COURSES = ["数据结构", "计算机组成原理", "操作系统", "计算机网络", "高等数学"]


@pytest.fixture
def provider(monkeypatch):
    def factory(name: str):
        return FakeProvider(provider=name, input_tokens=20, output_tokens=20)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", factory)


def _activate(db_session, username: str) -> int:
    user = db_session.query(User).filter_by(username=username).one()
    usage_service.activate_subscription(db_session, user.id, "advanced", 30)
    user_id = user.id
    # The TestClient writes through another SessionLocal connection.
    db_session.rollback()
    return user_id


def _declare(client, courses=None):
    """The product's own way to have courses: declare them in 学习设置.

    A course conversation is a surface of a course the learner HAS, so every test here has to
    own the course it chats about — which is the real chain (推荐/手动加入 → 我的课程 → 可对话).
    """
    reply = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "",
        "selected_courses": list(courses or COURSES), "recommended_courses": [],
        "material_types": [], "course_goals": {}, "onboarding_completed": True,
    })
    assert reply.status_code == 200, reply.text


def _ask(course_id: str, **more):
    body = {
        "message": "这门课的核心概念是什么？",
        "service_key": "course_learning",
        "course_id": course_id,
        "subject_key": "",
        "subject": "",
        "grade": "",
        "major": "",
        "material_ids": [],
        "branch_id": "",
        "hidden_instruction": "",
        "mastery_level": "",
        "learning_goal": "",
        "model_preference": "",
        "session_id": None,
        "model_id": None,
        "thinking_mode": "standard",
    }
    body.update(more)
    return body


# ── identity (A) ──────────────────────────────────────────────

def test_every_course_conversation_carries_its_own_course(client, db_session, provider):
    register_and_login(client, "p3-chat-identity")
    user_id = _activate(db_session, "p3-chat-identity")
    _declare(client)

    for course in COURSES:
        reply = client.post("/chat", json=_ask(course))
        assert reply.status_code == 200, f"{course}: {reply.text}"

    db_session.expire_all()
    sessions = (db_session.query(ChatSession)
                .filter(ChatSession.user_id == user_id)
                .order_by(ChatSession.id).all())
    assert [session.subject for session in sessions] == COURSES
    assert [session.course for session in sessions] == COURSES


def test_the_english_course_id_lands_on_the_same_conversation(client, db_session, provider):
    """A slug and a display name are two spellings of one course, not two courses."""
    register_and_login(client, "p3-chat-canonical")
    user_id = _activate(db_session, "p3-chat-canonical")
    _declare(client, ["数据结构"])

    assert client.post("/chat", json=_ask("data_structure")).status_code == 200

    db_session.expire_all()
    session = db_session.query(ChatSession).filter(ChatSession.user_id == user_id).one()
    assert session.subject == "数据结构" and session.course == "数据结构"
    # Reachable under either spelling, because the lookup goes through the same canonicalizer.
    assert len(client.get("/chat/history?course=数据结构").json()["sessions"]) == 1
    assert len(client.get("/chat/history?course=data_structure").json()["sessions"]) == 1


# ── isolation (E) ─────────────────────────────────────────────

def test_course_history_holds_only_that_courses_conversations(client, db_session, provider):
    register_and_login(client, "p3-chat-history")
    _activate(db_session, "p3-chat-history")
    _declare(client)

    client.post("/chat", json=_ask("数据结构", message="链表"))
    client.post("/chat", json=_ask("操作系统", message="进程"))

    data_structure = client.get("/chat/history?course=数据结构").json()["sessions"]
    operating_system = client.get("/chat/history?course=操作系统").json()["sessions"]

    assert [session["title"] for session in data_structure] == ["链表"]
    assert [session["title"] for session in operating_system] == ["进程"]
    # A course nobody asked in has nothing.
    assert client.get("/chat/history?course=高等数学").json()["sessions"] == []


def test_a_conversation_cannot_be_continued_from_another_course(client, db_session, provider):
    register_and_login(client, "p3-chat-continue")
    _activate(db_session, "p3-chat-continue")
    _declare(client)

    started = client.post("/chat", json=_ask("数据结构", message="链表"))
    assert started.status_code == 200
    session_id = started.json()["session"]["id"]

    # The same course continues it...
    again = client.post("/chat", json=_ask("数据结构", message="再来一题", session_id=session_id))
    assert again.status_code == 200, again.text

    # ...and another course cannot reach into it.
    refused = client.post("/chat", json=_ask("操作系统", message="进程", session_id=session_id))
    assert refused.status_code == 404


# ── capability (B, C, D) ──────────────────────────────────────

def test_every_course_without_materials_uses_the_same_capability(client, db_session, provider):
    """No course answers through a different (or missing) capability than the others."""
    register_and_login(client, "p3-chat-capability")
    user_id = _activate(db_session, "p3-chat-capability")
    _declare(client)

    for course in COURSES:
        reply = client.post("/chat", json=_ask(course))
        assert reply.status_code == 200, f"{course}: {reply.text}"

    db_session.expire_all()
    requests = db_session.query(AIRequest).filter(AIRequest.user_id == user_id).all()
    assert len(requests) == len(COURSES)
    # A course with no material is still answerable — plain tutoring, not an error.
    assert {request.capability for request in requests} == {"tutor.chat"}


def test_attached_materials_use_the_grounded_capability(client, db_session, provider):
    register_and_login(client, "p3-chat-grounded")
    user_id = _activate(db_session, "p3-chat-grounded")
    _declare(client, ["数据结构"])

    db_session.add(StudyMaterial(
        username="p3-chat-grounded", subject="数据结构", course_id="数据结构",
        subject_key="数据结构", file_type="pdf", original_filename="讲义.pdf",
        file_path="materials/讲义.pdf", file_size=10, extracted_text="链表的定义",
        summary="讲义", parse_status="success", chunk_count=3))
    db_session.commit()
    material_id = (db_session.query(StudyMaterial)
                   .filter(StudyMaterial.username == "p3-chat-grounded").one().id)
    db_session.rollback()

    reply = client.post("/chat", json=_ask("数据结构", material_ids=[material_id]))
    assert reply.status_code == 200, reply.text

    db_session.expire_all()
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user_id).one())
    assert request.capability == "material.qa"


def test_the_answer_survives_a_cost_that_cannot_be_settled_yet(
        client, db_session, monkeypatch):
    """A produced answer is not lost to an accounting state.

    A provider that reports no usage leaves the cost unknown. The reservation stays held for
    reconciliation (nothing is written off), and the learner still gets the answer — the
    course Q&A tab must not turn "we cannot price this yet" into "no answer".
    """
    register_and_login(client, "p3-chat-pending")
    user_id = _activate(db_session, "p3-chat-pending")
    _declare(client, ["数据结构"])
    monkeypatch.setattr(
        "ai.orchestrator.default_provider_factory",
        lambda name: FakeProvider(provider=name, behavior="unknown_usage"))

    reply = client.post("/chat", json=_ask("数据结构"))

    assert reply.status_code == 200, reply.text
    assert reply.json()["answer"].strip()
    db_session.expire_all()
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user_id).one())
    assert request.status == "reconciliation_pending"
    assert request.reserved_credits > 0


def test_an_explicit_model_is_the_one_that_runs(client, db_session, provider):
    register_and_login(client, "p3-chat-model")
    user_id = _activate(db_session, "p3-chat-model")
    _declare(client, ["数据结构"])

    reply = client.post("/chat", json=_ask("数据结构", model_id="qwen3.8-flash"))
    assert reply.status_code == 200, reply.text

    db_session.expire_all()
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user_id).one())
    assert request.model == "qwen3.8-flash"
