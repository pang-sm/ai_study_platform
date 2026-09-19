"""exam_prep adapters — chapter practice and past-paper attempts.

Both legacy rows are per-SESSION summaries whose per-question detail lives in
``result_json.results``. They carry genuinely different semantics and both are
preserved:

  * chapter practice grades choice questions (``correct`` bool) and leaves big
    questions ungraded — ``correct`` stays ``None``, the ``judge`` marker is kept;
  * past papers carry per-question ``score`` / ``full_score`` plus a real
    ``attempt_no``, so multiple sittings of the same paper stay distinguishable.

Neither source emits a Data Plane event today, so the Practice Core is the event
owner for these attempts — under its own event types, never ``course_practice``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from core.learning_context import ServiceNamespace

from ...spaces.exam_prep.context import cs408_context

from .. import service
from ..refs import QuestionRef, QuestionSourceType
from .base import MirrorOutcome, safe_mirror

logger = logging.getLogger("learning.practice")

CHAPTER_SOURCE_TYPE = "exam_practice_attempt"
PAST_PAPER_SOURCE_TYPE = "past_paper_attempt"


def _json_dict(raw) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _json_list(raw) -> list:
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def _ordered_items(question_ids: list, results: list) -> list[tuple[int, str, dict]]:
    """Pair each question id with its result entry, keeping a stable index.

    The index is taken over the question list so keys stay deterministic; a result
    entry without a matching id is only used positionally when the counts agree.
    """
    by_qid = {str(r.get("question_id")): r
              for r in results if isinstance(r, dict) and r.get("question_id") is not None}
    out = []
    for idx, qid in enumerate(question_ids):
        qid_str = str(qid)
        item = by_qid.get(qid_str)
        if item is None and len(results) == len(question_ids) and idx < len(results):
            item = results[idx]
        out.append((idx, qid_str, item or {}))
    return out


def _ungraded_to_none(value, answer=None):
    """Legacy correctness is bool or absent. Never coerce absent/'' to False.

    A QUESTION WITH NO SUBMITTED ANSWER HAS NO FACTUAL VERDICT. The legacy graders compare
    the empty string against the reference answer, so an unanswered question was written
    with ``correct=False`` — which the canonical wrong-answer state reads as a factual
    failure and keeps in the wrong book forever. The frozen product semantic is
    ``UNANSWERED != INCORRECT``, so the blank is downgraded to the tri-state ``None`` here,
    at the point where the legacy row becomes a canonical fact. This is the write boundary,
    not a read filter: no downstream reader has to know the legacy grader was wrong.
    """
    if not str(answer if answer is not None else "").strip():
        return None
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return bool(value)


def _unanswered_score_to_none(value, answer):
    """A blank submission has no authoritative score.

    The legacy past-paper writer records ``score: 0`` for an item the learner never
    answered. That is not a real zero — nothing was graded — so it crosses the canonical
    boundary as ``None``. A genuinely graded zero (an answer that IS present and scored 0)
    passes through untouched.
    """
    if not str(answer if answer is not None else "").strip():
        return None
    return value


def mirror_exam_practice_attempt(db, user, attempt,
                                 *, submitted_at: datetime | None = None) -> MirrorOutcome:
    """Mirror one submitted chapter-practice row (question bank questions)."""

    def _run() -> MirrorOutcome:
        if (attempt.status or "") != "submitted":
            return MirrorOutcome(reason="not_submitted")
        result = _json_dict(attempt.result_json)
        results = result.get("results") if isinstance(result.get("results"), list) else []
        question_ids = _json_list(attempt.question_ids_json)
        items = _ordered_items(question_ids, results)
        if not items:
            return MirrorOutcome(reason="no_item_detail")

        ns = ServiceNamespace.EXAM_PREP
        # CS408 adapter: the legacy subject_key IS the module; track and subject are implied
        # by the only exam with real data. Nothing here invents a second context type.
        context = cs408_context(
            user, module_key=attempt.subject_key,
            knowledge_point_id=attempt.knowledge_point_id)
        session, session_created = service.ensure_legacy_session(
            db, user, ns, source_type=CHAPTER_SOURCE_TYPE,
            source_session_key=attempt.id, mode=attempt.practice_type,
            context=context, started_at=attempt.started_at)

        outcome = MirrorOutcome()
        for idx, qid_str, item in items:
            ref = QuestionRef(
                source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                source_id=qid_str, service_namespace=ns,
                context={"subject_key": attempt.subject_key,
                         "exam_subject_id": context.exam_subject_id,
                         "exam_module_id": context.exam_module_id,
                         "knowledge_point_id": attempt.knowledge_point_id},
                raw_source={"table": "exam_question_bank",
                            "exam_practice_attempt_id": attempt.id,
                            "practice_type": attempt.practice_type},
            )
            res = service.record_attempt(
                db, user, session, ref,
                answer=item.get("user_answer"),
                correct=_ungraded_to_none(item.get("correct"), item.get("user_answer")),
                score=None, max_score=None,
                result={"judge": item.get("judge"),
                        "question_type": item.get("question_type"),
                        "standard_answer": item.get("standard_answer")},
                submitted_at=submitted_at or attempt.submitted_at,
                source=service.SourceIdentity(CHAPTER_SOURCE_TYPE, str(attempt.id),
                                              f"{qid_str}:{idx}"),
                context=context,
                _session_created=session_created and idx == 0,
            )
            outcome.mirrored += 1 if res.created else 0
            outcome.deduped += 0 if res.created else 1
        return outcome

    return safe_mirror("exam.chapter_practice", CHAPTER_SOURCE_TYPE, attempt.id, _run, db=db)


def mirror_past_paper_attempt(db, user, attempt,
                              *, submitted_at: datetime | None = None) -> MirrorOutcome:
    """Mirror one submitted past-paper sitting (real per-question scores + attempt_no)."""

    def _run() -> MirrorOutcome:
        if (attempt.status or "") != "submitted":
            return MirrorOutcome(reason="not_submitted")
        result = _json_dict(attempt.result_json)
        results = [r for r in (result.get("results") or []) if isinstance(r, dict)]
        if not results:
            return MirrorOutcome(reason="no_item_detail")

        ns = ServiceNamespace.EXAM_PREP
        context = cs408_context(user, module_key=attempt.subject_key)
        session, session_created = service.ensure_legacy_session(
            db, user, ns, source_type=PAST_PAPER_SOURCE_TYPE,
            source_session_key=attempt.id, mode=attempt.mode,
            context=context, started_at=attempt.started_at)

        outcome = MirrorOutcome()
        for idx, item in enumerate(results):
            qid = item.get("question_id")
            if qid is None:
                outcome.failed += 1
                continue
            qid_str = str(qid)
            ref = QuestionRef(
                source_type=QuestionSourceType.PAST_EXAM,
                source_id=qid_str, service_namespace=ns,
                context={"subject_key": attempt.subject_key,
                         "exam_subject_id": context.exam_subject_id,
                         "exam_module_id": context.exam_module_id,
                         # question_year = the PAPER's year, not the learner's target year
                         "question_year": attempt.year, "year": attempt.year},
                raw_source={"table": "past_paper_attempt", "year": attempt.year,
                            "attempt_no": attempt.attempt_no,
                            "past_paper_attempt_id": attempt.id},
            )
            res = service.record_attempt(
                db, user, session, ref,
                answer=item.get("user_answer"),
                correct=_ungraded_to_none(item.get("correct"), item.get("user_answer")),
                score=_unanswered_score_to_none(item.get("score"), item.get("user_answer")),
                max_score=_unanswered_score_to_none(item.get("full_score"),
                                                    item.get("user_answer")),
                result={"number": item.get("number"), "type": item.get("type"),
                        "feedback": item.get("feedback"),
                        "standard_answer": item.get("standard_answer")},
                submitted_at=submitted_at or attempt.submitted_at,
                attempt_no=attempt.attempt_no,
                source=service.SourceIdentity(PAST_PAPER_SOURCE_TYPE, str(attempt.id),
                                              f"{qid_str}:{idx}"),
                context=context,
                _session_created=session_created and idx == 0,
            )
            outcome.mirrored += 1 if res.created else 0
            outcome.deduped += 0 if res.created else 1
        return outcome

    return safe_mirror("exam.past_paper", PAST_PAPER_SOURCE_TYPE, attempt.id, _run, db=db)
