"""Product Data Plane SQLAlchemy models (Phase 2B1).

Only ``learning_events`` has a real producer this phase.  The other four tables are
declared so ``Base.metadata.create_all`` creates their schema, but they receive zero
real rows until later phases (model inference is NOT performed here).
"""
from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, UniqueConstraint

from database import Base
from models import utc_now


class LearningEvent(Base):
    __tablename__ = "learning_events"

    event_id = Column(String(36), primary_key=True)  # UUIDv5
    event_schema_version = Column(Integer, nullable=False, default=2)  # contract 1.2
    event_type = Column(String(50), nullable=False, index=True)
    event_granularity = Column(String(20), nullable=False, default="ITEM_LEVEL")

    source_type = Column(String(50), nullable=False)
    source_attempt_id = Column(String(50), nullable=False)
    source_item_key = Column(String(255), nullable=False)
    source_item_index = Column(Integer, nullable=False)

    user_id = Column(Integer, nullable=True)          # canonical User.id
    source_user_ref = Column(String(50), nullable=True)  # AIQuestionAttempt.username

    service_key = Column(String(50), nullable=True)
    course_id = Column(String(100), nullable=True)
    subject_key = Column(String(50), nullable=True)
    question_id = Column(String(100), nullable=True)
    knowledge_point_ref_json = Column(Text, nullable=True)

    item_snapshot_json = Column(Text, nullable=True)
    item_content_hash = Column(String(64), nullable=True)

    answer = Column(Text, nullable=True)
    correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    attempt_no = Column(Integer, nullable=True)

    # ACCEL_SPRINT_S5 attempt telemetry, carried onto the canonical fact stream so a
    # scientific reader can tell a measured duration from an unmeasured one without
    # opening the source row. NULL means the provenance was not observed; it is never
    # guessed. See ``learning.practice.telemetry`` for the admissible sources.
    response_time_source = Column(String(30), nullable=True)
    attempt_index = Column(Integer, nullable=True)

    occurred_at = Column(Float, nullable=False)
    ingested_at = Column(Float, nullable=False)
    source_payload_version = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String(255), nullable=False, unique=True)

    # snapshot provenance (Phase 2B0: source is NOT self-contained for backfill)
    snapshot_capture_mode = Column(String(20), nullable=False, default="LIVE_EMITTER")
    snapshot_completeness = Column(String(10), nullable=False, default="FULL")
    snapshot_missing_fields_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("source_type", "source_attempt_id", "source_item_key", name="uq_learning_event_source_item"),
        Index("ix_learning_events_user_id", "user_id"),
        Index("ix_learning_events_source_attempt", "source_type", "source_attempt_id"),
        # STEP 7F: the Learning Records query pattern — user-scoped, newest-first,
        # optional time window / namespace filter.
        Index("ix_learning_events_user_occurred", "user_id", "occurred_at"),
        Index("ix_learning_events_ns_occurred", "service_key", "occurred_at"),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    model_version_id = Column(String(64), primary_key=True)
    component_id = Column(String(50), nullable=False, index=True)
    runtime_release_id = Column(String(64), nullable=False)
    scientific_source_class = Column(String(64), nullable=True)
    scientific_source_sha = Column(String(64), nullable=True)
    asset_version = Column(String(64), nullable=True)
    checkpoint_sha = Column(String(64), nullable=True)
    variant_id = Column(String(64), nullable=True)
    family = Column(String(64), nullable=True)
    capability_id = Column(String(64), nullable=True)
    product_role = Column(String(20), nullable=True)
    ontology_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ModelInferenceRun(Base):
    __tablename__ = "model_inference_runs"

    inference_run_id = Column(String(64), primary_key=True)
    event_id = Column(String(36), nullable=False, index=True)
    component_id = Column(String(50), nullable=False, index=True)
    model_version_id = Column(String(64), nullable=False)
    runtime_release_id = Column(String(64), nullable=False)
    input_contract_version = Column(String(16), nullable=False)
    input_payload_hash = Column(String(64), nullable=False)
    eligibility_status = Column(String(20), nullable=False)
    execution_status = Column(String(20), nullable=False)
    started_at = Column(Float, nullable=True)
    finished_at = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    device = Column(String(16), nullable=True)
    offline = Column(Boolean, nullable=True)
    error_type = Column(String(64), nullable=True)
    error_message_safe = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    prediction_id = Column(String(64), primary_key=True)
    inference_run_id = Column(String(64), nullable=False, index=True)
    event_id = Column(String(36), nullable=False, index=True)
    component_id = Column(String(50), nullable=False, index=True)
    model_version_id = Column(String(64), nullable=False)
    prediction_type = Column(String(64), nullable=False)
    target_ref = Column(String(100), nullable=True)
    raw_score = Column(Float, nullable=True)
    normalized_score = Column(Float, nullable=True)
    predicted_label = Column(String(64), nullable=True)
    rank = Column(Integer, nullable=True)
    weak_label = Column(Boolean, nullable=False, default=False)
    score_semantics = Column(String(200), nullable=False)
    prediction_payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"

    outcome_id = Column(String(64), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    source_event_id = Column(String(36), nullable=False, index=True)
    reference_event_id = Column(String(36), nullable=True)
    outcome_type = Column(String(50), nullable=False)
    target_ref = Column(String(100), nullable=True)
    value = Column(Text, nullable=True)
    numeric_value = Column(Float, nullable=True)
    observed_at = Column(Float, nullable=False)
    observation_window = Column(String(20), nullable=True)
    label_source = Column(String(30), nullable=False)
    label_quality = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=utc_now)
