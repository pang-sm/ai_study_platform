"""Component eligibility evaluation (Phase 2B2).

Frozen 13-component matrix for the course_practice LearningEvent (from Phase 2A-R).
A component is runtime-ELIGIBLE only when: input READY AND scientific applicability
SUPPORTED AND product role permits operation.  PARTIAL/ONTOLOGY_MISMATCH/NOT_APPLICABLE
are all INELIGIBLE for a single real inference.
"""

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
