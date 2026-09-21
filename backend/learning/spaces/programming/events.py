"""Programming Space → canonical LearningEvent bridge.

WHICH ACTIONS BECOME FACTS
--------------------------
The exercise loop has five real learner actions. Three of them had no canonical fact at
all, so the product could not say what a learner did BEFORE they submitted:

    start            → ``exercise_started``   (this module)
    run              → ``code_run``           (this module)
    test             → ``code_tested``        (this module)
    submit           → ``code_submitted``     ALREADY owned — see below
    pass / fail      → ``code_submitted.correct``  ALREADY owned — the real judge verdict

``code_submitted`` is deliberately NOT re-emitted here. One fact has exactly ONE
authoritative producer (``learning.records.taxonomy``), and ``learning.practice.events``
already owns the submission through the durable ``PracticeAttempt`` the submit mirrors. A
second event for the same submission would double-count the learner's history.

NOTHING HERE IS INFERRED FROM AI TEXT
-------------------------------------
Every event is built from the server's own execution of the learner's code: the endpoint
ran it, and the model's prose about the code is never an input. That is exactly why
``code_challenge_attempts`` — whose ``status`` is keyword-matched out of an AI reply —
produces nothing on this path.

WHAT EXECUTION IS, AND IS NOT
-----------------------------
Running code is a FACT; whether it was CORRECT is not asserted here. ``code_run`` and
``code_tested`` carry no ``correct`` value, so no reader can mistake a run for a graded
verdict. The verdict belongs to the submission, and to ``code_submitted`` alone.

A single-sample PREVIEW (``/samples/run``) records nothing: it is a sub-action inside the
run loop that the progress row itself does not track, and emitting one event per sample
preview would flood the stream with actions the product never treated as steps.

FAILURE ISOLATION
-----------------
The domain row has already committed when these are called. Every failure is absorbed and
counted by ``learning.records.producers``, so a data-plane problem can never fail a run,
a test, or a start.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core import timeutil
from learning.records import producers
from learning.records.envelope import build_event

from . import context as programming_context

logger = logging.getLogger("learning.spaces.programming")

# action → canonical event type. Only actions the exercise loop itself records appear here.
ACTION_EVENT_TYPES = {
    "run": "code_run",
    "test": "code_tested",
}

# One source family per action, so a run and a test on the SAME progress row can never
# land on the same source identity.
SOURCE_TYPE_PREFIX = "programming_exercise"


def _source_type(action: str) -> str:
    return f"{SOURCE_TYPE_PREFIX}_{action}"


def _epoch(value) -> float:
    """One shared conversion: a naive persisted datetime is UTC, never server-local."""
    return timeutil.to_epoch_or_now(value)


def _stamp(epoch: float) -> str:
    """The stable ISO-8601 UTC item key for one action time.

    Derived from the epoch the progress row recorded, so a replay of the same action
    recomputes the same key and the deterministic event id collapses the duplicate.
    """
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()


def _payload(*, language, exercise_id, action, project_id, learning_context, extra=None):
    """The event snapshot. References and the language only — never the learner's code.

    ``context`` mirrors the shape ``learning.practice.adapters.programming`` writes, so the
    records projection reads ONE context shape regardless of which producer made the event.
    """
    payload = {
        "service_namespace": programming_context.PROGRAMMING_NAMESPACE,
        "programming_language": language,
        "exercise_id": exercise_id,
        "project_id": project_id,
        "action": action,
        "context": learning_context.to_dict(),
    }
    if extra:
        payload.update(extra)
    return payload


def emit_exercise_started(*, user_id, exercise, occurred_at, language=None,
                          project_id=None, source_user_ref=None) -> dict:
    """The learner began working on an exercise.

    IDENTITY IS (user, exercise): opening the same exercise again is the SAME fact, not a
    second one, so the deterministic event id collapses a resume into the start that
    already happened. The user is part of the source id because event identity is
    otherwise global — without it, two learners starting exercise 7 would share one event.
    """
    exercise_id = programming_context.normalize_exercise_id(getattr(exercise, "id", exercise))
    if exercise_id is None:
        return {"emitted": 0, "reason": "no_exercise_id"}
    lang = programming_context.normalize_language(
        language or getattr(exercise, "language", None))
    learning_context = programming_context.build_programming_context(
        _UserRef(user_id), language=lang, exercise_id=exercise_id)

    return producers.emit(lambda: build_event(
        event_type="exercise_started", user_id=user_id,
        service_namespace=programming_context.PROGRAMMING_NAMESPACE,
        occurred_at=_epoch(occurred_at),
        source_type=_source_type("start"), source_id=f"{user_id}:{exercise_id}",
        source_item_key="started",
        payload=_payload(language=lang, exercise_id=exercise_id, action="start",
                         project_id=project_id, learning_context=learning_context),
        source_user_ref=source_user_ref,
        granularity="ACTIVITY_LEVEL",
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["source_code"],
    ))


def emit_exercise_activity(*, user_id, exercise, action, occurred_at, language=None,
                           project_id=None, observed=None, source_user_ref=None) -> dict:
    """One real run or test of the learner's code for an exercise.

    ``occurred_at`` is the SAME timestamp the progress row recorded, and it doubles as the
    event's item key: the progress row keeps only the LAST action, so the event is the
    durable record of this one (``taxonomy`` marks both types EVENT_ONLY for that reason).
    Two actions landing on the identical microsecond therefore collapse into one event —
    an acceptable, and honest, resolution limit rather than an invented ordinal.
    """
    event_type = ACTION_EVENT_TYPES.get(action)
    if event_type is None:
        return {"emitted": 0, "reason": "unregistered_action"}

    exercise_id = programming_context.normalize_exercise_id(getattr(exercise, "id", exercise))
    if exercise_id is None:
        return {"emitted": 0, "reason": "no_exercise_id"}

    occurred = _epoch(occurred_at)
    lang = programming_context.normalize_language(
        language or getattr(exercise, "language", None))
    learning_context = programming_context.build_programming_context(
        _UserRef(user_id), language=lang, exercise_id=exercise_id)

    # Only execution facts the server itself produced travel with the event. A run reports
    # what the runner returned; a test reports how many of the exercise's own tests passed.
    extra = None
    if action == "test":
        extra = {"passed_count": _int_or_none(observed, "passed_count"),
                 "total_count": _int_or_none(observed, "total_count")}
    elif action == "run":
        extra = {"exit_code": _int_or_none(observed, "exit_code"),
                 "timed_out": _bool_or_none(observed, "timeout")}

    return producers.emit(lambda: build_event(
        event_type=event_type, user_id=user_id,
        service_namespace=programming_context.PROGRAMMING_NAMESPACE,
        occurred_at=occurred,
        # ``programming_exercise_progress`` is unique per (username, exercise), so the
        # (learner, exercise) pair IS the durable row this action is recorded against — and
        # unlike the row's surrogate id it does not depend on which process created it.
        # The learner is part of the source id because event identity is otherwise GLOBAL:
        # without it, two learners running exercise 7 in the same microsecond would share
        # one event and the second one would be silently dropped.
        source_type=_source_type(action), source_id=f"{user_id}:{exercise_id}",
        source_item_key=_stamp(occurred),
        payload=_payload(language=lang, exercise_id=exercise_id, action=action,
                         project_id=project_id, learning_context=learning_context,
                         extra=extra),
        source_user_ref=source_user_ref,
        granularity="ACTIVITY_LEVEL",
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="PARTIAL",
        snapshot_missing_fields=["source_code"],
    ))


class _UserRef:
    """The minimal user shape ``build_programming_context`` needs (it reads ``id``)."""

    __slots__ = ("id",)

    def __init__(self, user_id):
        self.id = user_id


def _int_or_none(observed, key):
    if not isinstance(observed, dict):
        return None
    value = observed.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(observed, key):
    if not isinstance(observed, dict):
        return None
    value = observed.get(key)
    return None if value is None else bool(value)
