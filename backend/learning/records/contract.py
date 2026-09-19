"""Typed wire contract for the Learning Records read surface (F1C6 closure).

These models exist so the OpenAPI document — and therefore the generated TypeScript
client — describes the record shape concretely instead of ``200 {}``. They are a
DECLARATION of what :mod:`learning.records.service` already returns; the service remains
the single source of the values.

Every field below is a reference or a factual metric. There is no field for learner
state, mastery, ability, or any scientific output, and none may be added here.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RecordSourceRef(BaseModel):
    """A REFERENCE to the domain row that owns the fact. Never the fact itself."""

    type: str
    id: str | None = None
    item_key: str | None = None


class RecordContext(BaseModel):
    """Domain references carried by the event, when the producing space has them."""

    knowledge_point_id: str | None = None
    exam_module_id: str | None = None
    course_id: str | None = None
    subject_key: str | None = None


class RecordSummary(BaseModel):
    """Small per-event-type factual metadata.

    Fields are populated per event type; unset fields are omitted. There is no
    ``mastery`` / ``confidence`` / probability field by design — a record states what
    factually happened, not what a model thinks.
    """

    # practice / programming families
    correct: bool | None = None
    score: float | None = None
    question_source_type: str | None = None
    question_source_id: str | None = None
    # knowledge
    new_status: str | None = None
    old_status: str | None = None
    # material
    material_id: str | None = None
    # audit-only (returned only with include_audit=true)
    capability: str | None = None
    status: str | None = None


class RecordView(BaseModel):
    """One user-facing learning record."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    record_category: str | None = None
    service_namespace: str
    occurred_at: str | None = Field(
        default=None, description="UTC ISO-8601 with +00:00 offset")
    schema_version: int | None = None
    context: RecordContext | None = None
    source: RecordSourceRef
    summary: RecordSummary | None = None


class RecordDetail(RecordView):
    """A single record, with the honest statement of what recovery is possible."""

    recovery: str


class RecordPage(BaseModel):
    """Cursor-paginated newest-first page. There is no total count by design."""

    records: list[RecordView]
    next_cursor: str | None = Field(
        default=None, description="Opaque; pass back as ?cursor= to fetch the next page")
    has_more: bool


# ----------------------------------------------------------------- summary

class RecordSummaryWindow(BaseModel):
    start_at: str | None = None
    end_at: str | None = None
    timezone: str = "UTC"


class RecordsSummaryResponse(BaseModel):
    """Deterministic study-history counts. NOT mastery, ability, or learner state."""

    window: RecordSummaryWindow
    service_namespace: str | None = None
    exam_module_id: str | None = None
    total_events: int
    practice_attempts: int
    graded_attempts: int
    factual_correct: int
    factual_incorrect: int
    ungraded_attempts: int
    programming_submissions: int
    material_interactions: int
    knowledge_status_changes: int
    by_category: dict[str, int]
    by_event_type: dict[str, int]
    metrics_semantics: str


# ----------------------------------------------------------------- taxonomy

class OwnershipEntry(BaseModel):
    business_fact: str
    event_type: str
    authoritative_producer: str
    event_identity: str
    scientific_eligible: bool
    status: str


class RecordsTaxonomyResponse(BaseModel):
    """The frozen taxonomy + the one-fact-one-owner registry (developer reference)."""

    event_schema_version: int
    active_event_types: list[str]
    deferred_event_types: list[str]
    user_facing_event_types: list[str]
    audit_only_event_types: list[str]
    categories: list[str]
    student_twin_eligible_types: list[str]
    ownership_matrix: list[OwnershipEntry]
