"""A candidate that answers with NOTHING is a failed candidate, not a failed request.

Providers do return a successful response with no text (a completion whose whole budget went to
internal reasoning is one live cause). The chain used to return that as the answer — settled,
ok=True, content="" — and the caller then had to invent a 502 for a request the ledger had
already billed. These tests pin the general rule: an empty completion is a candidate failure, the
chain moves to the next qualified candidate, and only when no candidate answers does the request
fail.
"""
from __future__ import annotations

import dataclasses

import pytest

from ai.gateway import GatewayError, GatewayErrorCategory
from ai.orchestrator import AIOrchestrator, is_empty_answer
from ai.providers import FakeProvider
from models import User
from usage import service
from usage.models import AICostRecord, AIRequest

EMPTY = ""
ANSWER = "正常回答"


class ScriptedProvider(FakeProvider):
    """Per-attempt script, decided by CALL INDEX so the test does not depend on pool order.

    A step is: ``None`` → raise a retriable timeout, ``""``/whitespace → an empty completion,
    anything else → that answer.
    """

    def __init__(self, script: list, calls: list, **kwargs):
        super().__init__(**kwargs)
        self._script = script
        self._calls = calls

    def complete(self, spec):
        index = len(self._calls)
        self._calls.append((self.name, spec.model))
        step = self._script[index] if index < len(self._script) else self._script[-1]
        if step is None:
            raise GatewayError(GatewayErrorCategory.timeout, "fake timeout", self.name,
                               retriable=True)
        return dataclasses.replace(super().complete(spec), content=step)


def _user(session, username, tier="advanced") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        service.activate_subscription(session, u.id, tier, 30)
    return u


def _orch(script: list, calls: list) -> AIOrchestrator:
    return AIOrchestrator(
        provider_factory=lambda name: ScriptedProvider(
            script, calls, provider=name, input_tokens=20, output_tokens=20))


def _run(session, username, script, **kwargs):
    u = _user(session, username)
    calls: list = []
    result = _orch(script, calls).execute(session, u.id, "tutor.chat", [{"role": "user",
                                                                        "content": "hi"}],
                                          request_id=f"{username}-1", **kwargs)
    return u, result, calls


# ── the definition (§2) ───────────────────────────────────────

def test_the_empty_definition_is_not_a_length_heuristic():
    for empty in (None, "", "   ", "\n\t "):
        assert is_empty_answer(empty) is True
    # A short answer IS an answer: "0" and "是" are complete replies.
    for answer in ("0", "是", "a", "  0  "):
        assert is_empty_answer(answer) is False


# ── A/B/C: an empty lead candidate falls through ─────────────

@pytest.mark.parametrize("empty", [EMPTY, "   ", None])
def test_an_empty_candidate_falls_through_to_the_next(db_session, empty):
    u, result, calls = _run(db_session, f"empty-{empty!r}".replace("'", "")[:20],
                            [empty, ANSWER])

    # The next candidate was tried, and IT answered.
    assert len(calls) == 2
    assert result.ok is True and result.status == "settled"
    assert result.content == ANSWER
    assert result.provider == calls[1][0] and result.model == calls[1][1]
    assert calls[0][0] != calls[1][0] or calls[0][1] != calls[1][1]
    # The record says which model answered and that a fallback served it.
    assert result.router["model"] == calls[1][1]
    assert result.router["reason_code"] == "fallback_after_failure"
    req = db_session.query(AIRequest).filter(AIRequest.request_id == f"{u.username}-1").one()
    assert req.status == "settled"
    assert req.model == calls[1][1]


def test_a_whitespace_only_completion_is_empty(db_session):
    _u, result, calls = _run(db_session, "empty-ws", ["  \n ", ANSWER])
    assert len(calls) == 2 and result.content == ANSWER


def test_a_short_answer_is_served_as_is(db_session):
    """A one-character answer is an answer — no fallback, no failure."""
    _u, result, calls = _run(db_session, "empty-short", ["0"])

    assert len(calls) == 1
    assert result.ok is True and result.status == "settled"
    assert result.content == "0"


