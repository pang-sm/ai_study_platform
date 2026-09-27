"""Course Q&A belongs to a course the learner HAS — the same rule its material library applies.

`/chat` used to accept any course name and open a conversation in it, so a learner could chat in
a course that was not theirs while the course's own material library refused the same scope. These
tests pin the boundary: a course scope requires current ownership, on every operation, and the
refusal happens before a session, a retrieval or a provider call exists. Exam and programming
scopes have their own contracts and are untouched.
"""
from __future__ import annotations

import pytest

from ai.providers import FakeProvider
from conftest import register_and_login
from models import ChatMessage, ChatSession, User
from usage import service as usage_service
from usage.models import AIRequest

HELD = "数据结构"
OTHER = "操作系统"
UNHELD = "量子力学导论"


@pytest.fixture
def provider(monkeypatch):
    """Records every provider call, so "was the provider paid for this?" is directly assertable."""
    calls: list = []

    def factory(name: str):
        calls.append(name)
        return FakeProvider(provider=name, input_tokens=20, output_tokens=20)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", factory)
    return calls


def _activate(db_session, username: str) -> int:
    user = db_session.query(User).filter_by(username=username).one()
    usage_service.activate_subscription(db_session, user.id, "advanced", 30)
    user_id = user.id
    db_session.rollback()  # the TestClient writes through another SessionLocal connection
    return user_id


def _declare(client, courses):
    """The learner's own way to have courses: declare them in 学习设置."""
    reply = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "",
        "selected_courses": list(courses), "recommended_courses": [],
        "material_types": [], "course_goals": {}, "onboarding_completed": True,
    })
    assert reply.status_code == 200, reply.text


def _ask(course_id, **more):
    body = {"message": "这门课的核心概念是什么？", "service_key": "course_learning",
            "course_id": course_id, "subject_key": "", "subject": "", "grade": "", "major": "",
            "material_ids": [], "branch_id": "", "hidden_instruction": "", "mastery_level": "",
            "learning_goal": "", "model_preference": "", "session_id": None, "model_id": None,
            "thinking_mode": "standard"}
    body.update(more)
    return body


# ── A: a held course opens normally ───────────────────────────

def test_a_held_course_can_open_a_conversation(client, db_session, provider):
    register_and_login(client, "own-a")
    user_id = _activate(db_session, "own-a")
    _declare(client, [HELD])

    reply = client.post("/chat", json=_ask(HELD))

    assert reply.status_code == 200, reply.text
    assert len(provider) == 1, "the first candidate answered; no fallback was needed"
    session_id = reply.json()["session"]["id"]
    db_session.expire_all()
    session = db_session.query(ChatSession).filter(ChatSession.id == session_id).one()
    assert session.user_id == user_id and session.subject == HELD


# ── B: a course the learner does not have opens nothing ───────

def test_an_unheld_course_cannot_open_a_conversation(client, db_session, provider):
    register_and_login(client, "own-b")
    user_id = _activate(db_session, "own-b")
    _declare(client, [HELD])

    reply = client.post("/chat", json=_ask(UNHELD))

    assert reply.status_code == 404
    # Nothing of this request exists: no session, no message, no billed request, no provider call.
    db_session.expire_all()
    assert db_session.query(ChatSession).filter(ChatSession.user_id == user_id).count() == 0
    assert db_session.query(ChatMessage).filter(ChatMessage.user_id == user_id).count() == 0
    assert db_session.query(AIRequest).filter(AIRequest.user_id == user_id).count() == 0
    assert provider == []


def test_an_unheld_course_cannot_be_asked_about_under_any_spelling(client, db_session, provider):
    """`data_structure` is not a way around the rule for a course the learner does not hold —
    but it IS the same course when they do (see the canonical test below)."""
    register_and_login(client, "own-b2")
    user_id = _activate(db_session, "own-b2")
    _declare(client, [HELD])

    assert client.post("/chat", json=_ask("data_structures")).status_code == 404
    assert client.post("/chat", json=_ask("linear_algebra")).status_code == 404
    db_session.expire_all()
    assert provider == []


# ── C: canonical spellings ────────────────────────────────────

def test_a_canonical_spelling_of_a_held_course_is_accepted(client, db_session, provider):
    register_and_login(client, "own-c")
    user_id = _activate(db_session, "own-c")
    _declare(client, [HELD])

    reply = client.post("/chat", json=_ask("data_structure"))

    assert reply.status_code == 200, reply.text
    db_session.expire_all()
    session = db_session.query(ChatSession).filter(ChatSession.user_id == user_id).one()
    # One course, one identity — the same rule the material scope uses.
    assert session.subject == HELD


# ── D: history ────────────────────────────────────────────────

def test_history_of_an_unheld_course_is_refused_not_emptied(client, db_session, provider):
    register_and_login(client, "own-d")
    _activate(db_session, "own-d")
    _declare(client, [HELD])

    refused = client.get("/chat/history", params={"course": UNHELD})

    # Not `200 []`: an empty list would quietly confirm a scope the learner does not have.
    assert refused.status_code == 404
    # And the course they DO have is unaffected.
    assert client.get("/chat/history", params={"course": HELD}).status_code == 200


