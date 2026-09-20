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


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid circular import
    return get_current_user(request, db)


def _activate_unified_from_payload(db: Session, user: models.User, payload: dict) -> dict:
    """Redemption activation hook: map the code's stored legacy plan → unified tier.

    The mapping lives in ``membership.tier_from_service_plan`` so that THIS path and the
    legacy ``POST /membership/redeem`` path cannot disagree about what one code grants.
    """
    tier = membership.tier_from_service_plan(payload["service_key"], payload["target_plan"])
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


class SubscriptionStateResponse(BaseModel):
    """The caller's CURRENT unified tier and the policy it was resolved under."""

    tier: str
    policy_version: str


class PlanDefinition(BaseModel):
    """One tier's factual limits. ``daily_budget`` is ``None`` when the tier has no daily
    cap (Advanced); that is a real absence, not a zero."""

    label: str
    daily_budget: int | None
    weekly_budget: int | None
    capabilities: list[str]


class PlanCatalogResponse(BaseModel):
    policy_version: str
    plans: dict[str, PlanDefinition]


class UsagePeriod(BaseModel):
    """One period's credit position. Every key is always present: an uncapped period reports
    ``None`` for all four rather than omitting keys, so a reader never has to branch on the
    shape before reading a number."""

    budget: int | None
    reserved: int | None
    settled: int | None
    remaining: int | None


class UsageSummaryResponse(BaseModel):
    tier: str
    periods: dict[str, UsagePeriod]


class RedeemPreviewResponse(BaseModel):
    """What one redemption code would grant, in unified-tier terms only.

    ``current_tier`` is stated so the learner can see the move before making it, and
    ``projected_expires_at`` is the server's own projection — not a client guess."""

    tier: str
    tier_label: str
    duration_days: int
    current_tier: str
    projected_expires_at: str
    code_expires_at: str | None


class RedeemResultResponse(BaseModel):
    """The consumed code's effect. ``current_tier`` is re-read AFTER activation, so it is the
    tier the caller actually holds now — the same value every capability gate will resolve."""

    tier: str
    tier_label: str
    status: str | None
    end_at: str | None
    duration_days: int | None
    current_tier: str


@router.get("/subscription", response_model=SubscriptionStateResponse)
def get_subscription(db: Session = Depends(get_db), current_user=Depends(_require_user)):
    tier = service.effective_subscription(db, current_user.id)
    return {"tier": tier, "policy_version": POLICY_VERSION}


@router.get("/subscription/plans", response_model=PlanCatalogResponse)
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


@router.post("/subscription/redeem/preview", response_model=RedeemPreviewResponse)
def preview_redeem(body: RedeemIn, db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    """Preview a REAL redemption code: the UNIFIED tier it grants, and for how long.

    No legacy plan code is returned. The code's stored target is an internal alias; showing
    it would put a string on screen that names no product tier the learner can act on.
    """
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="请输入兑换码")
    result = membership.preview_redemption_code(current_user, code, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    preview = result["preview"]
    tier = membership.tier_from_service_plan(preview["service_key"], preview["target_plan"])
    return {
        "tier": tier,
        "tier_label": service.PLAN_DEFINITIONS[tier]["label"],
        "duration_days": preview["membership_duration_days"],
        "current_tier": service.effective_subscription(db, current_user.id),
        "projected_expires_at": preview["projected_expires_at"],
        "code_expires_at": preview.get("code_expires_at"),
    }


@router.post("/subscription/redeem", response_model=RedeemResultResponse)
def redeem(body: RedeemIn, db: Session = Depends(get_db),
           current_user=Depends(_require_user)):
    """Redeem a REAL redemption code (atomic consume) → activate the unified subscription.

    THIS IS THE ONE USER-FACING REDEEM FLOW. A success here changes the unified tier, and
    because every capability gate resolves from that tier, the features the tier grants are
    open by the time this response is written. There is no second membership to keep in sync.
    """
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="请输入兑换码")
    result = membership.redeem_unified_code(current_user, code, db,
                                            activate_hook=_activate_unified_from_payload)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    tier = service.normalize_tier(result.get("tier"))
    return {"tier": tier, "tier_label": service.PLAN_DEFINITIONS[tier]["label"],
            "status": result.get("status"), "end_at": result.get("end_at"),
            "duration_days": result.get("duration_days"),
            "current_tier": service.effective_subscription(db, current_user.id)}


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def get_usage_summary(db: Session = Depends(get_db), current_user=Depends(_require_user)):
    return service.usage_summary(db, current_user.id)
