"""Restricted production canary: exercise the full StudentTwin data flywheel once.

Uses the Product Data Plane code (worker + runtime_client + inference) — it does NOT copy
any scientific formula. It connects only to the production persistent DB, picks the latest
eligible FULL/LIVE course_practice LearningEvent, replays its full history through the
Scientific Runtime Service, and verifies one idempotent ModelInferenceRun + ModelPrediction.

No user input. Sensitive values (username / answer / question text) are never logged.

Exit codes:
    0 = canary passed (or NO_ELIGIBLE_FULL_LIVE_EVENT)
    1 = failure
"""
import json
import os
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)

os.environ["DATA_PRODUCER_EXECUTION_ENABLED"] = "true"
os.environ.setdefault("SCIENTIFIC_RUNTIME_BASE_URL", "http://127.0.0.1:8101")

import database  # noqa: E402
from data_plane import inference, worker  # noqa: E402
from data_plane.models import (  # noqa: E402
    LearningEvent,
    ModelInferenceRun,
    ModelPrediction,
)


def _find_target(session):
    return (session.query(LearningEvent)
            .filter(LearningEvent.event_type == "course_practice",
                    LearningEvent.correct.isnot(None),
                    LearningEvent.snapshot_capture_mode == "LIVE_EMITTER",
                    LearningEvent.snapshot_completeness == "FULL")
            .order_by(LearningEvent.occurred_at.desc(), LearningEvent.event_id.desc())
            .first())


def main() -> int:
    session = database.SessionLocal()
    try:
        target = _find_target(session)
        if target is None:
            print("NO_ELIGIBLE_FULL_LIVE_EVENT")
            return 0  # safe no-op, 0 rows changed

        # L4: verify FULL snapshot + identity without logging sensitive values
        assert target.snapshot_capture_mode == "LIVE_EMITTER"
        assert target.snapshot_completeness == "FULL"
        missing = json.loads(target.snapshot_missing_fields_json or "[]")
        assert missing == [], "FULL snapshot must have no missing fields"

        # O: reconstruct expected history and verify semantics
        history = worker._load_history(session, target)
        assert len(history) >= 1, "history must include the target"
        assert history[-1].event_id == target.event_id, "last history item must be the target"
        for ev in history:
            if target.user_id is not None:
                assert ev.user_id == target.user_id, "cross-user leakage"
            else:
                assert ev.source_user_ref == target.source_user_ref, "cross-user leakage"
        for ev in history:
            assert ev.occurred_at < target.occurred_at or (
                ev.occurred_at == target.occurred_at and ev.event_id <= target.event_id
            ), "future leakage"

        pre_runs = session.query(ModelInferenceRun).count()
        pre_preds = session.query(ModelPrediction).count()

        # P: first run
        report = worker.run_once(database.SessionLocal, event_id=target.event_id)
        print("canary report:", json.dumps(report, default=str))
        assert report["events_inferred"] == 1, report
        assert report["inference_runs_created"] == 1, report
        assert report["predictions_created"] == 1, report

        run = (session.query(ModelInferenceRun)
               .filter_by(event_id=target.event_id)
               .order_by(ModelInferenceRun.created_at.desc()).first())
        assert run is not None and run.execution_status == "SUCCESS"
        assert run.eligibility_status == "ELIGIBLE"
        assert run.runtime_release_id == "zhixue-runtime-v1-phase1gr-p1"
        assert run.model_version_id == inference.STUDENT_TWIN_MODEL_VERSION_ID

        pred = session.query(ModelPrediction).filter_by(inference_run_id=run.inference_run_id).first()
        assert pred is not None
        assert pred.prediction_type == "student_twin_snapshot"
        assert pred.score_semantics == "deterministic_student_twin_state"
        payload = json.loads(pred.prediction_payload_json)
        assert payload, "prediction payload must be non-empty"
        assert "user_id" in payload and "concepts" in payload, "StudentState shape"

        # S: second run idempotency
        report2 = worker.run_once(database.SessionLocal, event_id=target.event_id)
        assert report2["inference_runs_created"] == 0, report2
        assert report2["predictions_created"] == 0, report2
        assert session.query(ModelInferenceRun).count() == pre_runs + 1
        assert session.query(ModelPrediction).count() == pre_preds + 1

        print("STUDENT_TWIN_PRODUCTION_CANARY: PASS")
        print("  target:", target.event_id[:8] + "...")
        print("  history_count:", len(history))
        print("  runtime_release:", run.runtime_release_id)
        print("  replayed_events:", len(history))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