# ── E: every candidate empty ─────────────────────────────────

def test_every_candidate_empty_fails_the_request(db_session):
    u, result, calls = _run(db_session, "empty-all", [EMPTY])

    # Every allowed attempt was made, and none of them counts as a success.
    assert len(calls) == 3
    assert result.ok is False
    assert result.content is None
    assert result.error_category == "empty_completion"
    assert result.status != "settled"
    req = db_session.query(AIRequest).filter(AIRequest.request_id == "empty-all-1").one()
    assert req.status == "reconciliation_pending"
    assert req.error_category == "empty_completion"
    # Nothing was settled as if an answer had been delivered.
    assert req.actual_credits is None


# ── F: the empty attempt is still paid for ───────────────────

def test_an_empty_attempt_is_recorded_and_the_answer_is_settled(db_session):
    u, result, calls = _run(db_session, "empty-billing", [EMPTY, ANSWER])
    assert result.content == ANSWER

    rows = (db_session.query(AICostRecord)
            .filter(AICostRecord.request_id == "empty-billing-1")
            .order_by(AICostRecord.id).all())
    # One row per provider call: the wasted attempt keeps its OWN usage, and the answering call
    # is settled by the ledger — no usage is dropped and nothing is double-counted.
    assert len(rows) == 2
    wasted, served = rows
    assert wasted.provider == calls[0][0] and wasted.model == calls[0][1]
    assert wasted.input_tokens == 20 and wasted.output_tokens == 20
    assert served.provider == calls[1][0] and served.model == calls[1][1]

    # The reservation is not lost: it was settled (not released, not left held) for the request.
    # Every period row the request reserved against is settled and holds nothing back.
    from usage.models import UsageBudget
    budgets = db_session.query(UsageBudget).filter(UsageBudget.user_id == u.id).all()
    assert budgets
    assert all(row.reserved_amount == 0 for row in budgets)
    assert max(row.settled_amount for row in budgets) == served.normalized_credits > 0


def test_an_empty_attempt_with_unknown_usage_is_recorded_as_a_log_only(db_session):
    """A provider that reports no usage leaves nothing to price — the request still goes on."""
    u = _user(db_session, "empty-nousage")
    calls: list = []

    class _UnknownUsageThenAnswering(ScriptedProvider):
        """The first attempt keeps its empty answer but reports no usage."""

        def complete(self, spec):
            response = super().complete(spec)  # the parent owns the call bookkeeping
            if len(self._calls) == 1:
                return dataclasses.replace(
                    response, usage=dataclasses.replace(response.usage,
                                                        usage_source="UNKNOWN"))
            return response

    orch = AIOrchestrator(provider_factory=lambda name: _UnknownUsageThenAnswering(
        ["", ANSWER], calls, provider=name, input_tokens=20, output_tokens=20))
    result = orch.execute(db_session, u.id, "tutor.chat", [{"role": "user", "content": "hi"}],
                          request_id="empty-nousage-1")

    assert result.content == ANSWER
    # Only the answering call has a priced record; the unpriced attempt is a warning in the log.
    rows = (db_session.query(AICostRecord)
            .filter(AICostRecord.request_id == "empty-nousage-1").all())
    assert len(rows) == 1 and rows[0].model == calls[1][1]


# ── G: the explicit-model contract ───────────────────────────

def test_an_explicit_model_is_never_silently_replaced(db_session):
    """The learner named a model. An empty answer from it is a failure — NOT a reason to answer
    with a different one behind their back. Pinned here so the contract cannot drift."""
    u = _user(db_session, "empty-explicit")
    calls: list = []
    orch = AIOrchestrator(provider_factory=lambda name: ScriptedProvider(
        [EMPTY], calls, provider=name, input_tokens=20, output_tokens=20))

    result = orch.execute(db_session, u.id, "tutor.chat", [{"role": "user", "content": "hi"}],
                          request_id="empty-explicit-1", explicit_model="deepseek-flash")

    # Exactly one attempt: the model that was asked for, and no other.
    assert calls == [("deepseek", "deepseek-flash")]
    assert result.ok is False
    assert result.error_category == "empty_completion"
    assert result.model == "deepseek-flash"


