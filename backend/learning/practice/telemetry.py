"""Canonical attempt telemetry — the ONE envelope for factual per-attempt observations.

WHY THIS MODULE EXISTS
----------------------
A learned model does not read "an attempt"; it reads a feature vector built from facts
about an interaction. When those facts are assembled ad hoc at each call site, two things
go wrong: the same quantity acquires different semantics in different places, and a value
that was never observed gets quietly replaced by a convenient default.

This module is the single definition of the per-attempt observations the product is
allowed to record, and of what each one provably means. It has three rules, and all three
exist because the alternative is a fabricated fact rather than a missing one.

RULE 1 — A DURATION WITHOUT A DEFINED BOUNDARY IS NOT A DURATION
----------------------------------------------------------------
``duration_ms`` is admitted only with a ``duration_source`` from :data:`DURATION_SOURCES`,
and each source names the two boundaries it measures between. There is deliberately no
"unknown" source that still carries a number: if the boundaries are not both real, the
duration is ``None``.

In particular, ``created_at - submitted_at`` is NOT a duration. Those two timestamps do
not bracket active answering — ``created_at`` is when the ROW was written and
``submitted_at`` is when the answer arrived, and for a mirrored legacy attempt they can be
seconds apart or months apart while no answering happened in between. A session span is
not a duration either: it covers every question in the session. Neither may be used, and
neither is used anywhere in this module.

RULE 2 — "NO HINT MECHANISM" IS NOT "ZERO HINTS USED"
-----------------------------------------------------
``hint_count = 0`` asserts that a hint system existed, was available, and the learner did
not use it. A surface that has no hint system at all has not observed that. The two are
different facts and only one of them is true of today's CS408 practice, so
:data:`HINT_NO_MECHANISM` is its own value and is NEVER encoded as a count. This mirrors
the source model's own semantics, where ``bottom_hint == 0`` means the learner did not ask
for a hint on a surface that offered one.

RULE 3 — ATTEMPT INDEX IS DERIVED FROM CANONICAL IDENTITY, NOT FROM SESSION POSITION
------------------------------------------------------------------------------------
``attempt_index`` is the 1-based ordinal of this attempt among the learner's attempts on
THIS question, counted over canonical ``(user_id, question identity)``. It is not the
question's position in a session, not a frontend list index, and not a paper-sitting
number. It is supplied by the caller from a real count, never inferred here.

WHAT THIS MODULE DOES NOT DO
----------------------------
It records no judgement. There is no difficulty feature, no correctness, no mastery, and
nothing derived from a model. In particular the editorial question label
(简单 / 中等 / 困难) is NOT converted into a numeric difficulty anywhere in this module:
that label is an authoring annotation, and turning it into ``-1/0/+1``, an IRT ``b``, or a
continuous difficulty would invent a psychometric quantity out of a word. A model that
needs a difficulty must have one from its own ontology.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------- duration

DURATION_SERVER_SERVE_TO_SUBMIT = "SERVER_SERVE_TO_SUBMIT"
DURATION_CLIENT_MONOTONIC_ACTIVE = "CLIENT_MONOTONIC_ACTIVE"
DURATION_UNAVAILABLE = "UNAVAILABLE"

# source -> (start boundary, submit boundary, what the measured value includes)
DURATION_SOURCES: dict[str, dict[str, str]] = {
    DURATION_SERVER_SERVE_TO_SUBMIT: {
        "start_boundary": "the server handed this item to the learner (a server-recorded "
                          "serve timestamp for THIS item)",
        "submit_boundary": "the server received the submission for THIS item",
        "unit": "milliseconds, integer, >= 0",
        "background_tab": "INCLUDED — the server observes wall clock only and cannot see "
                          "whether the tab was visible",
        "missing_semantics": "if either boundary is absent for this item, the duration is "
                             "None; it is never approximated from another timestamp",
    },
    DURATION_CLIENT_MONOTONIC_ACTIVE: {
        "start_boundary": "the item became answerable in the client (a monotonic-clock "
                          "reading taken when the item was presented)",
        "submit_boundary": "the client sent the submission (a monotonic-clock reading taken "
                           "at submit)",
        "unit": "milliseconds, integer, >= 0",
        "background_tab": "INCLUDED unless the client explicitly reports visible-only "
                          "time; a monotonic clock keeps running in a background tab, so "
                          "this value may exceed actual engaged time",
        "missing_semantics": "if the client cannot supply a monotonic measurement, the "
                             "duration is None — a Date.now() difference or a session span "
                             "is not admitted as a substitute",
    },
}

DURATION_SOURCE_VALUES = tuple(DURATION_SOURCES) + (DURATION_UNAVAILABLE,)

# Stable statements a reader can quote. They travel with the recorded fact.
DURATION_FORBIDDEN_DERIVATIONS = (
    "created_at - submitted_at",
    "session span (session started_at -> submit)",
    "any difference between two timestamps that do not bracket active answering",
)


# ---------------------------------------------------------------- hints

HINT_COUNTED = "COUNTED"
HINT_NO_MECHANISM = "NO_HINT_MECHANISM"
HINT_NOT_OBSERVED = "NOT_OBSERVED"

HINT_SOURCE_VALUES = (HINT_COUNTED, HINT_NO_MECHANISM, HINT_NOT_OBSERVED)

# The rule, stated once so no call site re-decides it.
HINT_SEMANTICS = (
    "COUNTED: a real hint mechanism served this many hint interactions, so hint_count is "
    "an observed non-negative integer. "
    "NO_HINT_MECHANISM: the surface offers no hint interaction at all, so the number of "
    "hints used was never observed — this is NOT scientifically equivalent to a counted "
    "zero and must never be stored as hint_count = 0. "
    "NOT_OBSERVED: a mechanism exists but this interaction did not record it."
)

# surfaces that genuinely have no hint system today
SURFACES_WITHOUT_HINT_MECHANISM = (
    "exam_prep chapter practice (CS408)",
    "exam_prep past papers (CS408)",
    "course_learning practice",
    "programming exercises",
)


# ---------------------------------------------------------------- envelope

@dataclass(frozen=True)
class AttemptTelemetry:
    """The factual per-attempt observations, each carrying its own provenance.

    ``duration_ms`` and ``hint_count`` are independently optional: a caller may hold one
    and not the other, and neither is ever filled in to make the record look complete.
    """

    duration_ms: int | None = None
    duration_source: str = DURATION_UNAVAILABLE
    hint_count: int | None = None
    hint_source: str = HINT_NO_MECHANISM
    attempt_index: int | None = None

    def __post_init__(self) -> None:
        if self.duration_source not in DURATION_SOURCE_VALUES:
            raise ValueError(f"unknown duration_source {self.duration_source!r}; "
                             f"valid={DURATION_SOURCE_VALUES}")
        if self.hint_source not in HINT_SOURCE_VALUES:
            raise ValueError(f"unknown hint_source {self.hint_source!r}; "
                             f"valid={HINT_SOURCE_VALUES}")
        if self.duration_source == DURATION_UNAVAILABLE:
            if self.duration_ms is not None:
                raise ValueError(
                    "duration_source UNAVAILABLE may not carry a duration — a number with "
                    "no measured boundary is not a duration")
        else:
            if self.duration_ms is None:
                raise ValueError(
                    f"duration_source {self.duration_source} requires a duration_ms")
            if not isinstance(self.duration_ms, int) or isinstance(self.duration_ms, bool):
                raise ValueError("duration_ms must be an integer number of milliseconds")
            if self.duration_ms < 0:
                raise ValueError("duration_ms may not be negative")

        if self.hint_source == HINT_COUNTED:
            if self.hint_count is None:
                raise ValueError("hint_source COUNTED requires a hint_count")
            if not isinstance(self.hint_count, int) or isinstance(self.hint_count, bool):
                raise ValueError("hint_count must be an integer")
            if self.hint_count < 0:
                raise ValueError("hint_count may not be negative")
        elif self.hint_count is not None:
            # The rule this whole module exists for: a surface with no hint mechanism
            # yields NO count, not a zero.
            raise ValueError(
                f"hint_source {self.hint_source} admits no hint_count; storing 0 here "
                f"would assert an observation that was never made")

        if self.attempt_index is not None:
            if not isinstance(self.attempt_index, int) or isinstance(self.attempt_index, bool):
                raise ValueError("attempt_index must be an integer")
            if self.attempt_index < 1:
                raise ValueError("attempt_index is 1-based; it may not be < 1")

    # ------------------------------------------------------------ projections

    def to_fact_fields(self) -> dict:
        """The durable columns this telemetry contributes to a recorded attempt."""
        return {
            "response_time_ms": self.duration_ms,
            "response_time_source": self.duration_source,
            "attempt_index": self.attempt_index,
        }

    def to_event_fields(self) -> dict:
        """The same facts, for the canonical LearningEvent envelope."""
        return dict(self.to_fact_fields())

    def as_dict(self) -> dict:
        return {
            "duration_ms": self.duration_ms,
            "duration_source": self.duration_source,
            **({"duration_semantics": DURATION_SOURCES[self.duration_source]}
               if self.duration_source in DURATION_SOURCES else {}),
            "hint_count": self.hint_count,
            "hint_source": self.hint_source,
            "hint_semantics": HINT_SEMANTICS,
            "attempt_index": self.attempt_index,
            "attempt_index_semantics": ATTEMPT_INDEX_SEMANTICS,
        }


ATTEMPT_INDEX_SEMANTICS = (
    "1-based ordinal of this attempt among the SAME learner's attempts on the SAME "
    "question, over canonical (user_id, question identity). NOT a session position, NOT a "
    "frontend list index, NOT a paper-sitting number."
)


def unobserved() -> AttemptTelemetry:
    """The honest default: nothing measured, nothing claimed."""
    return AttemptTelemetry()


# ---------------------------------------------------------------- version contract

# ACCEL_SPRINT_S6 PART G. The version of the RECORDED COLUMN SET, not of this file: it
# changes when a column is added or its meaning changes, so a dataset exported later can
# say which telemetry contract its facts were collected under.
TELEMETRY_SCHEMA_VERSION = "attempt-telemetry-v1"

# The migration that first created the columns.
TELEMETRY_COLUMNS_SINCE_REVISION = "20260919_0010"

# The release that first WROTE a value. The columns existed before this, which is why the
# two are recorded separately: a row written between the two releases has the columns and
# a NULL in them, and that NULL means "not observed", not "collected as zero".
TELEMETRY_COLLECTION_START_VERSION = "ACCEL_SPRINT_S6"

TELEMETRY_CONTRACT = {
    "schema_version": TELEMETRY_SCHEMA_VERSION,
    "columns_since_revision": TELEMETRY_COLUMNS_SINCE_REVISION,
    "collection_start_version": TELEMETRY_COLLECTION_START_VERSION,
    "columns": {
        "response_time_ms": {
            "unit": "integer milliseconds",
            "null_semantics": ("NOT OBSERVED — no producer records a per-item serve "
                               "boundary on any surface today, so this is NULL on every "
                               "row. A real 0 is a possible measured value and is NOT the "
                               "same as NULL."),
            "source_of_truth": ("none yet: 'SERVER_SERVE_TO_SUBMIT' would require a "
                                "per-item serve timestamp the product does not record, "
                                "and 'CLIENT_MONOTONIC_ACTIVE' requires a client that "
                                "measures one and sends it. Neither exists."),
        },
        "response_time_source": {
            "unit": "enum token",
            "null_semantics": ("unknown provenance — the row either predates S5 or was "
                               "written by a path that passed a bare duration. NULL is "
                               "never backfilled: the boundary was not recorded."),
            "source_of_truth": ("the writer, via learning.practice.telemetry "
                                "AttemptTelemetry.duration_source"),
        },
        "attempt_index": {
            "unit": "1-based ordinal, integer >= 1",
            "null_semantics": ("NOT OBSERVED. There is no zero: NULL and 1 are different "
                               "facts, and a NULL row is never to be read as a first "
                               "attempt."),
            "source_of_truth": ("learning.practice.service.record_attempt — counted over "
                                "canonical practice_attempts for the same learner and "
                                "question identity on the live path; a caller-supplied "
                                "value wins when one is given"),
        },
    },
    "historical_boundary": {
        "rule": ("every row written before "
                 f"{TELEMETRY_COLLECTION_START_VERSION} carries NULL in the S5 columns, "
                 "and NULL means NOT OBSERVED"),
        "for_training": ("a future model must treat NULL as 'missing' and never impute it "
                         "to zero: an unobserved attempt ordinal is not attempt 0, and an "
                         "unmeasured duration is not a fast answer"),
    },
    "prohibited_derivations": list(DURATION_FORBIDDEN_DERIVATIONS),
    "hint_rule": HINT_SEMANTICS,
}


def server_timed(duration_ms: int, *, attempt_index: int | None = None) -> AttemptTelemetry:
    """A duration the SERVER measured between a recorded serve and the submit."""
    return AttemptTelemetry(duration_ms=duration_ms,
                            duration_source=DURATION_SERVER_SERVE_TO_SUBMIT,
                            attempt_index=attempt_index)


def client_timed(duration_ms: int, *, attempt_index: int | None = None) -> AttemptTelemetry:
    """A duration the CLIENT measured on a monotonic clock while the item was open."""
    return AttemptTelemetry(duration_ms=duration_ms,
                            duration_source=DURATION_CLIENT_MONOTONIC_ACTIVE,
                            attempt_index=attempt_index)


def derived_attempt_index(prior_attempts_on_question: int) -> int:
    """The 1-based index for a new attempt, from a REAL prior count.

    ``prior_attempts_on_question`` must be counted from canonical rows — the number of
    attempts this learner already has on this question identity. A caller that does not
    have that count passes ``None`` and the index stays unrecorded.
    """
    if not isinstance(prior_attempts_on_question, int) or prior_attempts_on_question < 0:
        raise ValueError("prior_attempts_on_question must be a non-negative integer count")
    return prior_attempts_on_question + 1


# ---------------------------------------------------------------- difficulty guard

# The editorial label on a question. It is NOT a psychometric parameter.
EDITORIAL_DIFFICULTY_LABELS = ("简单", "中等", "困难")

EDITORIAL_DIFFICULTY_RULE = (
    "简单 / 中等 / 困难 is an editorial authoring label. It is NOT converted to -1/0/+1, "
    "NOT to an IRT b, and NOT to a continuous difficulty anywhere in the product. A model "
    "that consumes a difficulty must be given one from its own ontology; the label is "
    "carried as a string and never as a number."
)


def assert_no_editorial_difficulty_numeric(value) -> None:
    """Guard for any future writer: refuse a numeric encoding of the editorial label."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        raise ValueError(
            "a numeric difficulty may not be produced from the editorial label; see "
            "EDITORIAL_DIFFICULTY_RULE")
