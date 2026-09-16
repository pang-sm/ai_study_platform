"""create StudentTwin SHADOW Data Plane tables

Revision ID: 20260915_0001
Revises:
Create Date: 2026-09-15

Creates the four Data Plane physical tables required for StudentTwin SHADOW-ready:
  learning_events, model_versions, model_inference_runs, model_predictions.

Intentionally does NOT create ``learning_outcomes`` (V1) or any of the STEP 5
proposed tables (subscriptions / usage_* / review_* / practice_* / plans / tasks).

Schema mirrors backend/data_plane/models.py exactly (no FK constraints, matching the
loose event-projection design; global FK enforcement is deferred — see report §9).

This is additive-only: no DROP, no destructive rename, no legacy table modification.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260915_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("event_schema_version", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("event_granularity", sa.String(20), nullable=False, server_default="ITEM_LEVEL"),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_attempt_id", sa.String(50), nullable=False),
        sa.Column("source_item_key", sa.String(255), nullable=False),
        sa.Column("source_item_index", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("source_user_ref", sa.String(50), nullable=True),
        sa.Column("service_key", sa.String(50), nullable=True),
        sa.Column("course_id", sa.String(100), nullable=True),
        sa.Column("subject_key", sa.String(50), nullable=True),
        sa.Column("question_id", sa.String(100), nullable=True),
        sa.Column("knowledge_point_ref_json", sa.Text(), nullable=True),
        sa.Column("item_snapshot_json", sa.Text(), nullable=True),
        sa.Column("item_content_hash", sa.String(64), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.Float(), nullable=False),
        sa.Column("ingested_at", sa.Float(), nullable=False),
        sa.Column("source_payload_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("snapshot_capture_mode", sa.String(20), nullable=False, server_default="LIVE_EMITTER"),
        sa.Column("snapshot_completeness", sa.String(10), nullable=False, server_default="FULL"),
        sa.Column("snapshot_missing_fields_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source_type", "source_attempt_id", "source_item_key",
                            name="uq_learning_event_source_item"),
    )
    op.create_index("ix_learning_events_user_id", "learning_events", ["user_id"])
    op.create_index("ix_learning_events_source_attempt", "learning_events",
                    ["source_type", "source_attempt_id"])

    op.create_table(
        "model_versions",
        sa.Column("model_version_id", sa.String(64), primary_key=True),
        sa.Column("component_id", sa.String(50), nullable=False, index=True),
        sa.Column("runtime_release_id", sa.String(64), nullable=False),
        sa.Column("scientific_source_class", sa.String(64), nullable=True),
        sa.Column("scientific_source_sha", sa.String(64), nullable=True),
        sa.Column("asset_version", sa.String(64), nullable=True),
        sa.Column("checkpoint_sha", sa.String(64), nullable=True),
        sa.Column("variant_id", sa.String(64), nullable=True),
        sa.Column("family", sa.String(64), nullable=True),
        sa.Column("capability_id", sa.String(64), nullable=True),
        sa.Column("product_role", sa.String(20), nullable=True),
        sa.Column("ontology_version", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "model_inference_runs",
        sa.Column("inference_run_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False, index=True),
        sa.Column("component_id", sa.String(50), nullable=False, index=True),
        sa.Column("model_version_id", sa.String(64), nullable=False),
        sa.Column("runtime_release_id", sa.String(64), nullable=False),
        sa.Column("input_contract_version", sa.String(16), nullable=False),
        sa.Column("input_payload_hash", sa.String(64), nullable=False),
        sa.Column("eligibility_status", sa.String(20), nullable=False),
        sa.Column("execution_status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("finished_at", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("device", sa.String(16), nullable=True),
        sa.Column("offline", sa.Boolean(), nullable=True),
        sa.Column("error_type", sa.String(64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "model_predictions",
        sa.Column("prediction_id", sa.String(64), primary_key=True),
        sa.Column("inference_run_id", sa.String(64), nullable=False, index=True),
        sa.Column("event_id", sa.String(36), nullable=False, index=True),
        sa.Column("component_id", sa.String(50), nullable=False, index=True),
        sa.Column("model_version_id", sa.String(64), nullable=False),
        sa.Column("prediction_type", sa.String(64), nullable=False),
        sa.Column("target_ref", sa.String(100), nullable=True),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("normalized_score", sa.Float(), nullable=True),
        sa.Column("predicted_label", sa.String(64), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("weak_label", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("score_semantics", sa.String(200), nullable=False),
        sa.Column("prediction_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("model_predictions")
    op.drop_table("model_inference_runs")
    op.drop_table("model_versions")
    op.drop_table("learning_events")
