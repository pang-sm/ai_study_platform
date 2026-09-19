"""STEP 7C: AI Orchestrator — full request lifecycle, provider failure, idempotency."""
import threading

from ai.orchestrator import AIOrchestrator
from core.learning_context import LearningContext, ServiceNamespace
from ai.providers import FakeProvider
from models import User
from usage import service
from usage.models import AICostRecord, AIRequest, UsageBudget, UsageLedger


def _make_user(session, username="alice", tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        service.activate_subscription(session, u.id, tier, 30)
    return u


def _orch(behavior="success"):
    return AIOrchestrator(
        provider_factory=lambda name: FakeProvider(provider=name, behavior=behavior))


def _messages(text="hello"):
    return [{"role": "user", "content": text}]


# ---- B42: full lifecycle ----

def test_full_lifecycle_consistent(db_session):
    u = _make_user(db_session, "orch1", tier="standard")
    orch = _orch("success")
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(),
                          request_id="orch-req-1", max_tokens=200)
    assert result.ok is True
    assert result.status == "settled"

    req = db_session.query(AIRequest).filter(AIRequest.request_id == "orch-req-1").one()
    assert req.status == "settled"
    assert req.provider == "deepseek" and req.model == "deepseek-flash"

    # ledger has reserve + settle
    entries = {e.entry_type for e in db_session.query(UsageLedger)
               .filter(UsageLedger.request_id == "orch-req-1").all()}
    assert "reserve" in entries and "settle" in entries

    # cost record written
    assert db_session.query(AICostRecord).filter(
        AICostRecord.request_id == "orch-req-1").count() == 1

    # budget conserved: reserved back to 0, settled > 0
    b = db_session.query(UsageBudget).filter(
        UsageBudget.user_id == u.id, UsageBudget.period_type == "daily").one()
    assert b.reserved_amount == 0 and b.settled_amount > 0


def test_permission_denied(db_session):
    u = _make_user(db_session, "orch2")  # free
    orch = _orch("success")
    result = orch.execute(db_session, u.id, "report.generate", _messages())
    assert result.ok is False and result.status == "denied"
    assert result.error_category == "permission_denied"


# ---- B43: provider failure ----

def test_failure_before_usage_releases(db_session):
    u = _make_user(db_session, "orch3", tier="standard")
    orch = _orch("raise_auth")
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(),
                          request_id="orch-fail-1", max_tokens=200)
    assert result.ok is False and result.status == "released"
    b = db_session.query(UsageBudget).filter(
        UsageBudget.user_id == u.id, UsageBudget.period_type == "daily").one()
    assert b.reserved_amount == 0 and b.settled_amount == 0


def test_timeout_reconciliation_pending(db_session):
    u = _make_user(db_session, "orch4", tier="standard")
    orch = _orch("raise_timeout")
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(),
                          request_id="orch-timeout-1", max_tokens=200)
    assert result.ok is False and result.status == "reconciliation_pending"
    req = db_session.query(AIRequest).filter(AIRequest.request_id == "orch-timeout-1").one()
    assert req.status == "reconciliation_pending"


def test_unknown_usage_reconciliation_pending(db_session):
    u = _make_user(db_session, "orch5", tier="standard")
    orch = _orch("unknown_usage")
    result = orch.execute(db_session, u.id, "tutor.chat", _messages(),
                          request_id="orch-unknown-1", max_tokens=200)
    assert result.status == "reconciliation_pending"
    req = db_session.query(AIRequest).filter(AIRequest.request_id == "orch-unknown-1").one()
    assert req.status == "reconciliation_pending"


# ---- B44: billing idempotency (same request id) ----

def test_same_request_id_no_double_charge(db_session):
    u = _make_user(db_session, "orch6", tier="standard")
    orch = _orch("success")
    orch.execute(db_session, u.id, "tutor.chat", _messages(),
                 request_id="orch-dup-1", max_tokens=200)
    cost_before = db_session.query(AICostRecord).filter(
        AICostRecord.request_id == "orch-dup-1").count()
    # second execute with the same request id must NOT double-execute/double-settle
    second = orch.execute(db_session, u.id, "tutor.chat", _messages(),
                          request_id="orch-dup-1", max_tokens=200)
    assert second.ok is False  # already-reserved → denied, not re-settled
    cost_after = db_session.query(AICostRecord).filter(
        AICostRecord.request_id == "orch-dup-1").count()
    assert cost_after == cost_before == 1


def test_same_request_id_concurrent_no_double_reservation(db_session):
    u = _make_user(db_session, "orch7", tier="standard")
    uid = u.id
    service.get_or_create_budget(db_session, uid, "daily")
    service.get_or_create_budget(db_session, uid, "weekly")
    db_session.commit()

    results = []

    def worker():
        from database import SessionLocal
        s = SessionLocal()
        try:
            r = service.reserve_credits(s, uid, "orch-conc-1", "tutor.chat", 30)
            results.append(r["reserved"])
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # billing idempotency: the budget is reserved EXACTLY once (30, not 4×30)
    b = db_session.query(UsageBudget).filter(
        UsageBudget.user_id == uid, UsageBudget.period_type == "daily").one()
    db_session.refresh(b)
    assert b.reserved_amount == 30
    # exactly one request row for this request_id
    assert db_session.query(AIRequest).filter(
        AIRequest.request_id == "orch-conc-1").count() == 1


# ---- B22: capability inventory coverage ----

def test_all_capabilities_have_a_qualified_model_somewhere():
    from ai.pool import ALL_CAPABILITIES, QUALIFIED_POOL
    for cap in ALL_CAPABILITIES:
        covered = any(cap in e.capabilities for e in QUALIFIED_POOL)
        assert covered, f"capability {cap} has no qualified model"

def test_course_context_is_persisted_and_reused_for_ai_called(db_session, monkeypatch):
    """A Course AI request and its canonical event share one durable context snapshot."""
    u = _make_user(db_session, "orch-course-context")
    emitted = []
    monkeypatch.setattr("learning.records.producers.emit_ai_called",
                        lambda **kwargs: emitted.append(kwargs) or {"ok": True})
    context = LearningContext(
        user_id=u.id,
        service_namespace=ServiceNamespace.COURSE_LEARNING,
        course_id="data_structure",
        chapter_id="1",
        material_ids=["7"],
    )
    result = _orch("success").execute(
        db_session, u.id, "tutor.chat", _messages(), learning_context=context)
    assert result.ok is True
    req = db_session.query(AIRequest).filter(AIRequest.request_id == result.request_id).one()
    assert req.service_namespace == "course_learning"
    assert req.context_json == context.to_dict()
    assert emitted[0]["learning_context"] == context
    ledger_rows = db_session.query(UsageLedger).filter(
        UsageLedger.request_id == result.request_id).all()
    assert ledger_rows
    assert {row.service_namespace for row in ledger_rows} == {"course_learning"}
