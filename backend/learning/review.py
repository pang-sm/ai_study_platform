"""Unified Review projection — ONE read model over the review facts the product already has.

WHAT REVIEW IS HERE
-------------------
Review is not a second store and not a second scheduler. It is a PROJECTION over facts that
already exist and are already written by their own owners:

    course / exam wrong answers   ``wrong_answer_states`` (status = active)
    knowledge review dates        ``user_knowledge_progress.review_due_at`` (a STORED date)
    programming needs work        ``programming_exercise_progress`` (status + last submit)

Nothing is aggregated into a new table, nothing is recomputed into a new schedule, and no
domain's facts are copied. The projection answers one question — "what does this learner have
outstanding?" — from the stored rows, per learning space.

WHAT IT WILL NOT INVENT
-----------------------
* No AI weakness guess, no inferred interval, no memory score. There is no such field in this
  module's output because there is no such fact behind it.
* ``due_at`` is populated ONLY from ``user_knowledge_progress.review_due_at``, which is a
  stored date. A source that has a real signal but NO stored date (an active wrong answer, an
  exercise that needs work) is reported as ``needs_attention`` with ``due_at = None`` — never
  with a made-up date, and never as "due".
* ``due_source`` names the exact column a date came from, so no reader has to guess whether a
  date was scheduled or imagined.

WHAT IT WILL NOT RESOLVE
------------------------
It reads no question content. A review item names WHICH question (source type + id + scope)
and links to the domain page that already renders it safely; resolving stems here would
create a second question-materialization surface, which is exactly what P1.2 closed.

ISOLATION
---------
Every query is scoped by the caller's user id (or username where that is the storage key).
A review page assembled for one learner cannot contain another learner's rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from core.learning_context import ServiceNamespace, normalize_service_namespace

logger = logging.getLogger("learning.review")

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

# The closed bucket vocabulary. Derived from stored facts only.
BUCKET_DUE = "due"                          # a STORED due date that has passed
BUCKET_SCHEDULED = "scheduled"              # a STORED due date still in the future
BUCKET_NEEDS_ATTENTION = "needs_attention"  # a real signal with NO stored due date
BUCKETS = (BUCKET_DUE, BUCKET_NEEDS_ATTENTION, BUCKET_SCHEDULED)
_BUCKET_RANK = {BUCKET_DUE: 0, BUCKET_NEEDS_ATTENTION: 1, BUCKET_SCHEDULED: 2}

SOURCE_WRONG_ANSWER = "wrong_answer"
SOURCE_KNOWLEDGE_REVIEW = "knowledge_review"
SOURCE_PROGRAMMING_EXERCISE = "programming_exercise"

DUE_SOURCE_KNOWLEDGE = "user_knowledge_progress.review_due_at"

# Per-source cap. A review page is a bounded view, never a full-history export.
MAX_ITEMS_PER_SOURCE = 200
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _now() -> datetime:
    """Naive UTC, the convention every persisted datetime in this schema uses."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _epoch_of(iso_text) -> float:
    """Ordering epoch for a displayed ISO timestamp. An unparseable value sorts oldest."""
    if not iso_text:
        return 0.0
    try:
        return datetime.fromisoformat(str(iso_text)).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _truncate(text, limit: int = 80) -> str:
    value = str(text or "").strip()
    return value if len(value) <= limit else value[:limit].rstrip() + "…"


