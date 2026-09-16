"""STEP 7B: Unified Subscription / Capability Permission / Usage Budget & Ledger."""
import threading

import pytest

from models import User
from usage import service
from usage.capabilities import check_capability_permission
from usage.models import AIRequest, Subscription, UsageBudget, UsageLedger


def _make_user(session, username="alice") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


# ---- Subscription ----

def test_no_subscription_is_free(db_session):
    u = _make_user(db_session, "alice")
    assert service.effective_subscription(db_session, u.id) == "free"


def test_active_standard(db_session):
    u = _make_user(db_session, "bob")
    service.activate_subscription(db_session, u.id, "standard", 30)
    assert service.effective_subscription(db_session, u.id) == "standard"


def test_expired_returns_free(db_session):
    u = _make_user(db_session, "carol")
    sub = service.activate_subscription(db_session, u.id, "standard", 30)
    # force-expire
    from datetime import timedelta
    sub.end_at = sub.end_at - timedelta(days=60)
    db_session.commit()
    assert service.effective_subscription(db_session, u.id) == "free"


def test_one_effective_tier(db_session):
    u = _make_user(db_session, "dave")
    service.activate_subscription(db_session, u.id, "standard", 30)
    service.activate_subscription(db_session, u.id, "advanced", 30)
    assert service.effective_subscription(db_session, u.id) == "advanced"
    active = (db_session.query(Subscription)
              .filter(Subscription.user_id == u.id, Subscription.status == "active").count())
    assert active == 1


# ---- Capability Permission ----

def test_free_allowed_basic():
    assert check_capability_permission("free", "tutor.chat")["allowed"] is True


def test_free_denied_premium():
    r = check_capability_permission("free", "report.generate")
    assert r["allowed"] is False and r["reason"] == "tier_not_permitted"


def test_standard_allowed_generate():
    assert check_capability_permission("standard", "question.generate")["allowed"] is True


def test_advanced_allowed_report():
    assert check_capability_permission("advanced", "report.generate")["allowed"] is True


def test_unknown_capability_fails_closed():
    r = check_capability_permission("advanced", "bogus.cap")
    assert r["allowed"] is False and r["reason"] == "unknown_capability"


# ---- Budget / Ledger ----

def test_reserve_and_usage_summary(db_session):
    u = _make_user(db_session, "eve")
    r = service.reserve_credits(db_session, u.id, "req-1", "tutor.chat", 10)
    assert r["reserved"] is True
    summary = service.usage_summary(db_session, u.id)
    assert summary["periods"]["daily"]["reserved"] == 10
    assert summary["periods"]["daily"]["remaining"] == 90  # free daily = 100


def test_reserve_insufficient_budget(db_session):
    u = _make_user(db_session, "frank")
    # free daily = 100, weekly = 500; try to reserve > weekly
    r = service.reserve_credits(db_session, u.id, "req-2", "tutor.chat", 9999)
    assert r["reserved"] is False and r["reason"] == "insufficient_budget"


def test_reserve_permission_denied(db_session):
    u = _make_user(db_session, "grace")
    r = service.reserve_credits(db_session, u.id, "req-3", "report.generate", 10)
    assert r["reserved"] is False and r["reason"] == "tier_not_permitted"


def test_reserve_idempotent(db_session):
    u = _make_user(db_session, "heidi")
    service.reserve_credits(db_session, u.id, "req-4", "tutor.chat", 10)
    r2 = service.reserve_credits(db_session, u.id, "req-4", "tutor.chat", 10)
    assert r2["reason"] == "already_exists"
    # reserved amount not double-counted
    summary = service.usage_summary(db_session, u.id)
    assert summary["periods"]["daily"]["reserved"] == 10


def test_settle_exact(db_session):
    u = _make_user(db_session, "ivan")
    service.reserve_credits(db_session, u.id, "req-5", "tutor.chat", 10)
    r = service.settle_credits(db_session, "req-5", 10, provider="deepseek", model="deepseek-chat",
                               input_tokens=5000, output_tokens=1000, provider_cost=0.06, currency="CNY")
    assert r["settled"] is True and r["settled_credits"] == 10 and r["released_credits"] == 0


def test_settle_lower_releases_difference(db_session):
    u = _make_user(db_session, "judy")
    service.reserve_credits(db_session, u.id, "req-6", "tutor.chat", 10)
    r = service.settle_credits(db_session, "req-6", 6)
    assert r["settled_credits"] == 6 and r["released_credits"] == 4
    summary = service.usage_summary(db_session, u.id)
    assert summary["periods"]["daily"]["settled"] == 6


def test_settle_overage_not_permitted(db_session):
    u = _make_user(db_session, "karl")
    service.reserve_credits(db_session, u.id, "req-7", "tutor.chat", 10)
    r = service.settle_credits(db_session, "req-7", 15)
    assert r["settled"] is False and r["reason"] == "overage_not_permitted"


def test_settle_idempotent(db_session):
    u = _make_user(db_session, "laura")
    service.reserve_credits(db_session, u.id, "req-8", "tutor.chat", 10)
    service.settle_credits(db_session, "req-8", 10)
    r2 = service.settle_credits(db_session, "req-8", 10)
    assert r2["reason"] == "already_settled"
    # ledger has exactly one settle entry
    settles = (db_session.query(UsageLedger)
               .filter(UsageLedger.request_id == "req-8", UsageLedger.entry_type == "settle").count())
    assert settles == 1


def test_release_on_failure(db_session):
    u = _make_user(db_session, "mike")
    service.reserve_credits(db_session, u.id, "req-9", "tutor.chat", 10)
    r = service.release_credits(db_session, "req-9")
    assert r["released"] is True
    summary = service.usage_summary(db_session, u.id)
    assert summary["periods"]["daily"]["reserved"] == 0


# ---- Concurrency (no overspend) ----

def test_concurrent_reservation_no_overspend(db_session):
    u = _make_user(db_session, "nick")
    # pre-create the daily budget row to avoid creation race
    service.get_or_create_budget(db_session, u.id, "daily")
    db_session.commit()

    results = []

    def worker():
        from database import SessionLocal
        s = SessionLocal()
        try:
            r = service.reserve_credits(s, u.id, f"conc-{threading.get_ident()}", "tutor.chat", 60)
            results.append(r["reserved"])
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # free daily budget = 100; at most one 60-credit reservation can succeed
    assert results.count(True) == 1
    budget = (db_session.query(UsageBudget)
              .filter(UsageBudget.user_id == u.id, UsageBudget.period_type == "daily").first())
    db_session.refresh(budget)
    assert budget.reserved_amount <= budget.budget_amount


# ---- Cost engine ----

def test_normalize_and_estimate():
    assert service.normalize_credits(0.06, "CNY") == 6   # 0.06 CNY → 6 credits
    assert service.estimate_credits(5000, 1000) == 6     # 6000 tokens → 6 credits
