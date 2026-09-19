"""Course Space identity + LearningContext construction.

COURSE IDENTITY (audited, not invented)
---------------------------------------
There is no ``Course`` table in this system, and STEP 7G does not create one: course
identity today is a free-form ``course_id`` string carried on
``course_learning_preferences`` (unique per username+course_id), ``course_progress``,
``knowledge_points``, ``questions``, ``study_materials`` and friends. Inventing a
Course/CourseChapter entity to make the architecture look tidier would be a schema
expansion the product does not need.

So identity is defined as exactly what the data supports:

    course identity   = the exact, whitespace-stripped ``course_id`` string
    chapter identity  = the chapter key carried in the course context
    knowledge identity= the knowledge point id/code within that course

Identity is compared by exact key, NEVER by display name — two courses may share a
chapter title, and a chapter title is presentation, not identity.

This module is the single place a course-scoped ``LearningContext`` is built; there is
no second CourseContext type.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.learning_context import (
    LearningContext,
    ServiceNamespace,
    normalize_service_namespace,
)

COURSE_NAMESPACE = ServiceNamespace.COURSE_LEARNING.value


class CourseContextError(ValueError):
    """A course context that cannot be built or does not belong to the caller."""


@dataclass(frozen=True)
class CourseRef:
    """Canonical, minimal course identity reference."""

    course_id: str
    display_name: str | None = None
    chapter_id: str | None = None
    knowledge_point_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.course_id:
            raise CourseContextError("course_id must be non-empty")

    @property
    def identity(self) -> str:
        return self.course_id

    def to_dict(self) -> dict:
        return {
            "course_id": self.course_id,
            "display_name": self.display_name,
            "chapter_id": self.chapter_id,
            "knowledge_point_id": self.knowledge_point_id,
            "metadata": self.metadata or {},
        }


def normalize_course_id(value) -> str:
    """Canonical course key.

    Only whitespace is stripped: the stored value is the key every existing row uses,
    so case-folding it here would silently split or merge real courses.
    """
    course_id = str(value or "").strip()
    if not course_id:
        raise CourseContextError("course_id is required")
    return course_id


def normalize_namespace(value=COURSE_NAMESPACE) -> str:
    """Course namespace through the ONE shared alias normalizer ("course" is input-only)."""
    return normalize_service_namespace(value)


def build_course_context(user, *, course_id, chapter_id=None, knowledge_point_id=None,
                         material_ids=None, session_id=None,
                         display_name=None) -> LearningContext:
    """Build the canonical LearningContext for a course interaction.

    ``chapter_id`` and ``knowledge_point_id`` are stored as strings on the context so
    that both numeric ids and code-style keys are carried without losing their form.
    """
    ref = CourseRef(
        course_id=normalize_course_id(course_id),
        display_name=display_name,
        chapter_id=_str_or_none(chapter_id),
        knowledge_point_id=_str_or_none(knowledge_point_id),
    )
    return LearningContext(
        user_id=getattr(user, "id", None),
        service_namespace=ServiceNamespace.COURSE_LEARNING,
        course_id=ref.course_id,
        chapter_id=ref.chapter_id,
        knowledge_point_id=ref.knowledge_point_id,
        material_ids=[str(m) for m in material_ids] if material_ids else None,
        session_id=session_id,
    )


def resolve_course_context(db, user, course_id, **overrides) -> tuple[CourseRef, LearningContext]:
    """Return (CourseRef, LearningContext) for a course the USER actually has.

    Cross-course protection starts here: a caller cannot build a context for a course
    the user has no preference/row for, so a course-A session can never be handed a
    course-B context.
    """
    from models import CourseLearningPreference

    key = normalize_course_id(course_id)
    preference = (db.query(CourseLearningPreference)
                  .filter(CourseLearningPreference.username == user.username,
                          CourseLearningPreference.course_id == key)
                  .first())
    if preference is None:
        raise CourseContextError(f"course {key!r} is not attached to this user")

    ref = CourseRef(
        course_id=key,
        display_name=(preference.display_name or preference.course_id),
        chapter_id=_str_or_none(overrides.get("chapter_id")),
        knowledge_point_id=_str_or_none(overrides.get("knowledge_point_id")),
        metadata={"mastery_level": preference.mastery_level,
                  "learning_goal": preference.learning_goal,
                  "is_started": bool(preference.is_started)},
    )
    context = build_course_context(
        user, course_id=key, chapter_id=ref.chapter_id,
        knowledge_point_id=ref.knowledge_point_id,
        material_ids=overrides.get("material_ids"),
        session_id=overrides.get("session_id"),
        display_name=ref.display_name)
    return ref, context


def assert_course_matches(context: LearningContext, course_id) -> None:
    """Guard for cross-course access: the context and the target course must agree."""
    if context.course_id != normalize_course_id(course_id):
        raise CourseContextError(
            f"context is for course {context.course_id!r}, not {course_id!r}")
    if context.service_namespace != ServiceNamespace.COURSE_LEARNING:
        raise CourseContextError("context is not a course_learning context")


def _str_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
