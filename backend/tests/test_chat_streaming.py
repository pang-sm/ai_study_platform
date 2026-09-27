"""CHAT_STREAMING_P2B: the real streamed path — provider chunks, SSE, stop, and the ledger.

Everything here runs on fakes and never touches a paid API. What is being pinned:
  * text arrives as the PROVIDER produces it (never one finished answer sliced up afterwards),
  * a candidate is committed by its first visible delta and is never silently replaced,
  * a stop/disconnect closes the provider stream and keeps the text the learner already saw,
  * and every one of those endings still settles the ledger from real usage.
"""
from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from ai.gateway import GatewayError, GatewayErrorCategory, ProviderUsage
from ai.orchestrator import AIOrchestrator
from ai.providers import FakeProvider
from main import _chat_stream_frames
from schemas import ChatRequest
from conftest import register_and_login
from models import ChatMessage, ChatSession, User
from usage import service as usage_service
from usage.models import AICostRecord, AIRequest

HELD = "数据结构"
UNHELD = "量子力学导论"

USAGE = ProviderUsage(input_tokens=20, output_tokens=20, total_tokens=40,
                      usage_source="PROVIDER_REPORTED")


# ---------------------------------------------------------------- doubles


class Scripted(FakeProvider):
    """A provider whose stream script is picked by ATTEMPT ORDER.

    Pool order is a config, so a test that wants "the first candidate answers nothing and the
    second answers" must not depend on which model the router happens to put first.
    """

    def __init__(self, scripts: list, calls: list, closed: list, **kwargs):
        super().__init__(**kwargs)
        self._scripts = scripts
        self._calls = calls
        self._closed = closed

    def stream(self, spec):
        index = len(self._calls)
        self._calls.append((self.name, spec.model))
        script = self._scripts[min(index, len(self._scripts) - 1)]
        delegate = FakeProvider(provider=self.name, stream_script=script,
                                input_tokens=20, output_tokens=20)

        @contextmanager
        def _wrapped():
            try:
                with delegate.stream(spec) as events:
                    yield events
            finally:
                self._closed.append(index)      # the provider stream was closed

        return _wrapped()


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted provider factory and hand the test its bookkeeping lists."""
    state = {"calls": [], "closed": [], "scripts": []}

    def install(scripts: list) -> dict:
        state["scripts"] = scripts
        state["calls"] = []
        state["closed"] = []
        monkeypatch.setattr(
            "ai.orchestrator.default_provider_factory",
            lambda name: Scripted(state["scripts"], state["calls"], state["closed"],
                                  provider=name, input_tokens=20, output_tokens=20))
        return state
    return install


def _activate(db_session, username: str) -> int:
    user = db_session.query(User).filter_by(username=username).one()
    usage_service.activate_subscription(db_session, user.id, "advanced", 30)
    user_id = user.id
    db_session.rollback()
    return user_id


def _declare(client, courses):
    reply = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "",
        "selected_courses": list(courses), "recommended_courses": [],
        "material_types": [], "course_goals": {}, "onboarding_completed": True,
    })
    assert reply.status_code == 200, reply.text


def _body(course_id, **more):
    body = {"message": "这门课的核心概念是什么？", "service_key": "course_learning",
            "course_id": course_id, "subject_key": "", "subject": "", "grade": "", "major": "",
            "material_ids": [], "branch_id": "", "hidden_instruction": "", "mastery_level": "",
            "learning_goal": "", "model_preference": "", "session_id": None, "model_id": None,
            "thinking_mode": "standard"}
    body.update(more)
    return body


def frames(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    out: list[tuple[str, dict]] = []
    event = None
    for line in text.split("\n"):
        if line.startswith("event: "):
            event = line[7:].strip()
        elif line.startswith("data: "):
            out.append((event, json.loads(line[6:])))
        elif line == "":
            event = None
    return out


def answer_text(parsed: list[tuple[str, dict]]) -> str:
    return "".join(data["text"] for event, data in parsed if event == "delta")


TEXT = lambda *chunks: [("text", c) for c in chunks] + [("usage", USAGE), ("finish", "stop")]


# ---------------------------------------------------------------- A/B: normal stream


def test_a_normal_stream_delivers_deltas_then_done_and_persists_once(client, db_session, scripted):
    register_and_login(client, "st-a")
    user_id = _activate(db_session, "st-a")
    _declare(client, [HELD])
    scripted([TEXT("abc", "def")])

    response = client.post("/chat/stream", json=_body(HELD))

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    parsed = frames(response.text)
    assert [event for event, _ in parsed] == ["start", "delta", "delta", "done"]
    assert answer_text(parsed) == "abcdef"
    start = parsed[0][1]
    done = parsed[-1][1]
    assert start["request_id"] and start["session_id"]
    assert done["finish_reason"] == "stop" and done["stopped"] is False
    assert done["resolved_model"]

    # B: the session really holds the whole answer — one assistant message, not many.
    db_session.expire_all()
    session_id = done["session_id"]
    stored = (db_session.query(ChatMessage)
              .filter(ChatMessage.session_id == session_id, ChatMessage.role == "assistant").all())
    assert len(stored) == 1 and stored[0].content == "abcdef"
    assert (db_session.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == "user").count()) == 1

    # ...and the client can reload it through the ordinary non-streaming endpoint.
    detail = client.get(f"/chat/sessions/{session_id}", params={"course": HELD})
    assert detail.status_code == 200
    assert [m["content"] for m in detail.json()["messages"] if m["role"] == "assistant"] == ["abcdef"]


# ---------------------------------------------------------------- C: empty before any text


def test_an_empty_candidate_streams_nothing_and_the_next_one_answers(client, db_session, scripted):
    register_and_login(client, "st-c")
    _activate(db_session, "st-c")
    _declare(client, [HELD])
    state = scripted([
        [("usage", USAGE), ("finish", "stop")],       # candidate A: no visible text at all
        TEXT("ответ"),                                 # candidate B answers
    ])

    response = client.post("/chat/stream", json=_body(HELD))

    parsed = frames(response.text)
    assert answer_text(parsed) == "ответ"
    assert len(state["calls"]) == 2, "the empty candidate must not end the chain"
    done = parsed[-1][1]
    assert done["resolved_model"] == state["calls"][1][1] != state["calls"][0][1]
    assert done["finish_reason"] == "stop"


# ---------------------------------------------------------------- D: explicit model


def test_an_explicit_model_that_streams_nothing_is_not_replaced(client, db_session, scripted):
    register_and_login(client, "st-d")
    _activate(db_session, "st-d")
    _declare(client, [HELD])
    state = scripted([[("usage", USAGE), ("finish", "stop")]])

    response = client.post("/chat/stream", json=_body(HELD, model_id="deepseek-flash"))

    parsed = frames(response.text)
    assert [event for event, _ in parsed][0] == "start"
    assert parsed[-1][0] == "error"
    assert len(state["calls"]) == 1 and state["calls"][0][1] == "deepseek-flash"
    assert answer_text(parsed) == ""
    # Nothing was written for an answer nobody saw.
    db_session.expire_all()
    user_id = db_session.query(User).filter_by(username="st-d").one().id
    assert (db_session.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id, ChatMessage.role == "assistant").count()) == 0


# ---------------------------------------------------------------- E: failure before any text


def test_a_failure_before_the_first_delta_falls_back(client, db_session, scripted):
    register_and_login(client, "st-e")
    _activate(db_session, "st-e")
    _declare(client, [HELD])
    state = scripted([
        [("raise", GatewayError(GatewayErrorCategory.timeout, "boom", "fake", retriable=True))],
        TEXT("second chance"),
    ])

    parsed = frames(client.post("/chat/stream", json=_body(HELD)).text)

    assert answer_text(parsed) == "second chance"
    assert len(state["calls"]) == 2
    assert parsed[-1][1]["resolved_model"] == state["calls"][1][1]


# ---------------------------------------------------------------- F: failure AFTER text


def test_a_failure_after_visible_text_never_switches_model(client, db_session, scripted):
    register_and_login(client, "st-f")
    _activate(db_session, "st-f")
    _declare(client, [HELD])
    state = scripted([
        TEXT("abc") + [("raise", GatewayError(GatewayErrorCategory.provider_error, "broke",
                                              "fake", retriable=True))],
        TEXT("SHOULD NEVER APPEAR"),
    ])

    response = client.post("/chat/stream", json=_body(HELD))

    parsed = frames(response.text)
    assert answer_text(parsed) == "abc", "the second candidate must not be spliced on"
    assert len(state["calls"]) == 1, "a committed candidate is never replaced"
    assert parsed[-1][0] == "error"

    # The partial answer IS the turn: persisted, and the ledger settled the real call.
    db_session.expire_all()
    user_id = db_session.query(User).filter_by(username="st-f").one().id
    stored = (db_session.query(ChatMessage)
              .filter(ChatMessage.user_id == user_id, ChatMessage.role == "assistant").all())
    assert [m.content for m in stored] == ["abc"]
    req = db_session.query(AIRequest).order_by(AIRequest.id.desc()).first()
    assert req.status == "settled"


# ---------------------------------------------------------------- G/H: stop


def _open_stream(db_session, username, body):
    """Open the endpoint's own frame generator, so a test can walk away from it mid-answer.

    The in-process test transport buffers a response, so it cannot drop a connection. Driving the
    generator the response is built from IS the disconnect path: closing it throws GeneratorExit
    into exactly the code a real client departure reaches.
    """
    from main import _prepare_chat_turn, _chat_stream_run
    user = db_session.query(User).filter_by(username=username).one()
    turn = _prepare_chat_turn(db_session, user, ChatRequest(**body))
    run = _chat_stream_run(db_session, user, turn)
    return _chat_stream_frames(db_session, user, turn, run)


def test_stopping_closes_the_provider_stream_and_keeps_the_partial(client, db_session, scripted):
    register_and_login(client, "st-g")
    user_id = _activate(db_session, "st-g")
    _declare(client, [HELD])
    state = scripted([TEXT("abc", "def", "ghi")])

    stream = _open_stream(db_session, "st-g", _body(HELD))
    next(stream)                     # start
    next(stream)                     # the first answer text reached the learner
    stream.close()                   # ...and the learner pressed Stop

    assert state["closed"] == [0], "the provider stream must be closed when the reader goes away"
    assert state["calls"] and len(state["calls"]) == 1, "no second model was tried"

    db_session.expire_all()
    stored = (db_session.query(ChatMessage)
              .filter(ChatMessage.user_id == user_id, ChatMessage.role == "assistant").all())
    assert [m.content for m in stored] == ["abc"], "what was shown is what is kept"
    # The provider had not reported usage when the reader left, so the turn is HELD for
    # reconciliation rather than settled to zero — the existing unknown-usage rule, applied to a
    # stop, so a real call's cost is never invented away.
    request = (db_session.query(AIRequest).filter(AIRequest.user_id == user_id)
               .order_by(AIRequest.id.desc()).first())
    assert request.status == "reconciliation_pending"
    assert request.actual_credits is None


def test_stopping_after_usage_arrives_settles_the_real_cost(client, db_session, scripted):
    """The same stop, with the provider's usage already in hand, settles what was really spent."""
    register_and_login(client, "st-g2")
    user_id = _activate(db_session, "st-g2")
    _declare(client, [HELD])
    scripted([[("usage", USAGE), ("text", "abc"), ("text", "def"), ("finish", "stop")]])

    stream = _open_stream(db_session, "st-g2", _body(HELD))
    next(stream)                     # start
    next(stream)                     # abc (the usage chunk arrived first)
    stream.close()

    db_session.expire_all()
    stored = (db_session.query(ChatMessage)
              .filter(ChatMessage.user_id == user_id, ChatMessage.role == "assistant").all())
    assert [m.content for m in stored] == ["abc"]
    request = (db_session.query(AIRequest).filter(AIRequest.user_id == user_id)
               .order_by(AIRequest.id.desc()).first())
    assert request.status == "settled"
    assert request.actual_credits is not None


