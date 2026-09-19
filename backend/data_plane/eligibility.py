"""Component eligibility evaluation.

Two layers live here, and they answer different questions:

1. **Component matrix** (``COURSE_PRACTICE_MATRIX``) — the frozen 13-component
   productization status from Phase 2A-R. A component is runtime-ELIGIBLE only when input
   READY and scientific applicability SUPPORTED. PARTIAL / ONTOLOGY_MISMATCH /
   NOT_APPLICABLE are all INELIGIBLE for a real inference.

2. **StudentTwin input-domain rule** (``student_twin_input_eligibility``) — ACCEL_SPRINT_S2
   productization gate. The matrix says the COMPONENT is supported; this rule decides
   whether one FACTUAL EVENT may feed it. Type-level eligibility is necessary but NOT
   sufficient.

STUDENTTWIN INPUT RULE (product decision, 2026-09-19)
-----------------------------------------------------
A CS408 factual ``question_answered`` event — and the pre-existing ``course_practice``
family — may feed StudentTwin **when and only when it carries an authoritative binary
correctness fact**:

  * a non-empty user answer;
  * ``correct`` that is exactly ``True`` or ``False``;
  * a judge marker that is not ``self_review``.

The rule NEVER consults ``score``. A score is not a correctness verdict: a past-paper item
can be AI-graded to a real score while ``correct`` stays null, and an unanswered item can
carry a legacy ``score: 0``. Deriving correctness from a score is exactly what this rule
forbids.

``question_answered`` is NOT renamed to ``course_practice``, and no scientific algorithm
is involved: this is an INPUT-DOMAIN productization decision only.
"""
from dataclasses import dataclass

# ---------------------------------------------------------------- input-domain rule

STUDENT_TWIN_COMPONENT = "student_twin"

# Event families whose TYPE permits StudentTwin eligibility. Membership here is
# necessary, never sufficient — the per-event rule below decides.
STUDENT_TWIN_INPUT_EVENT_TYPES = ("course_practice", "question_answered")

# A judge marker meaning "no authoritative machine verdict was produced". A row carrying
# one of these is never eligible, even if a boolean somehow reached `correct`.
NON_AUTHORITATIVE_JUDGES = frozenset({"self_review"})

# stable reason codes (they travel to the product response, so they must not drift)
RULE_ELIGIBLE = "AUTHORITATIVE_BINARY_CORRECTNESS"
REASON_NO_ANSWER = "NO_USER_ANSWER"
REASON_NOT_BINARY = "CORRECTNESS_NOT_BINARY"
REASON_JUDGE = "JUDGE_NOT_AUTHORITATIVE"
REASON_FAMILY = "EVENT_FAMILY_NOT_STUDENT_TWIN_CAPABLE"

# One human-readable statement of the rule, carried by product responses.
RULE_STATEMENT = (
    "eligible iff the event family permits it AND a non-empty user answer exists AND "
    "correct is exactly true/false AND the judge is not self_review; correctness is "
    "never inferred from score")


@dataclass(frozen=True)
class InputEligibility:
    """The verdict for ONE event, with the reason it was reached."""

    eligible: bool
    reason: str
    event_type: str | None = None

    def as_dict(self) -> dict:
        return {"eligible": self.eligible, "reason": self.reason,
                "event_type": self.event_type}


def student_twin_input_eligibility(*, answer, correct, judge=None,
                                   event_type=None) -> InputEligibility:
    """The S2 input-domain rule. Pure; never touches the database or a model."""
    if event_type is not None and event_type not in STUDENT_TWIN_INPUT_EVENT_TYPES:
        return InputEligibility(False, REASON_FAMILY, event_type)
    if not str(answer if answer is not None else "").strip():
        return InputEligibility(False, REASON_NO_ANSWER, event_type)
    # exactly True or False: `isinstance` also rejects 0/1 smuggled in as ints
    if not isinstance(correct, bool):
        return InputEligibility(False, REASON_NOT_BINARY, event_type)
    if judge is not None and str(judge).strip().lower() in NON_AUTHORITATIVE_JUDGES:
        return InputEligibility(False, REASON_JUDGE, event_type)
    return InputEligibility(True, RULE_ELIGIBLE, event_type)


