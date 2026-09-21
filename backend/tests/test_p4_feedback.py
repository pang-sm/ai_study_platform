"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4 — Model Feedback.

WHAT THESE TESTS HOLD
---------------------
1. a rating is recorded against the REQUEST that produced the response, with the context that
   makes it interpretable later (capability, model, provider, router reason, latency, cost);
2. ownership is total: another learner's request id is a 404, and a rating can never be written
   against someone else's request;
3. the negative-reason vocabulary is CLOSED (the frozen taxonomy) and a negative rating must
   name a reason;
4. feedback NEVER changes the live router: the same inputs select the same model before and
   after a dislike, and the availability signal is untouched.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from data_plane.models import LearningEvent
from learning.feedback import REASON_TAXONOMY
from learning.records import taxonomy
from models import User

FEEDBACK = "/ai/feedback"
DEEP_STUDY = "/ai/deep-study"
COURSE = "数据结构"
ANSWER = "虚拟内存是操作系统对物理内存的抽象。"


class _ScriptedProvider(FakeProvider):
    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=ANSWER)


def _provider(name: str) -> FakeProvider:
    return _ScriptedProvider(provider=name, input_tokens=70, output_tokens=50)


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _run_one_ai_call(client, monkeypatch, username) -> str:
    """One real orchestrated call, returning its request_id."""
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider)
    response = client.post(DEEP_STUDY, json={"question": "什么是虚拟内存？", "course_id": COURSE})
    assert response.status_code == 200, response.text
    return response.json()["request_id"]


# ================================================================ 1. the record


def test_feedback_records_the_full_request_context(client, db_session, monkeypatch):
    register_and_login(client, "p4_fb_ok")
    grant_unified_tier(db_session, "p4_fb_ok", "standard")
    request_id = _run_one_ai_call(client, monkeypatch, "p4_fb_ok")

    response = client.post(FEEDBACK, json={
        "request_id": request_id, "rating": "down", "reason": "incorrect",
        "regenerated": True, "workflow_id": "deep_study"})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["request_id"] == request_id
    assert body["rating"] == "down" and body["reason"] == "incorrect"
    assert body["capability"] == "tutor.strong_reasoning"
    assert body["service_namespace"] == "course_learning"
    assert body["model"] and body["provider"]
    assert body["latency_ms"] is not None
    assert body["actual_credits"] is not None
    assert body["regenerated"] is True
    assert body["workflow_id"] == "deep_study"
    # the router's own reason travels with the rating, so "which model, chosen why" is part
    # of the feedback record
    assert body["router_reason"] in {"cheapest_qualified_within_budget",
                                     "only_qualified_candidate",
                                     "fallback_after_failure"}
    assert body["trains_router_online"] is False
    assert body["reason_taxonomy"] == list(REASON_TAXONOMY)

    # the audit fact exists, and it is AUDIT-ONLY: never study history
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == _user(db_session, "p4_fb_ok").id,
                      LearningEvent.event_type == "ai_feedback_submitted").all())
    assert events, "a rating is a canonical fact"
    payload = json.loads(events[0].item_snapshot_json)
    assert payload["rating"] == "down" and payload["reason"] == "incorrect"
    assert payload["request_id"] == request_id
    assert ANSWER not in events[0].item_snapshot_json      # no response text in the stream
    assert taxonomy.is_user_facing("ai_feedback_submitted") is False
    assert "ai_feedback_submitted" in taxonomy.audit_only_event_types()


def test_another_learners_request_is_a_404(client, db_session, monkeypatch):
    register_and_login(client, "p4_fb_owner")
    grant_unified_tier(db_session, "p4_fb_owner", "standard")
    stranger_request_id = _run_one_ai_call(client, monkeypatch, "p4_fb_owner")

    register_and_login(client, "p4_fb_caller")
    refused = client.post(FEEDBACK, json={"request_id": stranger_request_id,
                                          "rating": "up"})
    assert refused.status_code == 404, refused.text
    assert refused.json()["detail"]["code"] == "request_not_found"

    # the stranger's own feedback stream stayed empty
    db_session.expire_all()
    assert db_session.query(LearningEvent).filter(
        LearningEvent.user_id == _user(db_session, "p4_fb_caller").id,
        LearningEvent.event_type == "ai_feedback_submitted").count() == 0


def test_the_reason_taxonomy_is_closed(client, db_session, monkeypatch):
    register_and_login(client, "p4_fb_taxonomy")
    grant_unified_tier(db_session, "p4_fb_taxonomy", "standard")
    request_id = _run_one_ai_call(client, monkeypatch, "p4_fb_taxonomy")

    # a reason outside the frozen vocabulary is refused by the contract
    invalid = client.post(FEEDBACK, json={"request_id": request_id, "rating": "down",
                                          "reason": "vibes"})
    assert invalid.status_code == 422, invalid.text

    # a negative rating must name one of them
    missing = client.post(FEEDBACK, json={"request_id": request_id, "rating": "down"})
    assert missing.status_code == 400, missing.text
    assert missing.json()["detail"]["code"] == "reason_required"

    # a positive rating needs no reason
    up = client.post(FEEDBACK, json={"request_id": request_id, "rating": "up"})
    assert up.status_code == 200, up.text
    assert up.json()["reason"] is None


def test_feedback_never_changes_the_live_router(client, db_session, monkeypatch):
    """A dislike is stored; the selection rules and the health signal do not move."""
    from ai import router as router_module
    from ai.health import registry as health

    register_and_login(client, "p4_fb_router")
    grant_unified_tier(db_session, "p4_fb_router", "standard")
    request_id = _run_one_ai_call(client, monkeypatch, "p4_fb_router")

    before = router_module.select_model("standard", "tutor.chat", input_tokens=100,
                                        expected_output_tokens=200, available_budget=None)
    health_before = health().snapshot()

    client.post(FEEDBACK, json={"request_id": request_id, "rating": "down",
                                "reason": "too_verbose"})

    after = router_module.select_model("standard", "tutor.chat", input_tokens=100,
                                       expected_output_tokens=200, available_budget=None)
    assert (after.model, after.provider, after.reason_code) == \
           (before.model, before.provider, before.reason_code)
    assert health().snapshot() == health_before