def test_stopping_before_any_text_writes_no_empty_message(client, db_session, scripted):
    register_and_login(client, "st-h")
    user_id = _activate(db_session, "st-h")
    _declare(client, [HELD])
    state = scripted([TEXT("abc")])

    stream = _open_stream(db_session, "st-h", _body(HELD))
    next(stream)                     # start, and nothing else yet
    stream.close()                   # the learner stopped before the first token

    assert state["calls"] == [], "no provider call had begun"
    db_session.expire_all()
    # The question stays; no assistant row is invented for an answer nobody read.
    assert (db_session.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id, ChatMessage.role == "assistant").count()) == 0
    assert (db_session.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id, ChatMessage.role == "user").count()) >= 1
    request = (db_session.query(AIRequest).filter(AIRequest.user_id == user_id)
               .order_by(AIRequest.id.desc()).first())
    assert request.status != "settled", "a cancelled turn is not billed as an answer"


# ---------------------------------------------------------------- I: hidden reasoning


def test_a_reasoning_channel_never_reaches_the_stream(client, db_session, scripted):
    """Only a provider's ANSWER channel is representable; a thinking model's private channel is
    dropped in the adapter, so it cannot arrive here however it is spelled."""
    register_and_login(client, "st-i")
    _activate(db_session, "st-i")
    _declare(client, [HELD])
    scripted([TEXT("visible answer")])

    response = client.post("/chat/stream", json=_body(HELD, thinking_mode="deep"))

    assert "visible answer" in response.text
    lowered = response.text.lower()
    for leaked in ("reasoning", "chain of thought", "scratchpad", "thinking_content"):
        assert leaked not in lowered


