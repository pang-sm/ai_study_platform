"""Daily Learning Orchestrator V1 — "what should I do next", computed from real facts.

A PROJECTION, NOT A SOURCE OF TRUTH
-----------------------------------
An agenda item COPIES NO BUSINESS STATE. It names an object that already exists (a plan task,
a review item, a question, an exercise) and links to the surface that owns it. Completing the
real action there is the only thing that changes anything, and the next read of the agenda
simply recomputes: an item whose underlying fact changed is gone, and the ones behind it move
up. There is no second "completed" flag anywhere in this module, and the response says so in
its own semantics.

DETERMINISTIC, TRANSPARENT, VERSIONED
-------------------------------------
``AGENDA_POLICY_VERSION`` fixes the priority ladder, and every item carries the reason code and
the FACTS that put it there. The same stored facts produce the same items in the same order —
no model ranks anything, no weakness is predicted, no readiness is scored. Those words do not
appear in this module's output because those facts do not exist.

THREE DOMAINS, STRICTLY ISOLATED (P5 §C)
----------------------------------------
Course, exam and programming items coexist in one agenda, and EVERY item carries the domain of
ITS OWN row: a plan task is attributed from its own ``subject_key``, a review item from its own
space, a practice recommendation from the space that produced it. An item whose domain cannot
be established is EXCLUDED rather than attached to whatever context the caller happened to
send — a programming item can never appear under a course context, and a course item can never
be opened through an exam one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace, normalize_service_namespace

logger = logging.getLogger("learning.agenda")

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value
SPACES = (COURSE, EXAM, PROG)

AGENDA_POLICY_VERSION = "agenda_policy_v1"
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
MAX_PER_SOURCE = 30

SEMANTICS = (
    "deterministic projection over stored facts (plan tasks, review items, practice "
    "candidates). It copies no business state: completing the real action is what changes it. "
    "The order comes from a versioned rule, not from a model — no predicted weakness, no "
    "mastery, no readiness."
)

# ── action types (what the learner actually does) ──
ACTION_REVIEW = "review"
ACTION_PRACTICE = "practice"
ACTION_PLAN_TASK = "plan_task"
ACTION_PROGRAMMING = "programming"

# ── priority ladder (P5 §B) — the ORDER is the policy ──
REASON_OVERDUE_PLAN_TASK = "overdue_plan_task"
REASON_DUE_REVIEW = "due_review"
REASON_REPEATED_WRONG = "repeated_wrong"
REASON_NEEDS_WORK = "needs_work"
REASON_CURRENT_PLAN_TASK = "current_plan_task"
REASON_ADAPTIVE_RECOMMENDATION = "adaptive_recommendation"
REASON_UNSEEN_COVERAGE = "unseen_coverage"

PRIORITY_ORDER = (
    REASON_OVERDUE_PLAN_TASK,
    REASON_DUE_REVIEW,
    REASON_REPEATED_WRONG,
    REASON_NEEDS_WORK,
    REASON_CURRENT_PLAN_TASK,
    REASON_ADAPTIVE_RECOMMENDATION,
    REASON_UNSEEN_COVERAGE,
)
_PRIORITY_RANK = {reason: rank for rank, reason in enumerate(PRIORITY_ORDER)}

# What makes an item disappear — stated as the FACT that changes, not as a UI action.
RESOLVED_BY = {
    REASON_OVERDUE_PLAN_TASK: "plan_task_completion",
    REASON_CURRENT_PLAN_TASK: "plan_task_completion",
    REASON_DUE_REVIEW: "review_completion",
    REASON_REPEATED_WRONG: "review_completion",
    REASON_NEEDS_WORK: "review_completion",
    REASON_ADAPTIVE_RECOMMENDATION: "practice_attempt",
    REASON_UNSEEN_COVERAGE: "practice_attempt",
}

_MODULE_DISPLAY_FALLBACK = {}


class AgendaRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _parse_due(value):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:len(fmt) + 2], fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- domain attribution

def _attribute_plan_task(row) -> dict | None:
    """The domain a plan task belongs to, read from its OWN subject key — or None.

    ``course_learning:<course>`` and ``programming:<language>`` are the two keyed directions;
    an exam task is keyed by its module. A key this build does not recognize yields NOTHING:
    reporting another direction's task under this agenda would be a fabrication with the
    learner's own data.
    """
    key = str(row.subject_key or "").strip()
    if key.startswith("course_learning:"):
        # the plan key carries the resolved SEED id; the course's canonical identity is what
        # the course surfaces (and their routes) address, so it is resolved through the SAME
        # subject map the course space uses — never guessed, and left as-is when unknown.
        from subjects import normalize_subject_course_learning
        raw = key.split(":", 1)[1]
        return {"service_namespace": COURSE,
                "course_id": normalize_subject_course_learning(raw) or raw,
                "exam_module_id": None, "language": None}
    if key.startswith("programming:"):
        return {"service_namespace": PROG, "course_id": None, "exam_module_id": None,
                "language": key.split(":", 1)[1]}
    from learning.spaces.exam_prep.scope import resolve_cs408_module
    module = resolve_cs408_module(key)
    if module:
        return {"service_namespace": EXAM, "course_id": None, "exam_module_id": module,
                "language": None}
    return None


def _in_scope(domain: dict, *, namespace, course_id, exam_module_id, language) -> bool:
    if namespace and domain["service_namespace"] != namespace:
        return False
    if course_id and domain.get("course_id") != course_id:
        return False
    if exam_module_id and domain.get("exam_module_id") != exam_module_id:
        return False
    if language and domain.get("language") != language:
        return False
    return True


def _deep_link(domain: dict, *, kind: str, source_id=None) -> str:
    """The product route for THIS item's own domain (never the caller's context)."""
    space = domain["service_namespace"]
    if space == COURSE:
        course = domain.get("course_id") or ""
        if kind == "plan":
            return f"/course/{course}/plan"
        if kind == "review":
            return f"/course/{course}/wrong"
        return f"/course/{course}/practice"
    if space == EXAM:
        module = domain.get("exam_module_id")
        suffix = f"?module={module}" if module else ""
        if kind == "plan":
            return "/exam/cs408/plan" + suffix
        if kind == "review":
            return "/exam/cs408/wrong" + suffix
        return "/exam/cs408/practice" + suffix
    lang = domain.get("language") or "Python"
    if kind == "plan":
        return f"/programming/{lang}/plan"
    if kind == "review":
        return f"/programming/{lang}/errors"
    if source_id is not None:
        return f"/programming/{lang}/exercises/{source_id}"
    return f"/programming/{lang}/exercises"


# ---------------------------------------------------------------- sources

def _plan_items(db: DbSession, user, *, namespace, course_id, exam_module_id, language):
    from models import ExamStudyPlanTask

    rows = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username,
                    ExamStudyPlanTask.status != "completed")
            .order_by(ExamStudyPlanTask.id.asc()).limit(MAX_PER_SOURCE).all())
    today = _now().date()
    items, unattributed = [], 0
    for row in rows:
        domain = _attribute_plan_task(row)
        if domain is None:
            unattributed += 1
            continue
        if not _in_scope(domain, namespace=namespace, course_id=course_id,
                         exam_module_id=exam_module_id, language=language):
            continue
        due = _parse_due(row.due_date)
        overdue = due is not None and due < today
        items.append({
            "action_type": ACTION_PLAN_TASK,
            "service_namespace": domain["service_namespace"],
            "domain_context": {key: value for key, value in domain.items()
                               if key != "service_namespace" and value is not None},
            "source_type": "plan_task",
            "source_id": str(row.id),
            "title": str(row.title or "")[:120] or "计划任务",
            "summary": ("已逾期" if overdue else "计划内任务")
                       + (f"（截止 {row.due_date}）" if row.due_date else "（无截止日期）"),
            "priority_reason": (REASON_OVERDUE_PLAN_TASK if overdue
                                else REASON_CURRENT_PLAN_TASK),
            "deep_link": _deep_link(domain, kind="plan"),
            "due_at": (due.isoformat() if due else None),
            "facts": {"status": row.status, "due_date": row.due_date,
                      "task_type": row.task_type,
                      "overdue": overdue, "subject_key": row.subject_key},
            "status": "overdue" if overdue else "open",
        })
    return items, unattributed


def _review_items(db: DbSession, user, *, namespace, course_id, exam_module_id, language):
    """What is actionable NOW: a DUE date that has passed, or work with no date at all.

    A ``scheduled`` item is future work — it is not "what to do next", so it waits for its
    date. A ``needs_attention`` wrong answer or exercise has no date by nature (nothing stored
    one), and it IS actionable: it enters the agenda on its factual reason, ranked by the
    policy ladder rather than by a date it does not have.
    """
    from learning import review as review_service

    projection = review_service.collect_review_items(
        db, user, service_namespace=namespace, course_id=course_id,
        exam_module_id=exam_module_id, language=language,
        limit=MAX_PER_SOURCE, offset=0)
    items = []
    for item in projection["items"]:
        if item["review_status"] == review_service.BUCKET_SCHEDULED:
            continue                       # a future date is not today's work
        if (item["review_status"] == review_service.BUCKET_NEEDS_ATTENTION
                and item["source_type"] == review_service.SOURCE_KNOWLEDGE_REVIEW):
            continue                       # a knowledge point with no stored date is not due
        source = item["source_type"]
        if source == review_service.SOURCE_PROGRAMMING_EXERCISE:
            action, reason = ACTION_PROGRAMMING, REASON_NEEDS_WORK
        elif source == review_service.SOURCE_KNOWLEDGE_REVIEW:
            # a knowledge item only ever enters as DUE (its date is stored), so the reason is
            # the review date itself — not a wrong-answer signal
            action, reason = ACTION_REVIEW, REASON_DUE_REVIEW
        elif (item.get("metrics") or {}).get("wrong_count", 0) >= 2:
            action, reason = ACTION_REVIEW, REASON_REPEATED_WRONG
        else:
            action, reason = ACTION_REVIEW, REASON_NEEDS_WORK
        items.append({
            "action_type": action,
            "service_namespace": item["service_namespace"],
            "domain_context": dict(item["domain_context"] or {}),
            "source_type": source,
            "source_id": item["source_id"],
            "title": item["title"],
            "summary": item["summary"],
            "priority_reason": reason,
            "deep_link": item["deep_link"],
            "due_at": item.get("due_at"),
            "facts": {"review_reason": item["reason"],
                      "review_status": item["review_status"],
                      "due_source": item.get("due_source"),
                      "schedule": item.get("schedule"),
                      **(item.get("metrics") or {})},
            # a wrong-answer item carries its state status; a knowledge item carries its
            # review bucket — either way it is the item's OWN stored state, never a copy
            "status": item.get("status") or item.get("review_status"),
            "review_item_id": item["id"],
            "question_identity": item.get("question_identity"),
        })
    return items


def _engaged_spaces(db: DbSession, user) -> set[str]:
    """The spaces this learner actually uses — one bounded query per space.

    A practice recommendation is advice about work the learner is DOING. Recommending ten
    unseen exercises to someone who has never opened a space is not an agenda, it is a
    catalogue — so a space with no history of its own contributes no practice suggestions
    (its own list surface already serves discovery).
    """
    from learning.practice.models import PracticeAttempt

    engaged = set()
    for space in SPACES:
        exists = (db.query(PracticeAttempt.id)
                  .filter(PracticeAttempt.user_id == user.id,
                          PracticeAttempt.service_namespace == space)
                  .first())
        if exists is not None:
            engaged.add(space)
    return engaged


def _adaptive_items(db: DbSession, user, *, namespace, course_id, exam_module_id, language,
                    engaged: set[str]):
    from learning import adaptive as adaptive_service

    items = []
    for space in SPACES:
        if space not in engaged:
            continue
        if namespace and space != namespace:
            continue
        if space == COURSE and (exam_module_id or language):
            continue
        if space == EXAM and (course_id or language):
            continue
        if space == PROG and (course_id or exam_module_id):
            continue
        # a practice recommendation needs the space's OWN scope: a course agenda without a
        # course (or an exam agenda without a module) recommends nothing rather than guessing
        # which course/module was meant. Plan and review items still come from their own rows.
        if space == COURSE and not course_id:
            continue
        if space == EXAM and not exam_module_id:
            continue
        try:
            # emit_event=False: the learner asked for an AGENDA, not a selection. The
            # selection facts belong to the /adaptive/practice surface; writing one on every
            # agenda read would be event noise, not a new fact.
            selection = adaptive_service.select_candidates(
                db, user, service_key=space, course_id=course_id,
                exam_module_id=exam_module_id, language=language, limit=MAX_PER_SOURCE,
                emit_event=False)
        except adaptive_service.AdaptiveRefusal:
            continue                       # a space without a scope is simply not included
        for candidate in selection["candidates"]:
            if candidate["reason"] == adaptive_service.REASON_COVERAGE_GAP:
                reason = REASON_UNSEEN_COVERAGE
            else:
                reason = REASON_ADAPTIVE_RECOMMENDATION
            domain = {"service_namespace": space, "course_id": course_id,
                      "exam_module_id": exam_module_id, "language": language}
            if space == EXAM:
                domain["exam_module_id"] = exam_module_id or None
            items.append({
                "action_type": ACTION_PRACTICE,
                "service_namespace": space,
                "domain_context": {key: value for key, value in domain.items()
                                   if key != "service_namespace" and value is not None},
                "source_type": candidate["source_type"],
                "source_id": candidate["question_source_id"],
                "title": candidate["label"] or "练习题",
                "summary": selection["reasons"].get(candidate["reason"], candidate["reason"]),
                "priority_reason": reason,
                "deep_link": _deep_link(domain, kind="practice",
                                        source_id=candidate["question_source_id"]),
                "due_at": None,
                "facts": {"adaptive_reason": candidate["reason"],
                          "policy_version": selection["policy_version"],
                          **candidate["facts"]},
                "status": "open",
                "question_identity": {
                    "question_source_type": candidate["source_type"],
                    "question_source_id": candidate["question_source_id"],
                    "question_scope_key": "",
                },
            })
    return items


# ---------------------------------------------------------------- the agenda

def _identity(item: dict) -> tuple:
    """An item's identity: WHICH object, in WHICH domain. Never its title or position."""
    domain = item["domain_context"] or {}
    return (item["service_namespace"], domain.get("course_id"),
            domain.get("exam_module_id"), domain.get("language"),
            item["source_type"], item["source_id"])


