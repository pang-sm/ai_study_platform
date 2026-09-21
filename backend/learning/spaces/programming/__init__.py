"""Programming Space — the third Learning Space, on the same Shared Learning Core.

    Programming Space → LearningContext(programming) → Shared Practice / Records /
    Materials / AI Gateway → deterministic programming state

The space owns PROGRAMMING identity (language / exercise / project) and programming-specific
reads. Everything shared is delegated: practice facts to ``learning.practice``, records to
``learning.records``, AI to ``ai.orchestrator``.

There is no programming wrong-answer book and none is invented: a failed submission is a
``code_submitted`` fact with ``correct == False``, and the per-exercise product status is
``programming_exercise_progress``. Building a second error store would duplicate facts the
canonical stream already holds.
"""
from . import context, events, service  # noqa: F401

__all__ = ["context", "events", "service"]
