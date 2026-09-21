"""Structured Learning Report — deterministic metrics FIRST, AI narrative second.

THE REPORT IS FREE; THE NARRATIVE IS A CAPABILITY
-------------------------------------------------
The structured half costs nothing and needs no entitlement: it is the learner's own data,
computed. The narrative is the only part that spends credits, it is OFF unless explicitly
requested, and when it cannot be produced (tier, usage or a technical failure) the report is
returned anyway with ``narrative: null`` and the reason in ``narrative_error``. A missing
narrative is STATED, never simulated.

THE ORDER IS THE CONTRACT
-------------------------
    DB / Records / Review / State  →  deterministic structured metrics  →  ReportData
                                                                            ↓
                                                              optional LLM narrative

Every NUMBER in a report is computed by this module from stored rows, by SQL, at request
time. The language model never computes a metric and never sees the raw study history: when a
narrative is requested, it receives the ReportData — the already-computed facts — and is asked
to write prose over exactly that. A model that "feels" how the learner is doing is exactly what
this ordering forbids, and the prompt in ``prompts.build_report_narrative_messages`` says so.

MISSING IS NOT ZERO
-------------------
A metric that does not exist for a learning space (programming run/test counts inside a course
report) is reported as ``null`` with a reason in ``data_coverage.unavailable``. A metric that
exists and is zero because nothing happened in the window is reported as 0 — that is a fact,
not a fabrication. Nothing is ever filled in with a plausible number.

HIGHLIGHTS ARE RULES, NOT INFERENCES
------------------------------------
``highlights`` and ``attention_items`` are produced by named, deterministic rules over the
metrics, and every item says so (``origin: "deterministic"``, plus the rule id). The narrative
is the only AI-produced part of a report, it is labelled ``origin: "ai"``, and it is never
merged into the metric or highlight arrays.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace, normalize_service_namespace

logger = logging.getLogger("learning.report")

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

CAPABILITY = "report.generate"
DEFAULT_PERIOD_DAYS = 7
MAX_PERIOD_DAYS = 90
MAX_RECENT_EVENTS = 10

ORIGIN_DETERMINISTIC = "deterministic"
ORIGIN_AI = "ai"

BLOCK_ACTIVITY = "activity"
BLOCK_PRACTICE = "practice"
BLOCK_REVIEW = "review"
BLOCK_PLAN = "plan"
BLOCK_MATERIALS = "materials"
BLOCK_PROGRAMMING = "programming"


class ReportRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


# ---------------------------------------------------------------- window & context

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _window(period_days) -> tuple[datetime, datetime, float]:
    try:
        days = int(period_days)
    except (TypeError, ValueError):
        days = DEFAULT_PERIOD_DAYS
    days = max(1, min(days, MAX_PERIOD_DAYS))
    end = _now()
    start = end - timedelta(days=days)
    return start, end, start.replace(tzinfo=timezone.utc).timestamp()


def build_context(user, space: str, *, course_id=None, exam_module_id=None, language=None):
    """The canonical LearningContext for the report's space (and the identity it states)."""
    if space == COURSE:
        from learning.spaces.course_learning.context import build_course_context, normalize_course_id
        if not course_id:
            raise ReportRefusal("course_required", "课程学习报告需要 course_id")
        key = normalize_course_id(course_id)
        return build_course_context(user, course_id=key), {"service_namespace": space,
                                                          "course_id": key}
    if space == EXAM:
        from learning.spaces.exam_prep.context import cs408_context
        context = cs408_context(user, module_key=exam_module_id)
        return context, {"service_namespace": space,
                         "exam_subject_id": context.exam_subject_id,
                         "exam_module_id": context.exam_module_id}
    from learning.spaces.programming.context import build_programming_context, normalize_language
    context = build_programming_context(user, language=language)
    return context, {"service_namespace": space,
                     "programming_language": normalize_language(language)}


# ---------------------------------------------------------------- metric blocks

