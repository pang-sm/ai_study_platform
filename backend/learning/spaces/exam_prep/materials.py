"""One 408 subject's material scope — the exam side of the ONE material pipeline.

``study_materials.course_id = "<module>_11408"`` is a scope this product has STORED since
long before STEP7H, and ``scope.py`` names it as real user data rather than something this
phase invented. The domain behind it is provisioned too: ``main._material_domain``
classifies that id as ``exam_11408``, ``membership.TRACK_SERVICE_KEY`` gives it its own
service key, and ``SERVICE_PLAN_CATALOG["exam_11408"]`` has carried per-tier material
storage quotas since the catalog was written.

What was missing was only the surface that reads and writes it: a 408 upload had no page
to happen on, and no way to be listed back. So this module adds no second material system.
It builds the SAME scope triple ``main.resolve_material_scope`` validates, over the SAME
``study_materials`` table, serialized by the SAME ``serialize_material_list_item`` the
course library uses. The one exam-specific fact here is which rows belong to which module,
and even that is the id ``scope.py`` derives rather than a rule of its own.

Retrieval scope is the other half of the same statement: a question asked in 数据结构 is
grounded in ``data_structure_11408`` material, never in every file its owner uploaded.
"""
from __future__ import annotations

from . import scope
from .catalog import CS408_MODULES

#: The material domain an exam-subject upload belongs to. It is the ``track`` the pipeline
#: resolves for a ``<module>_11408`` id and the key its quota is read under, so it is stated
#: once here and asserted against the resolver rather than assumed.
EXAM_MATERIAL_TRACK = "exam_11408"


def subject_material_names() -> dict[str, str]:
    """{stored scope id: the subject's own name}, for labelling an exam material anywhere it
    surfaces.

    The learner's library lists every file they own — a 408 upload, a course upload and a
    chat attachment are one library to the person who made them — so the 408 subjects have
    to be named in the same place the courses are, or their material would be labelled with
    the stored key instead.
    """
    return {
        scope.build_legacy_exam_scope_id(module): scope.build_legacy_scope_subject_name(module)
        for module in CS408_MODULES
    }


def subject_material_scope(module_key: str) -> dict:
    """The material scope of ONE 408 subject, in the pipeline's own vocabulary.

    Raises ``ExamScopeError`` for a module 408 does not have, so a bad key is refused here
    rather than filed under a scope nothing reads back.
    """
    return {
        "course_id": scope.build_legacy_exam_scope_id(module_key),
        "subject_key": scope.resolve_cs408_module(module_key) or "",
        "subject": scope.build_legacy_scope_subject_name(module_key),
        "track": EXAM_MATERIAL_TRACK,
    }


def list_subject_materials(db, user, module_key: str) -> dict:
    """This subject's own material library, newest first.

    Scoped by the exam scope id ALONE, which is the same discriminator ``_material_domain``
    classifies on: it is what makes a row this subject's, and a row whose ``subject_key``
    was written differently (or not at all) is still this subject's material. A file the
    learner sent to a chat, or uploaded for a 专业学习 course that happens to share the
    subject's display name, is not — those carry a different scope id and are listed by
    their own surface.
    """
    from main import serialize_material_list_item  # lazy: avoids an import cycle
    from models import StudyMaterial

    scoped = subject_material_scope(module_key)
    rows = (
        db.query(StudyMaterial)
        .filter(
            StudyMaterial.username == user.username,
            StudyMaterial.is_deleted.is_(False),
            StudyMaterial.course_id == scoped["course_id"],
        )
        .order_by(StudyMaterial.created_at.desc())
        .all()
    )
    return {
        "subject_key": scoped["subject_key"],
        "course_id": scoped["course_id"],
        "items": [serialize_material_list_item(row) for row in rows],
        "total": len(rows),
    }


__all__ = ["EXAM_MATERIAL_TRACK", "list_subject_materials", "subject_material_names",
           "subject_material_scope"]