def _namespace_filter(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        return normalize_service_namespace(value)
    except ValueError:
        return None


# ---------------------------------------------------------------- course / exam wrong answers

def _wrong_answer_items(db: DbSession, user) -> list[dict]:
    """Active wrong-answer states of EVERY learning space that has them, ONE query.

    The state rows are read per space by their own status column; no content is resolved.
    """
    from learning.wrong_answers.models import STATUS_ACTIVE, WrongAnswerState

    rows = (db.query(WrongAnswerState)
            .filter(WrongAnswerState.user_id == user.id,
                    WrongAnswerState.service_namespace.in_([COURSE, EXAM]),
                    WrongAnswerState.status == STATUS_ACTIVE)
            .order_by(WrongAnswerState.last_wrong_at.desc())
            .limit(MAX_ITEMS_PER_SOURCE).all())

    items = []
    for state in rows:
        namespace = state.service_namespace
        scope = (state.question_scope_key or "").strip()
        course_id = scope.split(":", 1)[1] if scope.startswith("course:") else ""
        module_key = (state.module_key or "").strip()
        if namespace == COURSE:
            title = f"错题 · {course_id}" if course_id else "错题"
            deep_link = f"/course/{course_id}/wrong" if course_id else "/course"
        else:
            display = _module_display(module_key)
            title = f"错题 · {display}" if display else "错题"
            deep_link = ("/exam/cs408/wrong"
                         + (f"?module={module_key}" if module_key else ""))
        items.append({
            "id": f"wrong:{namespace}:{state.id}",
            "service_namespace": namespace,
            "domain_context": {"course_id": course_id or None,
                               "exam_module_id": module_key or None},
            "source_type": SOURCE_WRONG_ANSWER,
            "source_id": str(state.id),
            "question_identity": {
                "question_source_type": state.question_source_type,
                "question_source_id": state.question_source_id,
                "question_scope_key": state.question_scope_key,
            },
            "title": title,
            "summary": f"累计做错 {int(state.wrong_count or 0)} 次，尚未订正",
            "review_status": BUCKET_NEEDS_ATTENTION,
            "due_at": None,
            "due_source": None,
            "last_attempt_at": _iso(state.last_wrong_at),
            "reason": "wrong_answer_active",
            "metrics": {"wrong_count": int(state.wrong_count or 0)},
            "deep_link": deep_link,
        })
    return items


def _module_display(module_key: str) -> str:
    if not module_key:
        return ""
    try:
        from learning.spaces.exam_prep.context import cs408_module_display
        return cs408_module_display(module_key)
    except Exception:  # noqa: BLE001 — a display name is never worth failing a page
        return module_key


# ---------------------------------------------------------------- knowledge review dates

def _knowledge_items(db: DbSession, user) -> list[dict]:
    """Knowledge points of every space that have a STORED review date — and only those.

    A knowledge row with no ``review_due_at`` produces NO item: the product has no stored
    schedule for it, and inventing one here is the fabrication this module refuses.
    """
    from models import UserKnowledgeProgress

    rows = (db.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == user.username,
                    UserKnowledgeProgress.review_due_at.isnot(None))
            .order_by(UserKnowledgeProgress.review_due_at.asc())
            .limit(MAX_ITEMS_PER_SOURCE).all())

    now = _now()
    items = []
    for row in rows:
        module_key, is_exam = _exam_module_of(row.course_id)
        row_namespace = EXAM if is_exam else COURSE
        due_at = row.review_due_at
        bucket = BUCKET_DUE if due_at <= now else BUCKET_SCHEDULED
        title = _truncate(row.knowledge_point_title or row.knowledge_point_code
                          or "知识点", 60)
        interval = row.review_interval_days
        summary = ("复习计划已到期" if bucket == BUCKET_DUE else "复习计划已排期")
        if interval:
            summary += f"（间隔 {int(interval)} 天）"
        if is_exam:
            deep_link = ("/exam/cs408/knowledge"
                         + (f"?module={module_key}" if module_key else ""))
            domain = {"exam_module_id": module_key or None}
        else:
            deep_link = f"/course/{row.course_id}/knowledge"
            domain = {"course_id": row.course_id}
        items.append({
            "id": f"knowledge:{row.id}",
            "service_namespace": row_namespace,
            "domain_context": domain,
            "source_type": SOURCE_KNOWLEDGE_REVIEW,
            "source_id": str(row.id),
            "question_identity": None,
            "title": title,
            "summary": summary,
            "review_status": bucket,
            "due_at": _iso(due_at),
            "due_source": DUE_SOURCE_KNOWLEDGE,
            "last_attempt_at": _iso(row.last_studied_at),
            "reason": "knowledge_review_due" if bucket == BUCKET_DUE
                      else "knowledge_review_scheduled",
            "metrics": {"knowledge_point_code": row.knowledge_point_code,
                        "practice_count": int(row.practice_count or 0),
                        "review_interval_days": (int(interval) if interval else None)},
            "deep_link": deep_link,
        })
    return items


