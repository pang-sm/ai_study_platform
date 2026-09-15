"""Product-side HTTP client for the Scientific Runtime Service (contract v1).

The Product Backend does NOT import ``zhixue_runtime``; it delegates scientific inference
to the separate Scientific Runtime Service over localhost HTTP.  This module maps a
product LearningEvent to the contract-v1 event, computes the canonical scientific-input
hash, and performs the HTTP call + full contract validation.
"""
import hashlib
import json

import httpx

from core import config

CONTRACT_VERSION = 1
COMPONENT_ID = "student_twin"
SCIENTIFIC_SOURCE_CLASS = "ORIGINAL_ARCHIVE_VERIFIED"
SCIENTIFIC_SOURCE_COMMIT = "a16efa27aac90d9c8d8d9ee703aefe5919f4839e"

ACTIVITY_TYPE_PRACTICE = "PRACTICE"


class RuntimeClientError(RuntimeError):
    """Raised when the Scientific Runtime Service call fails or returns an invalid contract."""


def map_learning_event(le) -> dict:
    """Map a product LearningEvent row to a contract-v1 event dict.

    Optional fields stay ``None`` when not recorded — never fabricated to 0/default.
    """
    concept = None
    if getattr(le, "knowledge_point_ref_json", None):
        try:
            kp = json.loads(le.knowledge_point_ref_json)
        except (ValueError, TypeError):
            kp = None
        if isinstance(kp, dict) and kp.get("value"):
            concept = kp["value"]

    return {
        "event_id": le.event_id,
        "occurred_at": le.occurred_at,
        "activity_type": ACTIVITY_TYPE_PRACTICE,
        "correct": le.correct,
        "source": le.source_type or "course_practice",
        "item_id": le.question_id,
        "concept_ref": concept,
        "response_time_ms": le.response_time_ms,
        "attempt_no": le.attempt_no,
        "hints": None,
    }


def user_ref(le) -> str:
    """Stable per-user key: canonical user_id, falling back only for foreign records."""
    return str(le.user_id) if le.user_id is not None else (le.source_user_ref or le.event_id)


def build_request(target, history) -> dict:
    """Build a StudentTwinInferenceRequest for a target event from its ordered history."""
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": "run-" + target.event_id,
        "runtime_release_id": config.SCIENTIFIC_RUNTIME_RELEASE_ID,
        "user_ref": user_ref(target),
        "target_event_id": target.event_id,
        "events": [map_learning_event(e) for e in history],
    }


def canonical_inference_payload(request: dict) -> dict:
    """Only the fields that actually influence scientific inference.

    Excludes tracing metadata (``request_id``) and any execution-generated timestamps.
    """
    return {
        "contract_version": request["contract_version"],
        "runtime_release_id": request["runtime_release_id"],
        "user_ref": request["user_ref"],
        "target_event_id": request["target_event_id"],
        "events": request["events"],
    }


def canonical_input_hash(request: dict) -> str:
    """SHA-256 over the canonical JSON of the scientific input (history included).

    Canonical form: UTF-8, sort_keys=True, ensure_ascii=False, separators=(",", ":").
    """
    payload = canonical_inference_payload(request)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class StudentTwinRuntimeClient:
    """Synchronous HTTP client to the Scientific Runtime Service (127.0.0.1:8101)."""

    def __init__(self, base_url=None, timeout=None):
        self.base_url = (base_url or config.scientific_runtime_base_url()).rstrip("/")
        self.timeout = timeout or config.scientific_runtime_timeout()

    def infer(self, request: dict) -> dict:
        url = f"{self.base_url}/v1/inference/student-twin"
        try:
            resp = httpx.post(url, json=request, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise RuntimeClientError(f"runtime service unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise RuntimeClientError(
                f"runtime service HTTP {resp.status_code}: {resp.text[:200]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeClientError(f"runtime service returned non-JSON: {exc}") from exc

        # --- full contract validation (a mismatch must never produce a Prediction) ---
        if data.get("contract_version") != CONTRACT_VERSION:
            raise RuntimeClientError(f"unsupported contract_version {data.get('contract_version')}")
        if data.get("request_id") != request["request_id"]:
            raise RuntimeClientError("runtime response request_id mismatch")
        if data.get("runtime_release_id") != config.SCIENTIFIC_RUNTIME_RELEASE_ID:
            raise RuntimeClientError(
                f"runtime_release_id mismatch: {data.get('runtime_release_id')}")
        if data.get("component_id") != COMPONENT_ID:
            raise RuntimeClientError(f"component_id mismatch: {data.get('component_id')}")
        if data.get("target_event_id") != request["target_event_id"]:
            raise RuntimeClientError("runtime response target_event_id mismatch")
        if data.get("replayed_events") != len(request["events"]):
            raise RuntimeClientError(
                f"replayed_events mismatch: {data.get('replayed_events')} != {len(request['events'])}")
        if data.get("scientific_source_class") != SCIENTIFIC_SOURCE_CLASS:
            raise RuntimeClientError("scientific_source_class mismatch")
        if data.get("scientific_source_commit") != SCIENTIFIC_SOURCE_COMMIT:
            raise RuntimeClientError("scientific_source_commit mismatch")
        return data
