"""Inference data plane services: ModelVersion / ModelInferenceRun / ModelPrediction.

All writes are idempotent (INSERT OR IGNORE on a deterministic stable ID).  This keeps
repeated worker runs from creating duplicate rows.
"""
import time
import uuid

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import ModelVersion, ModelInferenceRun, ModelPrediction

# StudentTwin scientific provenance (frozen)
STUDENT_TWIN_MODEL_VERSION_ID = "student_twin@zhixue-runtime-v1-phase1gr@a16efa2"


def ensure_student_twin_model_version(session) -> ModelVersion:
    """Idempotently register the StudentTwin ModelVersion."""
    mv_id = STUDENT_TWIN_MODEL_VERSION_ID
    stmt = (sqlite_insert(ModelVersion).values(
        model_version_id=mv_id,
        component_id="student_twin",
        runtime_release_id="zhixue-runtime-v1-phase1gr",
        scientific_source_class="ORIGINAL_ARCHIVE_VERIFIED",
        scientific_source_sha="student_digital_twin@a16efa2",
        asset_version=None,
        checkpoint_sha=None,
        variant_id=None,
        family=None,
        capability_id="student_twin_snapshot",
        product_role="DATA_PRODUCER",
        ontology_version=None,
    ).on_conflict_do_nothing(index_elements=["model_version_id"]))
    session.execute(stmt)
    session.commit()
    return session.query(ModelVersion).filter(ModelVersion.model_version_id == mv_id).first()


def inference_run_id(event_id, component_id, model_version_id, input_payload_hash) -> str:
    name = f"{event_id}|{component_id}|{model_version_id}|{input_payload_hash}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


def prediction_id(run_id, prediction_type, target_ref) -> str:
    name = f"{run_id}|{prediction_type}|{target_ref or ''}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


def insert_inference_run(session, run_id, event_id, component_id, model_version_id,
                         input_payload_hash, eligibility_status, execution_status,
                         started_at=None, finished_at=None, latency_ms=None,
                         device="cpu", offline=True, error_type=None, error_message_safe=None) -> bool:
    stmt = (sqlite_insert(ModelInferenceRun).values(
        inference_run_id=run_id, event_id=event_id, component_id=component_id,
        model_version_id=model_version_id, runtime_release_id="zhixue-runtime-v1-phase1gr",
        input_contract_version="1", input_payload_hash=input_payload_hash,
        eligibility_status=eligibility_status, execution_status=execution_status,
        started_at=started_at, finished_at=finished_at, latency_ms=latency_ms,
        device=device, offline=offline, error_type=error_type, error_message_safe=error_message_safe,
    ).on_conflict_do_nothing(index_elements=["inference_run_id"]))
    r = session.execute(stmt)
    session.commit()
    return bool(r.rowcount)


def insert_prediction(session, pred_id, run_id, event_id, component_id, model_version_id,
                      prediction_type, target_ref=None, raw_score=None, normalized_score=None,
                      predicted_label=None, rank=None, weak_label=False, score_semantics="",
                      payload=None) -> bool:
    import json
    stmt = (sqlite_insert(ModelPrediction).values(
        prediction_id=pred_id, inference_run_id=run_id, event_id=event_id,
        component_id=component_id, model_version_id=model_version_id,
        prediction_type=prediction_type, target_ref=target_ref,
        raw_score=raw_score, normalized_score=normalized_score, predicted_label=predicted_label,
        rank=rank, weak_label=weak_label, score_semantics=score_semantics,
        prediction_payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) if payload else None,
    ).on_conflict_do_nothing(index_elements=["prediction_id"]))
    r = session.execute(stmt)
    session.commit()
    return bool(r.rowcount)
