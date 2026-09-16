"""STEP 7C-P: cross-provider fallback + no-bypass guarantees (no live API)."""
from ai.gateway import GatewayError, GatewayErrorCategory
from ai.orchestrator import AIOrchestrator
from ai.providers import FakeProvider
from models import User
from usage import service


def _make_user(session, username, tier="standard") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        service.activate_subscription(session, u.id, tier, 30)
    return u


def _messages(text="hello"):
    return [{"role": "user", "content": text}]


def test_primary_unavailable_falls_back_cross_provider(db_session):
    u = _make_user(db_session, "fb1", tier="standard")

    def factory(name):
        if name == "deepseek":
            raise GatewayError(GatewayErrorCategory.provider_unavailable, "deepseek down",
                               retriable=True)
        return FakeProvider(provider=name, behavior="success")

    orch = AIOrchestrator(provider_factory=factory)
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(), max_tokens=100)
    assert result.ok is True
    assert result.provider != "deepseek"          # fell back to a different provider
    assert result.model in {"glm-5.3-flash", "qwen3.8-flash"}  # qualified fallback


def test_no_fallback_on_permanent_error(db_session):
    u = _make_user(db_session, "fb2", tier="standard")

    def factory(name):
        raise GatewayError(GatewayErrorCategory.authentication, "bad key")

    orch = AIOrchestrator(provider_factory=factory)
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(), max_tokens=100)
    # authentication is non-retriable → no fallback, release full
    assert result.ok is False and result.status == "released"


def test_no_tier_bypass(db_session):
    u = _make_user(db_session, "fb3", tier="free")  # free cannot do programming.debug
    orch = AIOrchestrator(provider_factory=lambda name: FakeProvider(provider=name))
    result = orch.execute(db_session, u.id, "programming.debug", _messages())
    assert result.ok is False and result.status == "denied"
    assert result.error_category == "permission_denied"


def test_no_unqualified_model_via_fallback(db_session):
    # fallback must stay within the qualified pool: an unqualified explicit model is
    # rejected before any provider call.
    u = _make_user(db_session, "fb4", tier="free")
    orch = AIOrchestrator(provider_factory=lambda name: FakeProvider(provider=name))
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(),
                          explicit_model="deepseek-v4-pro")
    assert result.ok is False and result.status == "denied"
