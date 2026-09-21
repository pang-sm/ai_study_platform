"""Dynamic Planning — the AI proposes, the LEARNER applies. Two separate actions, on purpose.

PROPOSE ≠ APPLY
---------------
    current plan → deterministic context builder → AI proposal → diff → user accepts → apply

``propose_adjustment`` WRITES NOTHING. It reads the plan, the review projection, the practice
facts and the recent events of one learning space, asks a model for a bounded list of task
changes, validates every one of them against the plan it just read, and returns them together
with the plan's IDENTITY (a deterministic fingerprint of the plan's current state).

``apply_adjustment`` is the only thing that mutates a plan. It re-verifies, at apply time,
that the caller still owns the tasks and that the plan is still EXACTLY the plan the proposal
was built from. A proposal whose identity no longer matches is refused as stale — so an old
proposal can never overwrite a plan the learner has changed since.

WHAT THE MODEL MAY PROPOSE
--------------------------
A closed set of two operations on the SAME per-direction task table the plan already uses:

    create_task   a new task for this space (title + type + optional due date)
    update_task   a change to one of the caller's OWN tasks in this space

Anything else is dropped, and a proposal that survives validation with nothing left is
refused rather than applied as an empty change.

WHY USER-TRIGGERED ONLY
-----------------------
There is no background planner and no auto-apply path: planning is the learner's, and a
system that rewrote their plan while they slept would be a product decision nobody asked for.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace, normalize_service_namespace

logger = logging.getLogger("learning.plan_adjustment")

CAPABILITY = "planning.adjust"
MAX_CHANGES = 8
MAX_TITLE_CHARS = 200
MAX_REASON_CHARS = 600
MAX_CONTEXT_TASKS = 40

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

OP_CREATE = "create_task"
OP_UPDATE = "update_task"
ALLOWED_OPS = (OP_CREATE, OP_UPDATE)
ALLOWED_TASK_TYPES = ("knowledge", "review", "practice", "custom")

STATUS_VALUES = ("not_started", "in_progress", "completed")


class PlanAdjustmentRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


class StaleProposal(PlanAdjustmentRefusal):
    """The plan changed between the proposal and the apply."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _bounded(value, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit]


# ---------------------------------------------------------------- plan scope & identity

def plan_subject_key(space: str, *, course_id=None, exam_module_id=None, language=None) -> str:
    """The exact task-table key this space's plan lives under (one shared derivation)."""
    if space == COURSE:
        from main import _course_learning_task_subject_key   # lazy: the ONE derivation
        if not course_id:
            raise PlanAdjustmentRefusal("course_required", "课程计划调整需要 course_id")
        return _course_learning_task_subject_key(course_id)
    if space == PROG:
        from learning.spaces.programming.context import normalize_language
        return f"programming:{normalize_language(language)}"
    if not exam_module_id:
        raise PlanAdjustmentRefusal("module_required", "考试计划调整需要 exam_module_id")
    return str(exam_module_id).strip()


def _plan_tasks(db: DbSession, user, space: str, *, course_id=None, exam_module_id=None,
                language=None) -> list:
    """The caller's OWN tasks of this space's plan — never another learner's, never another
    direction's."""
    from models import ExamStudyPlanTask

    key = plan_subject_key(space, course_id=course_id, exam_module_id=exam_module_id,
                           language=language)
    rows = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username)
            .order_by(ExamStudyPlanTask.id.asc()).all())
    if space == EXAM:
        from learning.spaces.exam_prep.scope import resolve_cs408_module
        wanted = resolve_cs408_module(key) or key
        return [row for row in rows
                if (resolve_cs408_module(row.subject_key) or (row.subject_key or "")) == wanted]
    return [row for row in rows if (row.subject_key or "") == key]


