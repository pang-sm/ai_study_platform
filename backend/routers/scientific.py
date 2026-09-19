"""Product-facing scientific surface — misconception advisory + tutor-policy shadow hook.

Every route here is:
  * **authenticated** and scoped to the caller — user B can never read user A's learning
    state or wrong-answer context;
  * **read-only** — no scientific call mutates knowledge status, mastery, wrong state,
    plan or grade;
  * **authority-labelled** — each response carries the shared metadata block stating the
    component, the runtime release, the mode, and that it controls no product decision.

A scientific outage answers with an explicit bounded ``available: false`` state. It is
never a 500, and it never reaches the core learning loop.

The StudentTwin preview is exam-scoped and lives at
``GET /exam/prep/scientific/student-twin``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from learning.wrong_answers import service as wrong_service
from science import misconception, tutor_policy
from science.contract import MisconceptionAdvisoryResponse, TutorPolicyShadowResponse

router = APIRouter(prefix="/science", tags=["science"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


@router.post("/misconception-advisory", response_model=MisconceptionAdvisoryResponse)
def request_misconception_advisory(
        state_id: int = Query(description="the canonical wrong-answer record to analyse"),
        top_k: int = Query(default=misconception.TOP_K_DEFAULT, ge=1,
                           le=misconception.TOP_K_MAX),
        current_user=Depends(_require_user),
        db: Session = Depends(get_db)):
    """Candidate misconceptions for one wrong-answer record — ADVISORY, SHADOW today.

    The learner explicitly asks for this; nothing is computed in the background. The
    response exposes a SIMILARITY, never a probability or a diagnosis, and it changes no
    learner fact. ``metadata.mode`` is SHADOW_NOT_USER_VISIBLE while the ontology question
    is unresolved, so the candidates are computed for validation and must not be presented
    as a diagnosis.
    """
    try:
        return misconception.advise(db, current_user.id, state_id, top_k=top_k)
    except (wrong_service.StateNotFound, wrong_service.CrossUserAccess):
        # a cross-user id is reported as absent, so the surface is not an existence oracle
        raise HTTPException(status_code=404, detail="wrong-answer record not found")


@router.get("/tutor-policy", response_model=TutorPolicyShadowResponse)
def get_tutor_policy_shadow(current_user=Depends(_require_user),
                            db: Session = Depends(get_db)):
    """The SHADOW hook's current answer.

    It reports the exact blocker rather than fabricating a turn state, and
    ``controls_response`` is always false: a suggested action never changes the tutor's
    reply.
    """
    result = tutor_policy.shadow_suggest(db, current_user.id)
    return {
        "metadata": result["metadata"],
        "controls_response": result["controls_response"],
        "action_ontology": result["action_ontology"],
        "suggested_action": result.get("suggested_action"),
        "action_probabilities": result.get("action_probabilities"),
        "available": result["available"],
    }
