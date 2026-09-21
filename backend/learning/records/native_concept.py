"""The CS408-native concept reference — the product's OWN ontology, as recorded on a fact.

WHAT THIS IS FOR
----------------
The scientific knowledge-tracing models the product holds today were trained on OTHER
ontologies (ASSISTments skills, Junyi concepts), and the product has no honest mapping into
them — a measured 0.46 output swing under an arbitrary index assignment is why
``learner_state`` is blocked. The way out is not a mapping; it is a model trained on the
product's own concept space, and that model needs a training set built from facts that
carry a STABLE NATIVE CONCEPT REFERENCE.

This module is the single definition of what that reference is, so the fact that is written
today and the dataset that is exported tomorrow cannot drift apart.

THE HIERARCHY — AND WHAT EACH LEVEL ACTUALLY IS
-----------------------------------------------
    exam_track_id     the learner's preparation bundle (cs_408)
    exam_subject_id   the exam paper (cs_408)
    exam_module_id    a part of that subject (data_structure, operating_system, ...)
    knowledge_point_id  a canonical concept within that module

Only the last three ever appear on a fact, and ``exam_track_id`` appears on NONE of them:
a track is the learner's own bundle choice, not an attribute of what happened, so two
learners who answered the same question under different tracks must produce byte-identical
facts. ``core.learning_context.LearningContext.to_event_context`` encodes that rule; this
module keeps it encoded.

GRANULARITY IS RECORDED HONESTLY, NOT PADDED
--------------------------------------------
Different surfaces genuinely know different amounts:

    chapter practice   exam_module_id + knowledge_point_id
    past papers        exam_module_id ONLY — a past paper's per-question concept is not
                       asserted by any stored field, and this module does NOT derive one
                       from the question's text, chapter title or number
    programming        exercise identity

A reference that carries only ``exam_module_id`` is CORRECT for a past paper. Filling in a
``knowledge_point_id`` there would be the fabrication this module exists to prevent. A
consumer must therefore treat every level below ``exam_subject_id`` as OPTIONAL — and a
future KT dataset must group at the deepest level a fact actually carries, not at the
level it wishes it carried.

IDENTITY, NOT DISPLAY
---------------------
Every value here is a canonical id from ``learning.spaces.exam_prep.catalog`` or a stored
column. Display names, chapter titles and question stems are NOT inputs: matching a
question title against a knowledge-point name would invent a link that no product fact
supports, and a model trained on those links would learn the title-matching rule rather
than the learner.
"""
from __future__ import annotations

# The EXAM IDENTITY levels. They say WHICH EXAM a fact belongs to, not which concept it is
# about, so they are reported separately and never stand in as a concept key: a sequence
# grouped at "cs_408" would carry no concept signal at all, and silently filing a fact
# there would look like a concept assignment while asserting nothing.
EXAM_IDENTITY_LEVELS = (
    "exam_track_id",
    "exam_subject_id",
)

# The CONCEPT levels, deepest last. This is the order a consumer walks when it wants the
# most specific concept a fact actually carries.
NATIVE_CONCEPT_LEVELS = (
    "exam_module_id",
    "knowledge_point_id",
)

# The keys stored in a fact's ``knowledge_point_ref_json``. ``exam_subject_id`` is NOT one
# of them: it already has a dedicated ``learning_events.subject_key`` column, and storing
# the same value twice would let the two disagree.
NATIVE_CONCEPT_KEYS = ("knowledge_point_id", "exam_module_id")

# What a PROGRAMMING fact records about itself. Deliberately NOT part of
# ``NATIVE_CONCEPT_KEYS`` and NOT a concept level: a language and an exercise id say WHICH
# ITEM was worked on, not which concept it is about. They travel in the fact's context
# instead (``learning_events`` has no such column, and adding one would be a migration for
# a value that is additive and not identity-bearing). Declared here because this module is
# the ONE place the product states what each surface records; read back by the records
# projection, and ignored by the KT export on purpose.
PROGRAMMING_CONTEXT_KEYS = ("programming_language", "exercise_id")

# Never an input to a concept reference. Listed so a future reader sees the prohibition
# where the reference is defined, not only in a review comment.
NON_IDENTITY_INPUTS = (
    "knowledge_point_name", "knowledge_point_path", "chapter_title", "question stem",
    "display name", "question number",
)

REFERENCE_RULE = (
    "a native concept reference carries ONLY canonical ids that a stored product fact "
    "holds; a level the fact does not know is ABSENT rather than derived from a title, a "
    "path, a number or a name")


def reference_from_context(context: dict | None) -> dict:
    """The reference stored on a fact, from a ``LearningContext``-shaped dict.

    Absent keys are OMITTED rather than stored as null, so a fact written before a level
    existed and one written after it stays blank compare equal. This is the same rule the
    record envelope has always applied; it now lives here so the reader in
    ``science.kt_dataset`` shares it instead of restating it.
    """
    if not isinstance(context, dict):
        return {}
    return {key: context[key] for key in NATIVE_CONCEPT_KEYS
            if context.get(key) not in (None, "")}


def reference_from_event(event) -> dict:
    """The reference already stored on a canonical ``LearningEvent`` row.

    A malformed or absent blob yields ``{}`` — an unreadable reference is an UNKNOWN
    reference, never a partial one silently promoted to a concept.
    """
    import json

    try:
        data = json.loads(getattr(event, "knowledge_point_ref_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in NATIVE_CONCEPT_KEYS
            if data.get(key) not in (None, "")}


def concept_key(reference: dict) -> str | None:
    """The deepest native CONCEPT identity a reference actually carries.

    Returns ``None`` when no concept below the exam identity is known. A fact that carries
    only ``exam_subject_id`` has an exam, not a concept, and a caller must be able to see
    that rather than receive ``"cs_408"`` dressed up as one.
    """
    for level in reversed(NATIVE_CONCEPT_LEVELS):
        value = (reference or {}).get(level)
        if value not in (None, ""):
            return str(value)
    return None


def concept_level(reference: dict) -> str | None:
    """Which level :func:`concept_key` came from, or ``None`` when nothing is known."""
    for level in reversed(NATIVE_CONCEPT_LEVELS):
        value = (reference or {}).get(level)
        if value not in (None, ""):
            return level
    return None


def reference_for_learning_event(event) -> dict:
    """The full native identity of a fact: its subject plus its stored concept reference.

    ``exam_subject_id`` lives in the dedicated ``subject_key`` column and is folded back in
    here, so a consumer never has to know that the identity is split across two places. It
    is EXAM IDENTITY, not a concept — :func:`concept_key` ignores it on purpose.
    """
    reference = reference_from_event(event)
    subject = getattr(event, "subject_key", None)
    out: dict = {}
    if subject:
        out["exam_subject_id"] = str(subject)
    out.update(reference)
    return out


def declared_granularity_report() -> dict:
    """Which surfaces record which level. Documentation as an executable statement."""
    return {
        "rule": REFERENCE_RULE,
        "levels": list(NATIVE_CONCEPT_LEVELS),
        "exam_identity_levels": list(EXAM_IDENTITY_LEVELS),
        "track_never_recorded": ("exam_track_id is absent from every fact by design: a "
                                 "track is the learner's bundle choice, not an attribute "
                                 "of what happened"),
        "surfaces": {
            "exam_prep.chapter_practice": ["exam_module_id", "knowledge_point_id"],
            "exam_prep.past_papers": ["exam_module_id"],
            "programming": list(PROGRAMMING_CONTEXT_KEYS),
        },
        "non_identity_inputs": list(NON_IDENTITY_INPUTS),
    }
