"""Course Learning Space — the first space fully assembled on the Shared Learning Core.

    Course Space → LearningContext(course_learning) → Shared Practice / Wrong Answers /
    Records / Materials / AI Gateway → deterministic course & knowledge state

The space owns COURSE identity and course-specific reads. Everything shared is
delegated: practice to ``learning.practice``, wrong answers to ``learning.wrong_answers``,
records to ``learning.records``, AI to ``ai.orchestrator``.
"""
from . import context, knowledge, service, wrong_answers  # noqa: F401

__all__ = ["context", "knowledge", "service", "wrong_answers"]
