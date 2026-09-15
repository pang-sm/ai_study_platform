"""DataProducerWorker (Phase 2B2): runs scientific inference over persisted LearningEvents.

Only ``student_twin`` is supported this phase.  The worker is manual/--once (no automatic
startup).  It is gated by ``DATA_PRODUCER_EXECUTION_ENABLED`` (default false), separate from
``DATA_PLANE_WRITE_ENABLED``.

The worker is a DATA_PRODUCER: it writes ``model_versions`` / ``model_inference_runs`` /
``model_predictions`` only.  It never mutates product tables and never changes a product
decision (grade / recommendation / plan / grading / frontend).
"""
import hashlib
import logging
import os
import time
from itertools import groupby

from . import eligibility, inference, student_twin_runtime
from .models import LearningEvent

logger = logging.getLogger("data_plane.worker")

DEFAULT_COMPONENT = "student_twin"


def execution_enabled() -> bool:
    return os.getenv("DATA_PRODUCER_EXECUTION_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _user_key(ev) -> str:
    """Stable per-user key; canonical user_id, falling back only for foreign records."""
    return str(ev.user_id) if ev.user_id is not None else (ev.source_user_ref or ev.event_id)


def _input_payload_hash(ev) -> str:
    """Stable input hash over the fields actually consumed by the StudentTwin mapping.

    Optional fields (response_time_ms / attempt_no / hints) are intentionally excluded:
    they are only ever None this phase, and including them would add noise without
    changing the mapping.  Correctness is a bool, not a fabricated default.
    """
    payload = (ev.item_snapshot_json or "") + "|" + str(ev.correct)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_eligible_event(ev) -> bool:
    """A course_practice event is runtime-ELIGIBLE for student_twin only with a real outcome.

    A None ``correct`` (e.g. a PARTIAL backfilled record whose outcome was never captured)
    is NOT an inferred observation and must not be fabricated into one.
    """
    if ev.correct is None:
        return False
    return eligibility.evaluate(DEFAULT_COMPONENT, {})["eligibility_status"] == "ELIGIBLE"


def run_once(SessionLocal, limit: int = None, event_id: str = None) -> dict:
    """Run one pass of the worker over eligible LearningEvents (deterministic replay)."""
    report = {"events_scanned": 0, "events_eligible": 0, "events_inferred": 0,
              "inference_runs_created": 0, "predictions_created": 0,
              "errors": 0, "skipped_not_enabled": False}

    if not execution_enabled():
        report["skipped_not_enabled"] = True
        return report

    session = SessionLocal()
    try:
        inference.ensure_student_twin_model_version(session)
        q = (session.query(LearningEvent)
             .filter(LearningEvent.event_type == "course_practice")
             .order_by(LearningEvent.user_id, LearningEvent.occurred_at, LearningEvent.event_id))
        if event_id:
            q = q.filter(LearningEvent.event_id == event_id)
        if limit:
            q = q.limit(limit)
        events = q.all()
        report["events_scanned"] = len(events)

        # deterministic per-user ordering: (user_id, occurred_at, event_id)
        for _key, group in groupby(events, key=_user_key):
            user_events = list(group)
            eligible = [e for e in user_events if _is_eligible_event(e)]
            if not eligible:
                continue
            report["events_eligible"] += len(eligible)

            # Fresh scientific StudentTwin per user (empty state), replayed in order.
            # ``state_after_target_event`` is the cumulative state after ingesting every
            # eligible event up to and including the target event.
            try:
                replayer = student_twin_runtime.StudentTwinReplayer()
            except Exception as exc:  # runtime unavailable -> skip this user safely
                logger.warning("student_twin runtime unavailable for user %s: %s", _key, type(exc).__name__)
                report["errors"] += 1
                continue
            try:
                for ev in eligible:
                    # per-event isolation: one bad event must not drop the rest of the user
                    try:
                        replayer.ingest(ev)
                        state = replayer.state(_user_key(ev))
                    except Exception as exc:
                        logger.warning("student_twin ingest failed for event %s: %s", ev.event_id, type(exc).__name__)
                        report["errors"] += 1
                        continue

                    payload_hash = _input_payload_hash(ev)
                    run_id = inference.inference_run_id(
                        ev.event_id, DEFAULT_COMPONENT, inference.STUDENT_TWIN_MODEL_VERSION_ID, payload_hash)
                    started = time.time()
                    finished = time.time()
                    created_run = inference.insert_inference_run(
                        session, run_id, ev.event_id, DEFAULT_COMPONENT,
                        inference.STUDENT_TWIN_MODEL_VERSION_ID, payload_hash,
                        eligibility_status="ELIGIBLE", execution_status="SUCCESS",
                        started_at=started, finished_at=finished,
                        latency_ms=(finished - started) * 1000.0,
                        device="cpu", offline=True, error_type=None, error_message_safe=None)
                    pred_id = inference.prediction_id(run_id, "student_twin_snapshot", _user_key(ev))
                    created_pred = inference.insert_prediction(
                        session, pred_id, run_id, ev.event_id, DEFAULT_COMPONENT,
                        inference.STUDENT_TWIN_MODEL_VERSION_ID, prediction_type="student_twin_snapshot",
                        target_ref=_user_key(ev), raw_score=None, normalized_score=None,
                        predicted_label=None, rank=None, weak_label=False,
                        score_semantics="deterministic_student_twin_state", payload=state)
                    if created_run:
                        report["inference_runs_created"] += 1
                    if created_pred:
                        report["predictions_created"] += 1
                    report["events_inferred"] += 1
            finally:
                replayer.close()
    finally:
        session.close()
    return report
