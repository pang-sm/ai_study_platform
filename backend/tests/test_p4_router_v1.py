"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4 — Router V1.

WHAT THESE TESTS HOLD
---------------------
1. a decision is EXPLAINABLE: it names the reason code, the candidate pool, the quality/cost/
   latency classes and the estimated cost of what it chose;
2. only the QUALIFIED pool for (capability, tier) is ever returned, and budget still rules;
3. a model whose provider is failing is SKIPPED while a healthy candidate remains, and the
   decision says which model was skipped; when everything is degraded the router tries anyway
   rather than refusing the learner;
4. the orchestrator RECORDS availability outcomes and PUBLISHES the decision (model, reason
   code, candidate count) into the audit event — so "which model answered, chosen why" is
   answerable after the fact, including for a fallback;
5. nothing about a learner personalizes a selection (no user id reaches the router).

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import json

from ai import pool
from ai.health import HealthRegistry, registry as health_registry
from ai.orchestrator import AIOrchestrator
from ai.providers import FakeProvider
from ai.router import (
    REASON_CHEAPEST,
    REASON_EXPLICIT,
    REASON_ONLY_CANDIDATE,
    select_model,
)
from conftest import grant_unified_tier, register_and_login
from data_plane.models import LearningEvent
from models import User

CAPABILITY = "tutor.chat"


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _fail(provider: str, model: str, times: int = 3) -> None:
    for _ in range(times):
        health_registry().record_failure(provider, model, "timeout")


# ================================================================ 1. explainability


def test_the_decision_names_its_rule_and_its_candidates():
    decision = select_model("standard", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, available_budget=None)
    assert decision.ok and decision.model and decision.provider
    assert decision.reason == "auto_recommended"
    assert decision.reason_code in (REASON_CHEAPEST, REASON_ONLY_CANDIDATE)
    assert decision.quality_class and decision.latency_class and decision.cost_profile
    assert decision.estimated_credits is not None
    assert decision.candidate_pool, "the pool it chose from must be observable"
    for candidate in decision.candidate_pool:
        assert {"provider", "model", "quality_class", "cost_profile",
                "latency_class", "estimated_credits"} <= set(candidate)
    assert decision.router_version == "router_v1"


def test_only_the_qualified_pool_is_ever_offered():
    for tier, capability in (("free", "tutor.chat"), ("standard", CAPABILITY),
                             ("advanced", "report.generate")):
        decision = select_model(tier, capability, input_tokens=100,
                                expected_output_tokens=200, available_budget=None)
        if not decision.ok:
            continue
        qualified = {entry.model for entry in pool.qualified_models_for(tier, capability)}
        assert {candidate["model"] for candidate in decision.candidate_pool} <= qualified
        assert decision.model in qualified

    explicit = select_model("advanced", "programming.debug", explicit_model="deepseek-v4-pro",
                            input_tokens=100, expected_output_tokens=200,
                            available_budget=1000)
    assert explicit.reason_code == REASON_EXPLICIT
    unqualified = select_model("standard", "programming.debug", explicit_model="deepseek-v4-pro")
    assert unqualified.ok is False and unqualified.reason == "model_not_qualified"


def test_tier_and_budget_still_rule():
    assert select_model("free", "question.generate").reason == "tier_not_permitted"
    starved = select_model("advanced", "report.generate", input_tokens=10000,
                           expected_output_tokens=8000, available_budget=1)
    assert starved.ok is False and starved.reason == "budget_incompatible"

    # the same inputs always decide the same way (no clock, no randomness, no user)
    first = select_model("standard", CAPABILITY, input_tokens=100,
                         expected_output_tokens=200, available_budget=500)
    second = select_model("standard", CAPABILITY, input_tokens=100,
                          expected_output_tokens=200, available_budget=500)
    assert (first.model, first.reason_code, first.estimated_credits) == \
           (second.model, second.reason_code, second.estimated_credits)


# ================================================================ 2. availability


def test_a_degraded_model_is_skipped_and_reported():
    baseline = select_model("standard", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, available_budget=None)
    _fail(baseline.provider, baseline.model)

    after = select_model("standard", CAPABILITY, input_tokens=100,
                         expected_output_tokens=200, available_budget=None)
    assert after.ok
    assert (after.provider, after.model) != (baseline.provider, baseline.model)
    assert baseline.model in after.skipped_degraded
    assert after.degraded_fallback is False

    # an explicit request for a degraded model still works: the user's choice is not vetoed
    explicit = select_model("standard", CAPABILITY, explicit_model=baseline.model,
                            input_tokens=100, expected_output_tokens=200,
                            available_budget=None)
    assert explicit.model == baseline.model


