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
from learning.spaces.plan_task_types import plan_task_types

logger = logging.getLogger("learning.plan_adjustment")

CAPABILITY = "planning.adjust"
MAX_CHANGES = 8
MAX_TITLE_CHARS = 200
MAX_CONTEXT_TASKS = 40

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

OP_CREATE = "create_task"
OP_UPDATE = "update_task"
ALLOWED_OPS = (OP_CREATE, OP_UPDATE)
# The task kind used when a proposal does not name one. Legal in every space's vocabulary.
DEFAULT_TASK_TYPE = "knowledge"

# The update fields a planning suggestion may touch, and nothing else.
#
# `status` is deliberately NOT here. Marking a task in_progress/completed is a claim about what
# the LEARNER has already done, and a planning model has no standing to make it: it would write
# fabricated progress into the learner's real plan. Progress is a recorded fact, not a suggestion.
UPDATABLE_FIELDS = ("due_date", "title")

# ---------------------------------------------------------------- what a change MEANS

# The learner-facing meaning of a change. DERIVED by this module from the validated mutation, and
# never authored by the model — which is what makes the label on screen and the write that
# happens the same thing by construction rather than by agreement.
TYPE_INSERT = "INSERT"
TYPE_RESCHEDULE = "RESCHEDULE"
TYPE_REPLACE = "REPLACE"
# Net-effect classification of the WHOLE proposal, over the same validated changes.
TYPE_REDUCE_LOAD = "REDUCE_LOAD"
TYPE_INCREASE_LOAD = "INCREASE_LOAD"

SUPPORTED_ADJUSTMENT_TYPES = (TYPE_INSERT, TYPE_RESCHEDULE, TYPE_REPLACE,
                              TYPE_REDUCE_LOAD, TYPE_INCREASE_LOAD)

# Named so the refusal is legible rather than a generic unknown-op drop:
#   REMOVE  — ExamStudyPlanTask has no soft-delete, and this feature deletes nothing.
#   REORDER — ExamStudyPlanTask has no sort_order/position; order is the row id.
UNSUPPORTED_OP_TYPES = {"remove_task": "REMOVE", "delete_task": "REMOVE", "drop_task": "REMOVE",
                        "reorder_tasks": "REORDER", "move_task": "REORDER",
                        "reorder": "REORDER"}
NOT_SUPPORTED_ADJUSTMENT_TYPES = ("REMOVE", "REORDER")

MAX_EVIDENCE = 2

# Direction words for a date move. `due_date` is a plain YYYY-MM-DD string on the model.
EARLIER = "earlier"
LATER = "later"

# ---------------------------------------------------------------- nothing to propose

# A model that proposes NOTHING has answered the question, and the answer is "your plan is fine".
# This used to be raised as `empty_proposal` and returned as HTTP 400, which read as an outage:
# the client could only map an unrecognised 400 onto "请求暂时不可用，请稍后重试。", so a learner
# whose plan needed no change — and, worse, a learner with no records at all — was told the
# service was broken. The real provider answers `{"changes": []}` routinely (measured 2026-09-29
# against the deployed model, for both an empty plan and a plan that was already on schedule), so
# this is the COMMON path, not an edge case.
#
# The outcome is therefore a successful response carrying a code and one learner-facing line.
OUTCOME_PROPOSED = "proposed"
OUTCOME_NO_RECORD = "no_learning_record"
OUTCOME_NO_CHANGE = "no_change_suggested"
OUTCOME_NOT_APPLICABLE = "suggestion_not_applicable"

