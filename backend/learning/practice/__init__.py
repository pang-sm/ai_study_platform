"""Unified Practice Core (STEP 7D).

One spine across the three learning spaces:

    PracticeSession → QuestionRef → PracticeAttempt → Result → (Explanation) → LearningEvent

What is unified: session identity, attempt identity, user/context isolation, question
reference, the result envelope, history, and the learning-event bridge.

What is deliberately NOT unified: domain semantics. An objective question carries a
boolean ``correct``; a programming submission carries the judge's real pass/fail and
score; anything genuinely undecidable stays ``correct = None``. No domain is forced
into another's shape, and nothing is inferred that the source did not state.
"""
from . import models, refs, service  # noqa: F401

__all__ = ["models", "refs", "service"]
