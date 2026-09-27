"""A 408 conversation can carry the knowledge point the learner opened, and nothing more.

The knowledge outline links into the paper's own 对话 page with the canonical code of the node
the learner was reading. That code has to reach the model as the FOCUS of the turn and reach the
platform as the turn's `LearningContext.knowledge_point_id` — the same field `/ai/deep-study`
already carries — or the learner is silently in a conversation about the whole paper while the
page tells them it is about one point.

What it must NOT do is compose a question. The learner's own words are the question; the code is
context, and the stored conversation is the learner's turn as they typed it.
"""
import pytest
from fastapi.testclient import TestClient

from ai.providers import FakeProvider
from conftest import register_and_login
from usage.models import AIRequest
from usage import service as usage_service
from models import ChatMessage, ChatSession, User

MODULE = "computer_organization"
KNOWLEDGE_POINT = "1.1.1"


class CountingProvider(FakeProvider):
    def __init__(self, calls: list, **kwargs):
        super().__init__(**kwargs)
        self._calls = calls

    def complete(self, spec):
        self._calls.append((self.name, spec.model, spec.capability))
        return super().complete(spec)


@pytest.fixture
def provider(monkeypatch):
    calls: list = []

    def _install(content: str | None = None) -> list:
        def _make(name: str) -> FakeProvider:
            return CountingProvider(calls, provider=name, input_tokens=50, output_tokens=50)
        monkeypatch.setattr("ai.orchestrator.default_provider_factory", _make)
        return calls

    return _install


def _activate(db_session, username, tier="advanced"):
    user = db_session.query(User).filter_by(username=username).one()
    usage_service.activate_subscription(db_session, user.id, tier, 30)
    db_session.rollback()


def _ask(message="这一步为什么是这样", **more):
    body = {
        "message": message,
        "service_key": "exam_11408",
        "course_id": "",
        "course": "",
        "subject_key": "",
        "exam_subject": MODULE,
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


def _latest_request(db_session, username) -> AIRequest:
    user = db_session.query(User).filter_by(username=username).one()
    request = (db_session.query(AIRequest).filter(AIRequest.user_id == user.id)
               .order_by(AIRequest.id.desc()).first())
    assert request is not None, "the turn produced no ai_requests row"
    return request


def _latest_learner_message(db_session, username) -> ChatMessage:
    user = db_session.query(User).filter_by(username=username).one()
    session_ids = [row.id for row in db_session.query(ChatSession)
                   .filter(ChatSession.user_id == user.id)]
    assert session_ids, "the turn produced no chat session"
    return (db_session.query(ChatMessage)
            .filter(ChatMessage.session_id.in_(session_ids), ChatMessage.role == "user")
            .order_by(ChatMessage.id.desc()).first())


def test_a_turn_that_names_a_knowledge_point_files_it_as_its_context(client, db_session, provider):
    register_and_login(client, "kp-chat-scope")
    _activate(db_session, "kp-chat-scope")
    provider()

    reply = client.post("/chat", json=_ask(knowledge_point_id=KNOWLEDGE_POINT))
    assert reply.status_code == 200, reply.text

    context = _latest_request(db_session, "kp-chat-scope").context_json
    assert context["service_namespace"] == "exam_prep"
    assert context["exam_module_id"] == MODULE
    # The point the learner opened is the turn's context — not a note somewhere beside it.
    assert context["knowledge_point_id"] == KNOWLEDGE_POINT


def test_a_turn_without_one_carries_none(client, db_session, provider):
    register_and_login(client, "kp-chat-none")
    _activate(db_session, "kp-chat-none")
    provider()

    assert client.post("/chat", json=_ask()).status_code == 200
    context = _latest_request(db_session, "kp-chat-none").context_json
    assert context["exam_module_id"] == MODULE
    assert not context.get("knowledge_point_id")


def test_the_stored_question_is_the_learners_own_words(client, db_session, provider):
    register_and_login(client, "kp-chat-message")
    _activate(db_session, "kp-chat-message")
    provider()

    question = "这个知识点里，为什么先算地址再取数？"
    assert client.post("/chat", json=_ask(message=question, knowledge_point_id=KNOWLEDGE_POINT)).status_code == 200

    # The conversation the learner reads back is their question — the context the model was given
    # is not written into it, and no question was asked on their behalf.
    assert _latest_learner_message(db_session, "kp-chat-message").content == question


@pytest.mark.parametrize("value", ["x" * 400, "  1.1.1  "])
def test_the_point_is_normalized_the_one_place_a_value_enters(client, db_session, provider, value):
    """Whatever arrives, what is stored is a trimmed, bounded string — never the raw input."""
    name = f"kp-chat-norm-{len(value)}"
    register_and_login(client, name)
    _activate(db_session, name)
    provider()

    assert client.post("/chat", json=_ask(knowledge_point_id=value)).status_code == 200
    stored = _latest_request(db_session, name).context_json.get("knowledge_point_id")
    assert stored == value.strip()[:120]