MESSAGE_NO_RECORD = "还没有足够学习记录。你可以先添加一个学习任务。"
MESSAGE_NO_CHANGE = "当前计划没有需要调整的地方。"
MESSAGE_NOT_APPLICABLE = "这次的建议里没有可以应用的内容，计划保持不变。"


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
                       exam_module_id=None, language=None, tasks=None) -> dict:
    """Everything the proposal may reason over — all of it already stored.

    ``tasks`` may be supplied by a caller that has already read the plan, so one proposal reads
    the task table once rather than twice.
    """
    from learning import review as review_service

    if tasks is None:
        tasks = _plan_tasks(db, user, space, course_id=course_id,
                            exam_module_id=exam_module_id, language=language)
    today = _now().date()
    # Counted over the WHOLE plan, not over the (truncated) list the model is shown: "2 项已逾期"
    # is a claim about the learner's plan, and under-reporting it for a long plan would make the
    # figure on screen disagree with the plan it describes.
    overdue = completed = 0
    for row in tasks:
        due = _parse_due(row.due_date)
        status = (row.status or "not_started").strip() or "not_started"
        if status == "completed":
            completed += 1
        elif due is not None and due < today:
            overdue += 1

    task_views = [{
        "task_id": row.id,
        "title": _bounded(row.title, 120),
        "task_type": row.task_type,
        "status": (row.status or "not_started").strip() or "not_started",
        "due_date": row.due_date or None,
    } for row in tasks[:MAX_CONTEXT_TASKS]]

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

def _clean_changes(raw, tasks_by_id: dict, allowed_task_types: tuple) -> tuple[list[dict], list[dict]]:
    """(accepted, dropped) — every change is validated against THIS plan's own tasks.

    Each accepted change carries BOTH the mutation that will be applied and the display fields
    derived from it (`type` / `field` / `before` / `after`). They are the same object on purpose:
    a screen cannot show one change while the write performs another, because there is only one.

    `before` is READ FROM THE PLAN, never taken from the caller. A model (or a client) that
    claims a task's current date is something it is not cannot make that claim reach the UI or
    the write — the value shown is the value in the plan, or the change is dropped.
    """
    accepted, dropped = [], []

    def _keep(change: dict) -> bool:
        """Keep one change, unless the proposal is already at its bound."""
        if len(accepted) >= MAX_CHANGES:
            return False
        accepted.append(change)
        return True

    for item in (raw or [])[:MAX_CHANGES * 2]:
        if len(accepted) >= MAX_CHANGES:
            break
        if not isinstance(item, dict):
            dropped.append({"reason": "not_an_object"})
            continue
        op = str(item.get("op") or "").strip()
        if op in UNSUPPORTED_OP_TYPES:
            # Named explicitly: "this kind of change is not supported" is a different answer from
            # "I did not understand the op", and the learner-facing contract says which.
            dropped.append({"reason": "adjustment_type_not_supported",
                            "adjustment_type": UNSUPPORTED_OP_TYPES[op], "op": op})
            continue
        if op not in ALLOWED_OPS:
            dropped.append({"reason": "unknown_op", "op": op})
            continue

        if op == OP_CREATE:
            title = _bounded(item.get("title"), MAX_TITLE_CHARS)
            if not title:
                dropped.append({"reason": "missing_title"})
                continue
            task_type = str(item.get("task_type") or DEFAULT_TASK_TYPE).strip()
            # The kind must be one the TARGET SPACE can own and complete. Rewriting an
            # unsupported kind would put a task in the plan that was never proposed, so the
            # change is dropped and says why instead.
            if task_type not in allowed_task_types:
                dropped.append({"reason": "task_type_not_supported_in_space",
                                "task_type": task_type,
                                "allowed": list(allowed_task_types)})
                continue
            due = _bounded(item.get("due_date"), 30) or None
            if due is not None and _parse_due(due) is None:
                dropped.append({"reason": "invalid_due_date", "due_date": due})
                continue
            # A plan holds dated work, so a task with no day is not a task the plan can hold.
            # The model often has no basis for choosing one — so the change is KEPT as a
            # suggestion the learner completes, not silently discarded: the client is told the
            # date is still needed and must supply one before this can be applied.
            _keep({"op": OP_CREATE, "title": title, "task_type": task_type, "due_date": due,
                   "needs_due_date": due is None,
                   "type": TYPE_INSERT, "task_title": title, "field": "task",
                   "before": None, "after": due})
            continue

        task_id = item.get("task_id")
        current = tasks_by_id.get(task_id)
        if current is None:
            # not this plan's task — never touch it, never describe it
            dropped.append({"reason": "task_not_in_this_plan", "task_id": task_id})
            continue

        before_due = (current.get("due_date") or "").strip() or None
        before_title = (current.get("title") or "").strip()
        kept = 0
        complained = False

        if item.get("due_date") is not None:
            wanted_due = _bounded(item.get("due_date"), 30) or None
            if wanted_due is not None and _parse_due(wanted_due) is None:
                dropped.append({"reason": "invalid_due_date", "task_id": task_id,
                                "due_date": wanted_due})
                complained = True
            elif wanted_due != before_due and _keep(
                    {"op": OP_UPDATE, "task_id": task_id, "due_date": wanted_due,
                     "type": TYPE_RESCHEDULE, "task_title": before_title, "field": "due_date",
                     "before": before_due, "after": wanted_due,
                     "direction": _direction(before_due, wanted_due)}):
                kept += 1

        if item.get("title") is not None and len(accepted) < MAX_CHANGES:
            wanted_title = _bounded(item.get("title"), MAX_TITLE_CHARS)
            if not wanted_title:
                dropped.append({"reason": "empty_title", "task_id": task_id})
                complained = True
            elif wanted_title != before_title and _keep(
                    {"op": OP_UPDATE, "task_id": task_id, "title": wanted_title,
                     "type": TYPE_REPLACE, "task_title": before_title, "field": "title",
                     "before": before_title, "after": wanted_title}):
                kept += 1

        if kept == 0 and not complained:
            # The request named no updatable field, or named the value the plan already holds:
            # there is nothing to tell the learner, so nothing is shown and nothing is written.
            dropped.append({"reason": "no_supported_field", "task_id": task_id})

    return accepted, dropped


