"""Cross-process integration test: Product DataProducerWorker -> HTTP -> Scientific Runtime.

Requires the Scientific Runtime Service to be running on 127.0.0.1:8101 (started separately).
Uses a temp SQLite Product DB and a real LearningEvent fixture.
"""
import json
import os
import sys
import tempfile
import time

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)

_TMP = tempfile.mkdtemp(prefix="zhixue-integration-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/app.db"
os.environ["DATA_PRODUCER_EXECUTION_ENABLED"] = "true"
os.environ["SCIENTIFIC_RUNTIME_BASE_URL"] = "http://127.0.0.1:8101"

import database  # noqa: E402
from database import Base  # noqa: E402
import data_plane.models  # noqa: E402,F401  (register tables)
from data_plane import worker  # noqa: E402
from data_plane.models import LearningEvent, ModelInferenceRun, ModelPrediction  # noqa: E402

Base.metadata.create_all(database.engine)


def make_event(event_id, user_id, correct, occurred_at, kp_value="kp1"):
    return LearningEvent(
        event_id=event_id, event_schema_version=2, event_type="course_practice",
        event_granularity="ITEM_LEVEL", source_type="course_practice",
        source_attempt_id=f"att-{event_id}", source_item_key="q1:0", source_item_index=0,
        user_id=user_id, source_user_ref=f"user-{user_id}", service_key="course_learning",
        course_id=None, subject_key="math", question_id="q1",
        knowledge_point_ref_json=json.dumps({"type": "FREE_TEXT", "value": kp_value}),
        item_snapshot_json=json.dumps({"question_id": "q1", "question_text": "stem"}),
        item_content_hash="h", answer="B", correct=correct, score=None,
        response_time_ms=None, attempt_no=None, occurred_at=occurred_at,
        ingested_at=time.time(), source_payload_version=1,
        idempotency_key=f"course_practice:att-{event_id}:q1:0",
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="FULL",
        snapshot_missing_fields_json="[]",
    )


def main():
    session = database.SessionLocal()
    try:
        session.add(make_event("e1", 1, False, 1000.0))
        session.add(make_event("e2", 1, True, 1060.0))
        session.commit()

        r1 = worker.run_once(database.SessionLocal)
        print("run 1:", {k: r1[k] for k in ("events_inferred", "inference_runs_created", "predictions_created", "errors")})
        assert r1["events_inferred"] == 2
        assert r1["inference_runs_created"] == 2
        assert r1["predictions_created"] == 2
        assert r1["errors"] == 0

        # verify a real student_twin_snapshot prediction landed
        preds = session.query(ModelPrediction).order_by(ModelPrediction.event_id).all()
        assert [p.prediction_type for p in preds] == ["student_twin_snapshot", "student_twin_snapshot"]
        payload = json.loads(preds[1].prediction_payload_json)
        assert "global_ability" in payload and "concepts" in payload
        assert payload["user_id"] == "1"

        # second run must be fully idempotent
        r2 = worker.run_once(database.SessionLocal)
        assert r2["inference_runs_created"] == 0
        assert r2["predictions_created"] == 0
        assert session.query(ModelInferenceRun).count() == 2
        assert session.query(ModelPrediction).count() == 2

        print("CROSS-PROCESS INTEGRATION: PASS")
    finally:
        session.close()


if __name__ == "__main__":
    main()