def _question_identity(item: dict) -> tuple | None:
    """The QUESTION an item is about, when it names one.

    A wrong-answer item and a practice recommendation can point at the SAME question from two
    sources. They are the same thing to do, so only the higher-priority one is shown — the
    other is counted as deduplicated rather than silently repeated.
    """
    question = item.get("question_identity") or {}
    source_type = str(question.get("question_source_type") or "").strip()
    source_id = str(question.get("question_source_id") or "").strip()
    if not source_type or not source_id:
        return None
    domain = item["domain_context"] or {}
    return (item["service_namespace"], domain.get("course_id"),
            domain.get("exam_module_id"), domain.get("language"), source_type, source_id)


def _sort_key(item: dict):
    rank = _PRIORITY_RANK.get(item["priority_reason"], 99)
    return (rank, item.get("due_at") or "9999", item["source_type"],
            item["source_id"].zfill(12))


def build_agenda(db: DbSession, user, *, service_key=None, course_id=None,
                 exam_module_id=None, language=None, limit: int = DEFAULT_LIMIT) -> dict:
    """The caller's next actions, in policy order, from facts that already exist."""
    namespace = None
    if service_key:
        try:
            namespace = normalize_service_namespace(service_key)
        except ValueError as exc:
            raise AgendaRefusal("unknown_space", str(exc)) from None
        if namespace not in SPACES:
            raise AgendaRefusal("unknown_space", f"议程暂不支持该学习空间: {namespace}")

    safe_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    plan_items, unattributed = _plan_items(
        db, user, namespace=namespace, course_id=course_id,
        exam_module_id=exam_module_id, language=language)
    review_items = _review_items(
        db, user, namespace=namespace, course_id=course_id,
        exam_module_id=exam_module_id, language=language)
    adaptive_items = _adaptive_items(
        db, user, namespace=namespace, course_id=course_id,
        exam_module_id=exam_module_id, language=language,
        engaged=_engaged_spaces(db, user))

    # ONE object appears ONCE: the higher-priority source wins, the other is counted. The same
    # question reached from two sources collapses the same way.
    merged: dict[tuple, dict] = {}
    by_question: dict[tuple, tuple] = {}
    deduped = 0
    for item in plan_items + review_items + adaptive_items:
        key = _identity(item)
        question_key = _question_identity(item)
        if question_key is not None and question_key in by_question:
            key = by_question[question_key]
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            if question_key is not None:
                by_question[question_key] = key
            continue
        deduped += 1
        if _sort_key(item) < _sort_key(existing):
            merged[key] = item
    ordered = sorted(merged.values(), key=_sort_key)
    window = ordered[:safe_limit]

    by_namespace: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for item in ordered:
        by_namespace[item["service_namespace"]] = \
            by_namespace.get(item["service_namespace"], 0) + 1
        by_reason[item["priority_reason"]] = by_reason.get(item["priority_reason"], 0) + 1

    return {
        "policy_version": AGENDA_POLICY_VERSION,
        "generated_at": _iso(_now()),
        "items": window,
        "total_items": len(ordered),
        "source_summary": {
            "plan_tasks": len(plan_items),
            "review_items": len(review_items),
            "adaptive_candidates": len(adaptive_items),
            "unattributable_plan_tasks": unattributed,
            "deduplicated": deduped,
        },
        "by_namespace": by_namespace,
        "by_reason": by_reason,
        "priority_order": list(PRIORITY_ORDER),
        "filters": {"service_key": namespace, "course_id": course_id,
                    "exam_module_id": exam_module_id, "language": language},
        "semantics": SEMANTICS,
    }