def _direction(before, after) -> str | None:
    """earlier / later for two date strings, when both are real dates."""
    first, second = _parse_due(before), _parse_due(after)
    if first is None or second is None or first == second:
        return None
    return EARLIER if second < first else LATER


# ---------------------------------------------------------------- what the learner reads

def _task_index(tasks) -> dict:
    """task id -> the fields a change may read. The ONLY source of a change's `before`."""
    return {row.id: {"title": row.title, "due_date": row.due_date,
                     "status": row.status, "task_type": row.task_type}
            for row in tasks}


def _day_delta(before, after) -> int | None:
    first, second = _parse_due(before), _parse_due(after)
    if first is None or second is None:
        return None
    return abs((second - first).days)


def _describe(change: dict) -> str:
    """One change, said the way a learner would say it."""
    title = change.get("task_title") or "计划中的一项任务"
    if change["type"] == TYPE_INSERT:
        return f"新增「{title}」"
    if change["type"] == TYPE_REPLACE:
        return f"把「{title}」替换为「{change.get('after') or '新标题'}」"
    if change.get("after") is None:
        return f"清除「{title}」的计划日期"
    days = _day_delta(change.get("before"), change.get("after"))
    if change.get("direction") == LATER:
        return f"把「{title}」推迟 {days} 天" if days else f"把「{title}」推迟"
    if change.get("direction") == EARLIER:
        return f"把「{title}」提前 {days} 天" if days else f"把「{title}」提前"
    return f"调整「{title}」的计划日期"


def _summary(changes: list[dict]) -> str:
    """The one-line headline. Derived from the same changes that will be applied."""
    if not changes:
        return ""
    head = _describe(changes[0])
    rest = len(changes) - 1
    return head if not rest else f"{head}，并另外调整 {rest} 项"


