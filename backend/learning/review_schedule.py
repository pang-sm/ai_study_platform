"""Intelligent Review V1 — a DETERMINISTIC review schedule over real facts.

WHY THIS IS NOT A SCIENTIFIC COMPONENT CALL
-------------------------------------------
A spaced-repetition model needs a real ``interval`` / ``rating`` / ``lapse`` history, and the
product does not have one (``science/capabilities.py`` declares INTERVAL_HISTORY_ABSENT). So
V1 does NOT call the ``memory`` component — a model fed fabricated interval history would
produce a fabricated schedule, and the SSOT forbids exactly that.

What it does instead: a transparent, versioned, testable POLICY over stored facts.

    review_due_at (stored) · wrong repeats · the LAST review's real result · last attempt
    · the item's manual/product state

Every computed date carries:

    policy_version   the rule that produced it (bump = a different rule, never a silent change)
    reason           which branch of the policy decided the interval
    scheduled_at     when it was computed
    due_at           the next date
    facts            the exact inputs it used, so the date can be re-derived and checked

COMPLETION IS WHAT MOVES A SCHEDULE
-----------------------------------
``complete_review`` records the learner's REAL result, emits ``review_completed`` and then
reschedules from that result. A review that did not happen cannot advance anything, and a
schedule is never advanced by a model — only by the learner's action and its outcome.

Stored durably as canonical events (``review_scheduled`` / ``review_completed``); for a
KNOWLEDGE item the knowledge-progress row's own ``review_due_at`` / ``review_interval_days``
columns are updated too, so the projection and the knowledge page agree.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

logger = logging.getLogger("learning.review_schedule")

POLICY_VERSION = "review_policy_v1"

# The policy's interval table. Days between reviews, by the branch that applied.
BASE_INTERVAL_DAYS = 7
FIRST_INTERVAL_DAYS = 3
MAX_INTERVAL_DAYS = 60
REPEATED_WRONG_INTERVAL_DAYS = 2
AFTER_INCORRECT_INTERVAL_DAYS = 1

REASON_FIRST_SCHEDULE = "first_schedule"
REASON_AFTER_CORRECT = "after_correct"
REASON_AFTER_INCORRECT = "after_incorrect"
REASON_REPEATED_WRONG = "repeated_wrong"
REASON_MANUAL_STATE = "manual_state"

ITEM_PREFIX_WRONG = "wrong:"
ITEM_PREFIX_KNOWLEDGE = "knowledge:"
ITEM_PREFIX_PROGRAMMING = "programming:"

MAX_ITEMS_PER_RUN = 50


class ReviewScheduleRefusal(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------- the policy

def compute_schedule(*, last_review_result: str | None, previous_interval_days: int | None,
                     repeated_wrong_count: int = 0, item_status: str | None = None,
                     now: datetime | None = None) -> dict:
    """The ONE policy function: real inputs → the next due date and why.

    Pure and deterministic: the same inputs always produce the same date. Every branch is
    named in ``reason`` and the inputs travel back in ``facts``.
    """
    now = now or _now()
    facts = {
        "last_review_result": last_review_result,
        "previous_interval_days": previous_interval_days,
        "repeated_wrong_count": int(repeated_wrong_count or 0),
        "item_status": item_status,
    }

    if last_review_result == "incorrect":
        interval = AFTER_INCORRECT_INTERVAL_DAYS
        reason = REASON_AFTER_INCORRECT
    elif repeated_wrong_count >= 2:
        interval = REPEATED_WRONG_INTERVAL_DAYS
        reason = REASON_REPEATED_WRONG
    elif last_review_result == "correct":
        previous = previous_interval_days or FIRST_INTERVAL_DAYS
        interval = min(max(previous * 2, FIRST_INTERVAL_DAYS), MAX_INTERVAL_DAYS)
        reason = REASON_AFTER_CORRECT
    elif item_status and str(item_status).strip() in ("mastered",):
        interval = MAX_INTERVAL_DAYS
        reason = REASON_MANUAL_STATE
    else:
        interval = FIRST_INTERVAL_DAYS
        reason = REASON_FIRST_SCHEDULE

    return {
        "policy_version": POLICY_VERSION,
        "reason": reason,
        "interval_days": int(interval),
        "scheduled_at": _iso(now),
        "due_at": _iso(now + timedelta(days=int(interval))),
        "facts": facts,
    }


# ---------------------------------------------------------------- item addressing

def _split_item_id(item_id: str) -> tuple[str, str]:
    text = str(item_id or "").strip()
    for prefix, kind in ((ITEM_PREFIX_WRONG, "wrong"), (ITEM_PREFIX_KNOWLEDGE, "knowledge"),
                         (ITEM_PREFIX_PROGRAMMING, "programming")):
        if text.startswith(prefix):
            return kind, text[len(prefix):]
    raise ReviewScheduleRefusal("unknown_item", f"无法识别的复习项: {item_id!r}")


def resolve_item(db: DbSession, user, item_id: str) -> dict:
    """The caller's OWN item behind a review id — or a refusal. Never another learner's row."""
    kind, raw_id = _split_item_id(item_id)
    try:
        numeric = int(raw_id.split(":", 1)[-1] if kind == "wrong" else raw_id)
    except (TypeError, ValueError):
        raise ReviewScheduleRefusal("unknown_item", f"无法识别的复习项: {item_id!r}") from None

    if kind == "wrong":
        from learning.wrong_answers.models import WrongAnswerState
        row = (db.query(WrongAnswerState)
               .filter(WrongAnswerState.id == numeric,
                       WrongAnswerState.user_id == user.id).first())
        if row is None:
            raise ReviewScheduleRefusal("item_not_found", "复习项不存在")
        return {"kind": kind, "row": row, "service_namespace": row.service_namespace,
                "question_source_type": row.question_source_type,
                "question_source_id": row.question_source_id,
                "status": row.status, "wrong_count": int(row.wrong_count or 0)}

    if kind == "knowledge":
        from models import UserKnowledgeProgress
        row = (db.query(UserKnowledgeProgress)
               .filter(UserKnowledgeProgress.id == numeric,
                       UserKnowledgeProgress.username == user.username).first())
        if row is None:
            raise ReviewScheduleRefusal("item_not_found", "复习项不存在")
        return {"kind": kind, "row": row, "service_namespace": "course_learning",
                "question_source_type": None, "question_source_id": None,
                "status": row.status, "wrong_count": 0,
                "previous_interval_days": row.review_interval_days}

    from models import ProgrammingExerciseProgress
    row = (db.query(ProgrammingExerciseProgress)
           .filter(ProgrammingExerciseProgress.id == numeric,
                   ProgrammingExerciseProgress.username == user.username).first())
    if row is None:
        raise ReviewScheduleRefusal("item_not_found", "复习项不存在")
    return {"kind": kind, "row": row, "service_namespace": "programming",
            "question_source_type": None, "question_source_id": None,
            "status": row.personal_status, "wrong_count": 0}


def _last_review_result(db: DbSession, user, item_id: str) -> tuple[str | None, str | None]:
    """(result, reviewed_at) of the newest REAL review of this item — or (None, None)."""
    from data_plane.models import LearningEvent

    row = (db.query(LearningEvent)
           .filter(LearningEvent.user_id == user.id,
                   LearningEvent.event_type == "review_completed",
                   LearningEvent.source_type == "review_item",
                   LearningEvent.source_attempt_id == str(item_id))
           .order_by(LearningEvent.occurred_at.desc()).first())
    if row is None:
        return None, None
    import json
    try:
        payload = json.loads(row.item_snapshot_json or "{}")
    except (TypeError, ValueError):
        payload = {}
    result = payload.get("result")
    return (str(result) if result else None), _iso(
        datetime.utcfromtimestamp(row.occurred_at))


def latest_scheduled_due(db: DbSession, user_id: int, item_id: str) -> dict | None:
    """The newest ``review_scheduled`` fact for one item — the review projection's due source."""
    from data_plane.models import LearningEvent

    row = (db.query(LearningEvent)
           .filter(LearningEvent.user_id == user_id,
                   LearningEvent.event_type == "review_scheduled",
                   LearningEvent.source_type == "review_item",
                   LearningEvent.source_attempt_id == str(item_id))
           .order_by(LearningEvent.occurred_at.desc()).first())
    if row is None:
        return None
    import json
    try:
        payload = json.loads(row.item_snapshot_json or "{}")
    except (TypeError, ValueError):
        return None
    if not payload.get("due_at"):
        return None
    return {"due_at": payload.get("due_at"),
            "policy_version": payload.get("policy_version"),
            "reason": payload.get("reason"),
            "interval_days": payload.get("interval_days"),
            "scheduled_at": payload.get("scheduled_at")}


