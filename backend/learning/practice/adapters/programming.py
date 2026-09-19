"""programming adapter — mirrors a real exercise submission into the Practice Core.

WHICH SOURCE, AND WHY NOT THE OBVIOUS ONE
-----------------------------------------
``code_challenge_attempts.status`` looks like an attempt verdict, but it is derived by
keyword-matching the AI's prose reply (``failed`` / ``partial`` / ``probable_pass`` /
``unknown``). It is not an execution result, so it must never become ``correct``.
``code_challenge_attempts`` is therefore INELIGIBLE as a correctness source.

The real judge result lives on the exercise submit path:
``programming_exercise_progress`` (durable per user+exercise, with
``last_submit_passed`` / ``last_public_passed_count`` / ``last_public_total_count``)
and ``programming_exercise_submissions`` (a durable first-pass fact). Both are written
only after the sandbox actually ran the tests, so ``passed`` here is a real verdict.

The exercise itself is the natural practice container, so a legacy-compat session is
created per (user, exercise). Individual submissions are distinguished by the submit
timestamp captured in the request — not by re-reading the aggregate row, which the
next submit would have overwritten.
"""
from __future__ import annotations

import logging
from datetime import datetime

from core.learning_context import LearningContext, ServiceNamespace

from .. import service
from ..refs import QuestionRef, QuestionSourceType
from .base import MirrorOutcome, safe_mirror

logger = logging.getLogger("learning.practice")

SOURCE_ATTEMPT_TYPE = "programming_exercise_progress"

# Not a correctness source — kept as a named constant so the exclusion is greppable
# and cannot be quietly reversed later.
LLM_DERIVED_STATUS_SOURCE = "code_challenge_attempt"


def mirror_programming_submission(db, user, exercise, progress_id, judge_result: dict,
                                  *, submitted_at: datetime | None = None,
                                  language: str | None = None) -> MirrorOutcome:
    """Mirror one real submit. ``judge_result`` must come from execution, not from AI text.

    ``progress_id`` is passed as a plain value so the mirror never depends on the
    caller's ORM instance still being attached to a live session.
    """

    def _run() -> MirrorOutcome:
        if progress_id is None:
            return MirrorOutcome(reason="no_progress_row")
        if submitted_at is None:
            # Without a real submission timestamp there is no stable identity for this
            # attempt, and fabricating one would break idempotency.
            return MirrorOutcome(reason="no_submission_timestamp")

        passed = judge_result.get("passed")
        correct = None if passed is None else bool(passed)
        passed_count = judge_result.get("passed_count")
        total_count = judge_result.get("total_count")

        ns = ServiceNamespace.PROGRAMMING
        lang = language or getattr(exercise, "language", None)
        context = LearningContext(user_id=user.id, service_namespace=ns,
                                  programming_language=lang, exercise_id=exercise.id)
        session, session_created = service.ensure_legacy_session(
            db, user, ns, source_type="programming_exercise",
            source_session_key=exercise.id, mode="exercise",
            context=context, started_at=None)

        ref = QuestionRef(
            source_type=QuestionSourceType.PROGRAMMING_EXERCISE,
            source_id=str(exercise.id), service_namespace=ns,
            context={"exercise_id": exercise.id, "language": lang},
            raw_source={"table": "programming_exercises", "exercise_id": exercise.id,
                        "progress_id": progress_id},
        )
        res = service.record_attempt(
            db, user, session, ref,
            answer=None,                     # the submission source holds no durable code
            correct=correct,
            score=float(passed_count) if passed_count is not None else None,
            max_score=float(total_count) if total_count is not None else None,
            result={"passed": passed, "passed_count": passed_count,
                    "total_count": total_count, "source": "execution"},
            submitted_at=submitted_at,
            source=service.SourceIdentity(SOURCE_ATTEMPT_TYPE, str(progress_id),
                                          submitted_at.isoformat()),
            context=context,
            _session_created=session_created,
        )
        return MirrorOutcome(mirrored=1 if res.created else 0,
                             deduped=0 if res.created else 1)

    return safe_mirror("programming.exercise_submission", SOURCE_ATTEMPT_TYPE,
                       getattr(exercise, "id", None), _run, db=db)