def _evidence(context: dict, changes: list[dict]) -> list[dict]:
    """Reasons a learner can check against their own records — real stored numbers only.

    Every item is a statement ABOUT A VALUE THE PLAN ALREADY HOLDS. Nothing here is inferred,
    predicted, or phrased as a judgement about the learner: there is no mastery, no error count
    the system did not record, and no estimate of time. An item whose number is zero is not a
    weaker reason — it is not a reason — so it is absent rather than restated as zero.

    Items that bear on what this proposal actually does are ranked first; ties go to the larger
    number. At most ``MAX_EVIDENCE`` are returned.
    """
    plan = context.get("plan") or {}
    review = context.get("review") or {}
    practice = context.get("practice") or {}
    by_status = review.get("by_status") or {}

    inserts = [change for change in changes if change["type"] == TYPE_INSERT]
    # An insert that is not a plain knowledge task bears on the review / practice evidence. Read
    # as "not knowledge" rather than a list of the other kinds, so a space's vocabulary can change
    # without this drifting out of step with it.
    inserts_study = any((change.get("task_type") or DEFAULT_TASK_TYPE) != DEFAULT_TASK_TYPE
                        for change in inserts)
    moves_later = any(change.get("direction") == LATER for change in changes)
    moves_earlier = any(change.get("direction") == EARLIER for change in changes)

    candidates: list[dict] = []

    overdue = int(plan.get("overdue") or 0)
    if overdue:
        candidates.append({"code": "plan_overdue", "metric": overdue,
                           "text": f"当前有 {overdue} 项任务已逾期",
                           "bears": moves_later or moves_earlier})

    due = int(by_status.get("due") or 0)
    if due:
        candidates.append({"code": "review_due", "metric": due,
                           "text": f"复习清单里有 {due} 项已经到期",
                           "bears": inserts_study or moves_earlier})

    incorrect = int(practice.get("factual_incorrect") or 0)
    if incorrect:
        candidates.append({"code": "practice_incorrect", "metric": incorrect,
                           "text": f"已记录的练习中有 {incorrect} 次做错",
                           "bears": bool(inserts)})

    total = int(plan.get("total") or 0)
    completed = int(plan.get("completed") or 0)
    if total:
        candidates.append({"code": "plan_progress", "metric": total - completed,
                           "text": f"当前计划共 {total} 项，已完成 {completed} 项",
                           "bears": bool(inserts) or moves_later})

    candidates.sort(key=lambda item: (item["bears"], item["metric"]), reverse=True)
    return [{"code": item["code"], "text": item["text"], "metric": item["metric"]}
            for item in candidates[:MAX_EVIDENCE]]


def _rationale(evidence: list[dict]) -> str:
    """The ONE reason this proposal rests on — the top-ranked evidence item, not a list of all.

    Joining every evidence item here would print the same sentence twice: the caller shows
    `evidence` beside the proposal, so a rationale that restated them would be the page saying
    one thing in two places. The learner needs the reason, once.
    """
    if not evidence:
        # No stored number bears on this change. Saying so is the honest answer; inventing a
        # reason would be the one thing this module must never do.
        return "这次调整只依据你计划里现有的任务，系统没有可用于判断进度的记录。"
    return f"{evidence[0]['text']}。"


def _has_learner_history(context_facts: dict) -> bool:
    """Does this learner hold ANY record a plan suggestion could act on?

    Judged from the same three surfaces a suggestion is built from — the plan, the review list and
    the practice facts — so this answer cannot disagree with what the proposal itself reasons over
    (``_evidence`` reads exactly these).

    ``recent_events`` is deliberately NOT part of it. It is the model's context, but it is not
    evidence of LEARNING: it accumulates bookkeeping events, and a previous
    ``plan_adjustment_proposed`` is one of them. Counting it meant a learner with an empty plan and
    nothing studied yet was told their plan needed no adjustment — the answer for someone who HAS
    a plan — instead of being told there is nothing to plan around yet. Measured on the production
    acceptance account, 2026-09-29: plan 0, review 0, practice 0, and a plan_adjustment_proposed
    event left over from an earlier acceptance round.
    """
    plan = context_facts.get("plan") or {}
    review = context_facts.get("review") or {}
    practice = context_facts.get("practice") or {}
    return bool(int(plan.get("total") or 0) or int(review.get("total") or 0)
                or int(practice.get("attempts") or 0))