def scheduled_dues(db: DbSession, user_id: int, item_ids: list[str]) -> dict[str, dict]:
    """Batch variant for the review projection: one query for the whole page."""
    from data_plane.models import LearningEvent
    import json

    ids = [str(item) for item in item_ids if item]
    if not ids:
        return {}
    rows = (db.query(LearningEvent)
            .filter(LearningEvent.user_id == user_id,
                    LearningEvent.event_type == "review_scheduled",
                    LearningEvent.source_type == "review_item",
                    LearningEvent.source_attempt_id.in_(ids))
            .order_by(LearningEvent.occurred_at.asc()).all())
    out: dict[str, dict] = {}
    for row in rows:
        try:
            payload = json.loads(row.item_snapshot_json or "{}")
        except (TypeError, ValueError):
            continue
        if not payload.get("due_at"):
            continue
        out[str(row.source_attempt_id)] = {
            "due_at": payload.get("due_at"),
            "policy_version": payload.get("policy_version"),
            "reason": payload.get("reason"),
            "interval_days": payload.get("interval_days"),
            "scheduled_at": payload.get("scheduled_at"),
        }
    return out


# ---------------------------------------------------------------- scheduling & completion

def _apply_to_domain(db: DbSession, item: dict, schedule: dict) -> None:
    """Where the item HAS a real column for it, write the computed date."""
    if item["kind"] == "knowledge":
        row = item["row"]
        row.review_due_at = datetime.fromisoformat(schedule["due_at"])
        row.review_interval_days = schedule["interval_days"]
        db.commit()


