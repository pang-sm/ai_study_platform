"""Typed wire contracts for every product-facing scientific response.

The models exist so OpenAPI describes the shapes concretely. They declare what
:mod:`science.student_twin`, :mod:`science.misconception` and :mod:`science.tutor_policy`
already return; the services remain the source of the values.

Deliberately absent from every model here: ``probability``, ``confidence``,
``mastery``, ``prediction``, ``diagnosis``. Scientific output is a preview, a similarity
or a suggestion — the field names are part of the semantic gate.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScientificAuthority(BaseModel):
    """Who produced this number, and what it is allowed to do. Never optional."""

    component: str
    mode: str = Field(
        description="PREVIEW | SHADOW | SHADOW_NOT_USER_VISIBLE | UNAVAILABLE")
    controls_product_decision: bool
    writes_learner_fact: bool
    generated_at: str
    request_id: str | None = None
    runtime_release_id: str | None = None
    source_class: str | None = None
    latency_ms: float | None = None
    blockers: list[str] | None = None
    semantics: str | None = None


class StudentTwinInputSummary(BaseModel):
    """What evidence the preview actually used, and what it declined to use.

    ``excluded_reasons`` maps a stable reason code (``NO_USER_ANSWER``,
    ``CORRECTNESS_NOT_BINARY``, ``JUDGE_NOT_AUTHORITATIVE``,
    ``EVENT_FAMILY_NOT_STUDENT_TWIN_CAPABLE``) to how many real events it rejected.
    ``eligibility_rule`` is the S2 input-domain rule in one sentence; no scientific
    algorithm is described here because none is involved.
    """

    event_count: int
    event_types: dict[str, int]
    excluded_event_count: int
    excluded_reasons: dict[str, int] | None = None
    scanned_events: int
    bounded_to: int
    scope: dict[str, Any]
    eligibility_rule: str
    semantics: str


class StudentTwinPreviewResponse(BaseModel):
    """A learning-state EXPERIMENT view. Not a mastery score, not a prediction."""

    model_config = ConfigDict(extra="forbid")

    metadata: ScientificAuthority
    input_summary: StudentTwinInputSummary
    state: dict[str, Any] | None = None


class LearnerStateModelRequirement(BaseModel):
    """What the model needs as INPUT. A requirement, never a claim that it was executed."""

    component: str
    scientific_source_commit: str
    families: list[str]
    ontologies: dict[str, int] = Field(
        description="ontology name -> index-space size the model was trained on")
    required_input: list[str]
    available_product_input: list[str]
    missing_input: list[str]
    ontology_mapping: str = Field(
        description="NONE — no mapping from the product concept space exists")
    active_product_variant: str | None = None
    variant_mode: str
    engineering_representative_only: bool
    score_semantics: str
    user_facing_label_zh: str = Field(
        description="the only permitted user-facing framing for this semantic; NOT "
                    "surfaced while the mode is SHADOW_NOT_USER_VISIBLE")
    user_facing_label_note: str


class LearnerStateEvidenceWindow(BaseModel):
    """The REAL canonical facts the product holds, and what the input rule rejected."""

    event_count: int
    event_types: dict[str, int]
    distinct_items: int
    excluded_event_count: int
    excluded_reasons: dict[str, int] | None = None
    scanned_events: int
    bounded_to: int
    window: dict[str, Any]
    scope: dict[str, Any]
    eligibility_rule: str
    semantics: str


class LearnerStatePreviewResponse(BaseModel):
    """A GATED capability report: the exact reason no next-response probability exists.

    ``next_response_probability`` is typed nullable and is null in every response this
    mode can produce — there is no honest input to compute it from. The field is named
    after the model's real output (never a bare ``probability``, never ``prediction``,
    never ``mastery``), so the contract itself cannot be mistaken for a mastery score.
    """

    metadata: ScientificAuthority
    score_semantics: str
    next_response_probability: float | None = Field(
        default=None,
        description="P(correct on the learner's NEXT response). Null while the mode is "
                    "SHADOW_NOT_USER_VISIBLE. NOT a mastery probability.")
    model_requirement: LearnerStateModelRequirement
    evidence_window: LearnerStateEvidenceWindow
    runtime_reachable: bool | None = None
    runtime_provenance: dict[str, Any]


class EvidenceReliabilityRequirement(BaseModel):
    """What the RELIABILITY PANEL needs as INPUT. A requirement, never a claim of execution.

    ``variants`` maps each frozen checkpoint to its own input dimension; the five are
    feature ablations and are not interchangeable.
    """

    component: str
    scientific_source_class: str
    scientific_source_commit: str
    variants: dict[str, int] = Field(
        description="variant id -> that checkpoint's input feature dimension")
    variant_mode: str = Field(description="PANEL — never averaged, voted, or auto-selected")
    active_product_variant: str | None = None
    replacement_readiness: str
    required_input: list[str]
    available_product_input: list[str]
    missing_input: list[str]
    # ACCEL_SPRINT_S5 PART C — the exact input contract, read off the frozen training
    # source. ``feature_vector`` is the position order; ``feature_schema`` states what each
    # position MEANS and how it was computed; ``feature_availability`` answers the separate
    # question of whether this product can honestly produce it.
    feature_vector: list[str] = Field(
        description="the 8-wide vector in position order: 7 static features then the "
                    "dynamic p_t, concatenated last")
    feature_schema: list[dict] = Field(
        description="per position: name, block, dtype, semantics, raw unit, transform, "
                    "and the source expression it was read from")
    feature_availability: list[dict] = Field(
        description="per position: AVAILABLE_NOW | CAN_BE_COLLECTED_FACTUALLY | "
                    "NOT_AVAILABLE | SEMANTICALLY_INCOMPATIBLE, with the product source "
                    "and the reason")
    product_feature_compatibility: str = Field(
        description="COMPATIBLE only when every required feature is honestly constructible")
    incompatible_features: list[str]
    standardization: dict = Field(
        description="which features are z-scored, the formula, and the fact that the "
                    "training mean/std are not bundled")
    missing_value_policy: dict
    training_pipeline: dict = Field(
        description="dataset, cohort filter, split, sequence grouping and how alpha was "
                    "chosen — transcribed from the frozen source")
    source_sha256: dict = Field(
        description="sha256 of the exact source bytes each transcription was read from")
    score_semantics: str
    scientific_threshold: float | None = Field(
        default=None,
        description="null — no calibration/validity threshold was established")
    user_facing_label_zh: str = Field(
        description="the only permitted user-facing framing for this semantic; NOT "
                    "surfaced while the mode is SHADOW_NOT_USER_VISIBLE")
    user_facing_label_note: str


class ScalerGate(BaseModel):
    """Whether the training standardizer may be used, and on what grounds (ACCEL_SPRINT_S5).

    The standardizer is part of the frozen model: without the training mean/std no caller
    can scale a raw value into the space the checkpoints were trained on, and no substitute
    is admissible. ``gate_passed`` is derived from ``recovery_method`` — it is never set
    independently, so the flag cannot disagree with the method that justified it.
    """

    component: str
    applies_to_features: list[str]
    standardizer_required: bool
    recovery_method: str = Field(
        description="NOT_RECOVERED | FOUND_FITTED_ARTIFACT | RECONSTRUCTED_FROM_FROZEN_DATA")
    recovery_evidence: dict | None = Field(
        default=None,
        description="digests and source identity of the artifact the method was applied "
                    "to; null while nothing has been recovered")
    accepted_methods: list[str]
    forbidden_methods: list[str] = Field(
        description="the routes that may NOT be used: fitting on product users, on a test "
                    "split or on the inference batch, assuming a standard normal, borrowing "
                    "another experiment's statistics, or inverting the checkpoint weights")
    missing_artifacts: list[str]
    gate_passed: bool
    note: str


class EvidenceReliabilityPreviewResponse(BaseModel):
    """A GATED capability report: the exact reason no reliability weight exists.

    ``reliability_weight`` is typed nullable and is null in every response this mode can
    produce — there is no honest input to compute it from. The field is named after the
    component's real output (never a bare ``score``, never ``probability``, never
    ``confidence``), so the contract itself cannot be misread as a correctness estimate.
    """

    metadata: ScientificAuthority
    score_semantics: str
    reliability_weight: float | None = Field(
        default=None,
        description="reliability weight w in (0,1). Null while the mode is "
                    "SHADOW_NOT_USER_VISIBLE. NOT a probability of correctness.")
    model_requirement: EvidenceReliabilityRequirement
    scaler_gate: ScalerGate
    evidence_window: LearnerStateEvidenceWindow
    runtime_reachable: bool | None = None
    runtime_provenance: dict[str, Any]


class KtDatasetReadiness(BaseModel):
    """What is still missing before a CS408-native KT model could actually be trained."""

    interactions_collected: int
    learners_collected: int
    native_concept_identity: str = Field(
        description="AVAILABLE | NO_DATA_YET — whether any interaction carries a stable "
                    "native concept reference at all")
    blockers: list[str] = Field(
        description="stable reason codes; includes NO_TRAINING_RUN_ATTEMPTED because this "
                    "module builds a dataset and trains nothing")


class KtDatasetAuditResponse(BaseModel):
    """The future training dataset's contract health. Carries NO rows and no learner data.

    It reports coverage and exclusions, never content: the full export is an offline path,
    so nothing a learner produced can leave through this endpoint.
    """

    dataset_contract_version: str
    sequence_count: int
    interaction_count: int
    concept_levels: dict[str, int] = Field(
        description="how many interactions were filed at each native concept level")
    excluded: dict[str, int] = Field(
        description="why facts were excluded, by stable reason code — an exclusion that is "
                    "counted is not a silent one")
    exclusion_semantics: dict[str, str]
    dataset_hash: str = Field(
        description="sha256 over the canonical dataset body, so an export can be audited "
                    "by re-running it")
    scope: dict
    semantics: str
    readiness: KtDatasetReadiness


class MisconceptionWrongRecord(BaseModel):
    state_id: int | None = None
    service_namespace: str | None = None
    status: str | None = None
    question_source_type: str | None = None
    question_source_id: str | None = None


class MisconceptionCandidate(BaseModel):
    rank: int | None = None
    candidate_id: str | None = None
    candidate_label: str | None = None
    similarity: float | None = Field(
        default=None,
        description="cosine-like similarity. NOT a probability and NOT a diagnosis "
                    "confidence.")


class MisconceptionAdvisoryResponse(BaseModel):
    metadata: ScientificAuthority
    wrong_record: MisconceptionWrongRecord
    score_semantics: str
    candidates: list[MisconceptionCandidate]
    available: bool
    ontology_domain: str | None = None
    weak_label: bool | None = None


class ScientificCapabilityEntry(BaseModel):
    """One component's PRODUCT-FACING readiness.

    ``available`` is not "a runtime endpoint exists": it means the product can produce this
    component's output from real facts it holds today.
    """

    component: str
    mode: str = Field(description="PREVIEW | SHADOW | SHADOW_NOT_USER_VISIBLE | UNAVAILABLE")
    available: bool
    user_visible: bool
    controls_product_decision: bool
    writes_learner_fact: bool
    blockers: list[str] = Field(description="stable reason codes; empty when none")
    semantics: str = Field(description="short label for what the component's output IS")


class ScientificCapabilityTotals(BaseModel):
    components: int
    available: int
    user_visible: int
    controls_product_decision: int
    writes_learner_fact: int


class ScientificCapabilitiesResponse(BaseModel):
    """The product-facing scientific capability summary. Carries no scientific number."""

    generated_at: str
    source_class: str
    terminology: dict[str, str] = Field(
        description="what each reported field means, so no reader has to infer it")
    totals: ScientificCapabilityTotals
    components: list[ScientificCapabilityEntry]


class TutorPolicyShadowResponse(BaseModel):
    metadata: ScientificAuthority
    controls_response: bool
    action_ontology: list[str]
    suggested_action: str | None = None
    action_probabilities: dict[str, float] | None = None
    available: bool
