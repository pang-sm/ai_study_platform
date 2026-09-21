"""P6.2 §A/§B/§C — legacy AI closure: the last three bypasses, closed and held.

WHAT THESE TESTS HOLD
---------------------
1. `/chat`'s PROGRAMMING branch runs on the unified chain and returns the REAL
   ``ai_requests`` identity of the answer it just produced — capability, namespace, tier and
   settlement checked against the store, not against the response;
2. `/code/challenges/{id}/submit`'s AI branch does the same, and its two DETERMINISTIC
   branches (empty code / wrong language) still make no model call — and therefore report no
   identity instead of inventing one;
3. `/code/diagnose` creates no ``ai_requests`` row and consumes no credits: it is a compiler
   check, and the semantic correction of P6.2 §C is held here as a contract;
4. `/code/analyze` still returns its real id — the §A/§B work did not disturb P6.1;
5. the §D guard over the closed product paths reports ZERO forbidden bypasses.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import ast
import dataclasses
import json

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import (AiUsageLog, CodeChallenge, CodeSession, User, UserLearningTrack)
from usage.models import AIRequest, UsageLedger

CHAT = "/chat"
SUBMIT = "/code/challenges/{challenge_id}/submit"
DIAGNOSE = "/code/diagnose"
ANALYZE = "/code/analyze"
FEEDBACK = "/ai/feedback"

ANSWER = "这段代码的边界条件有问题：n 为 0 时返回 1。"
VERDICT = "## 判定结论\n\n**大概率通过**\n\n## 主要问题\n\n边界条件已覆盖。"
CODE = "def solve(n):\n    return n + 1\n"


class _Provider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=ANSWER)


class _VerdictProvider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=VERDICT)


class _RecordingProvider(FakeProvider):
    """Counts every model call, so a path that must NOT call one can be proven not to."""

    def __init__(self, *args, sink: list, **kwargs):
        super().__init__(*args, **kwargs)
        self._sink = sink

    def complete(self, spec):
        self._sink.append(spec)
        return super().complete(spec)


def _provider(cls=_Provider):
    def factory(name: str) -> FakeProvider:
        return cls(provider=name, input_tokens=50, output_tokens=40)
    return factory


def _recording(sink: list):
    def factory(name: str) -> FakeProvider:
        return _RecordingProvider(provider=name, input_tokens=50, output_tokens=40, sink=sink)
    return factory


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _owned_request(db, request_id: str, user_id: int):
    """The identity contract, checked against the store itself."""
    return (db.query(AIRequest)
            .filter(AIRequest.request_id == request_id, AIRequest.user_id == user_id).first())


def _ledger_types(db, request_id: str) -> set[str]:
    return {row.entry_type for row in
            db.query(UsageLedger).filter(UsageLedger.request_id == request_id).all()}


def _counts(db) -> dict:
    return {"requests": db.query(AIRequest).count(),
            "ledger": db.query(UsageLedger).count(),
            "legacy_meter": db.query(AiUsageLog).count()}


def _challenge(db, user, *, language="Python") -> CodeChallenge:
    challenge = CodeChallenge(
        username=user.username, course_id="programming", language=language,
        title="两数之和", difficulty="easy", description="返回两数之和",
        requirements="函数 solve 返回两数之和", input_format="无", output_format="一个整数",
        examples="solve(1,2) == 3", test_cases="[]")
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def _session(db, user, challenge) -> CodeSession:
    session = CodeSession(username=user.username, course_id="programming",
                          title="挑战练习", language=challenge.language,
                          challenge_id=challenge.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _chat_body(**overrides) -> dict:
    body = {"message": "为什么我的循环没有输出？", "service_key": "programming",
            "subject": "Python 程序设计", "subject_key": "programming",
            "course_id": "python_programming", "course": "Python 程序设计"}
    body.update(overrides)
    return body


# ================================================================ 1. /chat (programming)


def test_programming_chat_runs_on_the_unified_stack_and_returns_a_real_id(
        client, db_session, monkeypatch):
    """§A: the programming branch is no longer a bypass.

    Before P6.2 it called the provider directly, so the answer had NO ``ai_requests`` row,
    NO capability/permission decision, NO reservation and no identity to rate. Now it is one
    ordinary request on the same chain as everything else — and the test proves it against
    the store, then closes the loop by rating the id it was given.

    No tier is granted: the capability this branch asks for is part of the Free learning
    loop, which is the behaviour the branch had before the convergence.
    """
    register_and_login(client, "p62_chat_prog")
    user = _user(db_session, "p62_chat_prog")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    db_session.expire_all()
    before = _counts(db_session)

    response = client.post(CHAT, json=_chat_body())
    assert response.status_code == 200, response.text
    body = response.json()
    request_id = body.get("request_id")
    assert request_id, "the programming chat answer has a real ai_requests identity"
    assert body["answer"], "the user-visible answer is unchanged"

    db_session.expire_all()
    row = _owned_request(db_session, request_id, user.id)
    assert row is not None, "the id must be an actual ai_requests row of the CALLER"
    assert row.capability in ("tutor.chat", "material.qa")
    assert row.service_namespace == "programming", "filed under the space that owns it"
    assert row.tier == "free", "no membership was granted, so the request is a Free one"
    assert row.status == "settled", "usage settles on the unified chain"

    # usage settles: reserve then settle, both written against THIS request
    assert {"reserve", "settle"} <= _ledger_types(db_session, request_id)

    # the legacy meter is not written by a converged path
    assert _counts(db_session)["legacy_meter"] == before["legacy_meter"]

    rated = client.post(FEEDBACK, json={"request_id": request_id, "rating": "up"})
    assert rated.status_code == 200, rated.text
    assert rated.json()["capability"] in ("tutor.chat", "material.qa")


def test_programming_chat_carries_the_learners_declared_language(client, db_session,
                                                                 monkeypatch):
    """The programming context is real: it takes the language from the learner's own profile.

    Without this, a C++ learner's chat would be filed under the context module's default and
    the durable fact would claim a language they never used.
    """
    register_and_login(client, "p62_chat_lang")
    user = _user(db_session, "p62_chat_lang")
    db_session.add(UserLearningTrack(
        user_id=user.id, track_type="programming",
        onboarding_detail_json=json.dumps({"main_language": "cpp"})))
    db_session.commit()
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    response = client.post(CHAT, json=_chat_body())
    assert response.status_code == 200, response.text

    db_session.expire_all()
    row = _owned_request(db_session, response.json()["request_id"], user.id)
    assert row is not None
    assert (row.context_json or {}).get("programming_language") == "C++", \
        "the declared language is normalized and carried, never guessed"


# ================================================================ 2. challenge submit


def test_challenge_submit_ai_branch_runs_on_the_orchestrator(client, db_session, monkeypatch):
    """§B: the judgment is a real model call, so it runs on the unified chain."""
    register_and_login(client, "p62_submit")
    grant_unified_tier(db_session, "p62_submit", "standard")
    user = _user(db_session, "p62_submit")
    challenge = _challenge(db_session, user)
    session = _session(db_session, user, challenge)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(_VerdictProvider))

    db_session.expire_all()
    before = _counts(db_session)

    response = client.post(SUBMIT.format(challenge_id=challenge.id),
                           json={"username": "", "session_id": session.id,
                                 "code": CODE, "language": "Python"})
    assert response.status_code == 200, response.text
    body = response.json()

    # the response contract is preserved …
    assert body["success"] is True and body["attempt_id"]
    assert body["status"] == "probable_pass", "the verdict is still read out of the answer"
    assert body["ai_feedback"].startswith("## 判定结论"), "markdown normalization is intact"
    # … and it now says what produced the judgment
    request_id = body.get("request_id")
    assert request_id, "the AI branch returns the identity of the request that answered"

    db_session.expire_all()
    row = _owned_request(db_session, request_id, user.id)
    assert row is not None and row.capability == "programming.explain"
    assert row.service_namespace == "programming"
    assert row.status == "settled"
    assert {"reserve", "settle"} <= _ledger_types(db_session, request_id)
    assert _counts(db_session)["legacy_meter"] == before["legacy_meter"]

    assert client.post(FEEDBACK, json={"request_id": request_id, "rating": "up"}
                       ).status_code == 200


def test_challenge_submit_deterministic_branches_make_no_ai_call(client, db_session,
                                                                monkeypatch):
    """§B: judging that needs no model never gets one, and never fabricates an identity.

    Two submissions are answered from the request itself (no code at all; a language that is
    not the challenge's). Both must stay deterministic: the provider is never touched, no
    ``ai_requests`` row and no credits appear, and the response reports NO request id rather
    than inventing one.
    """
    register_and_login(client, "p62_submit_det")
    grant_unified_tier(db_session, "p62_submit_det", "standard")
    user = _user(db_session, "p62_submit_det")
    challenge = _challenge(db_session, user)
    session = _session(db_session, user, challenge)
    calls: list = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _recording(calls))

    db_session.expire_all()
    before = _counts(db_session)

    empty = client.post(SUBMIT.format(challenge_id=challenge.id),
                        json={"username": "", "session_id": session.id,
                              "code": "   ", "language": "Python"})
    assert empty.status_code == 200, empty.text
    assert empty.json()["status"] == "failed"
    assert "request_id" in empty.json(), "the field is present, so the contract is uniform"
    assert empty.json()["request_id"] is None, "no model call → no identity to report"

    wrong_language = client.post(SUBMIT.format(challenge_id=challenge.id),
                                 json={"username": "", "session_id": session.id,
                                       "code": CODE, "language": "c"})
    assert wrong_language.status_code == 200, wrong_language.text
    assert wrong_language.json()["status"] == "failed"
    assert wrong_language.json()["request_id"] is None

    db_session.expire_all()
    assert calls == [], "a deterministic branch must not reach a model"
    assert _counts(db_session) == before, "no ai_requests row and no credit movement"


# ================================================================ 3. /code/diagnose


def test_code_diagnose_creates_zero_ai_requests_and_zero_credits(client, db_session):
    """§C held as a contract: 代码诊断 / 静态诊断 is DETERMINISTIC — it is not an AI feature.

    The check compiles with the local toolchain, so it can create no request, consume no
    credit and offer nothing for AI feedback to rate. The response says nothing about AI —
    not a null id, no field at all.
    """
    register_and_login(client, "p62_diagnose")
    user = _user(db_session, "p62_diagnose")

    db_session.expire_all()
    before = _counts(db_session)

    ok = client.post(DIAGNOSE, json={"language": "python", "code": "x = 1\n"})
    assert ok.status_code == 200 and ok.json()["status"] == "ok"
    broken = client.post(DIAGNOSE, json={"language": "python", "code": "def f(:\n"})
    assert broken.status_code == 200 and broken.json()["status"] == "error"

    for response in (ok, broken):
        assert "request_id" not in response.json(), "a compiler check has no AI identity"

    db_session.expire_all()
    after = _counts(db_session)
    assert after == before, "diagnose moves neither the request table nor the credit ledger"
    assert (db_session.query(AIRequest).filter(AIRequest.user_id == user.id).count() == 0)


# ================================================================ 4. /code/analyze


def test_code_analyze_still_returns_a_real_owned_request_id(client, db_session, monkeypatch):
    """Regression: §A/§B moved two branches and must not have disturbed the third."""
    register_and_login(client, "p62_analyze")
    grant_unified_tier(db_session, "p62_analyze", "standard")
    user = _user(db_session, "p62_analyze")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider())

    body = client.post(ANALYZE, json={"username": "", "course_id": "programming",
                                      "language": "python", "code": CODE,
                                      "question": "这段代码对吗？"}).json()
    request_id = body.get("request_id")
    assert request_id

    db_session.expire_all()
    row = _owned_request(db_session, request_id, user.id)
    assert row is not None and row.capability == "programming.explain"
    assert row.status == "settled"


# ================================================================ 5. the §D guard


def test_closed_product_paths_report_zero_forbidden_bypasses():
    """§D: the closure is a checked count, not a claim in a report.

    Recomputes the guard's own check over the declared closed paths — including the module
    paths (Deep Study / Report / Wrong Analysis / Plan Adjustment / Debug Agent) — and states
    the number of forbidden bypasses. A new direct provider call anywhere in a closed path
    turns this red before it can ship.
    """
    from test_course_ai_reachability import (BACKEND_DIR, CLOSED_ENDPOINTS, CLOSED_MODULES,
                                             MAIN_SOURCE, _Index, _bounds,
                                             _provider_violations)

    index = _Index(MAIN_SOURCE)
    offenders: list[str] = []
    for func_name in CLOSED_ENDPOINTS:
        for violation in _provider_violations(index.tree, _bounds(index, func_name)):
            offenders.append(f"{func_name}: {violation}")
    for rel in CLOSED_MODULES:
        text = (BACKEND_DIR / rel).read_text(encoding="utf-8")
        for violation in _provider_violations(ast.parse(text)):
            offenders.append(f"{rel}: {violation}")

    assert len(CLOSED_ENDPOINTS) + len(CLOSED_MODULES) == 8, "the §D path list is complete"
    assert offenders == [], f"forbidden provider bypasses in closed product paths: {offenders}"
