"""Course Learning's narrow adapter onto the unified AI execution boundary."""
from __future__ import annotations

from fastapi import HTTPException

from ai.orchestrator import AIOrchestrator, OrchestratorResult
from core.learning_context import LearningContext, ServiceNamespace


def execute_course_ai(db, user, capability: str, messages: list[dict], *,
                      learning_context: LearningContext, max_tokens: int | None = None,
                      temperature: float | None = None,
                      explicit_model: str | None = None,
                      model_preference: str | None = None,
                      thinking: bool | None = None) -> OrchestratorResult:
    """Execute exactly one Course AI operation with canonical durable ownership."""
    if learning_context.service_namespace != ServiceNamespace.COURSE_LEARNING:
        raise ValueError("Course AI requires course_learning LearningContext")
    if learning_context.user_id != user.id:
        raise ValueError("Course AI LearningContext must belong to current user")
    result = AIOrchestrator().execute(
        db, user.id, capability, messages, max_tokens=max_tokens,
        temperature=temperature, learning_context=learning_context,
        explicit_model=explicit_model,
        model_preference=model_preference, thinking=thinking)
    if not result.ok:
        raise HTTPException(status_code=_denial_status(result.error_category),
                            detail="AI capability unavailable")
    # `ok` is the provider's outcome and `content` is its answer. A `reconciliation_pending` (or
    # `released`) ledger status says how the CALL was billed, not whether it answered — the
    # reservation stays held and reconciliation still has to happen, but the learner is not made
    # to lose an answer that was produced. Only a call with nothing to show is an error.
    if not result.content:
        raise HTTPException(status_code=502, detail="AI returned no answer")
    return result


def _denial_status(error_category: str | None) -> int:
    """Orchestrator refusal → HTTP status (the ONE rule, mirroring the exam/programming spaces).

    An entitlement refusal and a budget refusal are DIFFERENT answers (403 vs 429) and are never
    degraded into a fallback; everything else that stopped the call is a technical failure and
    maps to 502. It must NOT be a 429: "the model could not answer" is not "your quota is used
    up", and telling a learner the second when the first happened is a false statement they
    cannot act on.
    """
    if error_category in {"permission_denied", "tier_not_permitted"}:
        return 403
    if error_category in {"budget_reserve_failed", "budget_incompatible"}:
        return 429
    return 502


def stream_course_ai(db, user, capability: str, messages: list[dict], *,
                     learning_context: LearningContext, max_tokens: int | None = None,
                     explicit_model: str | None = None,
                     model_preference: str | None = None,
                     thinking: bool | None = None):
    """The streaming twin of `execute_course_ai`: same context requirements, read live.

    Deliberately NOT a second chat stack: it hands the SAME canonical LearningContext to the
    orchestrator's streaming path, so permission, budget, routing and billing are decided by the
    one implementation both call shapes share. Cancellation and settlement are the stream's own
    concern (see `StreamRun`), not a second policy here.
    """
    if learning_context.service_namespace != ServiceNamespace.COURSE_LEARNING:
        raise ValueError("Course AI requires course_learning LearningContext")
    if learning_context.user_id != user.id:
        raise ValueError("Course AI LearningContext must belong to current user")
    return AIOrchestrator().stream(
        db, user.id, capability, messages, max_tokens=max_tokens,
        learning_context=learning_context, explicit_model=explicit_model,
        model_preference=model_preference, thinking=thinking)
