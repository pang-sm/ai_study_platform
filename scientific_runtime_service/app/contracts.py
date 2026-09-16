"""Typed StudentTwin inference DTOs (contract v1).

Frozen request/response contract shared with the Product Backend runtime client. Optional
fields are explicitly nullable — neither side may fabricate a value for a missing field.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .config import COMPONENT_ID, CONTRACT_VERSION, RUNTIME_RELEASE_ID


class StudentTwinEvent(BaseModel):
    event_id: str
    occurred_at: float
    activity_type: str
    correct: bool
    source: Optional[str] = None
    item_id: Optional[str] = None
    concept_ref: Optional[str] = None
    response_time_ms: Optional[int] = None
    attempt_no: Optional[int] = None
    hints: Optional[int] = None


class StudentTwinInferenceRequest(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: Optional[str] = None
    user_ref: str
    target_event_id: str
    events: list[StudentTwinEvent]


class StudentTwinInferenceResponse(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: str
    component_id: str = COMPONENT_ID
    scientific_source_class: str
    scientific_source_commit: str
    target_event_id: str
    replayed_events: int
    state: dict[str, Any]
    latency_ms: float


class CapabilitiesResponse(BaseModel):
    runtime_release_id: str
    components: list[str]