# ── E: a course taken out of 我的课程 ──────────────────────────

def test_a_removed_course_keeps_its_history_but_not_its_access(client, db_session, provider):
    register_and_login(client, "own-e")
    user_id = _activate(db_session, "own-e")
    _declare(client, [HELD, OTHER])

    started = client.post("/chat", json=_ask(HELD, message="链表是什么"))
    assert started.status_code == 200, started.text
    session_id = started.json()["session"]["id"]

    # The learner takes 数据结构 out of 我的课程.
    _declare(client, [OTHER])
    declared = client.get("/course-learning/onboarding").json()
    assert declared["selected_courses"] == [OTHER]

    # Every operation on that conversation is refused...
    assert client.get(f"/chat/sessions/{session_id}", params={"course": HELD}).status_code == 404
    assert client.post("/chat", json=_ask(HELD, session_id=session_id)).status_code == 404
    assert client.get("/chat/history", params={"course": HELD}).status_code == 404
    assert client.delete(f"/chat/sessions/{session_id}", params={"course": HELD}).status_code == 404

    # ...while the conversation itself is NOT physically deleted: the history is data, and the
    # record of what was said stays.
    db_session.expire_all()
    assert db_session.query(ChatSession).filter(ChatSession.id == session_id).count() == 1
    assert db_session.query(ChatMessage).filter(ChatMessage.session_id == session_id).count() >= 1
    # Re-adding the course makes it reachable again, unchanged.
    _declare(client, [HELD, OTHER])
    assert client.get(f"/chat/sessions/{session_id}", params={"course": HELD}).status_code == 200


# ── F: cross-course inside one learner ────────────────────────

def test_a_conversation_cannot_be_reached_under_another_course(client, db_session, provider):
    register_and_login(client, "own-f")
    _activate(db_session, "own-f")
    _declare(client, [HELD, OTHER])

    session_id = client.post("/chat", json=_ask(HELD)).json()["session"]["id"]

    assert client.get(f"/chat/sessions/{session_id}", params={"course": OTHER}).status_code == 404
    assert client.delete(f"/chat/sessions/{session_id}", params={"course": OTHER}).status_code == 404
    assert client.post("/chat", json=_ask(OTHER, session_id=session_id)).status_code == 404
    # The conversation is still exactly where it belongs.
    assert client.get(f"/chat/sessions/{session_id}", params={"course": HELD}).status_code == 200


# ── G: another learner ────────────────────────────────────────

def test_another_learners_course_is_neither_a_scope_nor_a_session(client, db_session, provider):
    register_and_login(client, "own-g-owner")
    _activate(db_session, "own-g-owner")
    _declare(client, [HELD])
    session_id = client.post("/chat", json=_ask(HELD)).json()["session"]["id"]
    client.post("/logout")

    register_and_login(client, "own-g-other")
    user_id = _activate(db_session, "own-g-other")
    _declare(client, [OTHER])

    # Not a scope they can open...
    assert client.post("/chat", json=_ask(HELD)).status_code == 404
    # ...not a history they can list...
    assert client.get("/chat/history", params={"course": HELD}).status_code == 404
    # ...and not a session they can read or delete (the id alone is not a key).
    assert client.get(f"/chat/sessions/{session_id}", params={"course": HELD}).status_code == 404
    assert client.delete(f"/chat/sessions/{session_id}", params={"course": HELD}).status_code == 404

    db_session.expire_all()
    assert db_session.query(ChatSession).filter(ChatSession.id == session_id).count() == 1
    assert db_session.query(ChatMessage).filter(ChatMessage.user_id == user_id).count() == 0


# ── H/I: the other spaces keep their own contracts ────────────

def test_exam_chat_is_not_a_course_scope(client, db_session, provider):
    register_and_login(client, "own-h")
    _activate(db_session, "own-h")

    reply = client.post("/chat", json={"message": "进程和线程的区别", "service_key": "exam_11408",
                                       "exam_subject": "operating_system", "subject": "",
                                       "course": ""})

    assert reply.status_code == 200, reply.text


def test_programming_chat_is_not_a_course_scope(client, db_session, provider):
    register_and_login(client, "own-i")
    _activate(db_session, "own-i")

    reply = client.post("/chat", json={"message": "这段代码为什么报错", "service_key": "programming",
                                       "course_id": "python_programming", "subject": "",
                                       "subject_key": "programming"})

    assert reply.status_code == 200, reply.text


def test_general_chat_has_no_course_to_own(client, db_session, provider):
    """A conversation with no course scope is not this rule's business."""
    register_and_login(client, "own-j")
    _activate(db_session, "own-j")

    reply = client.post("/chat", json={"message": "你好", "subject": "", "course": ""})

    assert reply.status_code == 200, reply.text
