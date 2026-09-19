"""Unified Wrong Answer Core (STEP 7E).

    PracticeAttempt  →  WrongAnswerState

A WrongAnswerState is the CURRENT dynamic error state of one user against one
canonical question. It is not "Question.is_wrong = true", and it is not a copy of the
attempt history: the history stays in ``practice_attempts`` (immutable facts), and this
row only holds where the user currently stands with that question.

The state is a PRODUCT FACT, not a scientific prediction. Nothing here infers a
misconception, a mastery probability, or a learner ability.
"""
from . import models, project, service  # noqa: F401

__all__ = ["models", "project", "service"]
