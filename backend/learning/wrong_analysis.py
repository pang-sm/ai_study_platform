"""Deep Wrong-Cause Analysis — FACT first, AI hypothesis second, and never conflated.

WHAT IS DIFFERENT FROM "AI EXPLAINS THE ANSWER"
-----------------------------------------------
An explanation endpoint takes a question and explains it. This one takes a REAL wrong-answer
state the learner actually owns, resolves its facts through the SAME hardened resolvers the
wrong-answer page uses (owner + course/module + declared table — no second materialization
surface), and asks a model for one bounded, structured reading of WHY the answer went wrong.

THE TWO HALVES ARE LABELLED
---------------------------
    facts      — the question, the learner's own answer, the reference answer, the recorded
                 analysis, the real attempt history and the recorded state. Deterministic.
    analysis   — error_category / reasoning_gap / correct_reasoning / next_action /
                 review_recommendation. An AI hypothesis about a mistake.

The analysis is NEVER written back as a learner fact: it is not mastery, not a measured
weakness, not a diagnosis of ability, and nothing downstream may treat it as one. The response
states both origins explicitly so a client cannot confuse them.

WHAT IT REFUSES
---------------
A state whose question content cannot be resolved (another learner's question, another
module's question, a legacy row that cannot prove its id space) is NOT analysed: there is
nothing to reason about, and analysing an empty stem would produce pure invention. This is also
why the module never builds its own content lookup.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace

logger = logging.getLogger("learning.wrong_analysis")

CAPABILITY = "wrong_answer.analyze"
MAX_ATTEMPTS_IN_CONTEXT = 8
MAX_TEXT_CHARS = 1200

ORIGIN_FACT = "deterministic"
ORIGIN_AI = "ai"

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value

ANALYSIS_FIELDS = ("error_category", "reasoning_gap", "correct_reasoning",
                   "next_action", "review_recommendation")


class WrongAnalysisRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


class WrongAnalysisOutputError(ValueError):
    """The model returned something that is not a usable analysis."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bounded(value, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit]


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


def _resolver(space: str):
    """The ONE resolver that owns this space's wrong-answer content (P1.2 / P1.3)."""
    if space == COURSE:
        from learning.spaces.course_learning import wrong_answers as course_wrong
        return course_wrong
    from learning.spaces.exam_prep import wrong_answers as exam_wrong
    return exam_wrong


def _context_for(user, state, record: dict):
    """The canonical LearningContext of the state's OWN space (never the caller's choice)."""
    if state.service_namespace == COURSE:
        from learning.spaces.course_learning.context import build_course_context
        course_id = record.get("course_id")
        if not course_id:
            raise WrongAnalysisRefusal("context_unavailable", "错题缺少课程上下文")
        return build_course_context(user, course_id=course_id), {"course_id": course_id}
    from learning.spaces.exam_prep.context import cs408_context
    module_key = record.get("module_key") or None
    context = cs408_context(user, module_key=module_key)
    return context, {"exam_subject_id": context.exam_subject_id,
                     "exam_module_id": context.exam_module_id}


def build_facts(db: DbSession, state, record: dict, attempts: list[dict]) -> dict:
    """The FACT half: what was asked, what the learner answered, what happened."""
    context_identity = {}
    if state.service_namespace == COURSE:
        context_identity = {"course_id": record.get("course_id")}
    else:
        context_identity = {"exam_module_id": record.get("module_key") or None}
    return {
        "question": {
            "stem": _bounded(record.get("stem")),
            "question_type": record.get("question_type"),
            "options": record.get("options") or {},
            "reference_answer": _bounded(record.get("reference_answer")),
            "explanation": _bounded(record.get("analysis")),
            "knowledge_point_id": record.get("knowledge_point_id"),
            "knowledge_point_name": record.get("knowledge_point_name"),
        },
        "user_answer": _bounded(record.get("user_answer")),
        "wrong_count": int(record.get("repeat_wrong_count") or 0),
        "state_status": record.get("status"),
        "first_wrong_at": record.get("first_wrong_at"),
        "last_wrong_at": record.get("last_wrong_at"),
        "attempt_history": [
            {"answer": _bounded(item.get("answer"), 200), "correct": item.get("correct"),
             "submitted_at": item.get("submitted_at")}
            for item in attempts[-MAX_ATTEMPTS_IN_CONTEXT:]
        ],
        "context": context_identity,
        "source": {
            "question_source_type": state.question_source_type,
            "question_source_id": state.question_source_id,
        },
    }


def analyze_wrong_answer(db: DbSession, user, *, state) -> dict:
    """ONE structured wrong-cause analysis for a state the caller owns.

    The caller resolves and OWNERSHIP-checks the state; this function resolves its content
    through the space's hardened resolver and refuses when that content is not available.
    """
    resolver = _resolver(state.service_namespace)
    record = resolver.build_record(db, state)
    if not str(record.get("stem") or "").strip():
        raise WrongAnalysisRefusal(
            "question_content_unavailable",
            "题目内容不可用（未通过归属/上下文校验），无法分析错因")
    attempts = resolver.attempt_history(db, state)
    facts = build_facts(db, state, record, attempts)
    context, _identity = _context_for(user, state, record)

    from prompts import build_wrong_analysis_messages
    messages = build_wrong_analysis_messages(facts)

    if context.service_namespace == ServiceNamespace.EXAM_PREP:
        from learning.spaces.exam_prep.ai import execute_exam_ai as execute
    else:
        from learning.spaces.course_learning.ai import execute_course_ai as execute

    result = execute(db, user, CAPABILITY, messages, learning_context=context,
                     max_tokens=700, temperature=0.3)

    parsed = _extract_json_object(result.content or "")
    if parsed is None:
        raise WrongAnalysisOutputError("model returned no JSON object")
    analysis = {field: _bounded(parsed.get(field), 600) for field in ANALYSIS_FIELDS}
    if not any(analysis.values()):
        raise WrongAnalysisOutputError("model returned an empty analysis")

    _emit(user, state=state, context=context, request_id=result.request_id, analysis=analysis)

    usage = result.usage or {}
    return {
        "state_id": state.id,
        "service_namespace": state.service_namespace,
        "capability": CAPABILITY,
        "request_id": result.request_id,
        "facts": facts,
        "fact_origin": ORIGIN_FACT,
        "analysis": analysis,
        "analysis_origin": ORIGIN_AI,
        "analysis_semantics": ("AI 对错因的解释，不是对学习者能力的测量；不写回为学习事实"),
        "usage": {
            "estimated_credits": result.estimated_credits,
            "actual_credits": result.actual_credits,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "usage_source": usage.get("usage_source"),
        },
        # HONEST: the analysis text has no owned durable store this round. The FACT that an
        # analysis happened is durable (the canonical event + the AI request row); the text
        # itself lives in this response only.
        "persistence": {
            "stored": False,
            "reason": "no_owned_store_for_ai_analysis_text",
            "durable_facts": ["ai_requests", "learning_events:wrong_analysis_generated"],
        },
        "generated_at": _now().isoformat(),
    }


def _emit(user, *, state, context, request_id: str, analysis: dict) -> None:
    """One canonical fact: an analysis was produced. Failure-isolated."""
    try:
        from learning.records import producers
        producers.emit_wrong_analysis_generated(
            user_id=user.id, state_id=state.id,
            question_source_type=state.question_source_type,
            question_source_id=state.question_source_id, request_id=request_id,
            service_namespace=state.service_namespace, learning_context=context,
            occurred_at=None, source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("wrong_analysis.event_failed error=%s", type(exc).__name__)