def _activity_block(db: DbSession, user, space: str, start_epoch: float) -> dict:
    """Events in the window, by type, with the number of distinct study days."""
    from data_plane.models import LearningEvent

    base = db.query(LearningEvent).filter(
        LearningEvent.user_id == user.id, LearningEvent.service_key == space,
        LearningEvent.occurred_at >= start_epoch)
    total = base.count()
    days = (db.query(func.count(func.distinct(func.strftime(
        "%Y-%m-%d", LearningEvent.occurred_at, "unixepoch"))))
        .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == space,
                LearningEvent.occurred_at >= start_epoch).scalar() or 0)
    by_type = {event_type: count for event_type, count in
               db.query(LearningEvent.event_type, func.count(LearningEvent.event_id))
               .filter(LearningEvent.user_id == user.id,
                       LearningEvent.service_key == space,
                       LearningEvent.occurred_at >= start_epoch)
               .group_by(LearningEvent.event_type).all()}
    return {"events": int(total), "active_days": int(days), "by_event_type": by_type}


def _practice_block(db: DbSession, user, space: str, start: datetime,
                    *, course_id=None) -> dict:
    """Factual practice outcomes in the window — the tri-state, never collapsed."""
    from learning.practice.models import PracticeAttempt

    q = (db.query(
            func.count(PracticeAttempt.id),
            func.sum(case((PracticeAttempt.correct.is_(True), 1), else_=0)),
            func.sum(case((PracticeAttempt.correct.is_(False), 1), else_=0)))
         .filter(PracticeAttempt.user_id == user.id,
                 PracticeAttempt.service_namespace == space,
                 PracticeAttempt.submitted_at.isnot(None),
                 PracticeAttempt.submitted_at >= start))
    if course_id:
        q = q.filter(func.json_extract(PracticeAttempt.question_ref_json,
                                       "$.context.course_id") == str(course_id))
    total, correct, incorrect = q.one()
    attempts = int(total or 0)
    correct_count = int(correct or 0)
    incorrect_count = int(incorrect or 0)
    return {
        "attempts": attempts,
        "factual_correct": correct_count,
        "factual_incorrect": incorrect_count,
        # an ungraded attempt is neither: it is counted, not scored
        "ungraded": attempts - correct_count - incorrect_count,
    }


def _review_block(db: DbSession, user, space: str) -> dict:
    """The learner's outstanding review work in this space (the same projection /review uses)."""
    from learning import review as review_service

    summary = review_service.review_summary(db, user, service_namespace=space)
    return {
        "total": int(summary["total"]),
        "by_status": dict(summary["by_status"]),
        "by_source": dict(summary["by_source"]),
    }


def _plan_keys(space: str, *, course_id=None, exam_module_id=None, language=None) -> tuple:
    """(exact subject keys, resolved module) for this space's plan rows."""
    if space == COURSE:
        from main import _course_learning_task_subject_key   # lazy: one shared derivation
        return ([_course_learning_task_subject_key(course_id)], None)
    if space == PROG:
        from learning.spaces.programming.context import normalize_language
        return ([f"programming:{normalize_language(language)}"], None)
    return ([], exam_module_id)


def _plan_block(db: DbSession, user, space: str, *, course_id=None, exam_module_id=None,
                language=None) -> dict | None:
    """Task counts from the shared per-direction task table.

    A space whose plan tasks cannot be attributed to it returns ``None`` — "not this space's
    plan" — rather than a zero that would look like an empty plan.
    """
    from models import ExamStudyPlanTask

    keys, module = _plan_keys(space, course_id=course_id, exam_module_id=exam_module_id,
                              language=language)
    rows = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username).all())
    if keys:
        scoped = [row for row in rows if (row.subject_key or "") in set(keys)]
    elif module:
        from learning.spaces.exam_prep.scope import resolve_cs408_module
        wanted = resolve_cs408_module(module) or module
        scoped = [row for row in rows
                  if (resolve_cs408_module(row.subject_key) or (row.subject_key or "")) == wanted]
    else:
        return None

    today = _now().date()
    by_status: dict[str, int] = {}
    overdue = 0
    for row in scoped:
        status = (row.status or "not_started").strip() or "not_started"
        by_status[status] = by_status.get(status, 0) + 1
        due = _parse_due(row.due_date)
        if due is not None and due < today and status != "completed":
            overdue += 1
    completed = by_status.get("completed", 0)
    return {
        "total": len(scoped),
        "by_status": by_status,
        "completed": completed,
        "open": len(scoped) - completed,
        "overdue": overdue,
    }


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


