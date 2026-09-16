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
    CONTRACT_VERSION,
    RUNTIME_RELEASE_ID,
    SCIENTIFIC_SOURCE_CLASS,
    SCIENTIFIC_SOURCE_COMMIT,
)
from .contracts import (
    CapabilitiesResponse,
    StudentTwinInferenceRequest,
    StudentTwinInferenceResponse,
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
        "components": [COMPONENT_ID],
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
