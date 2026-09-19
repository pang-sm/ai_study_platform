"""Product-facing scientific capability summary (ACCEL_SPRINT_S4, PART I).

WHAT THIS ANSWERS
-----------------
"Which scientific capabilities can this product actually use, and what is each one allowed
to do?" It is deliberately NOT a runtime endpoint inventory: a component being reachable
over HTTP says nothing about whether the product can honestly feed it or show it. So
``available`` means *this product can produce this component's output from real facts it
holds today*, and nothing weaker.

READ-ONLY AND AUTHORITY-LABELLED
--------------------------------
Every entry carries ``controls_product_decision`` and ``writes_learner_fact``. For every
scientific component in the pool both are False, permanently: a scientific number may
annotate evidence, and may never gate a decision or write a learner fact.

No filesystem path, no internal stack trace and no model asset location is exposed here —
only component identity, product-facing readiness, blockers and a short semantic label.

The registry below is the single place where the product's scientific surface is declared.
Each entry imports its mode from the module that owns it, so this summary cannot drift from
what the individual endpoints report.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import evidence_reliability, metadata, misconception, tutor_policy

# ``user_visible`` is true only for a capability the learner may actually be shown. Exactly
# one component qualifies today.
VISIBLE = True
NOT_VISIBLE = False

# ``available`` — can the product produce this component's output from real facts?
#   reason codes are stable so the product surface can be asserted on.
NO_PRODUCT_SURFACE = "NO_PRODUCT_SURFACE_IN_PRODUCT_BACKEND"


class _Capability:
    __slots__ = ("component", "mode", "available", "user_visible", "blockers", "semantic",
                 "runtime_available", "scientifically_compatible", "product_input_ready")

    def __init__(self, component, mode, available, user_visible, blockers, semantic,
                 *, runtime_available=False, scientifically_compatible=False):
        self.component = component
        self.mode = mode
        self.available = available
        self.user_visible = user_visible
        self.blockers = tuple(blockers)
        self.semantic = semantic
        # ACCEL_SPRINT_S5 PART N — the three dimensions the single ``available`` flag was
        # silently carrying. They are reported separately because they fail independently:
        # a component can be reachable over HTTP and still have no honest input, and it can
        # have a real input and still mean something else in this domain.
        self.runtime_available = runtime_available
        self.scientifically_compatible = scientifically_compatible
        # ``product_input_ready`` is the same fact ``available`` has always reported, under
        # the name the S5 contract uses. Both are emitted; neither may be read as "an
        # endpoint exists".
        self.product_input_ready = available


# The components this service actually answers over HTTP. Membership here says the
# component is REACHABLE and nothing more — it is deliberately the only thing this set
# asserts, because "the endpoint exists" is exactly the reading the summary must prevent.
RUNTIME_ENDPOINT_COMPONENTS = frozenset({
    "student_twin", "misconception_v2", "tutor_policy", "learner_state",
    "evidence_reliability",
})


# The 13 scientific components (SSOT §36). Order is the SSOT's.
REGISTRY: tuple[_Capability, ...] = (
    _Capability(
        "student_twin", metadata.MODE_PREVIEW, available=True, user_visible=VISIBLE,
        blockers=(),
        semantic="deterministic rule-based learning-state replay — not a neural model, "
                 "not a mastery score",
        runtime_available=True, scientifically_compatible=True),
    _Capability(
        "learner_state", metadata.MODE_SHADOW_NOT_USER_VISIBLE, available=False,
        user_visible=NOT_VISIBLE,
        blockers=("ONTOLOGY_MAPPING_ABSENT", "CALIBRATION_GATE_NOT_ESTABLISHED"),
        semantic="next-response P(correct); trained on the ASSISTments/Junyi ontology, "
                 "with no mapping from the CS408 concept space",
        runtime_available=True, scientifically_compatible=False),
    _Capability(
        "misconception_v2", misconception.PRODUCT_MODE, available=True,
        user_visible=NOT_VISIBLE,
        blockers=("ONTOLOGY_MISMATCH",),
        semantic="candidate-misconception retrieval similarity against an English Eedi "
                 "ontology — a similarity, never a probability or a diagnosis",
        runtime_available=True, scientifically_compatible=False),
    _Capability(
        "tutor_policy", tutor_policy.PRODUCT_MODE, available=False,
        user_visible=NOT_VISIBLE,
        blockers=("MISSING_TRUTHFUL_TURN_STATE_FIELDS",),
        semantic="suggested pedagogical action over focus/generic/probing/telling; "
                 "controls no tutor response",
        # The 4-way ontology is domain-agnostic — the blocker is the turn state, not the
        # science. Reporting these as one boolean would hide which of the two is missing.
        runtime_available=True, scientifically_compatible=True),
    _Capability(
        "evidence_reliability", evidence_reliability.PRODUCT_MODE, available=False,
        user_visible=NOT_VISIBLE,
        runtime_available=True, scientifically_compatible=False,
        blockers=(
            evidence_reliability.BLOCKER_HINTS,
            evidence_reliability.BLOCKER_RESPONSE_TIME,
            evidence_reliability.BLOCKER_ATTEMPT_COUNT,
            evidence_reliability.BLOCKER_ONTOLOGY,
            evidence_reliability.BLOCKER_B_MAP,
            evidence_reliability.BLOCKER_STANDARDIZATION,
            evidence_reliability.BLOCKER_UPSTREAM_P_T,
            evidence_reliability.BLOCKER_CALIBRATION,
        ),
        semantic="reliability weight w in (0,1) for an observation — not a probability "
                 "of correctness and not a confidence"),
    _Capability(
        "memory", metadata.MODE_SHADOW_NOT_USER_VISIBLE, available=False,
        user_visible=NOT_VISIBLE,
        blockers=("REVIEW_RATING_HISTORY_ABSENT", "LAPSE_HISTORY_ABSENT",
                  "INTERVAL_HISTORY_ABSENT"),
        semantic="recall probability from a spaced-repetition review history; the "
                 "product records no review ratings, lapses or interval history"),
    _Capability(
        "irt", metadata.MODE_SHADOW_NOT_USER_VISIBLE, available=False,
        user_visible=NOT_VISIBLE,
        blockers=("ITEM_IDENTITY_ONTOLOGY_MISMATCH", "ABILITY_STATE_ABSENT"),
        semantic="online 1PL-style theta update under fixed item difficulty; the item "
                 "identity space and the ability state both have no product source"),
    _Capability(
        "concept_verifier", metadata.MODE_SHADOW_NOT_USER_VISIBLE, available=False,
        user_visible=NOT_VISIBLE,
        blockers=("CONCEPT_ONTOLOGY_MISMATCH",),
        semantic="question-concept alignment score; trained on English Eedi constructs "
                 "with no CS408 counterpart"),
    _Capability(
        "difficulty_prior", metadata.MODE_UNAVAILABLE, available=False,
        user_visible=NOT_VISIBLE, blockers=("MISSING_EMBEDDING", NO_PRODUCT_SURFACE),
        semantic="item difficulty prior — no product surface"),
    _Capability(
        "planner", metadata.MODE_UNAVAILABLE, available=False,
        user_visible=NOT_VISIBLE, blockers=("ONTOLOGY_MISMATCH", NO_PRODUCT_SURFACE),
        semantic="study planning — no product surface"),
    _Capability(
        "tutor_guard", metadata.MODE_UNAVAILABLE, available=False,
        user_visible=NOT_VISIBLE, blockers=("DEPENDENCY_NOT_AVAILABLE", NO_PRODUCT_SURFACE),
        semantic="tutor-response guard — no product surface"),
    _Capability(
        "execution_router", metadata.MODE_UNAVAILABLE, available=False,
        user_visible=NOT_VISIBLE, blockers=("CAPABILITY_NOT_APPLICABLE", NO_PRODUCT_SURFACE),
        semantic="execution routing infrastructure — not a learner-facing capability"),
    _Capability(
        "domestic_registry", metadata.MODE_UNAVAILABLE, available=False,
        user_visible=NOT_VISIBLE, blockers=("CAPABILITY_NOT_APPLICABLE", NO_PRODUCT_SURFACE),
        semantic="model registry infrastructure — not a learner-facing capability"),
)


def summary() -> dict:
    """The typed product-facing capability summary. Pure, read-only, no runtime call."""
    entries = [{
        "component": cap.component,
        "mode": cap.mode,
        "available": cap.available,
        # PART N: the four readiness questions, each answered on its own. A reader must be
        # able to see that a component is reachable AND unusable, or usable AND
        # meaningless in this domain, without inferring either from the other.
        "runtime_available": cap.runtime_available,
        "scientifically_compatible": cap.scientifically_compatible,
        "product_input_ready": cap.product_input_ready,
        "user_visible": cap.user_visible,
        "controls_product_decision": metadata.CONTROLS_PRODUCT_DECISION,
        "writes_learner_fact": metadata.WRITES_LEARNER_FACT,
        "blockers": list(cap.blockers),
        "semantics": cap.semantic,
    } for cap in REGISTRY]

    declared = {cap.component for cap in REGISTRY if cap.runtime_available}
    if declared != set(RUNTIME_ENDPOINT_COMPONENTS):
        # A drift here means one of the two lists was edited alone, which would let the
        # summary claim a surface the service does not serve (or hide one it does).
        raise AssertionError(
            f"runtime_available components {sorted(declared)} do not match the served "
            f"set {sorted(RUNTIME_ENDPOINT_COMPONENTS)}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_class": "ORIGINAL_ARCHIVE_VERIFIED",
        "terminology": {
            "available": ("the product can produce this component's output from real "
                          "facts it holds today — NOT the mere existence of a runtime "
                          "endpoint"),
            "runtime_available": ("this service exposes an endpoint for the component. It "
                                  "is REACHABILITY ONLY and implies nothing about whether "
                                  "the product can feed it or show it"),
            "scientifically_compatible": ("the component's own scientific domain and "
                                          "ontology match this product's CS408 domain, so "
                                          "its output means here what it means in its "
                                          "research setting"),
            "product_input_ready": ("the product can construct this component's REAL input "
                                    "from real facts it holds today. Same fact as "
                                    "`available`; both names are emitted so neither "
                                    "reader has to translate"),
            "user_visible": "the learner may be shown this capability",
            "mode": "PREVIEW | SHADOW | SHADOW_NOT_USER_VISIBLE | UNAVAILABLE",
            "controls_product_decision": ("whether the output may gate, grade, rank, "
                                          "unlock or mutate anything"),
            "writes_learner_fact": "whether the component may persist a learner fact",
        },
        "totals": {
            "components": len(entries),
            "available": sum(1 for e in entries if e["available"]),
            "user_visible": sum(1 for e in entries if e["user_visible"]),
            "controls_product_decision": sum(
                1 for e in entries if e["controls_product_decision"]),
            "writes_learner_fact": sum(1 for e in entries if e["writes_learner_fact"]),
        },
        "components": entries,
    }
