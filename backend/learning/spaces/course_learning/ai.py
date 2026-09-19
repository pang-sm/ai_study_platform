"""Course Learning's narrow adapter onto the unified AI execution boundary."""
from __future__ import annotations

from fastapi import HTTPException

from ai.orchestrator import AIOrchestrator, OrchestratorResult
from core.learning_context import LearningContext, ServiceNamespace


def execute_course_ai(db, user, capability: str, messages: list[dict], *,
                      learning_context: LearningContext, max_tokens: int | None = None,
                      temperature: float | None = None) -> OrchestratorResult:
    """Execute exactly one Course AI operation with canonical durable ownership."""
    if learning_context.service_namespace != ServiceNamespace.COURSE_LEARNING:
        raise ValueError("Course AI requires course_learning LearningContext")
    if learning_context.user_id != user.id:
        raise ValueError("Course AI LearningContext must belong to current user")
    result = AIOrchestrator().execute(
        db, user.id, capability, messages, max_tokens=max_tokens,
        temperature=temperature, learning_context=learning_context)
    if not result.ok:
        status = 403 if result.error_category in {"permission_denied", "tier_not_permitted"} else 429
        raise HTTPException(status_code=status, detail="AI capability unavailable")
    if result.status == "reconciliation_pending" or not result.content:
        raise HTTPException(status_code=502, detail="AI usage reconciliation pending")
    return result
