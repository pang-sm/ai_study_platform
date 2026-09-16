"""Canonical LearningContext for the zhixue-ai product backend.

LearningContext is a REQUEST / BUSINESS context — NOT a scientific learner state.
It identifies the user, the learning space (``service_namespace``), and optional
domain references. It must never carry LLM-generated learner state or scientific
state (mastery / ability / P(correct) etc.).

Frozen service namespaces (SSOT §29 / §66):
  course_learning
  exam_11408
  programming

Canonical naming note: the Data Plane LearningEvent model column is ``service_key``
(legacy); the canonical application-layer name is ``service_namespace``. The mapping
``service_namespace -> service_key`` is done at the emitter/projection layer, not here.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ServiceNamespace(str, Enum):
    COURSE_LEARNING = "course_learning"
    EXAM_11408 = "exam_11408"
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

    programming_language: Optional[str] = None
    exercise_id: Optional[int] = None

    material_ids: Optional[list[str]] = None
    session_id: Optional[int] = None

    def to_dict(self) -> dict:
        """JSON-serializable, exclude unset (None) fields."""
        return self.model_dump(exclude_none=True)

    def to_event_context(self) -> dict:
        """Project to a LearningEvent-compatible context dict.

        Uses the canonical ``service_namespace`` key here; the emitter maps this onto
        the LearningEvent ``service_key`` column (value-identical for the three spaces).
        """
        return {
            "service_namespace": self.service_namespace.value,
            "course_id": self.course_id,
            "subject_key": self.subject_key,
            "chapter_id": self.chapter_id,
            "knowledge_point_id": self.knowledge_point_id,
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


def is_valid_service_namespace(value: str) -> bool:
    return value in VALID_SERVICE_NAMESPACES
