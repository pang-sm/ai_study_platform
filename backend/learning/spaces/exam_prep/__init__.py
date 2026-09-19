"""Exam Prep Space — every national standardized postgraduate exam subject.

    Exam Space → LearningContext(exam_prep) → Shared Practice / Wrong Answers /
    Records / Materials / AI Gateway

The space owns EXAM identity (track / subject / module) and its catalog. Everything
shared is delegated: practice to ``learning.practice``, wrong answers to
``learning.wrong_answers``, records to ``learning.records``, AI to ``ai.orchestrator``.

``exam_11408`` is an INPUT alias of this space, never a canonical value.
"""
from . import ai, catalog, context, scope  # noqa: F401

__all__ = ["ai", "catalog", "context", "scope"]