def _materials_block(db: DbSession, user, space: str, start_epoch: float) -> dict | None:
    """Material activity from the canonical events. Not a programming concept → None there."""
    if space == PROG:
        return None
    from data_plane.models import LearningEvent

    material_id = func.json_extract(LearningEvent.item_snapshot_json, "$.material_id")
    opened = (db.query(func.count(LearningEvent.event_id))
              .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == space,
                      LearningEvent.event_type == "material_opened",
                      LearningEvent.occurred_at >= start_epoch).scalar() or 0)
    asked = (db.query(func.count(LearningEvent.event_id))
             .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == space,
                     LearningEvent.event_type == "material_asked",
                     LearningEvent.occurred_at >= start_epoch).scalar() or 0)
    touched = (db.query(func.count(func.distinct(material_id)))
               .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == space,
                       LearningEvent.event_type.in_(("material_opened", "material_asked")),
                       LearningEvent.occurred_at >= start_epoch).scalar() or 0)
    return {"opened": int(opened), "asked": int(asked),
            "distinct_materials": int(touched)}


def _programming_block(db: DbSession, user, space: str, start_epoch: float,
                       *, language=None) -> dict | None:
    """Runs / test checks / graded submissions. Only the programming space has these."""
    if space != PROG:
        return None
    from data_plane.models import LearningEvent

    exercise_id = func.json_extract(LearningEvent.item_snapshot_json, "$.exercise_id")

    def _count(event_type: str) -> int:
        q = (db.query(func.count(LearningEvent.event_id))
             .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == PROG,
                     LearningEvent.event_type == event_type,
                     LearningEvent.occurred_at >= start_epoch))
        if language:
            q = q.filter(func.json_extract(LearningEvent.item_snapshot_json,
                                           "$.programming_language") == str(language))
        return int(q.scalar() or 0)

    def _submitted(correct: bool) -> int:
        q = (db.query(func.count(LearningEvent.event_id))
             .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == PROG,
                     LearningEvent.event_type == "code_submitted",
                     LearningEvent.correct.is_(correct),
                     LearningEvent.occurred_at >= start_epoch))
        if language:
            q = q.filter(func.json_extract(LearningEvent.item_snapshot_json,
                                           "$.programming_language") == str(language))
        return int(q.scalar() or 0)

    exercises = (db.query(func.count(func.distinct(exercise_id)))
                 .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == PROG,
                         LearningEvent.occurred_at >= start_epoch).scalar() or 0)
    return {
        "runs": _count("code_run"),
        "tests": _count("code_tested"),
        "submissions": _count("code_submitted"),
        "submissions_passed": _submitted(True),
        "submissions_failed": _submitted(False),
        "distinct_exercises": int(exercises),
    }


def _recent_events(db: DbSession, user, space: str, start_epoch: float) -> list[dict]:
    """The newest events of the window — references and timing, never payload text."""
    from data_plane.models import LearningEvent
    from learning.records import taxonomy

    rows = (db.query(LearningEvent)
            .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == space,
                    LearningEvent.occurred_at >= start_epoch)
            .order_by(LearningEvent.occurred_at.desc())
            .limit(MAX_RECENT_EVENTS).all())
    return [{
        "event_type": row.event_type,
        "category": taxonomy.category_for(row.event_type),
        "occurred_at": _iso(datetime.utcfromtimestamp(row.occurred_at)),
    } for row in rows]


# ---------------------------------------------------------------- rules

