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
from science import misconception, status, tutor_policy
from science.contract import MisconceptionAdvisoryResponse, TutorPolicyShadowResponse

router = APIRouter(prefix="/science", tags=["science"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


def _require_admin(request: Request, db: Session = Depends(get_db)):
    """Admin gate for the diagnostics surface (S8 PART 10).

    Reuses the product's ONE admin predicate rather than growing a second one. An ordinary
    authenticated learner gets the same 403 an anonymous caller would, so this route is not
    an existence oracle for the internal status either.
    """
    from main import get_current_user, is_admin_user  # lazy import, same reason
    user = get_current_user(request, db)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


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


@router.get("/status")
def get_scientific_status(probe_runtime: bool = Query(default=False),
                          current_user=Depends(_require_admin),
                          db: Session = Depends(get_db)):
    """ADMIN-ONLY scientific capability + model-execution status.

    NOT a learner page. It exists for competition, demo and engineering proof: which
    capability is user-visible, which is shadow and collecting data, which is research-only
    and why, and what technical evidence exists that each retained self-developed model is
    real (family, digests, runtime route, the test that executes it, product mode, blocker).

    It carries no per-user field and takes no user parameter, so it cannot become a view of
    anybody's learning. It exposes no raw prompt, no filesystem path and no secret — a
    runtime is named by its logical route, never by host or install location.

    ``probe_runtime`` defaults to FALSE: an unprobed runtime reports ``reachable: null``,
    which is a different answer from ``false`` and is never conflated with it.
    """
    from science import client as sci_client
    reachable = None
    if probe_runtime:
        reachable = bool(sci_client.get_client().health())
    return status.diagnostics(runtime_reachable=reachable)
