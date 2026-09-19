"""Canonical LearningContext for the zhixue-ai product backend.

LearningContext is a REQUEST / BUSINESS context — NOT a scientific learner state.
It identifies the user, the learning space (``service_namespace``), and optional
domain references. It must never carry LLM-generated learner state or scientific
state (mastery / ability / P(correct) etc.).

Frozen service namespaces (SSOT §29 / §66):
  course_learning
  exam_prep
  programming

Canonical naming note: the Data Plane LearningEvent model column is ``service_key``
(legacy); the canonical application-layer name is ``service_namespace``. The mapping
``service_namespace -> service_key`` is done at the emitter/projection layer, not here.

STEP7H1: the exam space's canonical namespace is ``exam_prep`` (all national
standardized postgraduate exam subjects). ``exam_11408`` and friends are INPUT-only
aliases normalized once here — they are never a canonical storage value. The historical
string still exists in the product as the LEGACY MEMBERSHIP service key and the LEGACY
QUOTA bucket key; those are a different dimension and are not renamed by this change.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ServiceNamespace(str, Enum):
    COURSE_LEARNING = "course_learning"
    EXAM_PREP = "exam_prep"
    PROGRAMMING = "programming"


class LearningContext(BaseModel):
    """Immutable, validated business context for one learning interaction.

    ``frozen=True`` makes instances hashable and mutation-controlled; use
    ``model_copy(update=...)`` to derive a new context rather than mutate in place.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    user_id: Optional[int] = None
    service_namespace: ServiceNamespace

    # domain references (optional, canonical IDs/references)
    course_id: Optional[str] = None
    subject_key: Optional[str] = None
    chapter_id: Optional[str] = None
    knowledge_point_id: Optional[str] = None

    # exam_prep domain references. ``subject_key`` above stays the LEGACY MIRROR of
    # ``exam_module_id`` so the frozen STEP7D exam adapters keep their behaviour; the
    # canonical exam fields are these three.
    exam_track_id: Optional[str] = None
    exam_subject_id: Optional[str] = None
    exam_module_id: Optional[str] = None

    programming_language: Optional[str] = None
    exercise_id: Optional[int] = None

    material_ids: Optional[list[str]] = None
    session_id: Optional[int] = None

    def to_dict(self) -> dict:
        """JSON-serializable, exclude unset (None) fields."""
        return self.model_dump(exclude_none=True)

    def event_subject_key(self) -> Optional[str]:
        """The value the ``subject_key`` EVENT column must carry.

        For exam_prep the event's subject is the EXAM SUBJECT (``cs_408``), while the
        context's ``subject_key`` remains the module mirror. Keeping the two apart here
        means no caller has to remember the rule.
        """
        return resolve_event_subject_key(self.to_dict())

    def to_event_context(self) -> dict:
        """Project to a LearningEvent-compatible context dict.

        Uses the canonical ``service_namespace`` key here; the emitter maps this onto
        the LearningEvent ``service_key`` column (value-identical for the three spaces).

        ``exam_track_id`` is deliberately ABSENT: a track is the learner's own subject
        bundle choice, not an attribute of the fact, so the same event must not differ
        because two learners picked different bundles.
        """
        return {
            "service_namespace": self.service_namespace.value,
            "course_id": self.course_id,
            "subject_key": self.event_subject_key(),
            "chapter_id": self.chapter_id,
            "knowledge_point_id": self.knowledge_point_id,
            "exam_module_id": self.exam_module_id,
            "programming_language": self.programming_language,
            "exercise_id": self.exercise_id,
            "material_ids": self.material_ids,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearningContext":
        return cls(**data)


# Frozen namespace values for validation helpers.
VALID_SERVICE_NAMESPACES = frozenset(ns.value for ns in ServiceNamespace)

# Legacy INPUT aliases → canonical namespace. These exist so historical callers that
# say "course" or "exam_11408" keep working; they are normalized ONCE at the boundary.
# No module may implement its own ``if service == "course"`` branch, and no durable write
# may store a legacy value: canonical storage is always the normalized namespace.
LEGACY_NAMESPACE_ALIASES = {
    "course": ServiceNamespace.COURSE_LEARNING.value,
    "course-learning": ServiceNamespace.COURSE_LEARNING.value,
    "course_learning": ServiceNamespace.COURSE_LEARNING.value,
    "exam": ServiceNamespace.EXAM_PREP.value,
    "exam-408": ServiceNamespace.EXAM_PREP.value,
    "exam_408": ServiceNamespace.EXAM_PREP.value,
    "exam408": ServiceNamespace.EXAM_PREP.value,
    "exam-11408": ServiceNamespace.EXAM_PREP.value,
    "exam_11408": ServiceNamespace.EXAM_PREP.value,
    "11408": ServiceNamespace.EXAM_PREP.value,
    "exam-prep": ServiceNamespace.EXAM_PREP.value,
    "exam_prep": ServiceNamespace.EXAM_PREP.value,
    "programming": ServiceNamespace.PROGRAMMING.value,
    "code": ServiceNamespace.PROGRAMMING.value,
}


def normalize_service_namespace(value) -> str:
    """Legacy alias or canonical value → the canonical namespace string.

    Raises ValueError for anything that is not a known learning space, so an unknown
    namespace fails loudly instead of being filed under a default.
    """
    if isinstance(value, ServiceNamespace):
        return value.value
    key = str(value or "").strip().lower()
    if key in LEGACY_NAMESPACE_ALIASES:
        return LEGACY_NAMESPACE_ALIASES[key]
    raise ValueError(f"unknown service namespace {value!r}")


def is_legacy_namespace_alias(value) -> bool:
    key = str(value or "").strip().lower()
    return key in LEGACY_NAMESPACE_ALIASES and key != LEGACY_NAMESPACE_ALIASES[key]


def is_valid_service_namespace(value: str) -> bool:
    """True only for a CANONICAL namespace value (legacy aliases are not canonical)."""
    return value in VALID_SERVICE_NAMESPACES


def resolve_event_subject_key(context: dict | None) -> Optional[str]:
    """The ``subject_key`` value a LearningEvent row must carry for a context dict.

    For exam_prep the event's subject is the EXAM SUBJECT; the context dict's own
    ``subject_key`` is the legacy module mirror. Producers that read a STORED context
    (rather than a live ``LearningContext``) must go through this, so the rule lives in
    one place instead of being re-derived by each emitter.
    """
    data = context or {}
    namespace = data.get("service_namespace")
    if namespace in (ServiceNamespace.EXAM_PREP.value, "exam_11408") \
            and data.get("exam_subject_id"):
        return data["exam_subject_id"]
    return data.get("subject_key")