def _nothing_to_apply(context_facts: dict, *, requested: bool) -> tuple[str, str]:
    """(outcome, the one line the learner reads) when a validated proposal holds no change."""
    if not _has_learner_history(context_facts):
        return OUTCOME_NO_RECORD, MESSAGE_NO_RECORD
    if not requested:
        return OUTCOME_NO_CHANGE, MESSAGE_NO_CHANGE
    return OUTCOME_NOT_APPLICABLE, MESSAGE_NOT_APPLICABLE


def _adjustment_types(changes: list[dict]) -> list[str]:
    """The proposal's meanings, in the canonical order — never a type it did not produce."""
    present = {change["type"] for change in changes}
    if any(change.get("direction") == LATER for change in changes):
        present.add(TYPE_REDUCE_LOAD)          # tasks moved later: less load, sooner
    if (any(change["type"] == TYPE_INSERT for change in changes)
            or any(change.get("direction") == EARLIER for change in changes)):
        present.add(TYPE_INCREASE_LOAD)        # something added, or brought forward
    return [name for name in SUPPORTED_ADJUSTMENT_TYPES if name in present]


def _overdue_count(tasks, changes: list[dict], today) -> int:
    """Overdue AFTER the proposal — the same rule the plan itself uses, recomputed."""
    proposed = {change["task_id"]: change.get("after") for change in changes
                if change["type"] == TYPE_RESCHEDULE and change.get("task_id") is not None}
    count = 0
    for row in tasks:
        status = (row.status or "not_started").strip() or "not_started"
        due = _parse_due(proposed[row.id]) if row.id in proposed else _parse_due(row.due_date)
        if status != "completed" and due is not None and due < today:
            count += 1
    return count


def _impact(context: dict, changes: list[dict], tasks) -> dict:
    """What actually changes — counted, never narrated into a forecast.

    Every number here is arithmetic over the plan in front of the learner and the changes being
    proposed. Nothing estimates effort, minutes, mastery or future performance: the plan model
    holds none of those, so no such sentence is available to write.
    """
    inserted = sum(1 for change in changes if change["type"] == TYPE_INSERT)
    rescheduled = [change for change in changes if change["type"] == TYPE_RESCHEDULE]
    replaced = sum(1 for change in changes if change["type"] == TYPE_REPLACE)
    moved_earlier = sum(1 for change in rescheduled if change.get("direction") == EARLIER)
    moved_later = sum(1 for change in rescheduled if change.get("direction") == LATER)

    plan = context.get("plan") or {}
    count_before = int(plan.get("total") or len(tasks))
    overdue_before = int(plan.get("overdue") or 0)
    overdue_after = _overdue_count(tasks, changes, _now().date())

    parts = []
    if inserted:
        parts.append(f"新增 {inserted} 项任务")
    if moved_earlier:
        parts.append(f"提前 {moved_earlier} 项")
    if moved_later:
        parts.append(f"推迟 {moved_later} 项")
    if replaced:
        parts.append(f"替换 {replaced} 项")

    text = "本次调整" + ("。" if not parts else "，" + "，".join(parts) + "。")
    # No "plan total went from N to M" sentence: the learner reads the plan itself right above
    # this, so a before/after counter tells them nothing they cannot see, and a count that only
    # moved because THIS panel is empty reads as a defect. The overdue line stays because a
    # learner cannot compute it by looking at the list.
    if overdue_before != overdue_after:
        text += f"调整后还有 {overdue_after} 项任务已逾期。"

    return {
        "inserted": inserted,
        "rescheduled": len(rescheduled),
        "moved_earlier": moved_earlier,
        "moved_later": moved_later,
        "replaced": replaced,
        "task_count_before": count_before,
        "task_count_after": count_before + inserted,
        "overdue_before": overdue_before,
        "overdue_after": overdue_after,
        "text": text,
    }


