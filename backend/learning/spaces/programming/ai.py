"""Programming's narrow adapter onto the unified AI execution boundary.

Mirrors ``course_learning.ai`` / ``exam_prep.ai``: the Programming space gets no AI system
of its own, only a typed door onto ``ai.orchestrator``. Its job is to guarantee that a
programming AI request carries a PROGRAMMING ``LearningContext`` — without that the request
would be filed under whatever namespace the caller happened to build.

``request_id`` is accepted because the debug agent runs a BOUNDED SEQUENCE of model calls and
each one must be identifiable on its own (§P3A: one row per step in ``ai_requests``, no
second workflow table). A caller that does not supply one gets the orchestrator's uuid.
"""
from __future__ import annotations

from fastapi import HTTPException

from ai.orchestrator import AIOrchestrator, OrchestratorResult
from core.learning_context import LearningContext, ServiceNamespace


def execute_programming_ai(db, user, capability: str, messages: list[dict], *,
                           learning_context: LearningContext,
                           max_tokens: int | None = None,
                           temperature: float | None = None,
                           request_id: str | None = None,
                           explicit_model: str | None = None,
                           model_preference: str | None = None,
                           thinking: bool | None = None) -> OrchestratorResult:
    """Execute exactly one Programming AI operation with canonical durable ownership."""
    if learning_context.service_namespace != ServiceNamespace.PROGRAMMING:
        raise ValueError("Programming AI requires a programming LearningContext")
    if learning_context.user_id != user.id:
        raise ValueError("Programming AI LearningContext must belong to current user")
    result = AIOrchestrator().execute(
        db, user.id, capability, messages, max_tokens=max_tokens,
        temperature=temperature, request_id=request_id, learning_context=learning_context,
        explicit_model=explicit_model,
        model_preference=model_preference, thinking=thinking)
    if not result.ok:
        raise HTTPException(status_code=denial_status(result.error_category),
                            detail="AI capability unavailable")
    # `ok` is the provider's outcome and `content` is its answer; a `reconciliation_pending` (or
    # `released`) ledger status says how the CALL was billed, not whether it answered. The
    # reservation stays held and reconciliation still has to happen, but the learner is not made
    # to lose an answer that was produced. Only a call with nothing to show is an error.
    if not result.content:
        raise HTTPException(status_code=502, detail="AI returned no answer")
    return result


def denial_status(error_category: str | None) -> int:
    """Orchestrator refusal → HTTP status (the ONE mapping, shared with the exam adapter).

    An entitlement refusal and a budget refusal are DIFFERENT answers (403 vs 429) and are
    never degraded into a fallback; an unavailable model or a technical stop is a 502 so the
    caller can decide what to do about it.
    """
    if error_category in {"permission_denied", "tier_not_permitted"}:
        return 403
    # SECURITY_S1C: `budget_incompatible` is the category the ROUTER raises when no candidate
    # fits the remaining budget — i.e. the ordinary shape of "you are out of budget", not an
    # edge case. The course and exam adapters both name it here; this one did not, so a spent
    # budget answered 502 ("capability unavailable") instead of 429, which states the opposite
    # of what happened. Same two names as the siblings, no new rule.
    if error_category in {"budget_reserve_failed", "budget_incompatible"}:
        return 429
    return 502


def stream_programming_ai(db, user, capability: str, messages: list[dict], *,
                          learning_context: LearningContext, max_tokens: int | None = None,
                          request_id: str | None = None,
                          explicit_model: str | None = None,
                          model_preference: str | None = None,
                          thinking: bool | None = None):
    """The streaming twin of `execute_programming_ai`: same canonical language context, read live."""
    if learning_context.service_namespace != ServiceNamespace.PROGRAMMING:
        raise ValueError("Programming AI requires a programming LearningContext")
    if learning_context.user_id != user.id:
        raise ValueError("Programming AI LearningContext must belong to current user")
    return AIOrchestrator().stream(
        db, user.id, capability, messages, max_tokens=max_tokens, request_id=request_id,
        learning_context=learning_context, explicit_model=explicit_model,
        model_preference=model_preference, thinking=thinking)