def test_the_adapter_drops_a_reasoning_only_chunk():
    """The one place a provider chunk is read: a chunk carrying ONLY reasoning produces nothing."""
    from types import SimpleNamespace

    from ai.gateway import AIRequestSpec, ChatMessage
    from ai.providers.common import stream_openai_chat

    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content=None, reasoning_content="SECRET THOUGHTS"),
            finish_reason=None)], usage=None),
        SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content="answer", reasoning_content=None),
            finish_reason=None)], usage=None),
        SimpleNamespace(choices=[SimpleNamespace(delta=None, finish_reason="stop")], usage=None),
    ]

    class _Client:
        class chat:  # noqa: N801 - mirrors the SDK's attribute shape
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    assert kwargs["stream"] is True
                    return iter(chunks)

    spec = AIRequestSpec(messages=(ChatMessage(role="user", content="hi"),), model="m",
                         max_tokens=100)
    with stream_openai_chat(_Client, spec, provider="fake") as events:
        collected = list(events)

    assert [e.text for e in collected if e.type == "text_delta"] == ["answer"]
    assert all("SECRET" not in (e.text or "") for e in collected)


# ---------------------------------------------------------------- J/K: scope


def test_an_unowned_course_is_refused_before_any_provider_call(client, db_session, scripted):
    register_and_login(client, "st-j")
    _activate(db_session, "st-j")
    _declare(client, [HELD])
    state = scripted([TEXT("never")])

    response = client.post("/chat/stream", json=_body(UNHELD))

    assert response.status_code == 404
    assert state["calls"] == []
    db_session.expire_all()
    user_id = db_session.query(User).filter_by(username="st-j").one().id
    assert db_session.query(AIRequest).filter(AIRequest.user_id == user_id).count() == 0
    assert db_session.query(ChatMessage).filter(ChatMessage.user_id == user_id).count() == 0