def test_auto_mode_may_fall_back(db_session):
    """The same empty answer WITHOUT an explicit model does move to the next candidate."""
    _u, result, calls = _run(db_session, "empty-auto", [EMPTY, ANSWER])

    assert len(calls) == 2
    assert result.ok is True and result.content == ANSWER


# ── H: the existing provider-exception fallback does not regress ──

def test_a_retriable_provider_failure_still_falls_back(db_session):
    _u, result, calls = _run(db_session, "empty-timeout", [None, ANSWER])

    assert len(calls) == 2
    assert result.ok is True and result.status == "settled"
    assert result.content == ANSWER
    assert result.router["reason_code"] == "fallback_after_failure"


def test_a_mix_of_timeout_and_empty_reports_the_last_outcome(db_session):
    """A retriable failure keeps the chain going; whatever ended it names the failure."""
    u = _user(db_session, "empty-mix")
    calls: list = []
    orch = AIOrchestrator(provider_factory=lambda name: ScriptedProvider(
        [EMPTY, None], calls, provider=name, input_tokens=20, output_tokens=20))

    result = orch.execute(db_session, u.id, "tutor.chat", [{"role": "user", "content": "hi"}],
                          request_id="empty-mix-1", max_tokens=200)

    # The empty lead, then the retriable timeout, then the timeout that ended the chain.
    assert len(calls) == 3
    assert result.ok is False
    # The LAST outcome decides the category: the timeout that ended the chain, not the empty one.
    assert result.error_category == "timeout"


def test_the_attempt_count_is_bounded(db_session):
    """No unbounded retrying: an all-empty chain makes exactly the allowed number of attempts."""
    _u, result, calls = _run(db_session, "empty-bounded", [EMPTY])
    assert len(calls) == 3
    assert result.error_category == "empty_completion"


# ── the provider boundary itself ──────────────────────────────

def test_a_provider_that_cannot_be_built_is_a_candidate_failure(db_session):
    """A candidate whose adapter cannot even be constructed is unavailable, not fatal.

    Live case: a provider with no credential in the environment raised `OpenAIError` from its
    constructor. That is not a `GatewayError`, so it escaped the chain and turned an answerable
    question into a 500 the moment a fallback reached it.
    """
    u = _user(db_session, "empty-unbuildable")
    calls: list = []
    attempts: list = []

    def factory(name):
        attempts.append(name)
        if len(attempts) == 1:
            raise RuntimeError("Missing credentials. Please pass an `api_key` ...")
        return ScriptedProvider([ANSWER], calls, provider=name, input_tokens=20, output_tokens=20)

    result = AIOrchestrator(provider_factory=factory).execute(
        db_session, u.id, "tutor.chat", [{"role": "user", "content": "hi"}],
        request_id="empty-unbuildable-1")

    # No exception escaped; the chain moved on and the next candidate answered.
    assert len(attempts) == 2
    assert result.ok is True and result.content == ANSWER
    assert result.router["reason_code"] == "fallback_after_failure"


def test_every_provider_unbuildable_fails_cleanly(db_session):
    u = _user(db_session, "empty-unbuildable-all")

    def factory(name):
        raise RuntimeError("Missing credentials. Please pass an `api_key` ...")

    result = AIOrchestrator(provider_factory=factory).execute(
        db_session, u.id, "tutor.chat", [{"role": "user", "content": "hi"}],
        request_id="empty-unbuildable-all-1")

    assert result.ok is False
    assert result.content is None
    assert result.error_category == "provider_unavailable"
    # Nothing provider-specific travels with the result.
    assert "api_key" not in (result.error_message or "")