# ---------------------------------------------------------------- propose

def propose_adjustment(db: DbSession, user, *, service_key: str, goal: str = "",
                       course_id=None, exam_module_id=None, language=None) -> dict:
    """Ask for a bounded adjustment. WRITES NOTHING — the plan is not touched.

    The model contributes CHANGES only. Everything a learner reads about those changes — what
    they mean, why they are suggested, what they add up to — is derived here from the plan and
    the learner's own stored records, so no sentence on screen can outrun the data behind it.
    """
    space = _space_of(service_key)
    tasks = _plan_tasks(db, user, space, course_id=course_id,
                        exam_module_id=exam_module_id, language=language)
    context_facts = build_plan_context(db, user, space, course_id=course_id,
                                       exam_module_id=exam_module_id, language=language,
                                       tasks=tasks)
    from prompts import build_plan_adjustment_messages
    messages = build_plan_adjustment_messages(context_facts, goal=_bounded(goal, 300),
                                              task_types=plan_task_types(space))

    execution_context = _context_for(user, space, course_id=course_id,
                                     exam_module_id=exam_module_id, language=language)
    result = _execute(db, user, space, execution_context, messages)

    parsed = _extract_json_object(result.content or "")
    if parsed is None:
        raise PlanAdjustmentRefusal("unusable_proposal", "这次没有生成可用的建议")
    requested = parsed.get("changes")
    accepted, dropped = _clean_changes(requested, _task_index(tasks), plan_task_types(space))

    # Nothing survived validation. That is a normal outcome of asking, not a failure of asking, so
    # it is returned as a proposal with no changes (which `can_apply: false` already forbids
    # applying) rather than as an error status.
    if accepted:
        outcome, message = OUTCOME_PROPOSED, ""
    else:
        outcome, message = _nothing_to_apply(context_facts, requested=bool(requested))

    evidence = _evidence(context_facts, accepted)
    proposal_id = uuid.uuid4().hex
    identity = context_facts["plan"]["identity"]
    # An empty proposal is not something that happened TO the learner's plan, so it is not
    # recorded as one: `plan_adjustment_proposed` is a learner-facing record type, and
    # "0 changes were proposed" is a row that says nothing.
    if accepted:
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
        "summary": _summary(accepted),
        "rationale": _rationale(evidence) if accepted else "",
        "outcome": outcome,
        "message": message,
        "adjustment_types": _adjustment_types(accepted),
        "evidence": evidence,
        "proposed_changes": accepted,
        "impact": _impact(context_facts, accepted, tasks),
        "can_apply": bool(accepted),
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
    # Re-validated against the LIVE plan, through the same derivation the proposal used: because
    # the identity matched, `before` is re-read as the same value the learner was shown, so the
    # write cannot differ from the preview even if a client edits the payload on the way back.
    accepted, dropped = _clean_changes(changes, _task_index(tasks), plan_task_types(space))
    # A proposal may carry a task whose day the MODEL could not choose — the learner picks it in
    # the client. Applied without one, the row would never be due and never be today's work, so
    # the write is refused here rather than the suggestion being discarded earlier.
    dated = []
    for change in accepted:
        if change["op"] == OP_CREATE and not change.get("due_date"):
            dropped.append({"reason": "missing_due_date", "title": change["title"]})
            continue
        dated.append(change)
    accepted = dated
    if not accepted:
        raise PlanAdjustmentRefusal("empty_proposal", "这次没有可以应用到计划的改动")

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
