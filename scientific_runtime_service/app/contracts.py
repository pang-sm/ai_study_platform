"""Typed StudentTwin inference DTOs (contract v1).

Frozen request/response contract shared with the Product Backend runtime client. Optional
fields are explicitly nullable — neither side may fabricate a value for a missing field.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .config import COMPONENT_ID, CONTRACT_VERSION, RUNTIME_RELEASE_ID


class StudentTwinEvent(BaseModel):
    event_id: str
    occurred_at: float
    activity_type: str
    correct: bool
    source: Optional[str] = None
    item_id: Optional[str] = None
    concept_ref: Optional[str] = None
    response_time_ms: Optional[int] = None
    attempt_no: Optional[int] = None
    hints: Optional[int] = None


class StudentTwinInferenceRequest(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: Optional[str] = None
    user_ref: str
    target_event_id: str
    events: list[StudentTwinEvent]


class StudentTwinInferenceResponse(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: str
    component_id: str = COMPONENT_ID
    scientific_source_class: str
    scientific_source_commit: str
    target_event_id: str
    replayed_events: int
    state: dict[str, Any]
    latency_ms: float


class CapabilitiesResponse(BaseModel):
    runtime_release_id: str
    components: list[str]


# ---------------------------------------------------------------- misconception_v2

class MisconceptionRequest(BaseModel):
    """Retrieval query: a question and the answer the learner gave.

    ``answer`` is the WRONG/candidate answer — the retrieval query template is
    ``"{question} [ANS] {answer}"``. It is never a "correct answer" input.
    """

    contract_version: int = CONTRACT_VERSION
    request_id: str
    question: str
    answer: str
    top_k: int = 3


class MisconceptionMatch(BaseModel):
    rank: int
    misconception_id: str
    misconception_text: str
    similarity: float = Field(
        description="cosine-like normalized inner product. A SIMILARITY, not a "
                    "probability and not a confidence.")


class MisconceptionResponse(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: str
    component_id: str = "misconception_v2"
    scientific_source_class: str
    scientific_source_commit: str
    matches: list[MisconceptionMatch]
    score_semantics: str
    weak_label: bool
    ontology_size: int
    ontology_domain: str
    product_role: str
    controls_product_decision: bool
    latency_ms: float


# ---------------------------------------------------------------- tutor_policy

class TutorPolicyRequest(BaseModel):
    """Full turn state. ``prev_actions`` must use the frozen 4-way ontology."""

    contract_version: int = CONTRACT_VERSION
    request_id: str
    problem: str
    wrong: str
    profile: Optional[str] = None
    confusion: Optional[str] = None
    prev_actions: list[str] = []
    history: list[list[str]] = []


class TutorPolicyResponse(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: str
    component_id: str = "tutor_policy"
    scientific_source_class: str
    scientific_source_commit: str
    suggested_action: str
    action_probabilities: dict[str, float]
    ranking: list[str]
    action_ontology: list[str]
    product_role: str
    controls_product_decision: bool
    latency_ms: float


# ---------------------------------------------------------------- learner_state

class LearnerStateRequest(BaseModel):
    """ONE knowledge-tracing family over a genuine SCIENTIFIC-ontology interaction sequence.

    ``q`` and ``r_prev`` are equal-length index sequences in the FAMILY's own ontology
    (``base`` ASSISTments = 123 skills, ``junyi`` = 835 concepts). ``q[i]`` is the
    skill/concept index the learner interacted with, and ``r_prev[i]`` is the response
    that PRECEDED it — the model's real input contract, unchanged.

    The indices must come from the scientific ontology the checkpoint was trained on. A
    product concept id (a Chinese CS408 knowledge point) is NOT an index in this space and
    mapping one onto the other would fabricate a latent feature; this endpoint therefore
    accepts indices only and does no product mapping of any kind.
    """

    contract_version: int = CONTRACT_VERSION
    request_id: str
    family: str = Field(
        description="DKT | SimpleKT | AKT | CGKT | CGKT_v2. Explicit: the panel never "
                    "averages, votes, or auto-selects a variant.")
    q: list[int]
    r_prev: list[int]
    mask: Optional[list[float]] = None


class LearnerStateResponse(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: str
    component_id: str = "learner_state"
    scientific_source_class: str
    scientific_source_commit: str
    family: str
    ontology: str = Field(
        description="base (ASSISTments, 123 skills) | junyi (835 concepts)")
    num_skills: int
    next_response_probability: list[float] = Field(
        description="Per-position P(correct on the NEXT response). A probability, NOT a "
                    "mastery probability, ability score, or difficulty.")
    score_semantics: str
    engineering_representative_only: bool
    active_product_variant: Optional[str] = None
    product_role: str
    controls_product_decision: bool
    latency_ms: float


# ---------------------------------------------------------------- evidence_reliability

class EvidenceReliabilityRequest(BaseModel):
    """ONE feature vector per variant, for the five-variant PANEL.

    ``features_by_variant`` maps a variant id (``42`` / ``42_nort`` / ``42_surprise`` /
    ``43`` / ``44``) to that variant's OWN feature vector. The variants are feature
    ABLATIONS with different dimensions (8 / 7 / 3 / 8 / 8), so the vectors are not
    interchangeable and the caller must supply each one.

    The vector is the interaction's already-standardized continuous features
    (``log_rt``, ``hint_count``, ``log_opp``, ``b_s`` z-scored with the TRAINING set's
    mean/std) followed by ``p_t``, the running learner-state prediction. Those
    standardization statistics and the IRT ``b_map`` behind ``b_s`` are NOT bundled with
    the checkpoints, so this endpoint can only be called by a caller that genuinely holds
    them. It does not derive, impute, or default any element.
    """

    contract_version: int = CONTRACT_VERSION
    request_id: str
    features_by_variant: dict[str, list[float]]


class EvidenceReliabilityResponse(BaseModel):
    contract_version: int = CONTRACT_VERSION
    request_id: str
    runtime_release_id: str
    component_id: str = "evidence_reliability"
    scientific_source_class: str
    scientific_source_commit: str
    variant_outputs: dict[str, float] = Field(
        description="variant id -> reliability weight w in (0,1). NOT a probability of "
                    "correctness and NOT a confidence.")
    score_range: float
    score_std: float
    variant_disagreement: float
    averaging: bool
    auto_selection: bool
    active_product_variant: Optional[str] = None
    variant_mode: str
    replacement_readiness: str
    score_semantics: str
    product_role: str
    controls_product_decision: bool
    latency_ms: float
