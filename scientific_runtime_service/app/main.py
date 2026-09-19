"""Scientific runtime service (Python) — typed StudentTwin inference only.

Bound to 127.0.0.1 in production; never exposed to the public internet.  It owns no
product DB, no auth, no course logic, no product decision, no LearningEvent storage.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException

from . import runtime_bridge
from .config import (
    COMPONENT_ID,
    COMPONENT_IDS,
    CONTRACT_VERSION,
    EVIDENCE_RELIABILITY_SOURCE_COMMIT,
    LEARNER_STATE_SOURCE_COMMIT,
    MISCONCEPTION_ONTOLOGY_DOMAIN,
    MISCONCEPTION_SOURCE_COMMIT,
    RUNTIME_RELEASE_ID,
    SCIENTIFIC_SOURCE_CLASS,
    SCIENTIFIC_SOURCE_COMMIT,
    TUTOR_POLICY_SOURCE_COMMIT,
)
from .contracts import (
    CapabilitiesResponse,
    EvidenceReliabilityRequest,
    EvidenceReliabilityResponse,
    LearnerStateRequest,
    LearnerStateResponse,
    MisconceptionRequest,
    MisconceptionResponse,
    StudentTwinInferenceRequest,
    StudentTwinInferenceResponse,
    TutorPolicyRequest,
    TutorPolicyResponse,
)

app = FastAPI(title="zhixue-runtime", version=RUNTIME_RELEASE_ID)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "component": COMPONENT_ID,
    }


@app.get("/v1/capabilities", response_model=CapabilitiesResponse)
def capabilities():
    return {
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "components": list(COMPONENT_IDS),
    }


@app.post("/v1/inference/student-twin", response_model=StudentTwinInferenceResponse)
def infer_student_twin(req: StudentTwinInferenceRequest):
    if req.contract_version != CONTRACT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported contract_version {req.contract_version}; expected {CONTRACT_VERSION}",
        )
    if not req.events:
        raise HTTPException(status_code=400, detail="events must not be empty")
    if req.events[-1].event_id != req.target_event_id:
        raise HTTPException(
            status_code=400,
            detail="target_event_id must equal the last event's event_id",
        )
    ids = [e.event_id for e in req.events]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="event_id must be unique")
    for prev, cur in zip(req.events, req.events[1:]):
        if (cur.occurred_at, cur.event_id) < (prev.occurred_at, prev.event_id):
            raise HTTPException(
                status_code=400,
                detail="events must be non-decreasing by (occurred_at, event_id)",
            )
    if req.runtime_release_id and req.runtime_release_id != RUNTIME_RELEASE_ID:
        raise HTTPException(
            status_code=400,
            detail=f"runtime_release_id mismatch: {req.runtime_release_id}",
        )

    started = time.time()
    state = runtime_bridge.replay_state(req.user_ref, req.events)
    latency_ms = (time.time() - started) * 1000.0

    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": req.request_id,
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "component_id": COMPONENT_ID,
        "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "target_event_id": req.target_event_id,
        "replayed_events": len(req.events),
        "state": state,
        "latency_ms": round(latency_ms, 3),
    }


@app.post("/v1/inference/misconception-v2", response_model=MisconceptionResponse)
def infer_misconception_v2(req: MisconceptionRequest):
    """Candidate misconception retrieval for one (question, wrong answer) pair.

    The score is a SIMILARITY (cosine-like normalized inner product), never a probability
    and never a confidence. Retrieved ids are WEAK labels from the scientific ontology,
    which is NOT the product ontology.
    """
    if req.contract_version != CONTRACT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported contract_version {req.contract_version}; expected {CONTRACT_VERSION}",
        )
    if not (req.question or "").strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    if not (req.answer or "").strip():
        raise HTTPException(status_code=400, detail="answer must not be empty")

    started = time.time()
    try:
        output = runtime_bridge.misconception_matches(req.question, req.answer, req.top_k)
    except runtime_bridge.RuntimeInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — asset/dependency failures are bounded
        raise HTTPException(
            status_code=503,
            detail=f"misconception_v2 unavailable: {type(exc).__name__}",
        ) from exc
    latency_ms = (time.time() - started) * 1000.0

    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": req.request_id,
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
        "scientific_source_commit": MISCONCEPTION_SOURCE_COMMIT,
        "matches": [
            {
                "rank": m["rank"],
                "misconception_id": m["misconception_id"],
                "misconception_text": m["misconception_text"],
                "similarity": m["retrieval_score"],
            }
            for m in output["results"]
        ],
        "score_semantics": output["score_semantics"],
        "weak_label": bool(output["weak_label"]),
        "ontology_size": int(output["ontology_size"]),
        "ontology_domain": MISCONCEPTION_ONTOLOGY_DOMAIN,
        "product_role": output["product_role"],
        "controls_product_decision": bool(output["controls_product_decision"]),
        "latency_ms": round(latency_ms, 3),
    }


@app.post("/v1/inference/learner-state", response_model=LearnerStateResponse)
def infer_learner_state(req: LearnerStateRequest):
    """Knowledge tracing: interaction sequence -> P(correct on the NEXT response).

    The output is a next-response probability. It is NOT a mastery probability, a
    knowledge-mastery score, an ability estimate, or a difficulty. The variant is named
    explicitly by the caller: this is a PANEL of engineering-representative families and it
    never averages, votes, or auto-selects a winner.

    ``q``/``r_prev`` index the FAMILY's own scientific ontology (base ASSISTments 123
    skills / junyi 835 concepts). No product concept is mapped here — see the request DTO.
    """
    if req.contract_version != CONTRACT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported contract_version {req.contract_version}; expected {CONTRACT_VERSION}",
        )
    if not req.q:
        raise HTTPException(status_code=400, detail="q must not be empty")
    if len(req.q) != len(req.r_prev):
        raise HTTPException(status_code=400, detail="q and r_prev must have the same length")

    started = time.time()
    try:
        output = runtime_bridge.learner_state_predict(req.family, req.q, req.r_prev, req.mask)
    except runtime_bridge.RuntimeInputError as exc:
        # the adapter validates the sequence against the family's real ontology size
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — asset/dependency failures are bounded
        raise HTTPException(
            status_code=503, detail=f"learner_state unavailable: {type(exc).__name__}",
        ) from exc
    latency_ms = (time.time() - started) * 1000.0

    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": req.request_id,
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
        "scientific_source_commit": LEARNER_STATE_SOURCE_COMMIT,
        "family": output["family"],
        "ontology": output["ontology"],
        "num_skills": output["num_skills"],
        "next_response_probability": output["next_response_probability"],
        "score_semantics": output["score_semantics"],
        "engineering_representative_only": bool(output["engineering_representative_only"]),
        "active_product_variant": output["active_product_variant"],
        "product_role": output["product_role"],
        "controls_product_decision": bool(output["controls_product_decision"]),
        "latency_ms": round(latency_ms, 3),
    }


@app.post("/v1/inference/tutor-policy", response_model=TutorPolicyResponse)
def infer_tutor_policy(req: TutorPolicyRequest):
    """Suggested pedagogical action for one turn state (SHADOW use only).

    The 4-way ontology is focus / generic / probing / telling. It is a classifier, not a
    controller: the suggestion must never change what the tutor actually replies.
    """
    if req.contract_version != CONTRACT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported contract_version {req.contract_version}; expected {CONTRACT_VERSION}",
        )
    if not (req.problem or "").strip():
        raise HTTPException(status_code=400, detail="problem must not be empty")
    if not (req.wrong or "").strip():
        raise HTTPException(status_code=400, detail="wrong must not be empty")

    started = time.time()
    try:
        output = runtime_bridge.tutor_policy_action(
            req.problem, req.wrong, req.profile, req.confusion,
            list(req.prev_actions), [list(h) for h in req.history])
    except runtime_bridge.RuntimeInputError as exc:
        # the adapter validates prev_actions against the frozen 4-way ontology
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503, detail=f"tutor_policy unavailable: {type(exc).__name__}",
        ) from exc
    latency_ms = (time.time() - started) * 1000.0

    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": req.request_id,
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
        "scientific_source_commit": TUTOR_POLICY_SOURCE_COMMIT,
        "suggested_action": output["requested_action"],
        "action_probabilities": output["action_probabilities"],
        "ranking": output["ranking"],
        "action_ontology": output["action_ontology"],
        "product_role": output["product_role"],
        "controls_product_decision": bool(output["controls_product_decision"]),
        "latency_ms": round(latency_ms, 3),
    }


@app.post("/v1/inference/evidence-reliability",
          response_model=EvidenceReliabilityResponse)
def infer_evidence_reliability(req: EvidenceReliabilityRequest):
    """Reliability weights for the five-variant PANEL (SHADOW use only).

    Each weight ``w in (0,1)`` states how much one observation should count in a
    reliability-weighted learner-state update. It is NOT a probability the response is
    correct, NOT a confidence, and NOT a judgement about the learner. The panel never
    averages, votes, or auto-selects a variant.

    The caller must supply the interaction's real standardized feature vector per variant.
    The standardization statistics and the IRT ``b_map`` that produced them are not
    bundled, so no product caller can construct this input today — the endpoint exists so
    a SHADOW consumer with genuine inputs can be wired without touching the runtime.
    """
    if req.contract_version != CONTRACT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported contract_version {req.contract_version}; expected {CONTRACT_VERSION}",
        )
    if not req.features_by_variant:
        raise HTTPException(status_code=400, detail="features_by_variant must not be empty")

    started = time.time()
    try:
        output = runtime_bridge.evidence_reliability_panel(
            {k: list(v) for k, v in req.features_by_variant.items()})
    except runtime_bridge.RuntimeInputError as exc:
        # the adapter validates each vector against that variant's real dimension
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — asset/dependency failures are bounded
        raise HTTPException(
            status_code=503, detail=f"evidence_reliability unavailable: {type(exc).__name__}",
        ) from exc
    latency_ms = (time.time() - started) * 1000.0

    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": req.request_id,
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
        "scientific_source_commit": EVIDENCE_RELIABILITY_SOURCE_COMMIT,
        "variant_outputs": output["variant_outputs"],
        "score_range": output["score_range"],
        "score_std": output["score_std"],
        "variant_disagreement": output["variant_disagreement"],
        "averaging": bool(output["averaging"]),
        "auto_selection": bool(output["auto_selection"]),
        "active_product_variant": output["active_product_variant"],
        "variant_mode": output["variant_mode"],
        "replacement_readiness": output["replacement_readiness"],
        "score_semantics": output["score_semantics"],
        "product_role": output["product_role"],
        "controls_product_decision": bool(output["controls_product_decision"]),
        "latency_ms": round(latency_ms, 3),
    }