def _highlights(metrics: dict) -> list[dict]:
    out = []
    activity = metrics.get(BLOCK_ACTIVITY) or {}
    practice = metrics.get(BLOCK_PRACTICE) or {}
    plan = metrics.get(BLOCK_PLAN) or {}

    if practice.get("attempts"):
        out.append({"rule": "practice_attempts", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"本周期完成 {practice['attempts']} 次练习，"
                            f"其中做对 {practice.get('factual_correct', 0)} 次",
                    "metric": {"attempts": practice["attempts"],
                               "factual_correct": practice.get("factual_correct", 0)}})
    if activity.get("active_days"):
        out.append({"rule": "active_days", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"本周期有 {activity['active_days']} 天产生了学习记录",
                    "metric": {"active_days": activity["active_days"]}})
    if plan.get("completed"):
        out.append({"rule": "plan_completed", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"完成 {plan['completed']} 个计划任务",
                    "metric": {"completed": plan["completed"],
                               "total": plan.get("total", 0)}})
    metrics_prog = metrics.get(BLOCK_PROGRAMMING) or {}
    if metrics_prog.get("submissions_passed"):
        out.append({"rule": "programming_passed", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"编程练习通过 {metrics_prog['submissions_passed']} 次提交",
                    "metric": {"submissions_passed": metrics_prog["submissions_passed"]}})
    return out


def _attention_items(metrics: dict) -> list[dict]:
    out = []
    review = metrics.get(BLOCK_REVIEW) or {}
    plan = metrics.get(BLOCK_PLAN) or {}
    practice = metrics.get(BLOCK_PRACTICE) or {}

    wrong = int((review.get("by_source") or {}).get("wrong_answer", 0))
    if wrong:
        out.append({"rule": "wrong_answers_active", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"有 {wrong} 道错题尚未订正",
                    "metric": {"active_wrong_answers": wrong}})
    due = int((review.get("by_status") or {}).get("due", 0))
    if due:
        out.append({"rule": "review_due", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"有 {due} 个知识点已到复习时间",
                    "metric": {"review_due": due}})
    if plan.get("overdue"):
        out.append({"rule": "plan_overdue", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"有 {plan['overdue']} 个计划任务已逾期",
                    "metric": {"overdue": plan["overdue"]}})
    if practice.get("factual_incorrect"):
        out.append({"rule": "practice_incorrect", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"本周期有 {practice['factual_incorrect']} 次练习做错",
                    "metric": {"factual_incorrect": practice["factual_incorrect"]}})
    needs_work = int((review.get("by_source") or {}).get("programming_exercise", 0))
    if needs_work:
        out.append({"rule": "programming_needs_work", "origin": ORIGIN_DETERMINISTIC,
                    "text": f"有 {needs_work} 个编程练习需要加强",
                    "metric": {"needs_work": needs_work}})
    return out


# ---------------------------------------------------------------- ReportData

def build_report_data(db: DbSession, user, *, space: str, period_days=DEFAULT_PERIOD_DAYS,
                      course_id=None, exam_module_id=None, language=None) -> dict:
    """ReportData: deterministic metrics over stored facts. NO model is involved."""
    start, end, start_epoch = _window(period_days)
    metrics: dict[str, dict | None] = {
        BLOCK_ACTIVITY: _activity_block(db, user, space, start_epoch),
        BLOCK_PRACTICE: _practice_block(db, user, space, start, course_id=course_id),
        BLOCK_REVIEW: _review_block(db, user, space),
        BLOCK_PLAN: _plan_block(db, user, space, course_id=course_id,
                                exam_module_id=exam_module_id, language=language),
        BLOCK_MATERIALS: _materials_block(db, user, space, start_epoch),
        BLOCK_PROGRAMMING: _programming_block(db, user, space, start_epoch, language=language),
    }
    unavailable = [
        {"block": block, "reason": "not_applicable_in_this_space"}
        for block, value in metrics.items() if value is None
    ]
    return {
        "report_period": {"days": (end - start).days, "start": _iso(start), "end": _iso(end)},
        "structured_metrics": metrics,
        "highlights": _highlights(metrics),
        "attention_items": _attention_items(metrics),
        "data_coverage": {
            "available_blocks": [block for block, value in metrics.items()
                                 if value is not None],
            "unavailable": unavailable,
            "recent_events": _recent_events(db, user, space, start_epoch),
            "notes": ("every figure is computed from stored rows in the report window; a "
                      "missing block is null, never zero"),
        },
    }