def explain_agenda(db: DbSession, user, **filters) -> dict:
    """Why these items, in this order — the policy and the facts behind every position."""
    agenda = build_agenda(db, user, limit=filters.pop("limit", DEFAULT_LIMIT), **filters)
    return {
        "policy_version": AGENDA_POLICY_VERSION,
        "priority_order": list(PRIORITY_ORDER),
        "priority_rules": {
            REASON_OVERDUE_PLAN_TASK: "计划任务已过截止日期（来自任务自身的 due_date）",
            REASON_DUE_REVIEW: "复习项已到期（存储或策略计算的到期日）",
            REASON_REPEATED_WRONG: "反复做错的错题状态（wrong_count >= 2）",
            REASON_NEEDS_WORK: "有未订正的错题或需要加强的练习",
            REASON_CURRENT_PLAN_TASK: "计划内尚未完成、未逾期的任务",
            REASON_ADAPTIVE_RECOMMENDATION: "自适应选题给出的练习建议（含原因码）",
            REASON_UNSEEN_COVERAGE: "该知识点尚无任何学习记录",
        },
        "explanation_of_order": (
            "items are ranked by the fixed ladder above, then by earliest due date, then by "
            "source/id — deterministic for the same stored facts. No model decides the order."),
        "completion_paths": {
            reason: RESOLVED_BY[reason] for reason in PRIORITY_ORDER
        },
        "why_the_next_read_changes": (
            "an item disappears when its OWN fact changes (a review completed, a task "
            "completed, an attempt recorded); the agenda re-reads those facts on every call "
            "and holds no state of its own"),
        "agenda": agenda,
    }
