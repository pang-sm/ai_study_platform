"""Unified Subscription + Usage API (STEP 7B final reconciliation).

New canonical endpoints (SSOT STEP 5 frozen target):
  GET  /subscription
  GET  /subscription/plans
  POST /subscription/orders            —— create PENDING order (does NOT activate)
  POST /subscription/orders/{id}/pay   —— local/test mock payment → verified activation
  POST /subscription/redeem            —— real redemption code → unified activation
  POST /subscription/redeem/preview    —— real redemption code preview
  GET  /usage/summary

Legacy membership/quota APIs remain DEPRECATE (compatibility), not deleted here.

Security invariants:
  * creating an order is NOT subscription activation (order → payment → activation)
  * redemption resolves the REAL redemption_codes table (no demo codes in production)
  * mock payment is explicit test-only and gated off in production mode
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import membership
import models
from database import get_db
from payments.registry import is_mock_payment_allowed
from payments.service import apply_verified_payment
from usage import service
from usage.capabilities import POLICY_VERSION

router = APIRouter()

# Legacy plan → unified tier mapping. Explicit entries cover the legacy redemption
# defaults; otherwise the rank in SERVICE_PLAN_CATALOG decides (rank 1-2 → standard,
# rank 3+ → advanced). Pure CONFIG, no table.
_EXPLICIT_PLAN_TIER = {"free": "free", "gift_pro": "advanced", "developer": "advanced"}


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid circular import
    return get_current_user(request, db)


def _unified_tier_from_plan(service_key: str, target_plan: str) -> str:
    plan = (target_plan or "").strip().lower()
    if plan in _EXPLICIT_PLAN_TIER:
        return _EXPLICIT_PLAN_TIER[plan]
    try:
        definition = membership.get_service_plan(service_key, plan)
    except ValueError:
        definition = None
    rank = int((definition or {}).get("rank", 0))
    if rank >= 3:
        return "advanced"
    if rank >= 1:
        return "standard"
    return "free"


def _activate_unified_from_payload(db: Session, user: models.User, payload: dict) -> dict:
    """Redemption activation hook: map legacy plan → unified tier and activate."""
    tier = _unified_tier_from_plan(payload["service_key"], payload["target_plan"])
    sub = service.activate_subscription(db, user.id, tier,
                                        payload["membership_duration_days"],
                                        source="redemption", commit=False)
    return {"tier": sub.tier, "status": sub.status, "end_at": str(sub.end_at),
            "source": sub.source, "duration_days": payload["membership_duration_days"]}


def _serialize_pending_order(order: models.MembershipOrder) -> dict:
    return {
        "id": order.id,
        "order_no": order.order_no,
        "tier": order.target_plan,
        "status": order.status,
        "amount_cents": order.amount,
        "currency": order.currency,
        "payment_provider": order.payment_provider,
        "created_at": str(order.created_at) if order.created_at else None,
        "order_expires_at": str(order.order_expires_at) if order.order_expires_at else None,
    }


class SubscriptionOrderIn(BaseModel):
    tier: str
    duration_days: int | None = None


class RedeemIn(BaseModel):
    code: str


@router.get("/subscription")
def get_subscription(db: Session = Depends(get_db), current_user=Depends(_require_user)):
    tier = service.effective_subscription(db, current_user.id)
    return {"tier": tier, "policy_version": POLICY_VERSION}


@router.get("/subscription/plans")
def get_subscription_plans():
    return {"policy_version": POLICY_VERSION, "plans": service.PLAN_DEFINITIONS}


@router.post("/subscription/orders")
def create_subscription_order(body: SubscriptionOrderIn,
                              db: Session = Depends(get_db),
                              current_user=Depends(_require_user)):
    """Create a PENDING order. Subscription is NOT activated here."""
    tier = service.normalize_tier(body.tier)
    if tier == "free":
        raise HTTPException(status_code=400, detail="free tier has no paid order")
    try:
        order = service.create_pending_order(db, current_user.id, tier, body.duration_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"order": _serialize_pending_order(order), "activated": False}


@router.post("/subscription/orders/{order_id}/pay")
def pay_subscription_order(order_id: int, db: Session = Depends(get_db),
                           current_user=Depends(_require_user)):
    """Local/test mock payment. Verified success activates the unified subscription.

    Explicit test-only: mock payment is not available in production mode.
    """
    order = db.query(models.MembershipOrder).filter(
        models.MembershipOrder.id == order_id,
        models.MembershipOrder.user_id == current_user.id,
        models.MembershipOrder.service_key == service.UNIFIED_SERVICE_KEY,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "paid":
        return {"order": _serialize_pending_order(order), "idempotent": True,
                "subscription": {"tier": service.effective_subscription(db, current_user.id)}}
    if order.status != "pending":
        raise HTTPException(status_code=409, detail="订单当前不可支付")
    if order.payment_provider != "mock" or not is_mock_payment_allowed():
        raise HTTPException(status_code=403, detail="模拟支付仅可用于本地开发或自动化测试")
    from payments.registry import get_payment_provider
    provider = get_payment_provider()
    payment_event = provider.verify_callback(
        {"order_no": order.order_no, "amount": order.amount, "currency": order.currency})
    try:
        order, idempotent = apply_verified_payment(db, payment_event)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.refresh(order)
    return {"order": _serialize_pending_order(order), "idempotent": idempotent,
            "subscription": {"tier": service.effective_subscription(db, current_user.id)}}


@router.post("/subscription/redeem/preview")
def preview_redeem(body: RedeemIn, db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    """Preview a REAL redemption code, mapped to a unified tier."""
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="请输入兑换码")
    result = membership.preview_redemption_code(current_user, code, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    preview = result["preview"]
    tier = _unified_tier_from_plan(preview["service_key"], preview["target_plan"])
    return {"tier": tier, "duration_days": preview["membership_duration_days"],
            "target_plan": preview["target_plan"],
            "service_key": preview["service_key"]}


@router.post("/subscription/redeem")
def redeem(body: RedeemIn, db: Session = Depends(get_db),
           current_user=Depends(_require_user)):
    """Redeem a REAL redemption code (atomic consume) → activate unified subscription."""
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="请输入兑换码")
    result = membership.redeem_unified_code(current_user, code, db,
                                            activate_hook=_activate_unified_from_payload)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return {"tier": result.get("tier"), "status": result.get("status"),
            "end_at": result.get("end_at"), "source": result.get("source"),
            "duration_days": result.get("duration_days")}


@router.get("/usage/summary")
def get_usage_summary(db: Session = Depends(get_db), current_user=Depends(_require_user)):
    return service.usage_summary(db, current_user.id)