def judge_of(event) -> str | None:
    """The judge marker carried by an event's factual snapshot, if any."""
    import json

    try:
        snapshot = json.loads(getattr(event, "item_snapshot_json", None) or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(snapshot, dict):
        return None
    judge = snapshot.get("judge")
    return str(judge) if judge is not None else None


def student_twin_event_eligibility(event) -> InputEligibility:
    """The rule applied to a canonical ``LearningEvent`` row."""
    return student_twin_input_eligibility(
        answer=getattr(event, "answer", None),
        correct=getattr(event, "correct", None),
        judge=judge_of(event),
        event_type=getattr(event, "event_type", None))

# requirement_status: READY / PARTIAL / BLOCKED / NOT_APPLICABLE
# scientific_applicability: SUPPORTED / OUT_OF_DOMAIN / ONTOLOGY_MISMATCH / UNRESOLVED / NOT_APPLICABLE
COURSE_PRACTICE_MATRIX = {
    "domestic_registry":   ("NOT_APPLICABLE", "NOT_APPLICABLE",   "CAPABILITY_NOT_APPLICABLE"),
    "difficulty_prior":    ("BLOCKED",        "SUPPORTED",        "MISSING_EMBEDDING"),
    "memory":              ("BLOCKED",        "SUPPORTED",        "MISSING_HISTORY"),
    "irt":                 ("BLOCKED",        "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH"),
    "tutor_guard":         ("BLOCKED",        "UNRESOLVED",       "DEPENDENCY_NOT_AVAILABLE"),
    "planner":             ("BLOCKED",        "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH"),
    "execution_router":    ("NOT_APPLICABLE", "NOT_APPLICABLE",   "CAPABILITY_NOT_APPLICABLE"),
    "concept_verifier":    ("PARTIAL",        "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH"),
    "tutor_policy":        ("BLOCKED",        "UNRESOLVED",       "MISSING_INPUT"),
    "misconception_v2":    ("BLOCKED",        "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH"),
    "evidence_reliability": ("PARTIAL",        "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH"),
    "learner_state":       ("PARTIAL",        "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH"),
    "student_twin":        ("READY",          "SUPPORTED",        "READY"),
}

# missing fields for PARTIAL components (documented, NOT fabricated)
MISSING_FIELDS = {
    "concept_verifier": ["concept_id"],
    "tutor_policy": ["student_profile", "confusion", "dialogue_history"],
    "evidence_reliability": ["hint_count", "log_rt", "b_s", "opportunity"],
    "learner_state": ["interaction_sequence"],
}


def evaluate(component_id: str, event: dict) -> dict:
    """Evaluate runtime eligibility of one component for one LearningEvent."""
    if component_id not in COURSE_PRACTICE_MATRIX:
        raise KeyError(f"unknown component {component_id!r}")
    req_status, sci_applicability, reason = COURSE_PRACTICE_MATRIX[component_id]

    eligible = (req_status == "READY" and sci_applicability == "SUPPORTED")
    return {
        "component_id": component_id,
        "requirement_status": req_status,
        "scientific_applicability": sci_applicability,
        "eligibility_status": "ELIGIBLE" if eligible else "INELIGIBLE",
        "reason_code": reason,
        "missing_fields": MISSING_FIELDS.get(component_id, []),
        "required_transformations": [],
        "safe_for_data_production": eligible,
    }


def eligible_components(event: dict) -> list:
    """Return component_ids that are ELIGIBLE for the given event."""
    return [cid for cid in COURSE_PRACTICE_MATRIX
            if evaluate(cid, event)["eligibility_status"] == "ELIGIBLE"]