def schedule_items(db: DbSession, user, *, item_ids: list[str] | None = None,
                   include_all: bool = False) -> dict:
    """Compute (and record) the next review date for the caller's items.

    With ``item_ids`` the given items are scheduled; with ``include_all`` every item of the
    caller's current review projection that does not yet have a schedule is. Never touches
    another learner's row.
    """
    from learning import review as review_service

    if item_ids:
        targets = [str(item) for item in item_ids][:MAX_ITEMS_PER_RUN]
        if not targets:
            raise ReviewScheduleRefusal("no_items", "没有需要排期的复习项")
    else:
        projection = review_service.collect_review_items(
            db, user, limit=MAX_ITEMS_PER_RUN, offset=0)
        targets = [item["id"] for item in projection["items"]]
        if not include_all:
            existing = scheduled_dues(db, user.id, targets)
            targets = [item_id for item_id in targets if item_id not in existing]
    if not targets:
        return {"policy_version": POLICY_VERSION, "scheduled": [], "count": 0,
                "semantics": _SEMANTICS}

    scheduled = []
    for item_id in targets:
        item = resolve_item(db, user, item_id)
        result, reviewed_at = _last_review_result(db, user, item_id)
        schedule = compute_schedule(
            last_review_result=result,
            previous_interval_days=item.get("previous_interval_days"),
            repeated_wrong_count=item.get("wrong_count", 0),
            item_status=item.get("status"))
        schedule["last_reviewed_at"] = reviewed_at
        _apply_to_domain(db, item, schedule)
        _emit_scheduled(user, item_id=item_id, schedule=schedule,
                        namespace=item["service_namespace"])
        scheduled.append({"item_id": item_id, **schedule})

    return {"policy_version": POLICY_VERSION, "scheduled": scheduled,
            "count": len(scheduled), "semantics": _SEMANTICS,
            "generated_at": _iso(_now())}


def complete_review(db: DbSession, user, *, item_id: str, result: str) -> dict:
    """Record the learner's OWN review result, then reschedule from it.

    ``result`` is the real outcome of the review (``correct`` / ``incorrect``). A review with
    no result is refused: an unreported review cannot move a schedule.
    """
    outcome = str(result or "").strip().lower()
    if outcome not in ("correct", "incorrect"):
        raise ReviewScheduleRefusal("result_required", "必须记录本次复习的真实结果")
    item = resolve_item(db, user, item_id)
    previous, _reviewed_at = _last_review_result(db, user, item_id)
    prior_schedule = latest_scheduled_due(db, user.id, item_id)
    schedule = compute_schedule(
        last_review_result=outcome,
        previous_interval_days=(prior_schedule or {}).get("interval_days")
        or item.get("previous_interval_days"),
        repeated_wrong_count=item.get("wrong_count", 0),
        item_status=item.get("status"))

    _emit_completed(user, item_id=item_id, result=outcome, schedule=schedule,
                    namespace=item["service_namespace"])
    _apply_to_domain(db, item, schedule)
    _emit_scheduled(user, item_id=item_id, schedule=schedule,
                    namespace=item["service_namespace"])

    return {
        "item_id": item_id,
        "result": outcome,
        "previous_review_result": previous,
        "policy_version": POLICY_VERSION,
        "scheduled_at": schedule["scheduled_at"],
        "due_at": schedule["due_at"],
        "interval_days": schedule["interval_days"],
        "reason": schedule["reason"],
        "source_facts": schedule["facts"],
        "semantics": _SEMANTICS,
    }


_SEMANTICS = (
    "deterministic review policy over stored facts (previous review result, "
    "repeated wrongs, the item's own state). No memory model is called: there is no real "
    "interval/rating/lapse history to feed one, and a fabricated schedule is worse than none."
)


# ---------------------------------------------------------------- events

def _emit_scheduled(user, *, item_id, schedule, namespace) -> None:
    try:
        from learning.records import producers
        producers.emit_review_scheduled(
            user_id=user.id, item_id=item_id, due_at=schedule["due_at"],
            policy_version=POLICY_VERSION, service_namespace=namespace,
            interval_days=schedule.get("interval_days"), reason=schedule.get("reason"),
            scheduled_at=schedule.get("scheduled_at"), facts=schedule.get("facts"),
            occurred_at=None, source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("review.schedule_event_failed error=%s", type(exc).__name__)


def _emit_completed(user, *, item_id, result, schedule, namespace) -> None:
    try:
        from learning.records import producers
        producers.emit_review_completed(
            user_id=user.id, item_id=item_id, result=result, service_namespace=namespace,
            policy_version=POLICY_VERSION, next_due_at=schedule["due_at"],
            occurred_at=None, source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("review.completed_event_failed error=%s", type(exc).__name__)
