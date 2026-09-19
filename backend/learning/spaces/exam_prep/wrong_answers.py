"""Exam Prep canonical wrong-answer projection — the ONE Exam wrong-answer read shape.

BC7. Before this module there were two wrong-answer truths for CS408:

  * the module-scoped ``GET /exam/11408/{subject}/wrong-questions`` list, which merges the
    two LEGACY tables and has no factual resolution — a question answered correctly on a
    retry stayed 未订正 forever, blanks entered the book, and re-sitting a paper duplicated
    every row;
  * ``wrong_answer_states``, the canonical store the Practice Core already keeps, which
    resolves factually but carried none of the display data a wrong-answer workspace needs
    and had no module filter.

F1C4 must not merge those two in the browser. This module is the backend half of the
answer: it reads the CANONICAL state rows and derives ONE normalized record per state,
resolving the display data from the same facts the state was built from.

WHAT IS AUTHORITATIVE HERE
--------------------------------------------------------------------
The state row decides identity, status and timing. The display data is read from, in
order of preference:

  1. the learner's own PracticeAttempt facts — the answer they actually gave, and the
     reference answer the submit already recorded in its result envelope;
  2. the question source (``exam_question_bank`` / ``ai_generated_questions`` / the
     document past-paper cache) for the stem, options and analysis, which are immutable
     protected content the attempt deliberately does not duplicate.

The legacy wrong-answer tables are read by NOTHING in this module. They are not a
fallback, not a merge input, and not a source of status.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from learning.practice.models import PracticeAttempt
from learning.practice.refs import QuestionSourceType
from learning.wrong_answers.models import WrongAnswerState
from learning.wrong_answers.project import attempts_for_question

from .catalog import CS408_MODULE_DISPLAY

logger = logging.getLogger("learning.spaces.exam_prep")

# ---------------------------------------------------------------- source kind

SOURCE_KIND_CHAPTER = "chapter_practice"
SOURCE_KIND_PAST_PAPER = "past_paper"
SOURCE_KIND_AI = "ai_generated"
SOURCE_KIND_OTHER = "other"

# The closed product vocabulary F1C4 renders. Every value maps onto a wrong-answer source
# the product already has: chapter practice, past papers, AI-generated questions. `other`
# exists so an unmapped provenance is stated honestly instead of being filed as one of the
# three.
SOURCE_KIND_LABELS = {
    SOURCE_KIND_CHAPTER: "章节练习",
    SOURCE_KIND_PAST_PAPER: "历年真题",
    SOURCE_KIND_AI: "AI 出题",
    SOURCE_KIND_OTHER: "其他",
}

_SOURCE_KIND_BY_SOURCE_TYPE = {
    QuestionSourceType.STATIC_QUESTION_BANK.value: SOURCE_KIND_CHAPTER,
    QuestionSourceType.PAST_EXAM.value: SOURCE_KIND_PAST_PAPER,
    QuestionSourceType.AI_GENERATED.value: SOURCE_KIND_AI,
}


def source_kind_of(question_source_type: str) -> str:
    return _SOURCE_KIND_BY_SOURCE_TYPE.get(question_source_type, SOURCE_KIND_OTHER)


def module_name_of(module_key: str) -> str:
    key = (module_key or "").strip()
    return CS408_MODULE_DISPLAY.get(key, key)


# ---------------------------------------------------------------- scope helpers


def scope_year(question_scope_key: str) -> int | None:
    """The paper year a past-exam scope carries, or None.

    ``project.past_exam_scope`` is the ONE place a past-exam scope is built, and its form is
    ``subject:<s>|module:<m>|year:<y>``. This reads that form back; it never invents a year
    for a question whose scope has none.
    """
    for part in (question_scope_key or "").split("|"):
        if part.startswith("year:"):
            try:
                return int(part.split(":", 1)[1])
            except (TypeError, ValueError):
                return None
    return None


def _scope_module(question_scope_key: str) -> str:
    for part in (question_scope_key or "").split("|"):
        if part.startswith("module:"):
            return part.split(":", 1)[1]
    return ""


def state_module(state: WrongAnswerState) -> str:
    """The module a state belongs to.

    The dedicated column is authoritative; the scope string is a bounded fallback for rows
    written before the column existed, so an old row is not reported as module-less.
    """
    return (state.module_key or "").strip() or _scope_module(state.question_scope_key)


# ---------------------------------------------------------------- fact helpers


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


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- source lookup


class _SourceIndex:
    """Batch lookup of the question content a page of states points at.

    One query per source table for the whole page. Reading the content per row would be an
    N+1 over a list that is explicitly paginated, and the content is exactly the part that
    does not live on the state row.

    Chapter states and past-paper states do NOT share an id space, and this index does not
    pretend they do. A chapter state's source id IS the ``exam_question_bank`` primary key.
    A past-paper state's is not: the past-paper submit keys its results by the PUBLIC
    question number (or, for a document-sourced paper, by the source's internal id), so its
    content is resolved by public identity — the same ``(subject_key, year, question_number)``
    BC6 froze.
    """

    def __init__(self, db: DbSession):
        self._db = db
        self._bank: dict[str, object] | None = None
        self._ai: dict[str, object] | None = None
        self._bank_by_number: dict[tuple[str, int, int], object] = {}
        self._documents: dict[tuple[str, int], dict[str, dict]] = {}

    def prime(self, states: list[WrongAnswerState]) -> None:
        bank_ids = set()
        ai_ids = set()
        papers = set()
        for state in states:
            kind = source_kind_of(state.question_source_type)
            value = _as_int(state.question_source_id)
            if kind in (SOURCE_KIND_CHAPTER, SOURCE_KIND_PAST_PAPER):
                if value is not None:
                    bank_ids.add(value)
                if kind == SOURCE_KIND_PAST_PAPER:
                    module = state_module(state)
                    year = scope_year(state.question_scope_key)
                    if module and year:
                        papers.add((module, int(year)))
            elif kind == SOURCE_KIND_AI and value is not None:
                ai_ids.add(value)
        self._bank = self._load_bank(bank_ids)
        self._ai = self._load_ai(ai_ids)
        self._bank_by_number = self._load_bank_numbers(papers)

    def _load_bank(self, ids: set[int]) -> dict[str, object]:
        from models import ExamQuestionBank
        if not ids:
            return {}
        rows = (self._db.query(ExamQuestionBank)
                .filter(ExamQuestionBank.id.in_(sorted(ids))).all())
        return {str(r.id): r for r in rows}

    def _load_bank_numbers(self, papers: set) -> dict:
        """Every active past-paper bank row of the papers this page touches."""
        from models import ExamQuestionBank
        if not papers:
            return {}
        rows = (self._db.query(ExamQuestionBank)
                .filter(ExamQuestionBank.source_type == "past_paper",
                        ExamQuestionBank.is_active == True)  # noqa: E712
                .all())
        wanted = {(module, int(year)) for module, year in papers}
        out = {}
        for row in rows:
            key = (row.subject_key, int(row.year or 0))
            if key in wanted and row.question_number is not None:
                out[(key[0], key[1], int(row.question_number))] = row
        return out

    def _load_ai(self, ids: set[int]) -> dict[str, object]:
        from models import AIGeneratedQuestion
        if not ids:
            return {}
        rows = (self._db.query(AIGeneratedQuestion)
                .filter(AIGeneratedQuestion.id.in_(sorted(ids))).all())
        return {str(r.id): r for r in rows}

    def bank(self, source_id: str):
        return (self._bank or {}).get(str(source_id))

    def bank_by_number(self, subject_key: str, year: int, question_number: int):
        return self._bank_by_number.get((subject_key, int(year), int(question_number)))

    def ai(self, source_id: str):
        return (self._ai or {}).get(str(source_id))

    def _document_cache(self, subject_key: str, year: int) -> dict[str, dict]:
        key = (subject_key, int(year))
        if key not in self._documents:
            import exam_past_paper
            by_id: dict[str, dict] = {}
            by_number: dict[int, dict] = {}
            for raw in exam_past_paper.document_questions(subject_key, int(year)):
                if raw.get("id") is not None:
                    by_id[str(raw.get("id"))] = raw
                number = _as_int(raw.get("number"))
                if number is not None:
                    by_number.setdefault(number, raw)
            self._documents[key] = {"by_id": by_id, "by_number": by_number}
        return self._documents[key]

    def document_by_id(self, subject_key: str, year: int, internal_id: str) -> dict | None:
        """A document-sourced question by the source's INTERNAL id (never exposed publicly)."""
        return self._document_cache(subject_key, year)["by_id"].get(str(internal_id))

    def document_by_number(self, subject_key: str, year: int, number: int) -> dict | None:
        return self._document_cache(subject_key, year)["by_number"].get(int(number))


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


def _document_question_type(raw_type) -> str:
    return "big" if str(raw_type or "").strip() in {"大题", "big", "简答题"} else "choice"


# ---------------------------------------------------------------- record


def build_record(db: DbSession, state: WrongAnswerState, *, index: _SourceIndex | None = None,
                 attempts: list[PracticeAttempt] | None = None) -> dict:
    """ONE normalized wrong-answer record. Nothing here reaches a legacy wrong table."""
    if attempts is None:
        attempts = attempts_for_question(
            db, user_id=state.user_id, service_namespace=state.service_namespace,
            question_source_type=state.question_source_type,
            question_source_id=state.question_source_id,
            question_scope_key=state.question_scope_key)
    if index is None:
        index = _SourceIndex(db)
        index.prime([state])

    source_kind = source_kind_of(state.question_source_type)
    module_key = state_module(state)
    latest_wrong = _latest_wrong(attempts)
    snapshot = _attempt_result(latest_wrong) if latest_wrong else {}
    ref = _attempt_ref(latest_wrong) if latest_wrong else {}
    ref_context = ref.get("context") or {}

    record = {
        "wrong_record_id": state.id,
        "status": state.status,
        "service_namespace": state.service_namespace,
        "module_key": module_key,
        "module_name": module_name_of(module_key),
        "source_kind": source_kind,
        "source_label": SOURCE_KIND_LABELS[source_kind],
        "question_type": None,
        "stem": "",
        "options": {},
        "user_answer": (latest_wrong.answer or "") if latest_wrong else "",
        "reference_answer": str(snapshot.get("standard_answer") or ""),
        "analysis": None,
        "year": None,
        "question_number": None,
        "question_bank_id": None,
        "knowledge_point_id": ref_context.get("knowledge_point_id"),
        "knowledge_point_name": None,
        "knowledge_point_path": None,
        "resources": [],
        "first_wrong_at": _iso(state.first_wrong_at),
        "last_wrong_at": _iso(state.last_wrong_at),
        "resolved_at": _iso(state.resolved_at),
        "repeat_wrong_count": int(state.wrong_count or 0),
    }

    if source_kind in (SOURCE_KIND_CHAPTER, SOURCE_KIND_AI):
        _fill_chapter(record, state, snapshot, index, module_key)
    elif source_kind == SOURCE_KIND_PAST_PAPER:
        _fill_past_paper(record, state, snapshot, index, module_key, has_facts=bool(attempts))
    else:
        # An unmapped provenance keeps the factual answer snapshot and says so, rather than
        # being dressed up as one of the three known kinds.
        record["question_type"] = snapshot.get("question_type") or None
    return record


def _fill_chapter(record: dict, state: WrongAnswerState, snapshot: dict,
                  index: _SourceIndex, module_key: str) -> None:
    is_bank = state.question_source_type == QuestionSourceType.STATIC_QUESTION_BANK.value
    if is_bank:
        # The chapter-practice redo contract takes explicit bank question ids, and this is
        # the already-authoritative chapter question identity the attempt recorded. It comes
        # from the FACT, so it is reported even when the content row cannot be read.
        record["question_bank_id"] = _as_int(state.question_source_id)
    row = index.bank(state.question_source_id) if is_bank else index.ai(state.question_source_id)
    record["question_type"] = snapshot.get("question_type") or (row.question_type if row else None)
    if row is None:
        return
    record["stem"] = row.stem or ""
    record["options"] = _parse_options(row.options_json)
    record["analysis"] = (row.analysis or None)
    if not record["reference_answer"]:
        record["reference_answer"] = (row.standard_answer or "")
    record["knowledge_point_id"] = record["knowledge_point_id"] or getattr(
        row, "knowledge_point_id", None)
    record["knowledge_point_name"] = getattr(row, "knowledge_point_name", None)
    record["knowledge_point_path"] = getattr(row, "knowledge_point_path", None)


def _fill_past_paper(record: dict, state: WrongAnswerState, snapshot: dict,
                     index: _SourceIndex, module_key: str, *, has_facts: bool) -> None:
    year = scope_year(state.question_scope_key)
    record["year"] = year
    record["question_type"] = snapshot.get("question_type") or None

    # The public past-paper identity is (subject_key, year, question_number) — BC6 frozen.
    # The submit keys its results by that number and persists them, so the attempt's own
    # envelope is the primary source and the content tables only supply display text.
    number = _as_int(snapshot.get("number"))
    if number is None:
        number = _as_int(snapshot.get("question_number"))

    row = None
    raw = None
    if not has_facts:
        # A legacy-imported state has no attempt facts at all, so there is no recorded
        # number to inherit. Its only identity is the source's own id, which for this table
        # is a bank PK or a document internal id.
        row = index.bank(state.question_source_id)
        if row is not None:
            number = _as_int(row.question_number)
        elif module_key and year:
            raw = index.document_by_id(module_key, year, state.question_source_id)
            if raw is not None:
                number = _as_int(raw.get("number"))
    elif module_key and year and number is not None:
        row = index.bank_by_number(module_key, year, number)
        if row is None:
            raw = index.document_by_number(module_key, year, number)

    record["question_number"] = number
    if row is not None:
        record["stem"] = row.stem or ""
        record["options"] = _parse_options(row.options_json)
        record["analysis"] = (row.analysis or None)
        if not record["reference_answer"]:
            record["reference_answer"] = (row.standard_answer or "")
        if not record["question_type"]:
            record["question_type"] = "big" if row.question_type == "big" else "choice"
    elif raw is not None:
        record["stem"] = raw.get("stem") or raw.get("content") or ""
        record["options"] = _parse_options(raw.get("options"))
        record["analysis"] = (raw.get("analysis") or None)
        if not record["reference_answer"]:
            record["reference_answer"] = str(
                raw.get("answer") or raw.get("standard_answer") or "")
        if not record["question_type"]:
            record["question_type"] = _document_question_type(raw.get("type"))
    if record["question_type"] is None and snapshot.get("type"):
        record["question_type"] = ("big" if str(snapshot.get("type")) in {"大题", "big"}
                                   else "choice")
    if module_key and year and number is not None:
        # The same resolution the past-paper question list performs, so a figure in the wrong
        # book and the same figure on the paper are the same URL.
        import exam_past_paper
        record["resources"] = [
            {"url": r.url} for r in exam_past_paper.resources_for(module_key, year, number)]


def build_records(db: DbSession, states: list[WrongAnswerState]) -> list[dict]:
    """Normalized records for a page of states, with one batched content lookup."""
    index = _SourceIndex(db)
    index.prime(states)
    return [build_record(db, state, index=index) for state in states]


def attempt_history(db: DbSession, state: WrongAnswerState) -> list[dict]:
    """The factual attempt history behind one state, newest last.

    Read from ``practice_attempts`` only. ``review_count``-style legacy counters are not
    part of this — they are not a review history (§10).
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

