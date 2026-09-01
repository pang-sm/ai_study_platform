"""Transactional payment orchestration; provider SDK code stays outside this module."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
import models
from membership import get_service_plan

PENDING, PAID, CANCELLED, EXPIRED = "pending", "paid", "cancelled", "expired"
REFUND_PENDING, PARTIALLY_REFUNDED, REFUNDED = "refund_pending", "partially_refunded", "refunded"


def _utc_now():
    return datetime.now(timezone.utc)


def _as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def _membership(db, user_id, service_key):
    return db.query(models.UserServiceMembership).filter(
        models.UserServiceMembership.user_id == user_id,
        models.UserServiceMembership.service_key == service_key,
    ).first()


def apply_verified_payment(db, event, sync_exam_membership=None):
    """Atomically event -> order -> grant -> revenue. Returns (order, idempotent)."""
    order = db.query(models.MembershipOrder).filter(models.MembershipOrder.order_no == event.order_no).first()
    if not order:
        raise ValueError("Unknown provider order")
    if not event.verified or event.event_type != "PAYMENT_SUCCEEDED":
        raise ValueError("Payment event was not verified")
    if event.amount != order.amount or event.currency != order.currency:
        raise ValueError("Provider amount or currency does not match server order")
    # SQLite has no row locks. This unique insert is the concurrency gate.
    try:
        with db.begin_nested():
            db.add(models.PaymentEvent(provider=event.provider, provider_event_id=event.provider_event_id,
                order_id=order.id, provider_transaction_id=event.provider_transaction_id,
                event_type=event.event_type, amount=event.amount, currency=event.currency,
                verification_result="verified", processing_status="received",
                metadata_json=json.dumps(event.metadata, ensure_ascii=False)))
            db.flush()
    except IntegrityError:
        db.expire_all()
        return db.query(models.MembershipOrder).filter(models.MembershipOrder.id == order.id).one(), True
    if order.status == PAID:
        return order, True
    if order.status != PENDING:
        raise ValueError("Order is not payable")
    now = _utc_now()
    membership = _membership(db, order.user_id, order.service_key)
    old_plan = membership.plan if membership and membership.is_enabled else "free"
    old_expiry = _as_utc(membership.expires_at) if membership else None
    # Upgrade is immediate, no proration; preserve remaining time then add the
    # purchased duration. Same-plan renewals have the exact same extension rule.
    base = max(now, old_expiry) if old_expiry else now
    snapshot = json.loads(order.quota_snapshot_json or "{}")
    duration = int(snapshot.get("duration_days") or (get_service_plan(order.service_key, order.target_plan) or {}).get("duration_days") or 0)
    new_expiry = base + timedelta(days=duration)
    if not membership:
        membership = models.UserServiceMembership(user_id=order.user_id, service_key=order.service_key)
        db.add(membership)
    membership.is_enabled, membership.plan, membership.status = True, order.target_plan, "active"
    membership.activated_at, membership.expires_at, membership.updated_at = now, new_expiry, now
    order.status, order.paid_at, order.paid_amount = PAID, now, event.amount
    order.provider_transaction_id, order.membership_started_at, order.membership_expires_at = event.provider_transaction_id, now, new_expiry
    db.add(models.MembershipGrant(user_id=order.user_id, service_key=order.service_key, order_id=order.id,
        old_plan=old_plan, new_plan=order.target_plan, old_expiry=old_expiry, new_expiry=new_expiry, grant_reason="payment_confirmed"))
    db.add(models.RevenueLedgerEntry(order_id=order.id, user_id=order.user_id, service_key=order.service_key,
        entry_type="PAYMENT", amount=event.amount, currency=order.currency, source=event.provider))
    db.query(models.PaymentEvent).filter(models.PaymentEvent.provider == event.provider,
        models.PaymentEvent.provider_event_id == event.provider_event_id).update({"processing_status": "processed", "processed_at": now})
    db.flush()
    if order.service_key == "exam_11408" and sync_exam_membership:
        sync_exam_membership(db, db.query(models.User).filter(models.User.id == order.user_id).one())
    return order, False


def recompute_membership_after_refund(db, user_id, service_key, sync_exam_membership=None):
    """Rebuild entitlement from non-refunded paid order history; never blanket-free a user."""
    now = _utc_now()
    orders = db.query(models.MembershipOrder).filter(models.MembershipOrder.user_id == user_id,
        models.MembershipOrder.service_key == service_key, models.MembershipOrder.status == PAID).order_by(models.MembershipOrder.paid_at, models.MembershipOrder.id).all()
    membership = _membership(db, user_id, service_key)
    if not membership:
        membership = models.UserServiceMembership(user_id=user_id, service_key=service_key)
        db.add(membership)
    active = [o for o in orders if o.refund_status != REFUNDED]
    if not active:
        membership.is_enabled, membership.plan, membership.status, membership.expires_at = False, "free", "inactive", None
    else:
        # A later successful order is the surviving entitlement. Keep its
        # granted expiry where possible, avoiding retroactive deletion of B.
        latest = active[-1]
        membership.is_enabled, membership.plan, membership.status = True, latest.target_plan, "active"
        membership.expires_at = latest.membership_expires_at or now
        membership.activated_at = latest.membership_started_at or now
    membership.updated_at = now
    db.flush()
    if service_key == "exam_11408" and sync_exam_membership:
        sync_exam_membership(db, db.query(models.User).filter(models.User.id == user_id).one())
    return membership