def plan_identity(db: DbSession, user, space: str, *, course_id=None, exam_module_id=None,
                  language=None) -> dict:
    """A deterministic fingerprint of the plan's CURRENT state.

    Built from the caller's own tasks only, and from the fields a proposal can change — so any
    edit, addition or removal between propose and apply changes the identity and makes the
    stale proposal unusable (which is the point).
    """
    tasks = _plan_tasks(db, user, space, course_id=course_id, exam_module_id=exam_module_id,
                        language=language)
    fingerprint = hashlib.sha256(json.dumps(
        [[row.id, row.title or "", row.task_type or "", row.status or "",
          row.due_date or "", _iso(row.updated_at)] for row in tasks],
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:32]
    return {
        "subject_key": plan_subject_key(space, course_id=course_id,
                                        exam_module_id=exam_module_id, language=language),
        "identity": fingerprint,
        "task_count": len(tasks),
        "latest_update": max((_iso(row.updated_at) or "" for row in tasks), default=None),
    }


# ---------------------------------------------------------------- deterministic context

def build_plan_context(db: DbSession, user, space: str, *, course_id=None,
                       exam_module_id=None, language=None) -> dict:
    """Everything the proposal may reason over — all of it already stored."""
    from learning import review as review_service

    tasks = _plan_tasks(db, user, space, course_id=course_id, exam_module_id=exam_module_id,
                        language=language)
    today = _now().date()
    task_views = []
    overdue = completed = 0
    for row in tasks[:MAX_CONTEXT_TASKS]:
        due = _parse_due(row.due_date)
        status = (row.status or "not_started").strip() or "not_started"
        if status == "completed":
            completed += 1
        elif due is not None and due < today:
            overdue += 1
        task_views.append({
            "task_id": row.id,
            "title": _bounded(row.title, 120),
            "task_type": row.task_type,
            "status": status,
            "due_date": row.due_date or None,
        })

    review = review_service.review_summary(db, user, service_namespace=space)
    practice = _practice_counts(db, user, space)
    return {
        "plan": {"identity": plan_identity(
                     db, user, space, course_id=course_id,
                     exam_module_id=exam_module_id, language=language)["identity"],
                 "total": len(tasks), "completed": completed, "overdue": overdue,
                 "tasks": task_views,
                 "truncated": len(tasks) > MAX_CONTEXT_TASKS},
        "review": {"total": review["total"], "by_status": review["by_status"],
                   "by_source": review["by_source"]},
        "practice": practice,
        "recent_events": _recent_event_types(db, user, space),
    }


def _practice_counts(db: DbSession, user, space: str) -> dict:
    from learning.practice.models import PracticeAttempt
    from sqlalchemy import case, func

    total, correct, incorrect = (
        db.query(func.count(PracticeAttempt.id),
                 func.sum(case((PracticeAttempt.correct.is_(True), 1), else_=0)),
                 func.sum(case((PracticeAttempt.correct.is_(False), 1), else_=0)))
        .filter(PracticeAttempt.user_id == user.id,
                PracticeAttempt.service_namespace == space).one())
    attempts = int(total or 0)
    right = int(correct or 0)
    wrong = int(incorrect or 0)
    return {"attempts": attempts, "factual_correct": right, "factual_incorrect": wrong,
            "ungraded": attempts - right - wrong}


def _recent_event_types(db: DbSession, user, space: str, limit: int = 15) -> list[str]:
    from data_plane.models import LearningEvent

    rows = (db.query(LearningEvent.event_type)
            .filter(LearningEvent.user_id == user.id, LearningEvent.service_key == space)
            .order_by(LearningEvent.occurred_at.desc()).limit(limit).all())
    return [row[0] for row in rows]


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


# ---------------------------------------------------------------- validation

def _clean_changes(raw, task_ids: set) -> tuple[list[dict], list[dict]]:
    """(accepted, dropped) — every change is validated against THIS plan's own tasks."""
    accepted, dropped = [], []
    for item in (raw or [])[:MAX_CHANGES * 2]:
        if not isinstance(item, dict):
            dropped.append({"reason": "not_an_object"})
            continue
        op = str(item.get("op") or "").strip()
        if op not in ALLOWED_OPS:
            dropped.append({"reason": "unknown_op", "op": op})
            continue
        if op == OP_CREATE:
            title = _bounded(item.get("title"), MAX_TITLE_CHARS)
            if not title:
                dropped.append({"reason": "missing_title"})
                continue
            task_type = str(item.get("task_type") or "knowledge").strip()
            if task_type not in ALLOWED_TASK_TYPES:
                task_type = "knowledge"
            accepted.append({"op": OP_CREATE, "title": title, "task_type": task_type,
                             "due_date": _bounded(item.get("due_date"), 30) or None,
                             "reason": _bounded(item.get("reason"), 200)})
        else:
            task_id = item.get("task_id")
            if task_id not in task_ids:
                # not this plan's task — never touch it
                dropped.append({"reason": "task_not_in_this_plan", "task_id": task_id})
                continue
            change = {"op": OP_UPDATE, "task_id": task_id,
                      "reason": _bounded(item.get("reason"), 200)}
            if item.get("due_date") is not None:
                change["due_date"] = _bounded(item.get("due_date"), 30) or None
            if item.get("title") is not None:
                title = _bounded(item.get("title"), MAX_TITLE_CHARS)
                if title:
                    change["title"] = title
            status = str(item.get("status") or "").strip()
            if status in STATUS_VALUES:
                change["status"] = status
            if set(change) <= {"op", "task_id", "reason"}:
                dropped.append({"reason": "no_supported_field", "task_id": task_id})
                continue
            accepted.append(change)
        if len(accepted) >= MAX_CHANGES:
            break
    return accepted, dropped


# ---------------------------------------------------------------- propose

def propose_adjustment(db: DbSession, user, *, service_key: str, goal: str = "",
                       course_id=None, exam_module_id=None, language=None) -> dict:
    """Ask for a bounded adjustment. WRITES NOTHING — the plan is not touched."""
    space = _space_of(service_key)
    context_facts = build_plan_context(db, user, space, course_id=course_id,
                                       exam_module_id=exam_module_id, language=language)
    from prompts import build_plan_adjustment_messages
    messages = build_plan_adjustment_messages(context_facts, goal=_bounded(goal, 300))

    execution_context = _context_for(user, space, course_id=course_id,
                                     exam_module_id=exam_module_id, language=language)
    result = _execute(db, user, space, execution_context, messages)

    parsed = _extract_json_object(result.content or "")
    if parsed is None:
        raise PlanAdjustmentRefusal("unusable_proposal", "模型未返回可用的计划建议")
    reason = _bounded(parsed.get("reason"), MAX_REASON_CHARS)
    plan_task_ids = {task["task_id"] for task in context_facts["plan"]["tasks"]}
    accepted, dropped = _clean_changes(parsed.get("changes"), plan_task_ids)
    if not accepted:
        raise PlanAdjustmentRefusal("empty_proposal", "模型没有给出可应用的调整")

    proposal_id = uuid.uuid4().hex
    identity = context_facts["plan"]["identity"]
    _emit_proposed(user, proposal_id=proposal_id, change_count=len(accepted),
                   identity=identity, space=space, context=execution_context,
                   request_id=result.request_id)
    usage = result.usage or {}
    return {
        "proposal_id": proposal_id,
        "capability": CAPABILITY,
        "request_id": result.request_id,
        "service_namespace": space,
        "subject_key": plan_subject_key(space, course_id=course_id,
                                        exam_module_id=exam_module_id, language=language),
        "plan_identity": identity,
        "reason": reason,
        "proposed_changes": accepted,
        "affected_tasks": [change["task_id"] for change in accepted
                           if change.get("task_id") is not None],
        "dropped_changes": dropped,
        "plan_snapshot": context_facts["plan"],
        "usage": {
            "estimated_credits": result.estimated_credits,
            "actual_credits": result.actual_credits,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "usage_source": usage.get("usage_source"),
        },
        "applies_to": ("POST /ai/plan-adjustment/apply 使用 plan_identity + proposed_changes "
                       "才会真正修改计划"),
        "generated_at": _now().isoformat(),
    }


# ---------------------------------------------------------------- apply

def apply_adjustment(db: DbSession, user, *, service_key: str, plan_identity_value: str,
                     changes: list[dict], proposal_id: str | None = None,
                     course_id=None, exam_module_id=None, language=None) -> dict:
    """Apply an ACCEPTED proposal. Ownership and the plan identity are re-verified HERE."""
    from models import ExamStudyPlanTask

    space = _space_of(service_key)
    current = plan_identity(db, user, space, course_id=course_id,
                            exam_module_id=exam_module_id, language=language)
    if not plan_identity_value or current["identity"] != plan_identity_value:
        raise StaleProposal("stale_proposal",
                            "计划已发生变化，请重新生成调整建议")
    tasks = _plan_tasks(db, user, space, course_id=course_id, exam_module_id=exam_module_id,
                        language=language)
    tasks_by_id = {row.id: row for row in tasks}
    accepted, dropped = _clean_changes(changes, {row.id: {"task_id": row.id} for row in tasks})
    if not accepted:
        raise PlanAdjustmentRefusal("empty_proposal", "没有可应用的调整")

    applied = 0
    for change in accepted:
        if change["op"] == OP_CREATE:
            db.add(ExamStudyPlanTask(
                username=user.username, subject_key=current["subject_key"],
                title=change["title"], task_type=change["task_type"],
                status="not_started", due_date=change.get("due_date")))
            applied += 1
            continue
        row = tasks_by_id.get(change["task_id"])
        if row is None:                       # ownership re-check per task
            dropped.append({"reason": "task_not_in_this_plan", "task_id": change["task_id"]})
            continue
        if "title" in change:
            row.title = change["title"]
        if "due_date" in change:
            row.due_date = change["due_date"]
        if "status" in change:
            row.status = change["status"]
        applied += 1
    db.commit()

    after = plan_identity(db, user, space, course_id=course_id,
                          exam_module_id=exam_module_id, language=language)
    _emit_applied(user, proposal_id=proposal_id, applied_count=applied,
                  identity=after["identity"], space=space,
                  course_id=course_id, exam_module_id=exam_module_id, language=language)
    return {
        "service_namespace": space,
        "subject_key": after["subject_key"],
        "applied_count": applied,
        "dropped_changes": dropped,
        "plan_identity": after["identity"],
        "plan_identity_before": plan_identity_value,
        "applied_at": _now().isoformat(),
    }


# ---------------------------------------------------------------- execution helpers

def _space_of(service_key: str) -> str:
    try:
        space = normalize_service_namespace(service_key or COURSE)
    except ValueError as exc:
        raise PlanAdjustmentRefusal("unknown_space", str(exc)) from None
    if space not in (COURSE, EXAM, PROG):
        raise PlanAdjustmentRefusal("unknown_space", f"计划调整暂不支持该学习空间: {space}")
    return space


def _context_for(user, space: str, *, course_id=None, exam_module_id=None, language=None):
    """The space's canonical LearningContext (the report module owns the ONE builder)."""
    from learning.report import build_context
    context, _identity = build_context(user, space, course_id=course_id,
                                       exam_module_id=exam_module_id, language=language)
    return context


def _execute(db: DbSession, user, space: str, context, messages: list[dict]):
    if context.service_namespace == ServiceNamespace.EXAM_PREP:
        from learning.spaces.exam_prep.ai import execute_exam_ai as execute
    elif context.service_namespace == ServiceNamespace.PROGRAMMING:
        from learning.spaces.programming.ai import execute_programming_ai as execute
    else:
        from learning.spaces.course_learning.ai import execute_course_ai as execute
    return execute(db, user, CAPABILITY, messages, learning_context=context,
                   max_tokens=900, temperature=0.3)


def _extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _emit_proposed(user, *, proposal_id, change_count, identity, space, context,
                   request_id) -> None:
    try:
        from learning.records import producers
        producers.emit_plan_adjustment_proposed(
            user_id=user.id, proposal_id=proposal_id, change_count=change_count,
            plan_identity=identity, service_namespace=space, request_id=request_id,
            learning_context=context, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_adjustment.proposed_event_failed error=%s", type(exc).__name__)


def _emit_applied(user, *, proposal_id, applied_count, identity, space, course_id,
                  exam_module_id, language) -> None:
    try:
        from learning.records import producers
        context = _context_for(user, space, course_id=course_id,
                               exam_module_id=exam_module_id, language=language)
        producers.emit_plan_adjustment_applied(
            user_id=user.id, proposal_id=proposal_id or "unknown",
            applied_count=applied_count, plan_identity=identity, service_namespace=space,
            learning_context=context, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_adjustment.applied_event_failed error=%s", type(exc).__name__)
