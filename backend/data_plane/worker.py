"""DataProducerWorker (Phase 6R): orchestrates scientific inference via the runtime service.

Only ``student_twin`` is supported this phase.  The worker is manual/--once (no automatic
startup).  It is gated by ``DATA_PRODUCER_EXECUTION_ENABLED`` (default false), separate from
``DATA_PLANE_WRITE_ENABLED``.

Execution path::

    LearningEvent (target) -> full ordered history -> runtime_client (HTTP)
        -> Scientific Runtime Service (zhixue_runtime) -> ModelInferenceRun -> ModelPrediction

Target selection and history loading are strictly separated: ``--event-id`` / ``--limit``
only select TARGET events; each target always gets its FULL history (same user, up to and
including the target, ordered by occurred_at/event_id, no future leakage).

The worker is a DATA_PRODUCER: it writes ``model_versions`` / ``model_inference_runs`` /
``model_predictions`` only.  It never mutates product tables, never runs a scientific
formula in-process, and never changes a product decision.
"""
import logging
import time

from sqlalchemy import and_, or_

from core import config

from . import eligibility, inference, runtime_client
from .models import LearningEvent

logger = logging.getLogger("data_plane.worker")

DEFAULT_COMPONENT = "student_twin"


def execution_enabled(session=None) -> bool:
    """Worker runs only when the data-producer flag is on AND the effective StudentTwin
    mode is INTERNAL (shadow) or ADVISORY. OFF (safe default) blocks the whole pipeline.

    ``session`` (optional) enables the persisted app_runtime_flags value to be consulted
    (env override → DB flag → OFF). Without a session, only the env override applies.
    """
    return (config.data_producer_execution_enabled()
            and config.effective_student_twin_mode(session) != "off")


def _is_eligible_event(ev) -> bool:
    """A course_practice event is runtime-ELIGIBLE for student_twin only with a real outcome."""
    if ev.correct is None:
        return False
    return eligibility.evaluate(DEFAULT_COMPONENT, {})["eligibility_status"] == "ELIGIBLE"


def _load_history(session, target) -> list:
    """Full eligible history for the target's user, up to and including the target.

    Canonical boundary: same user, ``occurred_at < target`` OR (``==`` AND
    ``event_id <= target.event_id``), ordered by (occurred_at, event_id). The last item is
    always the target. No future leakage, no cross-user leakage.
    """
    if target.user_id is not None:
        identity = LearningEvent.user_id == target.user_id
    else:
        identity = LearningEvent.source_user_ref == target.source_user_ref

    boundary = or_(
        LearningEvent.occurred_at < target.occurred_at,
        and_(LearningEvent.occurred_at == target.occurred_at,
             LearningEvent.event_id <= target.event_id),
    )
    return (session.query(LearningEvent)
            .filter(LearningEvent.event_type == "course_practice",
                    LearningEvent.correct.isnot(None),
                    identity,
                    boundary)
            .order_by(LearningEvent.occurred_at, LearningEvent.event_id)
            .all())


def run_once(SessionLocal, limit: int = None, event_id: str = None) -> dict:
    """Run one pass of the worker over eligible LearningEvent TARGETS (full history each)."""
    report = {"events_scanned": 0, "events_eligible": 0, "events_inferred": 0,
              "inference_runs_created": 0, "predictions_created": 0,
              "errors": 0, "skipped_not_enabled": False}

    # fast path: data-producer flag alone can short-circuit without opening a session
    if not config.data_producer_execution_enabled():
        report["skipped_not_enabled"] = True
        return report

    session = SessionLocal()
    try:
        if not execution_enabled(session):
            report["skipped_not_enabled"] = True
            return report
        inference.ensure_student_twin_model_version(session)

        # ---- target selection (independent of history) ----
        target_q = (session.query(LearningEvent)
                    .filter(LearningEvent.event_type == "course_practice",
                            LearningEvent.correct.isnot(None))
                    .order_by(LearningEvent.user_id, LearningEvent.occurred_at, LearningEvent.event_id))
        if event_id:
            target_q = target_q.filter(LearningEvent.event_id == event_id)
        if limit:
            target_q = target_q.limit(limit)
        targets = target_q.all()
        report["events_scanned"] = len(targets)

        client = runtime_client.StudentTwinRuntimeClient()

        for target in targets:
            if not _is_eligible_event(target):
                continue
            report["events_eligible"] += 1

            # per-target isolation: one bad target must not drop the others
            try:
                history = _load_history(session, target)
                request = runtime_client.build_request(target, history)
                payload_hash = runtime_client.canonical_input_hash(request)
                run_id = inference.inference_run_id(
                    target.event_id, DEFAULT_COMPONENT,
                    inference.STUDENT_TWIN_MODEL_VERSION_ID, payload_hash)
                started = time.time()
                response = client.infer(request)
                finished = time.time()
                state = response["state"]
            except Exception as exc:
                logger.warning("student_twin inference failed for event %s: %s",
                               target.event_id, type(exc).__name__)
                report["errors"] += 1
                continue

            created_run = inference.insert_inference_run(
                session, run_id, target.event_id, DEFAULT_COMPONENT,
                inference.STUDENT_TWIN_MODEL_VERSION_ID, payload_hash,
                eligibility_status="ELIGIBLE", execution_status="SUCCESS",
                started_at=started, finished_at=finished,
                latency_ms=(finished - started) * 1000.0,
                device="cpu", offline=True, error_type=None, error_message_safe=None)
            pred_id = inference.prediction_id(run_id, "student_twin_snapshot",
                                              runtime_client.user_ref(target))
            created_pred = inference.insert_prediction(
                session, pred_id, run_id, target.event_id, DEFAULT_COMPONENT,
                inference.STUDENT_TWIN_MODEL_VERSION_ID, prediction_type="student_twin_snapshot",
                target_ref=runtime_client.user_ref(target), raw_score=None, normalized_score=None,
                predicted_label=None, rank=None, weak_label=False,
                score_semantics="deterministic_student_twin_state", payload=state)
            if created_run:
                report["inference_runs_created"] += 1
            if created_pred:
                report["predictions_created"] += 1
            report["events_inferred"] += 1
    finally:
        session.close()
    return report


def run_loop(SessionLocal, interval_seconds: float = 30.0, max_iterations: int = None) -> dict:
    """Run the worker on an interval (lightweight loop; no Celery/Kafka/Redis).

    Each pass is run_once(); failures inside run_once are already isolated per target
    and never raise. Sleeps interval_seconds between passes. Stops after max_iterations
    if set (None = loop until interrupted). Returns a cumulative report.
    """
    cumulative = {
        "iterations": 0, "events_scanned": 0, "events_eligible": 0, "events_inferred": 0,
        "inference_runs_created": 0, "predictions_created": 0, "errors": 0,
        "skipped_not_enabled": False,
    }
    iterations = 0
    while True:
        iterations += 1
        report = run_once(SessionLocal)
        for key in ("events_scanned", "events_eligible", "events_inferred",
                    "inference_runs_created", "predictions_created", "errors"):
            cumulative[key] = cumulative[key] + report.get(key, 0)
        if report.get("skipped_not_enabled"):
            cumulative["skipped_not_enabled"] = True
        cumulative["iterations"] = iterations
        if max_iterations is not None and iterations >= max_iterations:
            break
        time.sleep(interval_seconds)
    return cumulative
