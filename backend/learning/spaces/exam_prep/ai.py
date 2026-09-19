"""Exam Prep's narrow adapter onto the unified AI execution boundary.

Mirrors ``course_learning.ai``: Exam Prep gets no AI system of its own, only a typed
door onto ``ai.orchestrator``. Its job is to guarantee that an exam AI request carries an
exam ``LearningContext`` — without that, the request would be filed under whatever
namespace the caller happened to build, which is exactly the cross-space pollution
STEP7H1 fixes.
"""
from __future__ import annotations

import json

from fastapi import HTTPException

from ai.orchestrator import AIOrchestrator, OrchestratorResult
from core.learning_context import LearningContext, ServiceNamespace


def execute_exam_ai(db, user, capability: str, messages: list[dict], *,
                    learning_context: LearningContext,
                    max_tokens: int | None = None,
                    temperature: float | None = None) -> OrchestratorResult:
    """Execute exactly one Exam Prep AI operation with canonical durable ownership."""
    if learning_context.service_namespace != ServiceNamespace.EXAM_PREP:
        raise ValueError("Exam AI requires an exam_prep LearningContext")
    if learning_context.user_id != user.id:
        raise ValueError("Exam AI LearningContext must belong to current user")
    result = AIOrchestrator().execute(
        db, user.id, capability, messages, max_tokens=max_tokens,
        temperature=temperature, learning_context=learning_context)
    if not result.ok:
        raise HTTPException(status_code=_denial_status(result.error_category),
                            detail="AI capability unavailable")
    if result.status == "reconciliation_pending" or not result.content:
        raise HTTPException(status_code=502, detail="AI usage reconciliation pending")
    return result


def _denial_status(error_category: str | None) -> int:
    """Orchestrator refusal → HTTP status.

    An entitlement refusal and a budget refusal are DIFFERENT answers (403 vs 429) and are
    never degraded into a fallback; anything else that stopped the call is a technical
    failure and maps to 502 so the caller can apply its own product fallback.
    """
    if error_category in {"permission_denied", "tier_not_permitted"}:
        return 403
    if error_category in {"budget_reserve_failed", "budget_incompatible",
                          "no_qualified_model_available"}:
        return 429 if error_category != "no_qualified_model_available" else 502
    return 502


# ---------------------------------------------------------------- answer.grade

GRADE_MAX_SCORE = 10


class GradeOutputError(ValueError):
    """The model returned something that is not a usable grade."""


def _extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def grade_big_answer(db, user, *, learning_context: LearningContext, stem: str,
                     standard_answer: str, user_answer: str, subject_name: str = "",
                     question_number=None, max_tokens: int = 300) -> tuple[int, str]:
    """Grade one subjective answer through the unified boundary.

    Returns ``(score, feedback)`` with ``0 <= score <= GRADE_MAX_SCORE``. Raises
    ``GradeOutputError`` when the model produced no usable grade — the CALLER decides what
    to do about that, because what a malformed grade means for a learner's submission is a
    domain decision, not this module's.

    The prompt and the parsing live here on purpose: this is the one place an exam answer
    is graded, so the parser module no longer holds a provider client or a model name.
    """
    prompt = f"""你是11408考研阅卷老师。请评分(满分{GRADE_MAX_SCORE}分,按参考答案符合度)。

科目:{subject_name} 题号:第{question_number if question_number is not None else ''}题
题目:{str(stem or '')[:300]}
参考答案:{str(standard_answer or '')[:500]}
用户答案:{str(user_answer or '')[:500]}

严格返回JSON(不要markdown):{{"score":8,"feedback":"评语"}}"""
    result = execute_exam_ai(
        db, user, "answer.grade",
        [{"role": "user", "content": prompt}],
        learning_context=learning_context, temperature=0.3, max_tokens=max_tokens)

    data = _extract_json_object(result.content or "")
    if data is None:
        raise GradeOutputError("model returned no JSON object")
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        raise GradeOutputError("score is not an integer") from None
    if not 0 <= score <= GRADE_MAX_SCORE:
        raise GradeOutputError(f"score {score} out of range")
    feedback = str(data.get("feedback") or "").strip()
    return score, feedback