def test_a_success_restores_availability():
    baseline = select_model("standard", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, available_budget=None)
    _fail(baseline.provider, baseline.model)
    assert health_registry().is_degraded(baseline.provider, baseline.model) is True

    health_registry().record_success(baseline.provider, baseline.model)
    assert health_registry().is_degraded(baseline.provider, baseline.model) is False
    again = select_model("standard", CAPABILITY, input_tokens=100,
                         expected_output_tokens=200, available_budget=None)
    assert again.model == baseline.model


def test_when_every_candidate_is_degraded_the_router_still_tries():
    """Refusing a learner their answer is worse than trying a degraded model."""
    tier, capability = "free", CAPABILITY
    qualified = pool.qualified_models_for(tier, capability)
    for entry in qualified:
        _fail(entry.provider, entry.model)

    decision = select_model(tier, capability, input_tokens=100, expected_output_tokens=200,
                            available_budget=None)
    assert decision.ok, "a fully degraded pool must still answer, with the fact recorded"
    assert decision.degraded_fallback is True
    assert decision.skipped_degraded == []


def test_the_cooldown_expires_and_the_model_returns():
    """A degraded model recovers by itself once its cooldown passes (no manual reset)."""
    clock = {"now": 1000.0}
    registry = HealthRegistry(failure_threshold=2, cooldown_seconds=30.0,
                              clock=lambda: clock["now"])
    registry.record_failure("qwen", "qwen3.8-flash")
    registry.record_failure("qwen", "qwen3.8-flash")
    assert registry.is_degraded("qwen", "qwen3.8-flash") is True
    clock["now"] += 31
    assert registry.is_degraded("qwen", "qwen3.8-flash") is False


# ================================================================ 3. orchestration observability


def _messages():
    return [{"role": "user", "content": "解释一下虚拟内存"}]


def test_the_orchestrator_publishes_the_decision_and_records_health(
        client, db_session, monkeypatch):
    register_and_login(client, "p4_router_ok")
    user = _user(db_session, "p4_router_ok")
    grant_unified_tier(db_session, "p4_router_ok", "standard")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: FakeProvider(provider=name, input_tokens=50,
                                                  output_tokens=40))
    result = AIOrchestrator().execute(db_session, user.id, CAPABILITY, _messages())
    assert result.ok and result.status == "settled"

    db_session.expire_all()
    event = (db_session.query(LearningEvent)
             .filter(LearningEvent.event_type == "ai_called",
                     LearningEvent.source_attempt_id == result.request_id).one())
    payload = json.loads(event.item_snapshot_json)
    assert payload["model"] == result.model
    assert payload["router_reason_code"] in (REASON_CHEAPEST, REASON_ONLY_CANDIDATE)
    assert payload["candidate_count"] >= 1
    assert payload["router_version"] == "router_v1"
    assert payload["quality_class"] and payload["latency_class"]


def test_a_fallback_is_recorded_as_a_fallback(client, db_session, monkeypatch):
    register_on = register_and_login
    register_on(client, "p4_router_fallback")
    user = _user(db_session, "p4_router_fallback")
    grant_unified_tier(db_session, "p4_router_fallback", "advanced")

    calls = {"count": 0}

    def _factory(name: str):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeProvider(behavior="raise_timeout", provider=name)
        return FakeProvider(provider=name, input_tokens=40, output_tokens=30)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _factory)
    result = AIOrchestrator().execute(db_session, user.id, CAPABILITY, _messages())
    assert result.ok and result.status == "settled", result.status
    assert result.router["reason_code"] == "fallback_after_failure"
    assert result.router["fallback_from"], "the failed model must be named"
    assert calls["count"] >= 2, "the fallback really called a second candidate"

    # …and the failed model is now marked degraded (its provider really did fail)
    failed_provider, failed_model = result.router["fallback_from"].split("/", 1)
    assert health_registry().snapshot().get(f"{failed_provider}/{failed_model}") is not None

    db_session.expire_all()
    event = (db_session.query(LearningEvent)
             .filter(LearningEvent.event_type == "ai_called",
                     LearningEvent.source_attempt_id == result.request_id).one())
    payload = json.loads(event.item_snapshot_json)
    assert payload["router_reason_code"] == "fallback_after_failure"
    assert payload["model"] == result.model
