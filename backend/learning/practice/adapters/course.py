"""course_learning adapter — mirrors ``ai_question_attempts`` into the Practice Core.

``ai_question_attempts`` is a per-SESSION legacy row (one row per practice set) whose
per-question detail lives inside ``result_json``. This adapter fans it out into one
canonical ``PracticeAttempt`` per question.

Item keys deliberately match the frozen Data Plane identity
(``data_plane.identity.source_item_key(qid, index)`` over ``question_ids_json``), so a
canonical attempt and its learning event describe the same item.

This adapter does NOT emit learning events: the existing
``data_plane.emitter.build_course_practice_events`` path is the authoritative owner for
``course_practice`` events, and two emitters would double-count the learner's history.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from core.learning_context import LearningContext, ServiceNamespace

from .. import service
from ...spaces.exam_prep.catalog import CS408_SUBJECT
from ...spaces.exam_prep.context import cs408_context
from ..refs import QuestionRef, QuestionSourceType
from .base import MirrorOutcome, safe_mirror

logger = logging.getLogger("learning.practice")

SOURCE_ATTEMPT_TYPE = "ai_question_attempt"

# ai_question_attempts.mode → (learning space, legacy question origin)
_MODE_MAP = {
    "course_learning": (ServiceNamespace.COURSE_LEARNING, "questions",
                        QuestionSourceType.MATERIAL_GENERATED),
    "11408": (ServiceNamespace.EXAM_PREP, "ai_generated_questions",
              QuestionSourceType.AI_GENERATED),
}


def _result_items(attempt) -> list[dict]:
    """Normalize the two legacy ``result_json`` shapes into a list of item dicts."""
    try:
        data = json.loads(attempt.result_json or "{}")
    except (TypeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if isinstance(results, list):
        return [r for r in results if isinstance(r, dict)]
    if data.get("question_id") is not None:
        return [data]           # course mode: one question, flat object
    return []


def _answers_map(attempt) -> dict:
    try:
        data = json.loads(attempt.answers_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def build_refs(attempt) -> tuple[ServiceNamespace, list[tuple[int, str, QuestionRef, dict]]]:
    """Return (namespace, [(index, item_key, QuestionRef, item_dict), ...])."""
    mode = (attempt.mode or "").strip()
    ns, origin, source_type = _MODE_MAP.get(mode) or (
        ServiceNamespace.COURSE_LEARNING, "questions", QuestionSourceType.MATERIAL_GENERATED)

    try:
        qids = json.loads(attempt.question_ids_json or "[]")
    except (TypeError, ValueError):
        qids = []
    if not isinstance(qids, list):
        qids = []

    items = _result_items(attempt)
    by_qid = {str(it.get("question_id")): it for it in items if it.get("question_id") is not None}

    out = []
    for idx, qid in enumerate(qids):
        qid_str = str(qid)
        item = by_qid.get(qid_str)
        if item is None and len(items) == len(qids):
            item = items[idx]           # positional fallback when ids are absent
        if item is None:
            # No result detail for this question means the source states no attempt
            # fact. Recording one would invent an answer the learner never gave.
            continue
        if ns == ServiceNamespace.COURSE_LEARNING:
            # course_id is part of the question identity: the SAME question id can be
            # reused by two different courses, and without this the wrong-answer state
            # of course A would collide with course B (§42).
            ref_context = {"course_id": attempt.subject_key,
                           "subject_key": attempt.subject_key,
                           "knowledge_point_id": attempt.knowledge_point_id}
        else:
            # exam_prep: subject_key is the CS408 MODULE (legacy shape) and the canonical
            # exam fields are carried alongside. No course_id — this row is not a course.
            ref_context = {"subject_key": attempt.subject_key,
                           "exam_subject_id": CS408_SUBJECT,
                           "exam_module_id": attempt.subject_key,
                           "knowledge_point_id": attempt.knowledge_point_id}
        ref = QuestionRef(
            source_type=source_type,
            source_id=qid_str,
            service_namespace=ns,
            context=ref_context,
            # provenance is preserved verbatim: the mapping above never destroys it
            raw_source={"table": origin, "mode": mode,
                        "ai_question_attempt_id": attempt.id},
        )
        out.append((idx, f"{qid_str}:{idx}", ref, item))
    return ns, out


def mirror_ai_question_attempt(db, user, attempt,
                               *, submitted_at: datetime | None = None) -> MirrorOutcome:
    """Mirror one submitted ``AIQuestionAttempt`` row. Returns counters."""

    def _run() -> MirrorOutcome:
        if (attempt.status or "") != "submitted":
            return MirrorOutcome(reason="not_submitted")

        ns, refs = build_refs(attempt)
        if not refs:
            return MirrorOutcome(reason="no_item_detail")

        # Shared table, two learning spaces: mode="11408" rows are the EXAM space's and go
        # through the CS408 adapter (module = legacy subject_key); course rows keep the
        # course context.
        if ns == ServiceNamespace.EXAM_PREP:
            context = cs408_context(
                user, module_key=attempt.subject_key,
                knowledge_point_id=attempt.knowledge_point_id)
        else:
            context = LearningContext(user_id=user.id, service_namespace=ns,
                                      subject_key=attempt.subject_key,
                                      knowledge_point_id=attempt.knowledge_point_id)
        session, session_created = service.ensure_legacy_session(
            db, user, ns,
            source_type=SOURCE_ATTEMPT_TYPE,
            source_session_key=attempt.id,
            mode=attempt.mode,
            context=context,
            started_at=attempt.started_at,
        )

        answers = _answers_map(attempt)
        outcome = MirrorOutcome()
        for idx, item_key, ref, item in refs:
            raw_answer = item.get("user_answer")
            if raw_answer in (None, ""):
                raw_answer = answers.get(ref.source_id)
            correct = item.get("correct")
            if correct is not None:
                correct = bool(correct)     # legacy stores real bools; None stays None
            if not str(raw_answer if raw_answer is not None else "").strip():
                # UNANSWERED != INCORRECT — same rule as the exam adapters: a question with no
                # submitted answer has no verdict, whatever the legacy grader concluded from
                # comparing the empty string.
                correct = None
            result = service.record_attempt(
                db, user, session, ref,
                answer=raw_answer,
                correct=correct,
                score=None,
                max_score=None,
                result={"judge": item.get("judge"),
                        "question_type": item.get("question_type"),
                        "generation_mode": item.get("generation_mode")},
                submitted_at=submitted_at or attempt.submitted_at,
                source=service.SourceIdentity(SOURCE_ATTEMPT_TYPE, str(attempt.id), item_key),
                context=context,
                _session_created=session_created and idx == 0,
            )
            if result.created:
                outcome.mirrored += 1
            else:
                outcome.deduped += 1
        return outcome

    return safe_mirror("course.ai_question_attempt", SOURCE_ATTEMPT_TYPE, attempt.id,
                       _run, db=db)


# ---------------------------------------------------------------- ordinary practice
#
# The ``question_attempts`` table is the ordinary course practice flow. TWO endpoints
# write it and each write is a DISTINCT legacy row with its own id:
#
#   POST /practice/questions/{id}/attempts   → a real answer with a server-derived
#                                               judgement (correct / incorrect / unknown)
#   POST /practice/questions/{id}/feedback   → the learner asked for AI feedback on an
#                                               answer; self_result is "unknown", so it
#                                               carries NO factual judgement
#
# They are therefore mirrored 1:1 on the legacy row id — one legacy row, one canonical
# attempt — which is also what the STEP7D backfill does, so live and backfill agree.

QUESTION_ATTEMPT_SOURCE_TYPE = "question_attempt"


def self_result_to_correct(value) -> bool | None:
    """Legacy ``self_result`` → tri-state. An unknown/absent result stays None.

    Shared with the backfill so live and replay can never disagree.
    """
    text = (value or "").strip().lower()
    if text == "correct":
        return True
    if text in ("incorrect", "wrong"):
        return False
    return None


def mirror_question_attempt(db, user, attempt_row, question,
                            *, submitted_at: datetime | None = None) -> MirrorOutcome:
    """Mirror one ``question_attempts`` row (attempts OR feedback endpoint)."""

    def _run() -> MirrorOutcome:
        course_id = (getattr(question, "course_id", None)
                     or getattr(attempt_row, "course_id", None))
        ns = ServiceNamespace.COURSE_LEARNING
        context = LearningContext(
            user_id=user.id, service_namespace=ns, course_id=course_id,
            knowledge_point_id=(str(attempt_row.knowledge_point_id)
                                if attempt_row.knowledge_point_id else None))

        session, session_created = service.ensure_legacy_session(
            db, user, ns, source_type=QUESTION_ATTEMPT_SOURCE_TYPE,
            source_session_key=course_id or "course", mode="course_practice",
            context=context, started_at=None)

        ref = QuestionRef(
            source_type=QuestionSourceType.MATERIAL_GENERATED,
            source_id=str(attempt_row.question_id), service_namespace=ns,
            context={"course_id": course_id,
                     "knowledge_point_id": (str(attempt_row.knowledge_point_id)
                                            if attempt_row.knowledge_point_id else None)},
            raw_source={"table": "questions", "question_attempt_id": attempt_row.id,
                        "course_id": course_id},
        )
        res = service.record_attempt(
            db, user, session, ref,
            answer=attempt_row.user_answer,
            # tri-state, straight from the server-derived legacy result
            correct=self_result_to_correct(attempt_row.self_result),
            score=None, max_score=None,
            result={"self_result": attempt_row.self_result,
                    "feedback_present": bool(attempt_row.ai_feedback)},
            submitted_at=submitted_at or attempt_row.created_at,
            source=service.SourceIdentity(QUESTION_ATTEMPT_SOURCE_TYPE,
                                          str(attempt_row.id), None),
            context=context, _session_created=session_created)
        return MirrorOutcome(mirrored=1 if res.created else 0,
                             deduped=0 if res.created else 1)

    return safe_mirror("course.question_attempt", QUESTION_ATTEMPT_SOURCE_TYPE,
                       attempt_row.id, _run, db=db)


# ---------------------------------------------------------------- batch practice
#
# POST /practice/submit-result reports a COMPLETED practice batch. Its durable write is
# a single summary row (``learning_records`` record_type="practice") — per-question
# detail is never persisted, and each question's ``is_correct`` is CLIENT-ASSERTED.
#
# So the canonical fact here is the SESSION, not a set of attempts: promoting
# client-asserted correctness into immutable canonical attempts would let a client write
# its own learning facts (§25 server-trusted only), and there is nothing durable to
# recover them from anyway. The per-question grain is therefore deliberately NOT
# mirrored; the session-level completion is.

PRACTICE_BATCH_SOURCE_TYPE = "practice_batch_result"


def mirror_practice_batch(db, user, record, *, payload: dict | None = None) -> MirrorOutcome:
    """Mirror one completed practice batch as a canonical PracticeSession."""

    def _run() -> MirrorOutcome:
        # NOTE: not `payload = payload or {}` — that would make `payload` local to this
        # closure and read it before assignment.
        data = payload or {}
        course_id = (record.subject or data.get("course_id") or "").strip() or None
        ns = ServiceNamespace.COURSE_LEARNING
        context = LearningContext(user_id=user.id, service_namespace=ns,
                                  course_id=course_id,
                                  knowledge_point_id=(str(data["knowledge_point_id"])
                                                      if data.get("knowledge_point_id")
                                                      else None))
        session, created = service.ensure_legacy_session(
            db, user, ns, source_type=PRACTICE_BATCH_SOURCE_TYPE,
            source_session_key=str(record.id), mode=data.get("source") or "practice",
            context=context, started_at=None)
        if not created:
            return MirrorOutcome(deduped=1)
        session.completed_at = record.created_at
        from ..models import SESSION_COMPLETED
        session.status = SESSION_COMPLETED
        db.commit()
        return MirrorOutcome(mirrored=1)

    return safe_mirror("course.practice_batch", PRACTICE_BATCH_SOURCE_TYPE,
                       getattr(record, "id", None), _run, db=db)
