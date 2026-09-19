"""QuestionRef — the canonical typed reference to "what was practised".

A QuestionRef POINTS AT a question; it never copies the question. The 9333-item exam
bank, the 1923 programming exercises and every material-derived question stay exactly
where they are. Copying them into a unified question table would duplicate the
product's static assets and immediately start drifting from them.

Source types are the SSOT §19 canonical set. Legacy origins that are not in that set
map onto it, and the raw origin is always preserved in ``raw_source`` so no provenance
is lost by the mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.learning_context import ServiceNamespace, normalize_service_namespace


class QuestionSourceType(str, Enum):
    """Canonical question provenance (SSOT §19, frozen set)."""

    STATIC_QUESTION_BANK = "static_question_bank"   # exam_question_bank / 题库
    PAST_EXAM = "past_exam"                          # 历年真题
    AI_GENERATED = "AI_generated"                    # AI 出题
    MATERIAL_GENERATED = "material_generated"        # 资料/课程材料生成
    PROGRAMMING_EXERCISE = "programming_exercise"    # 编程练习
    ADAPTIVE = "adaptive"                            # 自适应选题（V1，本轮不实现）


# Legacy (table, practice context) → canonical source type. The mapping is explicit so
# that an unmapped legacy origin is a loud failure rather than a silent guess.
# Keys carry the CANONICAL namespace; a legacy caller saying "exam_11408" is normalized
# on the way in (``resolve_source_type``), so both spellings resolve identically.
LEGACY_SOURCE_MAP: dict[tuple[str, str], QuestionSourceType] = {
    ("course_learning", "questions"): QuestionSourceType.MATERIAL_GENERATED,
    ("course_learning", "ai_generated_questions"): QuestionSourceType.AI_GENERATED,
    ("exam_prep", "exam_question_bank"): QuestionSourceType.STATIC_QUESTION_BANK,
    ("exam_prep", "past_paper"): QuestionSourceType.PAST_EXAM,
    ("exam_prep", "ai_generated_questions"): QuestionSourceType.AI_GENERATED,
    ("programming", "programming_exercises"): QuestionSourceType.PROGRAMMING_EXERCISE,
    ("programming", "code_challenges"): QuestionSourceType.PROGRAMMING_EXERCISE,
}


def resolve_source_type(service_namespace: str, legacy_origin: str) -> QuestionSourceType:
    """Map a legacy question origin to the canonical source type.

    Raises for an unknown origin: a question whose provenance cannot be named must not
    be quietly filed under a default.
    """
    try:
        namespace = normalize_service_namespace(service_namespace)
    except ValueError:
        namespace = service_namespace
    key = (namespace, legacy_origin)
    if key not in LEGACY_SOURCE_MAP:
        raise KeyError(f"no canonical question source for {key!r}")
    return LEGACY_SOURCE_MAP[key]


@dataclass(frozen=True)
class QuestionRef:
    """Canonical, typed pointer to a practised question.

    ``source_id`` is the identity within ``source_type`` — for a static bank row it is
    the bank id, for an AI-generated question the generated-question id. The pair
    ``(source_type, source_id)`` is the question identity; it is deliberately NOT the
    attempt identity, because the same question is answered many times.
    """

    source_type: QuestionSourceType
    source_id: str
    service_namespace: ServiceNamespace
    source_version: str | None = None
    context: dict = field(default_factory=dict)
    raw_source: dict = field(default_factory=dict)

    def __post_init__(self):
        if not str(self.source_id).strip():
            raise ValueError("QuestionRef.source_id must be non-empty")

    @property
    def question_identity(self) -> tuple[str, str]:
        return (self.source_type.value, str(self.source_id))

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type.value,
            "source_id": str(self.source_id),
            "service_namespace": self.service_namespace.value,
            "source_version": self.source_version,
            "context": self.context or {},
            "raw_source": self.raw_source or {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionRef":
        return cls(
            source_type=QuestionSourceType(data["source_type"]),
            source_id=str(data["source_id"]),
            service_namespace=ServiceNamespace(data["service_namespace"]),
            source_version=data.get("source_version"),
            context=dict(data.get("context") or {}),
            raw_source=dict(data.get("raw_source") or {}),
        )


def make_ref(source_type: QuestionSourceType, source_id, service_namespace: ServiceNamespace,
             *, context: dict | None = None, raw_source: dict | None = None,
             source_version: str | None = None) -> QuestionRef:
    return QuestionRef(
        source_type=source_type,
        source_id=str(source_id),
        service_namespace=service_namespace,
        source_version=source_version,
        context=context or {},
        raw_source=raw_source or {},
    )