def test_a_conversation_cannot_be_streamed_under_another_course(client, db_session, scripted):
    register_and_login(client, "st-k")
    _activate(db_session, "st-k")
    _declare(client, [HELD, "操作系统"])
    scripted([TEXT("hello")])
    started = client.post("/chat/stream", json=_body(HELD))
    session_id = frames(started.text)[0][1]["session_id"]

    refused = client.post("/chat/stream", json=_body("操作系统", session_id=session_id))

    assert refused.status_code == 404


# ---------------------------------------------------------------- L/M: ledger


@pytest.mark.parametrize("ending", ["normal", "fallback", "interrupted"])
def test_every_ending_settles_the_ledger_from_real_usage(client, db_session, scripted, ending):
    register_and_login(client, f"st-l-{ending}")
    user_id = _activate(db_session, f"st-l-{ending}")
    _declare(client, [HELD])
    if ending == "normal":
        scripted([TEXT("fine")])
    elif ending == "fallback":
        scripted([[("usage", USAGE), ("finish", "stop")], TEXT("second")])
    else:
        scripted([TEXT("part") + [("raise", GatewayError(
            GatewayErrorCategory.provider_error, "broke", "fake", retriable=True))]])

    client.post("/chat/stream", json=_body(HELD))

    db_session.expire_all()
    request = (db_session.query(AIRequest).filter(AIRequest.user_id == user_id)
               .order_by(AIRequest.id.desc()).first())
    assert request.status == "settled"
    assert request.actual_credits is not None
    costs = db_session.query(AICostRecord).filter(
        AICostRecord.request_id == request.request_id).all()
    assert costs, "a real provider call must leave a cost record"
    # Nothing was written off and nothing was invented.
    budget = usage_service.get_or_create_budget(db_session, user_id, "daily")
    assert budget.reserved_amount == 0


