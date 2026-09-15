"""Product-side HTTP client for the Scientific Runtime Service (contract v1).

The Product Backend does NOT import ``zhixue_runtime``; it delegates scientific inference
to the separate Scientific Runtime Service over localhost HTTP.  This module maps a
product LearningEvent to the contract-v1 event and performs the HTTP call + validation.
"""
import json

import httpx

from core import config

CONTRACT_VERSION = 1

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


def _user_ref(le) -> str:
    return str(le.user_id) if le.user_id is not None else (le.source_user_ref or le.event_id)


def build_request(target, history) -> dict:
    """Build a StudentTwinInferenceRequest for a target event from its ordered history."""
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": "run-" + target.event_id,
        "runtime_release_id": config.SCIENTIFIC_RUNTIME_RELEASE_ID,
        "user_ref": _user_ref(target),
        "target_event_id": target.event_id,
        "events": [map_learning_event(e) for e in history],
    }


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
        if data.get("contract_version") != CONTRACT_VERSION:
            raise RuntimeClientError(
                f"unsupported runtime contract_version {data.get('contract_version')}"
            )
        return data
