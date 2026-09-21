"""Adaptive Practice V1 — deterministic practice selection over REAL product facts.

WHAT "ADAPTIVE" MEANS HERE
--------------------------
Not a model. Every candidate is ranked by facts the product already stores, and every
candidate carries a REASON CODE that names the rule which selected it:

    due_review      the question's knowledge point has a STORED review date that has passed
    recent_wrong    the learner's most recent factual attempt on this question was incorrect
    needs_work      an ACTIVE wrong-answer state with repeated factual failures exists
    coverage_gap    the question's knowledge point has no knowledge-progress row at all
    unseen_topic    the learner has never attempted this question

None of those is a claim about the learner's ability. A selection is a product decision, and
the module says so in its own response semantics. There is deliberately NO field named
weakness, mastery, probability, difficulty prior or predicted anything.

DELIBERATELY NOT USED
---------------------
``learner_state``, ``misconception_v2``, ``IRT`` and any difficulty prior are NOT inputs: none
of them has passed the Productization Gate, so using one here would be exactly the "model
output presented as a product fact" the SSOT forbids. V1 needs none of them — the reasons above
are computed from rows.

SPACES
------
``course_learning``  candidates are the course's own AI question book (the same rows the
                     workbook serves, owner- and course-scoped)
``exam_11408``       candidates are the module's ACTIVE public chapter-bank questions
``programming``      candidates are the language's ACTIVE approved exercises — the metadata
                     (difficulty, knowledge points, per-user progress) is real, so exercise
                     recommendation is included rather than deferred

ISOLATION
---------
Every read is scoped to the caller (and to the course/module/language they asked for). No
candidate is another learner's row, another course's question or another language's exercise.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace, normalize_service_namespace

logger = logging.getLogger("learning.adaptive")

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

POLICY_VERSION = "adaptive_policy_v1"
MAX_SCAN = 300
DEFAULT_LIMIT = 10
MAX_LIMIT = 30
RECENT_WINDOW_DAYS = 30

REASON_DUE_REVIEW = "due_review"
REASON_RECENT_WRONG = "recent_wrong"
REASON_NEEDS_WORK = "needs_work"
REASON_COVERAGE_GAP = "coverage_gap"
REASON_UNSEEN_TOPIC = "unseen_topic"

REASONS = (REASON_DUE_REVIEW, REASON_RECENT_WRONG, REASON_NEEDS_WORK,
           REASON_COVERAGE_GAP, REASON_UNSEEN_TOPIC)
_REASON_RANK = {reason: rank for rank, reason in enumerate(REASONS)}

SELECTION_SEMANTICS = (
    "deterministic selection over stored facts (attempts, wrong-answer states, stored review "
    "dates, knowledge status). Every candidate states the rule that selected it. This is not "
    "a weakness prediction, not mastery probability, and not a model output."
)


class AdaptiveRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- candidates by space

def _course_candidates(db: DbSession, user, course_id) -> tuple[list[dict], str]:
    from learning.spaces.course_learning.context import course_identity_forms, normalize_course_id
    from models import AIGeneratedQuestion

    key = normalize_course_id(course_id)
    forms = sorted(course_identity_forms(key))
    rows = (db.query(AIGeneratedQuestion)
            .filter(AIGeneratedQuestion.username == user.username,
                    AIGeneratedQuestion.subject_key.in_(forms),
                    func.coalesce(AIGeneratedQuestion.quality_status, "unchecked")
                    != "discarded")
            .order_by(AIGeneratedQuestion.id.desc()).limit(MAX_SCAN).all())
    return ([{
        # The label is the question's own METADATA (its knowledge point), never the stem:
        # this surface resolves no content, so it cannot become a third materialization path.
        "source_type": "AI_generated",
        "question_source_id": str(row.id),
        "label": row.knowledge_point_name or "",
        "question_type": row.question_type,
        "difficulty": row.difficulty,
        "knowledge_point_id": row.knowledge_point_id,
        "knowledge_point_name": row.knowledge_point_name,
    } for row in rows], key)


def _exam_subject_keys(module: str) -> list[str]:
    """EVERY exact spelling this module's bank rows may be stored under.

    A bounded, fixed set — the canonical module key, the legacy scope id and the two display
    forms — so the module filter can be applied IN SQL. Filtering in Python after a bounded id
    window would let another module's newest rows crowd this one out of the window entirely.
    """
    from learning.spaces.exam_prep.catalog import CS408_MODULE_DISPLAY
    from learning.spaces.exam_prep.scope import build_legacy_exam_scope_id

    keys = {module}
    try:
        keys.add(build_legacy_exam_scope_id(module))
    except Exception:  # noqa: BLE001 — an unknown module simply has no legacy key
        pass
    display = CS408_MODULE_DISPLAY.get(module)
    if display:
        keys.add(display)
        keys.add(f"11408 {display}")
    return sorted(keys)


def _exam_candidates(db: DbSession, user, exam_module_id) -> list[dict]:
    from learning.spaces.exam_prep.scope import resolve_cs408_module
    from models import ExamQuestionBank

    module = str(exam_module_id or "").strip()
    if not module:
        raise AdaptiveRefusal("module_required", "考试自适应练习需要 exam_module_id")
    wanted = resolve_cs408_module(module) or module
    rows = (db.query(ExamQuestionBank)
            .filter(ExamQuestionBank.is_active.is_(True),
                    ExamQuestionBank.visibility == "public",
                    ExamQuestionBank.subject_key.in_(_exam_subject_keys(wanted)))
            .order_by(ExamQuestionBank.id.desc()).limit(MAX_SCAN).all())
    out = []
    for row in rows:
        # defence in depth: the SQL filter is an exact-match key set, and the canonical check
        # still decides — a row that does not resolve to this module is never offered
        if (resolve_cs408_module(getattr(row, "subject_key", None)) or "") != wanted:
            continue
        out.append({
            "source_type": "static_question_bank",
            "question_source_id": str(row.id),
            "label": row.knowledge_point_name or "",
            "question_type": row.question_type,
            "difficulty": row.difficulty,
            "knowledge_point_id": row.knowledge_point_id,
            "knowledge_point_name": row.knowledge_point_name,
        })
        if len(out) >= MAX_SCAN:
            break
    return out


def _programming_candidates(db: DbSession, user, language) -> list[dict]:
    from learning.spaces.programming.context import normalize_language
    from models import ProgrammingExercise

    lang = normalize_language(language)
    rows = (db.query(ProgrammingExercise)
            .filter(ProgrammingExercise.language == lang,
                    ProgrammingExercise.is_active.is_(True),
                    ProgrammingExercise.quality_status == "approved")
            .order_by(ProgrammingExercise.id.desc()).limit(MAX_SCAN).all())
    return [{
        "source_type": "programming_exercise",
        "question_source_id": str(row.id),
        "label": row.title,
        "question_type": "code",
        "difficulty": row.difficulty,
        "knowledge_point_id": None,
        "knowledge_point_name": None,
    } for row in rows]


# ---------------------------------------------------------------- feature facts

def _attempt_facts(db: DbSession, user, space: str, source_type: str,
                   ids: list[str]) -> dict[str, dict]:
    """Per-question attempt facts, computed in ONE bounded query per source type."""
    from learning.practice.models import PracticeAttempt

    if not ids:
        return {}
    rows = (db.query(PracticeAttempt)
            .filter(PracticeAttempt.user_id == user.id,
                    PracticeAttempt.service_namespace == space,
                    PracticeAttempt.question_source_type == source_type,
                    PracticeAttempt.question_source_id.in_(ids))
            .order_by(PracticeAttempt.submitted_at.asc().nullsfirst(),
                      PracticeAttempt.id.asc())
            .all())
    facts: dict[str, dict] = {}
    for row in rows:
        entry = facts.setdefault(row.question_source_id, {
            "attempts": 0, "correct": 0, "incorrect": 0,
            "last_attempt_at": None, "last_correct": None, "last_wrong_at": None,
        })
        entry["attempts"] += 1
        if row.correct is True:
            entry["correct"] += 1
        elif row.correct is False:
            entry["incorrect"] += 1
            entry["last_wrong_at"] = row.submitted_at
        entry["last_attempt_at"] = row.submitted_at or entry["last_attempt_at"]
        entry["last_correct"] = row.correct
    return facts


def _wrong_facts(db: DbSession, user, space: str, source_type: str, ids: list[str]) -> dict:
    from learning.wrong_answers.models import STATUS_ACTIVE, WrongAnswerState

    if not ids:
        return {}
    rows = (db.query(WrongAnswerState)
            .filter(WrongAnswerState.user_id == user.id,
                    WrongAnswerState.service_namespace == space,
                    WrongAnswerState.question_source_type == source_type,
                    WrongAnswerState.question_source_id.in_(ids),
                    WrongAnswerState.status == STATUS_ACTIVE).all())
    return {row.question_source_id: {"wrong_count": int(row.wrong_count or 0),
                                     "last_wrong_at": row.last_wrong_at}
            for row in rows}


def _due_knowledge(db: DbSession, user, course_id=None) -> dict[str, str]:
    """Knowledge points whose STORED review date has passed → {point key: due iso}."""
    from models import UserKnowledgeProgress

    q = (db.query(UserKnowledgeProgress)
         .filter(UserKnowledgeProgress.username == user.username,
                 UserKnowledgeProgress.review_due_at.isnot(None),
                 UserKnowledgeProgress.review_due_at <= _now()))
    if course_id:
        q = q.filter(UserKnowledgeProgress.course_id == course_id)
    out = {}
    for row in q.limit(MAX_SCAN * 4).all():
        for key in (str(row.knowledge_point_code or "").strip(),
                    str(row.knowledge_point_id) if row.knowledge_point_id else ""):
            if key:
                out[key] = row.review_due_at.isoformat()
    return out


def _known_points(db: DbSession, user, course_id=None) -> set[str]:
    from models import UserKnowledgeProgress

    q = db.query(UserKnowledgeProgress).filter(
        UserKnowledgeProgress.username == user.username)
    if course_id:
        q = q.filter(UserKnowledgeProgress.course_id == course_id)
    keys = set()
    for row in q.limit(MAX_SCAN * 8).all():
        for value in (row.knowledge_point_code, row.knowledge_point_id):
            if value is not None and str(value).strip():
                keys.add(str(value).strip())
    return keys


# ---------------------------------------------------------------- the selection

def _reason_for(candidate: dict, facts: dict, wrong: dict, due: dict,
                known_points: set) -> tuple[str | None, dict]:
    """(reason, factual evidence). ``None`` = nothing to recommend about this candidate."""
    point_keys = [key for key in (_norm(candidate.get("knowledge_point_id")),
                                  _norm(candidate.get("knowledge_point_name"))) if key]
    due_at = next((due[key] for key in point_keys if key in due), None)
    if due_at:
        return REASON_DUE_REVIEW, {"knowledge_point_due_at": due_at}

    if facts.get("last_correct") is False and facts.get("last_wrong_at"):
        return REASON_RECENT_WRONG, {"last_attempt_at": _iso(facts["last_wrong_at"]),
                                     "incorrect_count": facts.get("incorrect", 0)}
    if wrong and wrong.get("wrong_count", 0) >= 2:
        return REASON_NEEDS_WORK, {"wrong_count": wrong["wrong_count"],
                                   "last_wrong_at": _iso(wrong.get("last_wrong_at"))}
    if not facts.get("attempts"):
        if point_keys and not any(key in known_points for key in point_keys):
            return REASON_COVERAGE_GAP, {"knowledge_point_id": candidate.get("knowledge_point_id"),
                                         "knowledge_point_name": candidate.get("knowledge_point_name")}
        return REASON_UNSEEN_TOPIC, {"attempts": 0}
    return None, {}


def _norm(value) -> str:
    return str(value).strip() if value is not None else ""


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _sort_key(candidate: dict):
    reason_rank = _REASON_RANK.get(candidate["reason"], 99)
    facts = candidate["facts"]
    if candidate["reason"] == REASON_DUE_REVIEW:
        inner = facts.get("knowledge_point_due_at") or ""
    elif candidate["reason"] in (REASON_RECENT_WRONG, REASON_NEEDS_WORK):
        # newest trouble first → invert the timestamp by string sort on a reversed key
        inner = _invert(facts.get("last_wrong_at") or facts.get("last_attempt_at") or "")
    else:
        # coverage_gap / unseen_topic carry no recency signal, and the display window is
        # bounded — so the NEWEST content in the group comes first. Deterministic, and it
        # means a question added today is visible today instead of sorting behind hundreds of
        # older unseen ones.
        inner = _invert(candidate["candidate_id"])
    return (reason_rank, inner, candidate["candidate_id"].zfill(12))


def _invert(iso_text: str) -> str:
    """Descending order for an ISO string inside an ascending sort."""
    return "".join(chr(0x10FFFD - ord(ch)) for ch in iso_text) if iso_text else "~"


def select_candidates(db: DbSession, user, *, service_key: str, course_id=None,
                      exam_module_id=None, language=None, limit: int = DEFAULT_LIMIT,
                      emit_event: bool = True) -> dict:
    """Rank the caller's practice candidates by FACTUAL reason, deterministically.

    ``emit_event=False`` is for a caller that CONSUMES a selection as an input (the daily
    agenda): a selection fact belongs to the surface the learner actually asked for, and
    writing one on every projection read would be event noise rather than a new fact.
    """
    try:
        space = normalize_service_namespace(service_key or COURSE)
    except ValueError as exc:
        raise AdaptiveRefusal("unknown_space", str(exc)) from None

    safe_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    identity: dict = {"service_namespace": space}
    course_key = None

    if space == COURSE:
        from learning.spaces.course_learning.context import CourseContextError
        try:
            candidates, course_key = _course_candidates(db, user, course_id)
        except CourseContextError as exc:
            # a course selection without a course is a caller error, not a crash
            raise AdaptiveRefusal("course_required", str(exc)) from None
        identity["course_id"] = course_key
    elif space == EXAM:
        candidates = _exam_candidates(db, user, exam_module_id)
        identity["exam_module_id"] = exam_module_id
    elif space == PROG:
        from learning.spaces.programming.context import normalize_language
        candidates = _programming_candidates(db, user, language)
        identity["programming_language"] = normalize_language(language)
    else:
        raise AdaptiveRefusal("unknown_space", f"自适应练习暂不支持该学习空间: {space}")

    by_type: dict[str, list[str]] = {}
    for candidate in candidates:
        by_type.setdefault(candidate["source_type"], []).append(candidate["question_source_id"])

    attempt_facts = {source_type: _attempt_facts(db, user, space, source_type, ids)
                     for source_type, ids in by_type.items()}
    wrong_facts = {source_type: _wrong_facts(db, user, space, source_type, ids)
                   for source_type, ids in by_type.items()}
    due = _due_knowledge(db, user, course_key)
    known = _known_points(db, user, course_key)

    selected, excluded = [], 0
    for candidate in candidates:
        source_type = candidate["source_type"]
        facts = attempt_facts.get(source_type, {}).get(candidate["question_source_id"], {})
        wrong = wrong_facts.get(source_type, {}).get(candidate["question_source_id"], {})
        reason, evidence = _reason_for(candidate, facts, wrong, due, known)
        if reason is None:
            excluded += 1
            continue
        selected.append({
            "candidate_id": f"{source_type}:{candidate['question_source_id']}",
            "source_type": source_type,
            "question_source_id": candidate["question_source_id"],
            "label": candidate["label"],
            "question_type": candidate["question_type"],
            "difficulty": candidate["difficulty"],
            "knowledge_point_id": candidate["knowledge_point_id"],
            "knowledge_point_name": candidate["knowledge_point_name"],
            "reason": reason,
            "facts": {
                "attempts": facts.get("attempts", 0),
                "factual_correct": facts.get("correct", 0),
                "factual_incorrect": facts.get("incorrect", 0),
                "last_attempt_at": _iso(facts.get("last_attempt_at")),
                "active_wrong_count": wrong.get("wrong_count", 0),
                **evidence,
            },
        })

    selected.sort(key=_sort_key)
    window = selected[:safe_limit]
    selection_id = uuid.uuid4().hex
    if emit_event:
        _emit(user, selection_id=selection_id, window=window, space=space, identity=identity)

    return {
        "selection_id": selection_id,
        "service_namespace": space,
        "context": identity,
        "policy_version": POLICY_VERSION,
        "candidates": window,
        "total_candidates": len(selected),
        "excluded_count": excluded,
        "counts_by_reason": {reason: sum(1 for item in selected if item["reason"] == reason)
                             for reason in REASONS},
        "reasons": {
            REASON_DUE_REVIEW: "知识点已到复习时间（来自存储的复习日期）",
            REASON_RECENT_WRONG: "最近一次作答是错误的",
            REASON_NEEDS_WORK: "存在反复做错的错题状态",
            REASON_COVERAGE_GAP: "该知识点在本科目中尚无任何学习记录",
            REASON_UNSEEN_TOPIC: "该题从未作答",
        },
        "semantics": SELECTION_SEMANTICS,
        "generated_at": _now().isoformat(),
    }


def _emit(user, *, selection_id, window, space, identity) -> None:
    try:
        from learning.records import producers
        producers.emit_adaptive_practice_selected(
            user_id=user.id, selection_id=selection_id, candidate_count=len(window),
            service_namespace=space,
            reason_codes=[item["reason"] for item in window],
            policy_version=POLICY_VERSION, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("adaptive.selection_event_failed error=%s", type(exc).__name__)