# ---------------------------------------------------------------- narrative

def compose_narrative(db: DbSession, user, report_data: dict, context) -> dict:
    """ONE model call over the ReportData — nothing else is put in front of the model."""
    from prompts import build_report_narrative_messages

    messages = build_report_narrative_messages(report_data)
    namespace = context.service_namespace
    if namespace == ServiceNamespace.EXAM_PREP:
        from learning.spaces.exam_prep.ai import execute_exam_ai as execute
    elif namespace == ServiceNamespace.PROGRAMMING:
        from learning.spaces.programming.ai import execute_programming_ai as execute
    else:
        from learning.spaces.course_learning.ai import execute_course_ai as execute

    result = execute(db, user, CAPABILITY, messages, learning_context=context,
                     max_tokens=900, temperature=0.4)
    return {
        "text": result.content or "",
        "origin": ORIGIN_AI,
        "capability": CAPABILITY,
        "request_id": result.request_id,
        "usage": {
            "estimated_credits": result.estimated_credits,
            "actual_credits": result.actual_credits,
            "input_tokens": (result.usage or {}).get("input_tokens"),
            "output_tokens": (result.usage or {}).get("output_tokens"),
            "usage_source": (result.usage or {}).get("usage_source"),
        },
    }


def generate_learning_report(db: DbSession, user, *, service_key: str,
                             period_days=DEFAULT_PERIOD_DAYS, course_id=None,
                             exam_module_id=None, language=None,
                             include_narrative: bool = False) -> dict:
    """The structured report, plus an optional narrative built strictly on top of it."""
    try:
        space = normalize_service_namespace(service_key or COURSE)
    except ValueError as exc:
        raise ReportRefusal("unknown_space", str(exc)) from None
    if space not in (COURSE, EXAM, PROG):
        raise ReportRefusal("unknown_space", f"报告暂不支持该学习空间: {space}")

    context, identity = build_context(user, space, course_id=course_id,
                                      exam_module_id=exam_module_id, language=language)
    report_data = build_report_data(db, user, space=space, period_days=period_days,
                                    course_id=identity.get("course_id"),
                                    exam_module_id=identity.get("exam_module_id"),
                                    language=identity.get("programming_language"))

    report_id = uuid.uuid4().hex
    narrative = None
    narrative_error = None
    if include_narrative:
        try:
            narrative = compose_narrative(db, user, report_data, context)
        except HTTPException as exc:
            # THE REPORT IS THE DELIVERABLE; the narrative is an add-on. A narrative that
            # cannot be produced is ABSENT and STATED — never faked, and never a reason to
            # withhold the deterministic report the learner can already read for free.
            # (403 = the tier does not hold the capability; 429 = the boundary's usage answer,
            # which is also what a technical failure maps to on this path; other codes are
            # reported as themselves.)
            if exc.status_code == 403:
                narrative_error = "capability_not_permitted"
            else:
                narrative_error = f"http_{exc.status_code}"
            logger.warning("learning.report_narrative_failed status=%s", exc.status_code)

    _emit(user, report_id=report_id, report_data=report_data, space=space, context=context,
          narrative=bool(narrative), request_id=(narrative or {}).get("request_id"))
    return {
        "report_id": report_id,
        **report_data,
        "context": identity,
        "narrative": narrative,
        "narrative_error": narrative_error,
        "generated_at": _iso(_now()),
    }


def _emit(user, *, report_id, report_data, space, context, narrative, request_id) -> None:
    """One canonical fact per generated report. Failure-isolated."""
    try:
        from learning.records import producers
        producers.emit_report_generated(
            user_id=user.id, report_id=report_id,
            period_days=report_data["report_period"]["days"], service_namespace=space,
            metric_blocks=report_data["data_coverage"]["available_blocks"],
            narrative=narrative, request_id=request_id, learning_context=context,
            occurred_at=None, source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("learning.report_event_failed error=%s", type(exc).__name__)
