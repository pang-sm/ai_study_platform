"""STEP 7B final: cost/refund settlement matrix + ledger conservation invariants.

The canonical rule (SSOT): provider billable usage/cost has priority over terminal
request reason. If the provider produced measurable usage, settle actual + release
the difference — regardless of timeout / user cancel / postprocessing failure.
"""
from models import User
from usage import service
from usage.models import AIRequest, UsageBudget, UsageLedger


def _make_user(session, username="alice") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def _daily_budget(session, user_id):
    b = (session.query(UsageBudget)
         .filter(UsageBudget.user_id == user_id, UsageBudget.period_type == "daily")
         .order_by(UsageBudget.id.desc()).first())
    session.refresh(b)
    return b


def _assert_invariants(budget):
    assert budget.reserved_amount >= 0
    assert budget.settled_amount >= 0
    available = budget.budget_amount - budget.reserved_amount - budget.settled_amount
    assert available >= 0
    return available


# ---- A17: ledger conservation ----

def test_reserve_settle_conservation(db_session):
    u = _make_user(db_session, "consrv1")
    assert service.reserve_credits(db_session, u.id, "r1", "tutor.chat", 80)["reserved"]
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 80

    r = service.settle_credits(db_session, "r1", 50, provider="deepseek", model="m")
    assert r["settled_credits"] == 50 and r["released_credits"] == 30
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 0          # reservation fully released
    assert b.settled_amount == 50          # actual settled
    _assert_invariants(b)

    # release trace for the 30-credit difference is present in the ledger
    releases = (db_session.query(UsageLedger)
                .filter(UsageLedger.request_id == "r1", UsageLedger.entry_type == "release").all())
    assert sum(e.amount for e in releases) == -30


def test_reserve_full_release_conservation(db_session):
    u = _make_user(db_session, "consrv2")
    service.reserve_credits(db_session, u.id, "r2", "tutor.chat", 40)
    assert service.release_credits(db_session, "r2")["released"]
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 0
    _assert_invariants(b)


def test_duplicate_settle_no_change(db_session):
    u = _make_user(db_session, "consrv3")
    service.reserve_credits(db_session, u.id, "r3", "tutor.chat", 30)
    service.settle_credits(db_session, "r3", 20)
    before = _daily_budget(db_session, u.id).settled_amount
    r2 = service.settle_credits(db_session, "r3", 20)
    assert r2["reason"] == "already_settled"
    assert _daily_budget(db_session, u.id).settled_amount == before


def test_duplicate_release_no_change(db_session):
    u = _make_user(db_session, "consrv4")
    service.reserve_credits(db_session, u.id, "r4", "tutor.chat", 30)
    service.release_credits(db_session, "r4")
    r2 = service.release_credits(db_session, "r4")
    assert r2["reason"] == "already_released"
    assert _daily_budget(db_session, u.id).reserved_amount == 0


def test_release_after_settle_is_guarded(db_session):
    u = _make_user(db_session, "consrv5")
    service.reserve_credits(db_session, u.id, "r5", "tutor.chat", 30)
    service.settle_credits(db_session, "r5", 30)
    r = service.release_credits(db_session, "r5")
    assert r["reason"] == "already_settled" and r["released"] is False
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 0 and b.settled_amount == 30  # no double release


# ---- A15: unknown usage → reconciliation_pending (no silent zero, no full refund) ----

def test_reconciliation_pending_keeps_reservation(db_session):
    u = _make_user(db_session, "recon1")
    service.reserve_credits(db_session, u.id, "r6", "tutor.chat", 50)
    r = service.mark_reconciliation_pending(db_session, "r6")
    assert r["ok"]
    req = db_session.query(AIRequest).filter(AIRequest.request_id == "r6").one()
    assert req.status == "reconciliation_pending"
    assert req.error_category == "cost_reconciliation_pending"
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 50  # reservation NOT released, NOT silently zeroed


def test_reconcile_credits_settles_actual(db_session):
    u = _make_user(db_session, "recon2")
    service.reserve_credits(db_session, u.id, "r7", "tutor.chat", 50)
    service.mark_reconciliation_pending(db_session, "r7")
    r = service.reconcile_credits(db_session, "r7", 40, provider="deepseek", model="m")
    assert r["settled_credits"] == 40 and r["released_credits"] == 10
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 0 and b.settled_amount == 40
    _assert_invariants(b)


def test_reconcile_confirmed_zero_releases(db_session):
    u = _make_user(db_session, "recon3")
    service.reserve_credits(db_session, u.id, "r8", "tutor.chat", 50)
    service.mark_reconciliation_pending(db_session, "r8")
    # confirmed zero billable usage → full release resolves the pending reservation
    assert service.release_credits(db_session, "r8")["released"]
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 0 and b.settled_amount == 0


# ---- A14: terminal-reason settlement semantics (usage has priority) ----

def test_timeout_with_measured_usage_settles_actual(db_session):
    u = _make_user(db_session, "term1")
    service.reserve_credits(db_session, u.id, "r9", "tutor.chat", 40)
    # timeout, but provider reported 15 credits of usage → settle actual, release diff
    r = service.settle_credits(db_session, "r9", 15, provider="deepseek", model="m")
    assert r["settled_credits"] == 15 and r["released_credits"] == 25


def test_user_cancel_no_usage_releases_full(db_session):
    u = _make_user(db_session, "term2")
    service.reserve_credits(db_session, u.id, "r10", "tutor.chat", 40)
    # user cancel with confirmed zero usage → release full
    assert service.release_credits(db_session, "r10")["released"]
    b = _daily_budget(db_session, u.id)
    assert b.reserved_amount == 0 and b.settled_amount == 0
