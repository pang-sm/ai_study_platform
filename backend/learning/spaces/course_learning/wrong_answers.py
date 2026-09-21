"""Course Space canonical wrong-answer projection — the ONE course wrong-answer read shape.

WHY THIS EXISTS
---------------
``wrong_answer_states`` is the canonical store the Practice Core already keeps, and the
course direction has had no read surface over it: the only course-shaped history was the
legacy attempt list (``/course-learning/practice/history``), which carries no state, no
resolution and no attempt facts.

This module reads the CANONICAL state rows and derives ONE normalized record per state,
resolving display data from the same facts the state was built from. It creates no second
wrong-answer table and no second source of truth.

ISOLATION IS THE POINT
----------------------
A course question is identified by ``course:<course_id>`` (see
``learning.wrong_answers.project.course_scope``), because the same question id can be
reused by two different courses of the same learner. Every read here is scoped by user AND
namespace AND that course scope — a course-A page can never contain a course-B state, and
neither exam nor programming states can appear at all.

The legacy wrong-answer tables are read by NOTHING in this module. They are not a fallback,
not a merge input, and not a source of status.

CONTENT IS RESOLVED FAIL-CLOSED
-------------------------------
A state's question content is looked up in exactly ONE table — the one the state's own
declared source type names — and a row is shown only when it is PROVABLY this learner's
question in THIS course. The owner, the course and the table are all checked against stored
identity, and no rule here ever falls back to the other table, searches it in order, or
matches a stem, a title or a position. When the proof fails the record keeps an honest empty
stem instead of a plausible wrong one.

The one exception is a PROVEN legacy row (see ``_content_table``): before P1.2 the course AI
adapter declared ``material_generated`` for questions that live in ``ai_generated_questions``,
and the attempt lineage is what proves which id space a stored row belongs to.

WHAT IT WILL NOT DO
-------------------
It does not derive a knowledge point from a stem, a title or a position, and it does not
invent a question type it cannot read. Content that cannot be resolved stays empty and says
so, rather than being filled with a plausible guess.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session as DbSession

from learning.practice.adapters.course import (
    QUESTION_ATTEMPT_SOURCE_TYPE as QUESTION_ATTEMPT_LINEAGE,
    SOURCE_ATTEMPT_TYPE as AI_QUESTION_LINEAGE,
)
from learning.practice.models import PracticeAttempt
from learning.practice.refs import QuestionSourceType
from learning.wrong_answers.models import WrongAnswerState
from learning.wrong_answers.project import attempts_for_question

from .context import course_identity_forms

logger = logging.getLogger("learning.spaces.course_learning")

# The closed product vocabulary the course wrong-answer workspace renders. Each value maps
# onto a wrong-answer source the course product already has; ``other`` exists so an unmapped
# provenance is stated honestly instead of being filed as one of the known kinds.
SOURCE_KIND_AI = "ai_generated"
SOURCE_KIND_MATERIAL = "course_material"
SOURCE_KIND_OTHER = "other"

SOURCE_KIND_LABELS = {
    SOURCE_KIND_AI: "AI 题册",
    SOURCE_KIND_MATERIAL: "课程题",
    SOURCE_KIND_OTHER: "其他",
}

_SOURCE_KIND_BY_SOURCE_TYPE = {
    QuestionSourceType.AI_GENERATED.value: SOURCE_KIND_AI,
    QuestionSourceType.MATERIAL_GENERATED.value: SOURCE_KIND_MATERIAL,
}


def source_kind_of(question_source_type: str) -> str:
    return _SOURCE_KIND_BY_SOURCE_TYPE.get(question_source_type, SOURCE_KIND_OTHER)


# ---------------------------------------------------------------- helpers


def _attempt_result(attempt: PracticeAttempt) -> dict:
    try:
        parsed = json.loads(attempt.result_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _attempt_ref(attempt: PracticeAttempt) -> dict:
    try:
        parsed = json.loads(attempt.question_ref_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _latest_wrong(attempts: list[PracticeAttempt]) -> PracticeAttempt | None:
    wrongs = [a for a in attempts if a.correct is False]
    return wrongs[-1] if wrongs else None


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_options(raw) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    text = (raw or "").strip() if isinstance(raw, str) else ""
    if not text:
        return {}
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _course_id_of(state: WrongAnswerState) -> str:
    """The course a state belongs to, read back from its own scope discriminator.

    ``project.course_scope`` wrote ``course:<course_id>``; this reads that exact form. A
    state whose scope is empty belongs to no course and yields "" — it is excluded from
    every course-scoped read rather than being attributed to a course by guesswork.
    """
    scope = (state.question_scope_key or "").strip()
    if scope.startswith("course:"):
        return scope.split(":", 1)[1]
    return ""


# ---------------------------------------------------------------- content lookup
#
# The question content a state points at lives in ONE table, named by the state's own
# declared source type. Nothing here searches a second table as a fallback, and nothing
# here returns a row that is not provably this learner's question in this course.

TABLE_AI_GENERATED = "ai_generated_questions"
TABLE_QUESTIONS = "questions"

_CONTENT_TABLE_BY_SOURCE_TYPE = {
    QuestionSourceType.AI_GENERATED.value: TABLE_AI_GENERATED,
    QuestionSourceType.MATERIAL_GENERATED.value: TABLE_QUESTIONS,
}

_SOURCE_KIND_BY_TABLE = {
    TABLE_AI_GENERATED: SOURCE_KIND_AI,
    TABLE_QUESTIONS: SOURCE_KIND_MATERIAL,
}


def _content_table(state: WrongAnswerState, attempts: list[PracticeAttempt]) -> str | None:
    """The ONE table this state's question id belongs to — or None when that is not provable.

    ``ai_generated_questions`` and ``questions`` have independent id spaces, so the table IS
    part of the question's identity and a bare id is not enough to read content.

    For a declared ``AI_generated`` state the table is stated by the declaration itself: only
    the course AI lineage writes it, and its ids are ``ai_generated_questions`` primary keys.

    A declared ``material_generated`` course state is the ambiguous one, and legitimately so:
    until P1.2 the course AI adapter declared exactly this value for questions living in
    ``ai_generated_questions``, so a stored row may be either table's id. Which one it is is
    decided by the attempt LINEAGE — ``source_attempt_type``, a stored fact of the canonical
    attempt — and only when that lineage is UNANIMOUS:

        every attempt "ai_question_attempt"   → ai_generated_questions (proven, legacy)
        every attempt "question_attempt"      → questions (the ordinary practice flow)
        anything else, mixed, or unnamed      → None: the id space cannot be established

    None of these are guesses: each is a stored fact of the attempt the state was built from.
    A state whose lineage cannot establish the table resolves to no content at all rather
    than being tested against both tables until one accepts the id.
    """
    declared = _CONTENT_TABLE_BY_SOURCE_TYPE.get(state.question_source_type)
    if declared is None:
        return None                       # unmapped provenance: no table, no content
    if declared != TABLE_QUESTIONS:
        return declared
    lineages = {(a.source_attempt_type or "").strip() for a in attempts}
    lineages.discard("")
    if lineages == {AI_QUESTION_LINEAGE}:
        return TABLE_AI_GENERATED
    if lineages == {QUESTION_ATTEMPT_LINEAGE}:
        return TABLE_QUESTIONS
    return None


class _CourseQuestionIndex:
    """Batch lookup of the question content a page of course states points at.

    One query per source table for the whole page, and both are scoped to the OWNER: a
    learner's page never even loads another learner's rows. Which of the two a given state
    may actually read is decided per state by :func:`_resolve_content` — this class only
    fetches candidates, it never decides that a candidate may be shown.
    """

    def __init__(self, db: DbSession):
        self._db = db
        self._ai: dict[tuple[str, str], object] = {}
        self._material: dict[tuple[str, str], object] = {}

    def prime(self, states: list[WrongAnswerState]) -> None:
        usernames = {(state.username or "").strip() for state in states}
        usernames.discard("")
        ids = {value for value in (_as_int(s.question_source_id) for s in states)
               if value is not None}
        self._ai = self._load_ai(usernames, ids)
        self._material = self._load_material(usernames, ids)

    def _load_ai(self, usernames: set[str], ids: set[int]) -> dict[tuple[str, str], object]:
        from models import AIGeneratedQuestion
        if not usernames or not ids:
            return {}
        rows = (self._db.query(AIGeneratedQuestion)
                .filter(AIGeneratedQuestion.username.in_(sorted(usernames)),
                        AIGeneratedQuestion.id.in_(sorted(ids))).all())
        return {((r.username or "").strip(), str(r.id)): r for r in rows}

    def _load_material(self, usernames: set[str], ids: set[int]) -> dict[tuple[str, str], object]:
        from models import Question
        if not usernames or not ids:
            return {}
        rows = (self._db.query(Question)
                .filter(Question.username.in_(sorted(usernames)),
                        Question.id.in_(sorted(ids))).all())
        return {((r.username or "").strip(), str(r.id)): r for r in rows}

    def ai(self, username: str, source_id: str):
        return self._ai.get((username, str(source_id)))

    def material(self, username: str, source_id: str):
        return self._material.get((username, str(source_id)))


def _resolve_content(index: _CourseQuestionIndex, state: WrongAnswerState,
                     attempts: list[PracticeAttempt]) -> tuple[str, object] | None:
    """The ONE row this state may show, and its table — or None for no content at all.

    THE GATE. A row is returned only when ALL of these hold against stored identity:

      1. the table is the one the declared source type names (with the proven legacy
         exception in :func:`_content_table`);
      2. the row's owner is the state's own learner;
      3. the row belongs to the state's own course;
      4. the state names an owner and a course at all.

    Anything else returns None. There is deliberately no second attempt against the other
    table: a mismatch between the declared source and the row it points at is a fact about
    the data, not a lookup to retry somewhere else.
    """
    table = _content_table(state, attempts)
    username = (state.username or "").strip()
    course_id = _course_id_of(state)
    if table is None or not username or not course_id:
        return None
    forms = course_identity_forms(course_id)
    if table == TABLE_AI_GENERATED:
        row = index.ai(username, state.question_source_id)
        if row is None or (row.username or "").strip() != username:
            return None
        if str(row.subject_key or "").strip() not in forms:
            return None                   # another course's question is not resolvable here
        return table, row
    row = index.material(username, state.question_source_id)
    if row is None or (row.username or "").strip() != username:
        return None
    if str(row.course_id or "").strip() not in forms:
        return None
    return table, row


def _fill_ai(record: dict, row) -> None:
    record["question_type"] = row.question_type or None
    record["stem"] = row.stem or ""
    record["options"] = _parse_options(row.options_json)
    record["analysis"] = row.analysis or None
    record["question_id"] = _as_int(row.id)
    if not record["reference_answer"]:
        record["reference_answer"] = row.standard_answer or ""
    record["knowledge_point_name"] = row.knowledge_point_name or None
    record["knowledge_point_path"] = row.knowledge_point_path or None
    record["knowledge_point_id"] = record["knowledge_point_id"] or (
        str(row.knowledge_point_id) if row.knowledge_point_id else None)


def _fill_material(record: dict, row) -> None:
    record["question_type"] = row.type or None
    record["stem"] = row.content or row.title or ""
    record["options"] = _parse_options(row.options)
    record["analysis"] = row.explanation or None
    # ``question_id`` is NOT set: the field is the id the course redo contract takes, and
    # that contract resolves ``ai_generated_questions`` (see the response model). Handing it
    # a ``questions`` primary key would be the same unstated-id-space defect this module
    # exists to prevent — a bare id that names a row in a table the caller never asked for.
    if not record["reference_answer"]:
        record["reference_answer"] = row.answer or ""
    if row.knowledge_point_id is not None:
        record["knowledge_point_id"] = record["knowledge_point_id"] or str(row.knowledge_point_id)


# ---------------------------------------------------------------- record


def build_record(db: DbSession, state: WrongAnswerState, *,
                 index: _CourseQuestionIndex | None = None,
                 attempts: list[PracticeAttempt] | None = None) -> dict:
    """ONE normalized course wrong-answer record. Nothing here reaches a legacy wrong table."""
    if attempts is None:
        attempts = attempts_for_question(
            db, user_id=state.user_id, service_namespace=state.service_namespace,
            question_source_type=state.question_source_type,
            question_source_id=state.question_source_id,
            question_scope_key=state.question_scope_key)
    if index is None:
        index = _CourseQuestionIndex(db)
        index.prime([state])

    # The resolved table decides the reported kind too: a legacy row whose lineage proves it
    # is an AI question is REPORTED as one, instead of being labelled from a stored
    # provenance the fix has shown to be wrong.
    resolved = _resolve_content(index, state, attempts)
    source_kind = (_SOURCE_KIND_BY_TABLE[resolved[0]] if resolved is not None
                   else source_kind_of(state.question_source_type))
    latest_wrong = _latest_wrong(attempts)
    snapshot = _attempt_result(latest_wrong) if latest_wrong else {}
    ref_context = (_attempt_ref(latest_wrong).get("context") or {}) if latest_wrong else {}

    record = {
        "wrong_record_id": state.id,
        "status": state.status,
        "service_namespace": state.service_namespace,
        "course_id": _course_id_of(state),
        "source_kind": source_kind,
        "source_label": SOURCE_KIND_LABELS[source_kind],
        "question_type": None,
        "stem": "",
        "options": {},
        # the answer the learner actually gave, from the attempt itself
        "user_answer": (latest_wrong.answer or "") if latest_wrong else "",
        "reference_answer": str(snapshot.get("standard_answer") or ""),
        "analysis": None,
        # the id the course redo contract takes — an AI 题册 question, and nothing else
        "question_id": None,
        "knowledge_point_id": ref_context.get("knowledge_point_id"),
        "knowledge_point_name": None,
        "knowledge_point_path": None,
        "first_wrong_at": _iso(state.first_wrong_at),
        "last_wrong_at": _iso(state.last_wrong_at),
        "resolved_at": _iso(state.resolved_at),
        "repeat_wrong_count": int(state.wrong_count or 0),
    }

    if resolved is not None and resolved[0] == TABLE_AI_GENERATED:
        _fill_ai(record, resolved[1])
    elif resolved is not None:
        _fill_material(record, resolved[1])
    else:
        # No proof, no content: the row is missing, or it is not provably this learner's
        # question in this course, or the id space itself cannot be established. The FACT is
        # not lost — the recorded type and the learner's own answer survive — and the stem
        # stays honestly empty rather than being filled with another course's or another
        # learner's question.
        record["question_type"] = snapshot.get("question_type") or None
    return record


def build_records(db: DbSession, states: list[WrongAnswerState]) -> list[dict]:
    """Normalized records for a page of states, with one batched content lookup."""
    index = _CourseQuestionIndex(db)
    index.prime(states)
    return [build_record(db, state, index=index) for state in states]


def attempt_history(db: DbSession, state: WrongAnswerState) -> list[dict]:
    """The factual attempt history behind one state, oldest first.

    Read from ``practice_attempts`` only. The legacy ``review_count``-style counters are not
    a review history and are not part of this.
    """
    return [
        {
            "attempt_id": attempt.id,
            "submitted_at": _iso(attempt.submitted_at),
            "answer": attempt.answer,
            "correct": attempt.correct,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "source_attempt_type": attempt.source_attempt_type,
        }
        for attempt in attempts_for_question(
            db, user_id=state.user_id, service_namespace=state.service_namespace,
            question_source_type=state.question_source_type,
            question_source_id=state.question_source_id,
            question_scope_key=state.question_scope_key)
    ]


def error_analysis(db: DbSession, state: WrongAnswerState) -> str | None:
    """Whatever the domain already produced for the latest factual attempt — never a guess."""
    attempts = attempts_for_question(
        db, user_id=state.user_id, service_namespace=state.service_namespace,
        question_source_type=state.question_source_type,
        question_source_id=state.question_source_id,
        question_scope_key=state.question_scope_key)
    for attempt in reversed(attempts):
        result = _attempt_result(attempt)
        value = result.get("feedback") or result.get("analysis")
        if value:
            return str(value)
    return None
