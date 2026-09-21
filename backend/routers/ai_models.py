"""User-facing model options (STEP 7C frozen target): GET /ai/models?capability=...

Returns ONLY ``auto`` + a small qualified set for the current user's tier + capability.
Never exposes the full provider registry, scientific runtime components, or disabled
models.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ai import pool
from database import get_db
from usage import service
from usage.capabilities import check_capability_permission

router = APIRouter()


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid circular import
    return get_current_user(request, db)


@router.get("/ai/models")
def list_ai_models(capability: str = "", db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    capability = (capability or "").strip().lower()
    if capability not in pool.ALL_CAPABILITIES:
        raise HTTPException(status_code=400, detail="unknown capability")
    tier = service.effective_subscription(db, current_user.id)
    # Entitlement gate: never expose model options for a capability the tier cannot use.
    # P6: an ops feature flag that GRANTED the capability also opens its menu — otherwise the
    # feature would be usable but unlistable, and the client would have nothing to show.
    from ops import feature_flags
    perm = feature_flags.capability_permitted(db, current_user.id, tier, capability)
    if not perm["allowed"]:
        raise HTTPException(status_code=403, detail="capability not permitted for tier")
    menu_tier = tier
    if perm.get("entitlement_grant"):
        menu_tier = feature_flags.minimum_tier_for(capability) or tier
    options = pool.user_visible_options(menu_tier, capability)
    return {
        "capability": capability,
        "tier": tier,
        "default": "auto",
        "policy_version": pool.POOL_VERSION,
        "options": options,
    }
