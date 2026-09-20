"""Unified Subscription / Usage Budget & Ledger / Cost (STEP 7B) core service.

Execution chain (SSOT §7): estimate → reserve → execute → actual → settle.
Ledger is append-oriented and idempotent. Budget reservation is concurrency-safe via
atomic conditional UPDATE (no overspend). Timezone for periods is UTC (naive, matching
the codebase's existing utcnow convention).

Normalized credits are integers. 1 credit ≈ ¥0.01 platform model cost (SSOT §6);
provider currency cost is preserved separately in ai_cost_records.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError

from models import MembershipOrder

from .capabilities import (
    CAPABILITY_TIER_POLICY,
    VALID_TIERS,
    check_capability_permission,
    normalize_tier,
)
from .models import AICostRecord, AIRequest, Subscription, UsageBudget, UsageLedger

__all__ = [
    "CAPABILITY_TIER_POLICY", "VALID_TIERS", "normalize_tier",
    "effective_subscription", "budget_amount_for",
]

CREDIT_UNIT_CNY = 0.01  # 1 credit ≈ ¥0.01 (SSOT §6, provisional)

# Unified subscription ordering (STEP 7B final reconciliation). Reuses the legacy
# membership_orders audit trail (STEP5 frozen); NO second order table is created.
UNIFIED_SERVICE_KEY = "unified"
UNIFIED_PLAN_PRICING = {
    "standard": {"price_cents": 2900, "default_duration_days": 30, "label": "Standard"},
    "advanced": {"price_cents": 14900, "default_duration_days": 30, "label": "Advanced"},
}

# Terminal AI request statuses that must never be re-settled or re-released.
_TERMINAL_STATUSES = ("settled", "released")

# tier → period credits (CONFIG). None = no membership cap (Advanced daily).
DAILY_BUDGET = {"free": 100, "standard": 1000, "advanced": None}
WEEKLY_BUDGET = {"free": 500, "standard": 5000, "advanced": 20000}


def _utcnow() -> datetime:
    return datetime.utcnow()


def effective_subscription(session, user_id: int, now: datetime | None = None) -> str:
    """One user → one effective tier. No active subscription → FREE.

    Considers only the unified `subscriptions` table (NOT legacy per-service membership).
    """
    now = now or _utcnow()
    sub = (session.query(Subscription)
           .filter(Subscription.user_id == user_id,
                   Subscription.status == "active",
                   (Subscription.end_at.is_(None)) | (Subscription.end_at > now))
           .order_by(Subscription.end_at.desc(), Subscription.id.desc())
           .first())
    return normalize_tier(sub.tier) if sub else "free"


def budget_amount_for(tier: str, period_type: str) -> int | None:
    tier = normalize_tier(tier)
    table = DAILY_BUDGET if period_type == "daily" else WEEKLY_BUDGET
    return table.get(tier)


def _period_bounds(period_type: str, now: datetime) -> tuple[datetime, datetime]:
    if period_type == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    # weekly: Monday 00:00 UTC
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def get_or_create_budget(session, user_id: int, period_type: str, now: datetime | None = None) -> UsageBudget:
    now = now or _utcnow()
    start, end = _period_bounds(period_type, now)
    budget = (session.query(UsageBudget)
              .filter(UsageBudget.user_id == user_id,
                      UsageBudget.period_type == period_type,
                      UsageBudget.period_start == start)
              .first())
    if budget is None:
        tier = effective_subscription(session, user_id, now)
        amount = budget_amount_for(tier, period_type) or 0
        budget = UsageBudget(user_id=user_id, period_type=period_type,
                             period_start=start, period_end=end,
                             budget_amount=amount, reserved_amount=0, settled_amount=0)
        session.add(budget)
        session.flush()
    return budget


def _atomic_reserve(session, budget: UsageBudget, amount: int) -> bool:
    """Atomic conditional reserve: UPDATE ... WHERE remaining >= amount. Returns True on success."""
    result = session.execute(
        update(UsageBudget)
        .where(UsageBudget.id == budget.id,
               (UsageBudget.budget_amount - UsageBudget.reserved_amount
                - UsageBudget.settled_amount) >= amount)
        .values(reserved_amount=UsageBudget.reserved_amount + amount,
                updated_at=_utcnow())
    )
    return result.rowcount == 1


def _atomic_release(session, budget: UsageBudget, amount: int) -> None:
    session.execute(
        update(UsageBudget)
        .where(UsageBudget.id == budget.id)
        .values(reserved_amount=UsageBudget.reserved_amount - amount,
                updated_at=_utcnow())
    )


def _ledger_entry(session, user_id: int, request_id: str, entry_type: str,
                  amount: int, reference_key: str,
                  service_namespace: str | None = None) -> bool:
    """Append an idempotent ledger entry. Returns False if already present."""
    existing = (session.query(UsageLedger)
                .filter(UsageLedger.reference_key == reference_key).first())
    if existing is not None:
        return False
    session.add(UsageLedger(user_id=user_id, request_id=request_id, entry_type=entry_type,
                            service_namespace=service_namespace,
                            amount=amount, reference_key=reference_key,
                            created_at=_utcnow()))
    session.flush()
    return True


def reserve_credits(session, user_id: int, request_id: str, capability: str,
                    amount: int, *, service_namespace: str | None = None,
                    context_json: dict | None = None) -> dict:
    """Permission check → budget check → atomic reservation. Idempotent per request_id."""
    tier = effective_subscription(session, user_id)
    perm = check_capability_permission(tier, capability)
    if not perm["allowed"]:
        return {"reserved": False, "reason": perm["reason"], "tier": tier,
                "capability": capability, "policy_version": perm["policy_version"]}

    existing = session.query(AIRequest).filter(AIRequest.request_id == request_id).first()
    if existing is not None:
        return {"reserved": existing.status in ("reserved", "executing", "settled"),
                "reason": "already_exists", "tier": tier, "request": existing}

    reserved_budgets: list[UsageBudget] = []
    try:
        for period_type in ("daily", "weekly"):
            if budget_amount_for(tier, period_type) is None:
                continue  # no membership cap for this period (Advanced daily)
            budget = get_or_create_budget(session, user_id, period_type)
            if not _atomic_reserve(session, budget, amount):
                for b in reserved_budgets:
                    _atomic_release(session, b, amount)
                session.commit()
                return {"reserved": False, "reason": "insufficient_budget", "tier": tier,
                        "capability": capability, "policy_version": perm["policy_version"]}
            reserved_budgets.append(budget)
    except Exception:
        session.rollback()
        raise

    for period_type in ("daily", "weekly"):
        if budget_amount_for(tier, period_type) is not None:
            _ledger_entry(session, user_id, request_id, "reserve", amount,
                          f"reserve:{request_id}:{period_type}", service_namespace)

    session.add(AIRequest(request_id=request_id, user_id=user_id, capability=capability,
                          tier=tier, status="reserved", estimated_credits=amount,
                          reserved_credits=amount, service_namespace=service_namespace,
                          context_json=context_json, created_at=_utcnow()))
    try:
        session.commit()
    except IntegrityError:
        # Same request_id won a concurrent race — the unique constraint is the gate.
        session.rollback()
        return {"reserved": False, "reason": "already_exists", "tier": tier,
                "capability": capability, "policy_version": perm["policy_version"]}
    return {"reserved": True, "reason": "ok", "tier": tier, "capability": capability,
            "policy_version": perm["policy_version"]}


def release_credits(session, request_id: str) -> dict:
    """Release a full reservation (confirmed zero billable usage). Idempotent.

    Never releases an already-settled request (terminal status guard) — that would
    double-count budget and break ledger conservation.
    """
    req = session.query(AIRequest).filter(AIRequest.request_id == request_id).first()
    if req is None:
        return {"released": False, "reason": "unknown_request"}
    if req.status in _TERMINAL_STATUSES:
        return {"released": req.status == "released",
                "reason": "already_released" if req.status == "released" else "already_settled"}
    reserved = req.reserved_credits or 0
    for period_type in ("daily", "weekly"):
        b = (session.query(UsageBudget)
             .filter(UsageBudget.user_id == req.user_id, UsageBudget.period_type == period_type)
             .first())
        if b is not None:
            _atomic_release(session, b, reserved)
    _ledger_entry(session, req.user_id, request_id, "release", -reserved,
                  f"release:{request_id}", req.service_namespace)
    req.status = "released"
    req.finished_at = _utcnow()
    session.commit()
    return {"released": True, "reason": "ok"}


def settle_credits(session, request_id: str, actual_amount: int,
                   provider: str = None, model: str = None,
                   input_tokens: int = None, output_tokens: int = None,
                   provider_cost: float = None, currency: str = "CNY",
                   pricing_version: str = None) -> dict:
    """Settle a reservation with the actual amount. Releases the difference if actual < reserved.

    Overage (actual > reserved) is NOT silently allowed — returns overage_not_permitted.
    """
    req = session.query(AIRequest).filter(AIRequest.request_id == request_id).first()
    if req is None:
        return {"settled": False, "reason": "unknown_request"}
    if req.status in _TERMINAL_STATUSES:
        return {"settled": req.status == "settled",
                "reason": "already_settled" if req.status == "settled" else "already_released"}

    reserved = req.reserved_credits or 0
    if actual_amount > reserved:
        return {"settled": False, "reason": "overage_not_permitted",
                "reserved": reserved, "actual": actual_amount}

    # settle reserved amount, release the unused difference
    settle_amount = actual_amount
    diff = reserved - actual_amount
    for period_type in ("daily", "weekly"):
        b = (session.query(UsageBudget)
             .filter(UsageBudget.user_id == req.user_id, UsageBudget.period_type == period_type)
             .first())
        if b is not None:
            session.execute(
                update(UsageBudget).where(UsageBudget.id == b.id)
                .values(reserved_amount=UsageBudget.reserved_amount - reserved,
                        settled_amount=UsageBudget.settled_amount + settle_amount,
                        updated_at=_utcnow())
            )

    _ledger_entry(session, req.user_id, request_id, "settle", settle_amount,
                  f"settle:{request_id}", req.service_namespace)
    if diff > 0:
        _ledger_entry(session, req.user_id, request_id, "release", -diff,
                      f"release:{request_id}:settle", req.service_namespace)

    if provider is not None or model is not None:
        session.add(AICostRecord(request_id=request_id, provider=provider or "unknown",
                                 model=model or "unknown", input_tokens=input_tokens,
                                 output_tokens=output_tokens, provider_cost=provider_cost,
                                 currency=currency, normalized_credits=settle_amount,
                                 pricing_version=pricing_version, created_at=_utcnow()))

    req.status = "settled"
    req.actual_credits = settle_amount
    req.provider = provider
    req.model = model
    req.finished_at = _utcnow()
    session.commit()
    return {"settled": True, "reason": "ok", "settled_credits": settle_amount,
            "released_credits": diff}


def mark_reconciliation_pending(session, request_id: str,
                                error_category: str = "cost_reconciliation_pending") -> dict:
    """Mark a request whose provider may have billed usage but whose usage/cost is
    unavailable. Does NOT settle zero and does NOT full-release (conservation-safe).

    ``error_category`` distinguishes the cause so anomalies stay measurable — e.g.
    ``reservation_overage`` when real cost exceeded the conservative reservation.

    A later reconcile_credits (or a confirmed-zero release) resolves the reservation.
    """
    req = session.query(AIRequest).filter(AIRequest.request_id == request_id).first()
    if req is None:
        return {"ok": False, "reason": "unknown_request"}
    if req.status in _TERMINAL_STATUSES:
        return {"ok": False, "reason": "already_terminal"}
    req.status = "reconciliation_pending"
    req.error_category = req.error_category or error_category
    req.finished_at = _utcnow()
    session.commit()
    return {"ok": True, "reason": "reconciliation_pending"}


def reconcile_credits(session, request_id: str, actual_amount: int,
                      provider: str = None, model: str = None,
                      input_tokens: int = None, output_tokens: int = None,
                      provider_cost: float = None, currency: str = "CNY",
                      pricing_version: str = None) -> dict:
    """Resolve a reconciliation_pending request once actual usage/cost is known.

    Mirrors settle_credits (settle actual, release difference) but is allowed from
    the reconciliation_pending state. Idempotent and terminal-safe.
    """
    req = session.query(AIRequest).filter(AIRequest.request_id == request_id).first()
    if req is None:
        return {"settled": False, "reason": "unknown_request"}
    if req.status in _TERMINAL_STATUSES:
        return {"settled": req.status == "settled",
                "reason": "already_settled" if req.status == "settled" else "already_released"}

    reserved = req.reserved_credits or 0
    if actual_amount > reserved:
        return {"settled": False, "reason": "overage_not_permitted",
                "reserved": reserved, "actual": actual_amount}

    settle_amount = actual_amount
    diff = reserved - actual_amount
    for period_type in ("daily", "weekly"):
        b = (session.query(UsageBudget)
             .filter(UsageBudget.user_id == req.user_id, UsageBudget.period_type == period_type)
             .first())
        if b is not None:
            session.execute(
                update(UsageBudget).where(UsageBudget.id == b.id)
                .values(reserved_amount=UsageBudget.reserved_amount - reserved,
                        settled_amount=UsageBudget.settled_amount + settle_amount,
                        updated_at=_utcnow())
            )

    _ledger_entry(session, req.user_id, request_id, "settle", settle_amount,
                  f"settle:{request_id}", req.service_namespace)
    if diff > 0:
        _ledger_entry(session, req.user_id, request_id, "release", -diff,
                      f"release:{request_id}:settle", req.service_namespace)

    if provider is not None or model is not None:
        session.add(AICostRecord(request_id=request_id, provider=provider or "unknown",
                                 model=model or "unknown", input_tokens=input_tokens,
                                 output_tokens=output_tokens, provider_cost=provider_cost,
                                 currency=currency, normalized_credits=settle_amount,
                                 pricing_version=pricing_version, created_at=_utcnow()))

    req.status = "settled"
    req.actual_credits = settle_amount
    req.provider = provider
    req.model = model
    req.finished_at = _utcnow()
    session.commit()
    return {"settled": True, "reason": "ok", "settled_credits": settle_amount,
            "released_credits": diff}


# ---- Cost Engine (MVP placeholder; real provider pricing in STEP 7C) ----

def normalize_credits(provider_cost: float, currency: str = "CNY") -> int:
    """Map provider currency cost → normalized credits. 1 credit ≈ ¥0.01."""
    if provider_cost is None:
        return 0
    if (currency or "CNY").upper() != "CNY":
        return int(round(provider_cost * 100))  # conservative 1:1 proxy for non-CNY
    return int(round(provider_cost / CREDIT_UNIT_CNY))


def estimate_credits(input_tokens: int = 0, output_tokens: int = 0) -> int:
    """Deterministic MVP estimate: ~1 credit per 1000 tokens (min 1)."""
    return max(1, int(round((input_tokens + output_tokens) / 1000.0)))


# ---- Subscription activation + plan catalog ----

PLAN_DEFINITIONS = {
    "free": {
        "label": "Free",
        "daily_budget": DAILY_BUDGET["free"],
        "weekly_budget": WEEKLY_BUDGET["free"],
        "capabilities": sorted(CAPABILITY_TIER_POLICY["free"]),
    },
    "standard": {
        "label": "Standard",
        "daily_budget": DAILY_BUDGET["standard"],
        "weekly_budget": WEEKLY_BUDGET["standard"],
        "capabilities": sorted(CAPABILITY_TIER_POLICY["standard"]),
    },
    "advanced": {
        "label": "Advanced",
        "daily_budget": DAILY_BUDGET["advanced"],
        "weekly_budget": WEEKLY_BUDGET["advanced"],
        "capabilities": sorted(CAPABILITY_TIER_POLICY["advanced"]),
    },
}


def activate_subscription(session, user_id: int, tier: str, duration_days: int | None,
                          source: str = "manual", commit: bool = True) -> Subscription:
    """Activate a unified subscription (one effective tier per user).

    Deactivates any existing active subscription, then creates a new active one.
    ``commit=False`` flushes only so callers can embed activation inside a larger
    transaction (e.g. payment verification) and commit once.
    """
    tier = normalize_tier(tier)
    now = _utcnow()
    session.query(Subscription).filter(
        Subscription.user_id == user_id, Subscription.status == "active"
    ).update({"status": "cancelled", "updated_at": now})
    end_at = now + timedelta(days=duration_days) if duration_days else None
    sub = Subscription(user_id=user_id, tier=tier, status="active",
                       start_at=now, end_at=end_at, source=source,
                       created_at=now, updated_at=now)
    session.add(sub)
    if commit:
        session.commit()
    else:
        session.flush()
    return sub


def create_pending_order(session, user_id: int, tier: str,
                         duration_days: int | None) -> MembershipOrder:
    """Create a PENDING unified subscription order. DOES NOT activate the subscription.

    Order creation ≠ payment success. Activation happens only after a verified
    payment callback (apply_verified_payment). Reuses membership_orders for the
    payment audit trail (no second order table).
    """
    tier = normalize_tier(tier)
    if tier == "free":
        raise ValueError("free tier has no paid order")
    pricing = UNIFIED_PLAN_PRICING.get(tier)
    if pricing is None:
        raise ValueError(f"no unified pricing for tier {tier}")
    days = int(duration_days or pricing["default_duration_days"])
    now = datetime.now(timezone.utc)
    order = MembershipOrder(
        order_no=f"U{now.strftime('%Y%m%d%H%M%S')}{secrets.token_hex(5).upper()}",
        user_id=user_id,
        service_key=UNIFIED_SERVICE_KEY,
        target_plan=tier,
        amount=int(pricing["price_cents"]),
        currency="CNY",
        list_price=int(pricing["price_cents"]),
        pricing_version="unified_v1",
        quota_snapshot_json=json.dumps({"unified_tier": tier, "duration_days": days},
                                       ensure_ascii=False, sort_keys=True),
        payment_provider="mock",
        status="pending",
        order_expires_at=now + timedelta(minutes=30),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def usage_summary(session, user_id: int) -> dict:
    """Current remaining / reserved / settled credits for daily + weekly periods.

    ACCEL_PRODUCT_S9: every period reports the SAME four keys. A tier with no cap used to
    omit ``reserved`` / ``settled``, so one endpoint returned two differently-shaped objects
    depending on a value — a consumer had to branch on the shape before it could read a
    number. The uncapped case now reports ``null`` for all four, which is the same statement
    (there is no period budget) in one shape.
    """
    tier = effective_subscription(session, user_id)
    summary = {"tier": tier, "periods": {}}
    for period_type in ("daily", "weekly"):
        amount = budget_amount_for(tier, period_type)
        if amount is None:
            summary["periods"][period_type] = {
                "budget": None, "reserved": None, "settled": None, "remaining": None}
            continue
        budget = get_or_create_budget(session, user_id, period_type)
        remaining = max(0, budget.budget_amount - budget.reserved_amount - budget.settled_amount)
        summary["periods"][period_type] = {
            "budget": budget.budget_amount,
            "reserved": budget.reserved_amount,
            "settled": budget.settled_amount,
            "remaining": remaining,
        }
    return summary
