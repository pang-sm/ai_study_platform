"""Legacy 11408 scope-id adapter — pure functions, no storage change.

The product already stores exam scope as a derived string id in places that are real
user data:

    user_knowledge_progress.course_id = "data_structure_11408"
    study_materials.course_id         = "data_structure_11408"
    seed_data/knowledge_maps/<module>_11408.json

That string is `<module>_11408`. Under the canonical model it means
``track=cs_408, subject=cs_408, module=<module>``. STEP7H1 interprets it — it does NOT
rewrite it, because rewriting stored ids is a data migration and buys nothing while the
module is still the only variable part.

Fail-closed rule: a value that IS a legacy scope id but names an unknown module raises,
rather than silently resolving to "no module" and filing the fact under the wrong scope.
"""
from __future__ import annotations

from dataclasses import dataclass

from .catalog import (
    CS408_MODULE_DISPLAY,
    CS408_SUBJECT,
    CS408_TRACK,
    is_known_module,
)

LEGACY_SCOPE_SUFFIX = "_11408"
_EXAM_PREFIX = "11408 "


class ExamScopeError(ValueError):
    """A legacy exam scope id that cannot be interpreted."""


@dataclass(frozen=True)
class ExamScope:
    exam_track_id: str
    exam_subject_id: str
    exam_module_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "exam_track_id": self.exam_track_id,
            "exam_subject_id": self.exam_subject_id,
            "exam_module_id": self.exam_module_id,
        }


def parse_legacy_exam_scope_id(value) -> ExamScope | None:
    """``<module>_11408`` → ExamScope(cs_408, cs_408, <module>).

    Returns None when the value is not a legacy scope id at all (a plain course key, a
    display name, an empty string). Raises when it IS one but names an unknown module.
    """
    text = str(value or "").strip()
    if not text.endswith(LEGACY_SCOPE_SUFFIX):
        return None
    module = text[: -len(LEGACY_SCOPE_SUFFIX)]
    if not is_known_module(module):
        raise ExamScopeError(f"unknown legacy exam scope {text!r}")
    return ExamScope(CS408_TRACK, CS408_SUBJECT, module)


def build_legacy_exam_scope_id(module_key) -> str:
    """``<module>`` → ``<module>_11408``. Raises for an unknown module."""
    module = str(module_key or "").strip()
    if not is_known_module(module):
        raise ExamScopeError(f"unknown CS408 module {module_key!r}")
    return f"{module}{LEGACY_SCOPE_SUFFIX}"


def resolve_cs408_module(*values) -> str | None:
    """Resolve the CS408 module from whichever legacy form a caller happens to hold.

    Accepts (in order of appearance): a legacy scope id (``data_structure_11408``), a
    bare module key (``data_structure``), the exam-normalised display (``11408 数据结构``)
    and the plain course display (``数据结构``). Returns None when nothing matches — an
    exam fact with no module is legitimate (subject-level), an invented module is not.
    """
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        scope = parse_legacy_exam_scope_id(text)
        if scope is not None:
            return scope.exam_module_id
        if is_known_module(text):
            return text
        if text.startswith(_EXAM_PREFIX):
            text = text[len(_EXAM_PREFIX):].strip()
        for module, display in CS408_MODULE_DISPLAY.items():
            if text == display:
                return module
    return None