def _exam_module_of(course_id) -> tuple[str, bool]:
    """(module_key, is_exam) for a stored knowledge ``course_id``.

    The exam space stores its knowledge rows under the legacy scope id
    (``data_structure_11408``); everything else is an ordinary course. The classification
    uses the SAME legacy-scope parser the exam space itself uses — a plain course display
    name (which also happens to look like a module name) stays a COURSE.
    """
    text = str(course_id or "").strip()
    if not text:
        return "", False
    try:
        from learning.spaces.exam_prep.scope import parse_legacy_exam_scope_id
        scope = parse_legacy_exam_scope_id(text)
    except Exception:  # noqa: BLE001
        return "", False
    return (scope.exam_module_id, True) if scope is not None else ("", False)


# ---------------------------------------------------------------- programming

def _programming_items(db: DbSession, user) -> list[dict]:
    """Exercises the learner must come back to, from the progress row and the catalog."""
    from learning.spaces.programming.context import normalize_language
    from models import ProgrammingExercise, ProgrammingExerciseProgress

    rows = (db.query(ProgrammingExerciseProgress)
            .filter(ProgrammingExerciseProgress.username == user.username)
            .order_by(ProgrammingExerciseProgress.last_updated_at.desc())
            .limit(MAX_ITEMS_PER_SOURCE).all())

    exercise_ids = [row.exercise_id for row in rows]
    exercises = {}
    if exercise_ids:
        exercises = {e.id: e for e in (
            db.query(ProgrammingExercise)
            .filter(ProgrammingExercise.id.in_(sorted(set(exercise_ids)))).all())}

    items = []
    for row in rows:
        needs_work = (row.personal_status or "") == "needs_work"
        last_failed = bool(row.last_submit_at) and row.last_submit_passed is False
        if not (needs_work or last_failed):
            continue
        exercise = exercises.get(row.exercise_id)
        language = normalize_language(getattr(exercise, "language", None))
        title = _truncate(getattr(exercise, "title", None) or f"练习 #{row.exercise_id}", 60)
        if needs_work:
            summary = "标记为需要加强"
        else:
            summary = (f"最近一次提交未通过"
                       f"（{int(row.last_public_passed_count or 0)}"
                       f"/{int(row.last_public_total_count or 0)} 用例通过）")
        items.append({
            "id": f"programming:{row.id}",
            "service_namespace": PROG,
            "domain_context": {"language": language, "exercise_id": row.exercise_id},
            "source_type": SOURCE_PROGRAMMING_EXERCISE,
            "source_id": str(row.exercise_id),
            "question_identity": None,
            "title": title,
            "summary": summary,
            "review_status": BUCKET_NEEDS_ATTENTION,
            "due_at": None,
            "due_source": None,
            "last_attempt_at": _iso(row.last_submit_at or row.last_test_at
                                    or row.last_run_at),
            "reason": "exercise_needs_work" if needs_work else "exercise_last_submit_failed",
            "metrics": {
                "passed_count": int(row.last_public_passed_count or 0),
                "total_count": int(row.last_public_total_count or 0),
                "personal_status": row.personal_status,
            },
            "deep_link": f"/programming/{language}/exercises/{row.exercise_id}",
        })
    return items


# ---------------------------------------------------------------- projection

SEMANTICS = (
    "deterministic projection of stored review facts (wrong-answer states, stored knowledge "
    "review dates, programming progress). No predicted weakness, no inferred interval, no "
    "memory score."
)


