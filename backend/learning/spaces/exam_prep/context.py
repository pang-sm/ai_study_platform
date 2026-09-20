"""Exam Prep LearningContext construction — the single place an exam context is built.

There is exactly ONE canonical ``LearningContext`` in this product; Exam Prep extends it
with ``exam_track_id`` / ``exam_subject_id`` / ``exam_module_id`` rather than introducing
a second ``ExamLearningContext`` type. Endpoints must never assemble these fields by
hand — they call one of the builders below.

Contract (STEP7H0 §7 / STEP7H1 §7):

    exam_track_id    the learner's preparation bundle      cs_408
    exam_subject_id  the actual exam paper                 cs_408
    exam_module_id   a part of that subject                data_structure

    LearningContext.subject_key  = LEGACY MIRROR of exam_module_id
                                   (keeps the frozen STEP7D exam adapters behaving)
    LearningEvent.subject_key    = exam_subject_id  (via ``event_subject_key()``)

CS408 is currently the only exam with real data, so it is the only adapter here. A new
subject gets its own adapter when it gets real content (STEP7H4) — not before.
"""
from __future__ import annotations

from core.learning_context import LearningContext, ServiceNamespace

from .catalog import CS408_MODULE_DISPLAY, CS408_SUBJECT, CS408_TRACK
from .scope import resolve_cs408_module

EXAM_NAMESPACE = ServiceNamespace.EXAM_PREP.value


class ExamContextError(ValueError):
    """An exam context that cannot be built."""


def build_exam_context(
    user,
    *,
    exam_track_id: str,
    exam_subject_id: str,
    exam_module_id: str | None = None,
    chapter_id=None,
    knowledge_point_id=None,
    material_ids=None,
    session_id=None,
) -> LearningContext:
    """Build the canonical exam-scoped ``LearningContext``.

    ``subject_key`` is set to ``exam_module_id`` on purpose: it is the LEGACY MIRROR that
    the frozen STEP7D exam adapters and QuestionRef contexts already read. The canonical
    fields are the ``exam_*`` ones.
    """
    track = str(exam_track_id or "").strip()
    subject = str(exam_subject_id or "").strip()
    if not track or not subject:
        raise ExamContextError("exam_track_id and exam_subject_id are required")
    module = _str_or_none(exam_module_id)
    return LearningContext(
        user_id=getattr(user, "id", None),
        service_namespace=ServiceNamespace.EXAM_PREP,
        exam_track_id=track,
        exam_subject_id=subject,
        exam_module_id=module,
        subject_key=module,
        chapter_id=_str_or_none(chapter_id),
        knowledge_point_id=_str_or_none(knowledge_point_id),
        material_ids=[str(m) for m in material_ids] if material_ids else None,
        session_id=session_id,
    )


def cs408_context(user, *, module_key=None, **overrides) -> LearningContext:
    """CS408 adapter: a legacy module key becomes (cs_408, cs_408, module).

    Callers holding a legacy ``subject_key`` must go through here rather than writing the
    mapping themselves.
    """
    return build_exam_context(
        user, exam_track_id=CS408_TRACK, exam_subject_id=CS408_SUBJECT,
        exam_module_id=module_key, **overrides)


def canonical_module_concept(module_key, stored_concept_id) -> str | None:
    """A STORED concept id → the canonical leaf code it provably is, or ``None``.

    ACCEL_PRODUCT_S9. This exists for the LEGACY MIRROR boundary, where the value being
    read is an unvalidated string written by an older release — possibly a practice
    sub-group label, possibly the ``computer_network`` chapter-4 numeric collision. Such a
    value is legitimate CONTENT provenance, but it is not a canonical concept and must
    never be promoted into the concept slot that reaches a learning event and, through it,
    a training dataset: the dataset would then carry a concept key no product fact asserts.

    ``None`` is the honest answer for every such value, and it is a DIFFERENT answer from
    "the caller declared no concept" — both end up absent, and both are correct. A value
    that IS canonical comes back unchanged; nothing is normalised, truncated or guessed.

    The resolver is imported lazily and used rather than restated: concept identity has
    exactly one owner (``science.concept_coverage``) and a second copy of the rules here
    would be the drift this function exists to prevent.
    """
    module = str(module_key or "").strip()
    stored = str(stored_concept_id or "").strip()
    if not module or not stored:
        return None
    from science import concept_coverage
    return concept_coverage.canonical_leaf_code(module, knowledge_point_id=stored)


def cs408_context_from_values(user, *values, **overrides) -> LearningContext:
    """CS408 adapter for callers holding mixed legacy scope strings.

    Accepts whatever an existing endpoint has on hand — ``data_structure_11408``, a bare
    module key, ``11408 数据结构`` or ``数据结构`` — and resolves the module. A value that
    is a legacy scope id naming an unknown module raises (see ``scope.parse_legacy_exam_scope_id``).
    """
    return cs408_context(user, module_key=resolve_cs408_module(*values), **overrides)


def cs408_module_display(module_key) -> str:
    return CS408_MODULE_DISPLAY.get((module_key or "").strip(), (module_key or "").strip())


def assert_exam_matches(context: LearningContext, *, exam_subject_id: str | None = None,
                        exam_module_id: str | None = None) -> None:
    """Guard for cross-subject/module access: a context may only be used where it fits."""
    if context.service_namespace != ServiceNamespace.EXAM_PREP:
        raise ExamContextError("context is not an exam_prep context")
    if exam_subject_id is not None and context.exam_subject_id != exam_subject_id:
        raise ExamContextError(
            f"context is for subject {context.exam_subject_id!r}, not {exam_subject_id!r}")
    if exam_module_id is not None and context.exam_module_id != exam_module_id:
        raise ExamContextError(
            f"context is for module {context.exam_module_id!r}, not {exam_module_id!r}")


def _str_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
