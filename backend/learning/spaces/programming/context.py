"""Programming Space identity + LearningContext construction.

PROGRAMMING IDENTITY (audited, not invented)
--------------------------------------------
There is no ``Language`` or ``Track`` table that owns programming identity, and this module
does not create one. The identity the data actually supports is:

    language identity   the canonical language name (C / C++ / Python / Java)
    exercise identity   ``programming_exercises.id`` — globally unique in the catalog
    project identity    ``code_projects.id`` — per learner, per language, per exercise
    track identity      ``user_learning_tracks(track_type='programming')``

Identity is compared by exact key, NEVER by display name: two exercises may share a title,
and a title is presentation, not identity.

WHERE THE LANGUAGE IS CARRIED
-----------------------------
``learning_events`` has no ``programming_language`` column, and this module adds none. The
language travels in the fact's domain-context JSON and item snapshot instead — it is
additive and NOT identity-bearing (``event_id`` depends only on the source triple), so it
needs no migration. ``learning.records.native_concept`` already declares
``["programming_language", "exercise_id"]`` as the programming surface; this module is
where those values are produced.

``project_id`` is deliberately NOT part of :class:`~core.learning_context.LearningContext`:
a project is a working container, not a property of the learning fact, and the frozen
context schema forbids extra fields.
"""
from __future__ import annotations

from core.learning_context import (
    LearningContext,
    ServiceNamespace,
    normalize_service_namespace,
)

PROGRAMMING_NAMESPACE = ServiceNamespace.PROGRAMMING.value

# The languages the product actually executes. This is the canonical set: a language is
# only listed here when the runner can compile or interpret it.
PROGRAMMING_LANGUAGES = ("C", "C++", "Python", "Java")

# The language a submission is recorded under when the source states none. Exactly one
# default exists, and it is the same one ``PROJECT_LANGUAGE_DEFAULT_ENTRY`` keys on.
DEFAULT_LANGUAGE = "Python"


class ProgrammingContextError(ValueError):
    """A programming context that cannot be built."""


def normalize_language(value) -> str:
    """Canonical language name for a raw label, or the default.

    This is the ONE language normalizer. ``main.normalize_project_language`` delegates
    here so the legacy call sites and the canonical event writers cannot disagree about
    what "cpp" means.
    """
    raw = str(value or "").strip().lower()
    if raw in ("c++", "cpp", "cplusplus") or "c++" in raw:
        return "C++"
    if raw in ("c", "c语言"):
        return "C"
    if raw in ("python", "py") or "python" in raw:
        return "Python"
    if raw == "java" or "java" in raw:
        return "Java"
    return DEFAULT_LANGUAGE


def normalize_namespace(value=PROGRAMMING_NAMESPACE) -> str:
    """Programming namespace through the ONE shared alias normalizer ("code" is input-only)."""
    return normalize_service_namespace(value)


def normalize_exercise_id(value) -> int | None:
    """Exercise identity, or ``None``. A non-numeric id is not guessed into one."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_programming_context(user, *, language=None, exercise_id=None,
                              session_id=None) -> LearningContext:
    """Build the canonical LearningContext for a programming interaction.

    ``language`` is always present and always canonical: a programming fact whose language
    is unknown would be filed under the default, and the default is a real language the
    product runs, so the fact stays usable.
    """
    return LearningContext(
        user_id=getattr(user, "id", None),
        service_namespace=ServiceNamespace.PROGRAMMING,
        programming_language=normalize_language(language),
        exercise_id=normalize_exercise_id(exercise_id),
        session_id=session_id,
    )


def language_of(context: dict | None) -> str | None:
    """The language a STORED context dict carries, or ``None`` when it states none.

    A reader must be able to tell "recorded as C++" from "recorded as nothing", so this
    never falls back to the default.
    """
    value = (context or {}).get("programming_language")
    text = str(value or "").strip()
    return text or None


def exercise_id_of(context: dict | None) -> int | None:
    return normalize_exercise_id((context or {}).get("exercise_id"))