def _project(db: DbSession, user, *, namespace=None, course_id=None, exam_module_id=None,
             language=None, bucket=None) -> tuple[list[dict], str]:
    """Every source read ONCE, then filtered. Returns ``(items, semantics)``."""
    items: list[dict] = []
    items.extend(_wrong_answer_items(db, user))
    items.extend(_knowledge_items(db, user))
    items.extend(_programming_items(db, user))

    course_filter = str(course_id or "").strip() or None
    module_filter = str(exam_module_id or "").strip() or None
    language_filter = str(language or "").strip() or None

    def _matches(item: dict) -> bool:
        if namespace is not None and item["service_namespace"] != namespace:
            return False
        if bucket is not None and item["review_status"] != bucket:
            return False
        domain = item["domain_context"] or {}
        if course_filter is not None and domain.get("course_id") != course_filter:
            return False
        if module_filter is not None and domain.get("exam_module_id") != module_filter:
            return False
        if language_filter is not None and domain.get("language") != language_filter:
            return False
        return True

    # A computed schedule can MOVE an item's bucket, so the schedules are attached BEFORE any
    # filter runs: filtering first would decide `status=due` from the pre-schedule value and
    # hide an item the schedule had just made due.
    _apply_schedules(db, user.id, items)
    filtered = [item for item in items if _matches(item)]
    filtered.sort(key=lambda item: (
        _BUCKET_RANK.get(item["review_status"], 9),
        item["due_at"] or "9999",
        -_epoch_of(item["last_attempt_at"]),
        item["id"],
    ))
    return filtered, SEMANTICS


def _apply_schedules(db: DbSession, user_id: int, items: list[dict]) -> None:
    """Let a COMPUTED schedule move an item's bucket — with its policy stated.

    A review schedule is a stored canonical fact (``review_scheduled``) produced by the
    deterministic policy, so an item that has one is genuinely due or scheduled. The date's
    provenance and the policy version travel with it, so a reader can always tell a computed
    date from a stored one and can re-derive it.
    """
    from learning import review_schedule

    dues = review_schedule.scheduled_dues(db, user_id, [item["id"] for item in items])
    if not dues:
        return
    now = _now()
    for item in items:
        scheduled = dues.get(item["id"])
        if not scheduled or not scheduled.get("due_at"):
            continue
        due_at = datetime.fromisoformat(scheduled["due_at"])
        item["due_at"] = scheduled["due_at"]
        item["due_source"] = (f"review_policy.{scheduled.get('policy_version') or 'review_policy_v1'}"
                              f".{scheduled.get('reason') or 'scheduled'}")
        item["review_status"] = BUCKET_DUE if due_at <= now else BUCKET_SCHEDULED
        item["schedule"] = {
            "policy_version": scheduled.get("policy_version"),
            "reason": scheduled.get("reason"),
            "interval_days": scheduled.get("interval_days"),
            "scheduled_at": scheduled.get("scheduled_at"),
        }


def collect_review_items(db: DbSession, user, *, service_namespace=None, course_id=None,
                         exam_module_id=None, language=None, bucket=None,
                         limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict:
    """The caller's outstanding review work, filtered and paginated.

    Every filter applies AFTER the per-source user scope, never instead of it.
    """
    namespace = _namespace_filter(service_namespace)
    wanted_bucket = (bucket or "").strip() or None
    if wanted_bucket is not None and wanted_bucket not in BUCKETS:
        raise ValueError(f"unknown status {wanted_bucket!r}")

    filtered, semantics = _project(
        db, user, namespace=namespace, course_id=course_id,
        exam_module_id=exam_module_id, language=language, bucket=wanted_bucket)

    return {
        "items": filtered[offset:offset + limit],
        "total": len(filtered),
        "limit": limit,
        "offset": offset,
        "buckets": {name: sum(1 for i in filtered if i["review_status"] == name)
                    for name in BUCKETS},
        "semantics": semantics,
    }


def review_summary(db: DbSession, user, *, service_namespace=None) -> dict:
    """Counts over the SAME projection — there is no second aggregation path."""
    namespace = _namespace_filter(service_namespace)
    items, semantics = _project(db, user, namespace=namespace)

    by_namespace: dict[str, int] = {}
    by_bucket: dict[str, int] = {name: 0 for name in BUCKETS}
    by_source: dict[str, int] = {}
    for item in items:
        by_namespace[item["service_namespace"]] = \
            by_namespace.get(item["service_namespace"], 0) + 1
        by_bucket[item["review_status"]] = by_bucket.get(item["review_status"], 0) + 1
        by_source[item["source_type"]] = by_source.get(item["source_type"], 0) + 1
    return {
        "service_namespace": namespace,
        "total": len(items),
        "by_namespace": by_namespace,
        "by_status": by_bucket,
        "by_source": by_source,
        "has_stored_due_dates": by_bucket[BUCKET_DUE] + by_bucket[BUCKET_SCHEDULED] > 0,
        "semantics": semantics,
    }
