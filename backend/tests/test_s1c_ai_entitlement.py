"""SECURITY_S1C — legacy /code/* AI must run the unified entitlement chain.

Before this round four programming endpoints reached the provider through ``call_deepseek``:
they ran a legacy daily counter (two of them ran none at all), wrote no ``ai_requests`` row and
no ledger entry, and ignored capability permission entirely. ``_repair_generated_challenge_with_ai``
was worse: a SECOND model call per malformed item, with no entitlement and no accounting.

Every test here is a money test, not a status-code test. The outbound call is replaced at the
orchestrator's factory (so the real permission / router / estimate / reserve / settle lifecycle
still runs) AND ``main.call_deepseek`` is replaced with a raiser — so a request that cheats its
way to a provider fails loudly instead of quietly spending. A refusal is only proven when the
provider call count is still zero.
"""
import dataclasses
import json

import pytest
from fastapi import HTTPException

import database
import main
import models
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from usage import service as usage_service
from usage.models import AIRequest


# ── doubles ────────────────────────────────────────────────────────────────────────

class CountingProvider(FakeProvider):
    def __init__(self, calls: list, content: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._calls = calls
        self._content = content

    def complete(self, spec):
        self._calls.append((self.name, spec.model, spec.capability))
        response = super().complete(spec)
        if self._content is None:
            return response
        return dataclasses.replace(response, content=self._content)


@pytest.fixture
def provider(monkeypatch):
    """Installs a counting provider and returns ``install(content) -> calls list``."""
    calls: list = []

    def _install(content: str | None = None) -> list:
        def _factory(name: str):
            return CountingProvider(calls, content=content, provider=name,
                                    input_tokens=50, output_tokens=50)
        monkeypatch.setattr("ai.orchestrator.default_provider_factory", _factory)
        return calls

    return _install


@pytest.fixture(autouse=True)
def legacy_client_is_a_tripwire(monkeypatch):
    """Any path that still reaches the legacy direct client fails loudly, not silently."""
    def _boom(*_args, **_kwargs):
        raise AssertionError("reached the legacy direct provider client (call_deepseek)")
    monkeypatch.setattr(main, "call_deepseek", _boom)


# ── helpers ────────────────────────────────────────────────────────────────────────

def _tiered(client, username: str, tier: str = "free") -> str:
    register_and_login(client, username)
    if tier != "free":
        db = database.SessionLocal()
        try:
            grant_unified_tier(db, username, tier, days=30)
        finally:
            db.close()
    return username


def _make_challenge(username: str, language: str = "Python") -> int:
    db = database.SessionLocal()
    try:
        challenge = models.CodeChallenge(
            username=username, language=language, title="S1C 题", difficulty="基础",
            description="S1C", requirements="", test_cases="[]",
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)
        return challenge.id
    finally:
        db.close()


def _make_session(username: str, challenge_id: int | None = None, language: str = "Python") -> int:
    db = database.SessionLocal()
    try:
        session = models.CodeSession(
            username=username, course_id="programming", title="S1C 会话",
            language=language, code="", challenge_id=challenge_id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id
    finally:
        db.close()


def _setup(client, username: str, which: str) -> dict:
    """Create whatever rows the endpoint needs to reach its AI gate.

    Both of these endpoints resolve a ``CodeSession`` before the gate, so without it a request
    would 404 and the test would prove nothing about entitlement.
    """
    if which == "generate":
        return {}
    if which == "learning_diagnosis":
        # The handler answers "not enough data" below 3 sessions and never reaches the gate.
        for _ in range(3):
            _make_session(username)
        return {}
    challenge_id = _make_challenge(username)
    session_id = _make_session(username, challenge_id=challenge_id)
    return {"challenge_id": challenge_id, "session_id": session_id}


def _db_user(username: str) -> tuple[int, str]:
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        return user.id, user.username
    finally:
        db.close()


def _ai_requests(user_id: int, capability: str) -> int:
    db = database.SessionLocal()
    try:
        return (db.query(AIRequest)
                .filter(AIRequest.user_id == user_id, AIRequest.capability == capability)
                .count())
    finally:
        db.close()


# The four converged endpoints, each with the capability it must ask for.
ENDPOINTS = [
    ("generate", "question.generate"),
    ("explain_failure", "programming.explain"),
    ("generate_tests", "question.generate"),
    ("learning_diagnosis", "report.generate"),
]


def _call(client, which: str, username: str, ctx: dict):
    if which == "generate":
        return client.post("/code/challenges/generate",
                           json={"username": username, "language": "Python", "count": 1})
    if which == "explain_failure":
        return client.post(f"/code/challenges/{ctx['challenge_id']}/explain-failure", json={
            "username": username, "session_id": ctx["session_id"], "language": "Python",
            "code": "print(1)", "test_case": {"input": "", "expected_output": ""},
            "actual_output": "", "exit_code": 0,
        })
    if which == "generate_tests":
        return client.post(f"/code/challenges/{ctx['challenge_id']}/generate-tests",
                           json={"username": username, "language": "python"})
    return client.post("/code/learning-diagnosis", json={"username": username})


# ── §9 tripwire: a Free learner cannot reach a provider, and nothing is spent ──────

@pytest.mark.parametrize("which,capability", ENDPOINTS)
def test_free_learner_is_refused_and_no_provider_call_is_made(client, provider, which, capability):
    calls = provider()
    username = _tiered(client, f"s1c-free-{which}", "free")
    ctx = _setup(client, username, which)

    response = _call(client, which, username, ctx)

    assert response.status_code == 403, response.text
    assert calls == [], f"{which} reached a provider for a Free learner: {calls}"


@pytest.mark.parametrize("which,capability", ENDPOINTS)
def test_free_learner_books_no_usage(client, provider, which, capability):
    """A refusal must not create a request row either — nothing happened, nothing is filed."""
    provider()
    username = _tiered(client, f"s1c-freebook-{which}", "free")
    ctx = _setup(client, username, which)
    user_id, _ = _db_user(username)

    _call(client, which, username, ctx)

    assert _ai_requests(user_id, capability) == 0


def test_budget_exhaustion_denies_before_the_provider(client, provider):
    """Standard tier but no budget left → 429, and still no provider call."""
    calls = provider()
    username = _tiered(client, "s1c-broke", "standard")
    user_id, _ = _db_user(username)

    db = database.SessionLocal()
    try:
        budget = usage_service.get_or_create_budget(db, user_id, "daily")
        budget.settled_amount = budget.budget_amount
        db.commit()
    finally:
        db.close()

    response = _call(client, "generate", username, {})

    assert response.status_code == 429, response.text
    assert calls == [], calls


def test_legacy_daily_limiter_is_not_the_authorization(client, provider):
    """The legacy counter can only refuse sooner. It can never grant what policy denies.

    A Free learner with a completely untouched daily counter still gets 403 — the daily
    counter's own message ("upgrade for more") must not be the answer that authorizes.
    """
    calls = provider()
    username = _tiered(client, "s1c-legacy-limit", "free")

    response = _call(client, "generate", username, {})

    assert response.status_code == 403
    body = response.text
    assert "使用次数已达上限" not in body, "the legacy quota message answered instead of the policy"
    assert calls == []


# ── the allow path: Standard runs through the boundary and is recorded ─────────────

def test_standard_learner_is_served_through_the_orchestrator(client, provider):
    calls = provider("这是一段解释。")
    username = _tiered(client, "s1c-standard", "standard")
    ctx = _setup(client, username, "explain_failure")
    user_id, _ = _db_user(username)
    before = _ai_requests(user_id, "programming.explain")

    response = _call(client, "explain_failure", username, ctx)

    assert response.status_code == 200, response.text
    assert response.json()["explanation"]
    assert len(calls) == 1, calls
    assert calls[0][2] == "programming.explain", calls
    assert _ai_requests(user_id, "programming.explain") == before + 1


def test_generate_records_the_question_generate_capability(client, provider):
    """The generation endpoint's ledger row names `question.generate`, not a legacy feature key."""
    calls = provider("[]")
    username = _tiered(client, "s1c-generate", "standard")
    user_id, _ = _db_user(username)

    _call(client, "generate", username, {})

    assert len(calls) >= 1, calls
    assert calls[0][2] == "question.generate", calls
    assert _ai_requests(user_id, "question.generate") >= 1


def test_learning_diagnosis_records_report_generate(client, provider):
    """A diagnosis is a report over the learner's history, so it asks `report.generate`.

    That capability is Advanced-only in the current policy — the same one the course learning
    report asks for — so the learner who is served is an Advanced one.
    """
    calls = provider("诊断报告正文")
    username = _tiered(client, "s1c-diagnosis", "advanced")
    ctx = _setup(client, username, "learning_diagnosis")
    user_id, _ = _db_user(username)

    response = _call(client, "learning_diagnosis", username, ctx)

    assert response.status_code != 403, response.text
    assert len(calls) >= 1, calls
    assert calls[0][2] == "report.generate", calls
    assert _ai_requests(user_id, "report.generate") >= 1


def test_standard_learner_is_refused_the_diagnosis(client, provider):
    """Pins the consequence of the mapping above, so it cannot drift silently.

    If the product decides a programming diagnosis belongs to Standard rather than Advanced,
    this is the test that must change — and `programming.explain` is the capability to use.
    """
    calls = provider("诊断报告正文")
    username = _tiered(client, "s1c-diagnosis-std", "standard")
    ctx = _setup(client, username, "learning_diagnosis")

    response = _call(client, "learning_diagnosis", username, ctx)

    assert response.status_code == 403, response.text
    assert calls == [], calls


def test_generate_tests_records_question_generate(client, provider):
    calls = provider("[]")
    username = _tiered(client, "s1c-tests", "standard")
    ctx = _setup(client, username, "generate_tests")
    user_id, _ = _db_user(username)

    _call(client, "generate_tests", username, ctx)

    assert len(calls) >= 1, calls
    assert calls[0][2] == "question.generate", calls
    assert _ai_requests(user_id, "question.generate") >= 1


# ── §4 the secondary/repair call is gated AND accounted ────────────────────────────

def test_repair_call_is_refused_for_a_free_learner(client, provider):
    calls = provider()
    username = _tiered(client, "s1c-repair-free", "free")
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        result = main._repair_generated_challenge_with_ai(
            {"title": "t"}, "Python", {"ok": False, "errors": ["bad"]}, db, user)
    finally:
        db.close()

    assert result is None, "a refused repair must degrade to 'unrepairable', not run"
    assert calls == [], calls


def test_repair_call_is_accounted_for_a_standard_learner(client, provider):
    """The second model call books its OWN request row — it is not free and not invisible."""
    calls = provider('{"title": "fixed"}')
    username = _tiered(client, "s1c-repair-std", "standard")
    user_id, _ = _db_user(username)
    before = _ai_requests(user_id, "question.generate")

    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        main._repair_generated_challenge_with_ai(
            {"title": "t"}, "Python", {"ok": False, "errors": ["bad"]}, db, user)
    finally:
        db.close()

    assert len(calls) == 1, calls
    assert calls[0][2] == "question.generate", calls
    assert _ai_requests(user_id, "question.generate") == before + 1


# ── the fifth bypass: a route that built its own provider client ───────────────────

def test_membership_recommendation_never_reaches_a_provider(client, monkeypatch):
    """`/membership/recommendation` built its own OpenAI client for an AI fallback layer.

    Nothing in the function-level declaration list could see it — that list tracks
    `call_deepseek` calls, and this path never called it. "Classify an arbitrary major" has no
    capability in the policy, so the call is refused rather than re-routed: the classifier
    lands on its documented final layer and asks the learner to choose.
    """
    import membership

    def _boom(*_args, **_kwargs):
        raise AssertionError("membership recommendation reached its AI fallback layer")

    monkeypatch.setattr(membership, "_ai_classify_major", _boom)

    username = _tiered(client, "s1c-major", "free")
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        user.major = "S1C-未匹配-专业-zzq"
        db.commit()
    finally:
        db.close()

    response = client.get("/membership/recommendation")

    assert response.status_code == 200, response.text
    assert response.json()["needs_manual_choice"] is True, response.text


# ── §5 an explicit model cannot widen entitlement ──────────────────────────────────

def test_explicit_model_does_not_bypass_the_capability_check(client, provider):
    calls = provider()
    username = _tiered(client, "s1c-explicit", "free")
    from learning.spaces.programming.ai import execute_programming_ai
    from learning.spaces.programming.context import build_programming_context

    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        with pytest.raises(HTTPException) as exc:
            execute_programming_ai(
                db, user, "question.generate",
                [{"role": "user", "content": "hi"}],
                learning_context=build_programming_context(user, language="Python"),
                explicit_model="deepseek-reasoner",
            )
    finally:
        db.close()

    assert exc.value.status_code == 403
    assert calls == [], calls


# ── §6 unknown capability fails closed ─────────────────────────────────────────────

def test_unknown_capability_is_denied_for_every_tier():
    from usage.capabilities import check_capability_permission

    for tier in ("free", "standard", "advanced"):
        permission = check_capability_permission(tier, "not.a.real.capability")
        assert permission["allowed"] is False, tier


def test_unknown_capability_never_reaches_a_provider(client, provider):
    calls = provider()
    username = _tiered(client, "s1c-unknown", "advanced")
    from learning.spaces.programming.ai import execute_programming_ai
    from learning.spaces.programming.context import build_programming_context

    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).one()
        with pytest.raises(HTTPException):
            execute_programming_ai(
                db, user, "not.a.real.capability",
                [{"role": "user", "content": "hi"}],
                learning_context=build_programming_context(user, language="Python"),
            )
    finally:
        db.close()

    assert calls == [], calls