def test_an_unreported_usage_stream_is_held_not_settled_to_zero(client, db_session, scripted):
    register_and_login(client, "st-l-unknown")
    user_id = _activate(db_session, "st-l-unknown")
    _declare(client, [HELD])
    scripted([[("text", "answer"), ("finish", "stop")]])      # no usage event at all

    parsed = frames(client.post("/chat/stream", json=_body(HELD)).text)

    assert answer_text(parsed) == "answer"
    assert parsed[-1][0] == "done", "an answer is still delivered when only its price is unknown"
    db_session.expire_all()
    request = (db_session.query(AIRequest).filter(AIRequest.user_id == user_id)
               .order_by(AIRequest.id.desc()).first())
    assert request.status == "reconciliation_pending"
    assert request.actual_credits is None


def test_the_stream_makes_bounded_attempts(client, db_session, scripted):
    register_and_login(client, "st-m")
    _activate(db_session, "st-m")
    _declare(client, [HELD])
    state = scripted([[("usage", USAGE), ("finish", "stop")]])   # every candidate answers nothing

    parsed = frames(client.post("/chat/stream", json=_body(HELD)).text)

    assert parsed[-1][0] == "error"
    assert 1 < len(state["calls"]) <= 3, "the chain is bounded by MAX_FALLBACK_ATTEMPTS"


def test_a_refusal_that_never_reached_a_provider_is_an_http_status(client, db_session, scripted):
    """Budget and permission refusals are ordinary HTTP answers, not a stream that starts."""
    register_and_login(client, "st-refusal")
    user = db_session.query(User).filter_by(username="st-refusal").one()
    usage_service.activate_subscription(db_session, user.id, "free", 30)
    _declare(client, [HELD])
    scripted([TEXT("never")])

    response = client.post("/chat/stream", json=_body(HELD, thinking_mode="deep"))

    assert response.status_code in {403, 429, 502}
    assert "text/event-stream" not in response.headers.get("content-type", "")
