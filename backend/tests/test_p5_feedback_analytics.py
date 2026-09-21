"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5 — Feedback analytics & production hardening.

WHAT THESE TESTS HOLD
---------------------
1. aggregation is CORRECT and READ-ONLY: counts, rates, latency and credits come from the
   stored ratings, and nothing is tuned, re-ranked or written;
2. privacy holds: a caller sees only their own ratings, and the platform view is admin-only
   and AGGREGATED — it never returns a user id, a request id or a per-learner row;
3. the audit semantics of P4 are preserved (the rating stays an audit fact);
4. the router is untouched by anything in this module;
5. the availability view is admin-only and STATES ITS SCOPE, which is the deployment finding
   from P5 §G made visible instead of implicit.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from learning.records import taxonomy
from models import User

ANALYTICS = "/ai/feedback/analytics"
AVAILABILITY = "/ai/feedback/availability"
FEEDBACK = "/ai/feedback"
DEEP_STUDY = "/ai/deep-study"
COURSE = "数据结构"
ANSWER = "虚拟内存是操作系统对物理内存的抽象。"


class _ScriptedProvider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=ANSWER)


def _provider(name: str) -> FakeProvider:
    return _ScriptedProvider(provider=name, input_tokens=60, output_tokens=40)


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _one_call(client, monkeypatch) -> str:
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    response = client.post(DEEP_STUDY, json={"question": "什么是虚拟内存？", "course_id": COURSE})
    assert response.status_code == 200, response.text
    return response.json()["request_id"]


def _rate(client, request_id, rating, reason=None) -> None:
    payload = {"request_id": request_id, "rating": rating}
    if reason:
        payload["reason"] = reason
    response = client.post(FEEDBACK, json=payload)
    assert response.status_code == 200, response.text


# ================================================================ 1. aggregation


def test_the_aggregate_is_correct_and_owner_scoped(client, db_session, monkeypatch):
    register_and_login(client, "p5_fa_owner")
    grant_unified_tier(db_session, "p5_fa_owner", "standard")
    for _ in range(2):
        _rate(client, _one_call(client, monkeypatch), "up")
    _rate(client, _one_call(client, monkeypatch), "down", "too_verbose")

    mine = client.get(ANALYTICS).json()
    assert mine["scope"] == "mine"
    assert mine["totals"]["ratings"] == 3
    assert mine["totals"]["up"] == 2 and mine["totals"]["down"] == 1
    assert mine["totals"]["down_rate"] == 0.3333
    assert mine["by_reason"] == {"too_verbose": 1}
    assert mine["by_capability"]["tutor.strong_reasoning"]["ratings"] == 3
    assert mine["by_model"], "the model that answered is part of the aggregate"
    assert mine["totals"]["avg_latency_ms"] is not None
    assert mine["router_mutation"] is False

    # another learner has their own (empty) view
    register_and_login(client, "p5_fa_other")
    other = client.get(ANALYTICS).json()
    assert other["totals"]["ratings"] == 0
    assert other["by_capability"] == {}


def test_the_platform_view_is_admin_only_and_aggregated(client, db_session, monkeypatch):
    register_and_login(client, "p5_fa_member")
    grant_unified_tier(db_session, "p5_fa_member", "standard")
    _rate(client, _one_call(client, monkeypatch), "down", "incorrect")

    refused = client.get(ANALYTICS, params={"scope": "platform"})
    assert refused.status_code == 403, refused.text
    assert client.get(AVAILABILITY).status_code == 403

    user = _user(db_session, "p5_fa_member")
    user.is_admin = 1
    db_session.commit()

    platform = client.get(ANALYTICS, params={"scope": "platform"}).json()
    assert platform["scope"] == "platform"
    assert platform["totals"]["ratings"] >= 1
    assert platform["by_reason"]["incorrect"] >= 1

    # AGGREGATED ONLY: every bucket is keyed by a capability/model/provider/workflow, never by
    # a learner, and no request identity appears anywhere in the payload.
    assert str(user.id) not in platform["by_capability"]
    assert str(user.id) not in platform["by_model"]
    assert str(user.id) not in platform["by_workflow"]
    assert "p5_fa_member" not in json.dumps(platform, ensure_ascii=False)
    assert "request_id" not in json.dumps(platform["by_reason"], ensure_ascii=False)
    assert set(platform) >= {"scope", "window_days", "totals", "by_reason", "by_model",
                             "router_mutation"}

    # the availability view states its scope — the §G finding, surfaced
    availability = client.get(AVAILABILITY).json()
    assert availability["scope"] == "process_local"
    assert availability["deployment_requirement"] == "single_backend_process"
    assert "carries no user id" in availability["note"]


def test_analytics_preserves_the_audit_semantics(client, db_session, monkeypatch):
    register_and_login(client, "p5_fa_audit")
    grant_unified_tier(db_session, "p5_fa_audit", "standard")
    request_id = _one_call(client, monkeypatch)
    _rate(client, request_id, "down", "bad_code")

    # the rating is STILL an audit fact, never study history
    assert taxonomy.is_user_facing("ai_feedback_submitted") is False
    assert "ai_feedback_submitted" in taxonomy.audit_only_event_types()
    # …and the analytics layer adds no event of its own
    from data_plane.models import LearningEvent
    db_session.expire_all()
    before = db_session.query(LearningEvent).filter(
        LearningEvent.user_id == _user(db_session, "p5_fa_audit").id).count()
    client.get(ANALYTICS)
    db_session.expire_all()
    after = db_session.query(LearningEvent).filter(
        LearningEvent.user_id == _user(db_session, "p5_fa_audit").id).count()
    assert after == before


# ================================================================ 2. no router mutation


def test_nothing_in_the_analytics_path_moves_the_router(client, db_session, monkeypatch):
    from ai import router as router_module

    register_and_login(client, "p5_fa_router")
    grant_unified_tier(db_session, "p5_fa_router", "advanced")
    for _ in range(3):
        _rate(client, _one_call(client, monkeypatch), "down", "slow")

    before = router_module.select_model("advanced", "tutor.chat", input_tokens=100,
                                        expected_output_tokens=200, available_budget=None)
    analytics = client.get(ANALYTICS).json()
    after = router_module.select_model("advanced", "tutor.chat", input_tokens=100,
                                       expected_output_tokens=200, available_budget=None)
    assert (before.model, before.provider, before.reason_code) == \
           (after.model, after.provider, after.reason_code)
    assert analytics["router_mutation"] is False
    assert "never trains, tunes or re-ranks" in analytics["semantics"]
