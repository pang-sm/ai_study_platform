"""tutor_policy product integration (PART E) — SHADOW hook, and NOT a tutor controller.

WHAT THE MODEL IS
-----------------
``tutor_policy`` is a BGE-M3 encoder with a 4-way classification head over the FROZEN
pedagogical action ontology:

    focus / generic / probing / telling

It is a classifier, not a controller. Historical L3 macro-F1 is ~0.48 (weak-but-supported),
and the action -> outcome causal utility is explicitly NOT_SUPPORTED.

HARD RULE
---------
``TUTOR_POLICY_CONTROLS_RESPONSE = False``. A suggested action must never change the
tutor's actual reply. This module therefore returns PREVIEWS only, and no caller in the
product is wired to consume them. There is nothing to disable: the hook is not on the
response path at all.

WHY THERE IS NO PRODUCT TURN STATE YET
--------------------------------------
The runtime needs ``FULL_STATE``: problem, the student's wrong solution, a student
profile, a teacher-described confusion, the PRIOR pedagogical actions, and the dialogue.
Two of those cannot be formed from real product facts:

  * ``prev_actions`` — the product has no ledger of pedagogical actions taken per turn.
    Nothing records "we chose probing last turn", so any value here would be invented.
  * ``confusion`` / ``profile`` — the research dataset fields have no product source, and
    mapping a knowledge state onto a research profile string would be fabrication.

The CS408 AI surface compounds it: ``question.explain`` is a one-shot explanation of a
question, not a tutoring dialogue with a submitted wrong solution.

This matches the frozen productization matrix (``data_plane.eligibility``:
``tutor_policy = MISSING_INPUT`` / ``UNRESOLVED``). The hook is wired and the bridge is
proven by tests; it answers "not available, here is why" until a real turn state exists.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from . import metadata
from .client import (
    ScientificClient,
    ScientificRejected,
    ScientificUnavailable,
    get_client,
    new_request_id,
)

logger = logging.getLogger("science.tutor_policy")

COMPONENT = "tutor_policy"
CONTRACT_VERSION = 1
RUNTIME_PATH = "/v1/inference/tutor-policy"
PRODUCT_MODE = metadata.MODE_SHADOW

# The frozen ontology. MUST NOT be rewritten to ALLOW / REJECT or any other vocabulary.
ACTION_ONTOLOGY = ("focus", "generic", "probing", "telling")

TUTOR_POLICY_CONTROLS_RESPONSE = False

BLOCKER_NO_ACTION_LEDGER = (
    "TURN_STATE_PREV_ACTIONS_UNAVAILABLE: the product records no pedagogical-action "
    "history per turn, so prev_actions has no honest value; inventing one would fabricate "
    "the dominant input signal of the model.")
BLOCKER_NO_RESEARCH_FIELDS = (
    "TURN_STATE_RESEARCH_FIELDS_UNAVAILABLE: 'profile' (student profile) and 'confusion' "
    "(teacher-described confusion) are research-dataset fields with no product source.")
BLOCKER_NOT_A_TUTOR_TURN = (
    "TURN_STATE_NOT_A_TUTOR_TURN: the CS408 AI surface exposes one-shot question "
    "explanation, not a tutoring dialogue with a submitted wrong solution.")


# ================================================================ ACCEL_SPRINT_S5 PART M
# THE PEDAGOGICAL-ACTION LEDGER AUDIT
#
# The question this answers: does the product ALREADY choose an explicit pedagogical
# action, such that recording it would produce real TutorPolicy training data? It is an
# audit, not a design — and the answer is NO, with the audit below as the evidence.
#
# WHAT THE AI PATH ACTUALLY CHOOSES
# ---------------------------------
# ``ai.orchestrator`` composes one lifecycle: permission -> router -> estimate -> reserve ->
# gateway -> actual cost -> settle. Every choice it makes is about HOW TO CALL A MODEL:
# which capability was requested, whether the tier permits it, which qualified model in the
# pool serves it, and whether the budget allows it. It never chooses what the TUTOR should
# do next, and the 4-way ontology does not appear in it.
#
# There IS one deterministic product decision adjacent to pedagogy: ``prompts.
# detect_question_type`` classifies the learner's own message into a question TYPE
# (concept_explanation / code_debug / exercise_solution / study_plan / project_help /
# general) and selects a response STRUCTURE for it. Three things make it NOT a pedagogical
# action ledger:
#
#   1. it is not in the frozen ontology. The model's classes are focus / generic / probing
#      / telling. A question type is what the learner ASKED FOR, not what the tutor DECIDED
#      TO DO — mapping the two would be the fabrication this sprint forbids, and the
#      mapping would be the dominant signal of any model trained on it;
#   2. it is not persisted. Nothing records which type a delivered turn was answered under,
#      so there is no history to read even if the semantic were right;
#   3. it is a property of the input, not a choice among alternatives with different
#      expected outcomes — and the frozen record already states the action -> outcome
#      causal utility is NOT_SUPPORTED.
#
# The capability that IS recorded (``ai_requests.capability``) is likewise an AI operation
# name (tutor.chat / question.explain / programming.debug), not a pedagogical action.
#
# CONCLUSION: no honest ledger can be built from what the product decides today, and none
# is invented here. The audit is executable so a future sprint can re-run it and see
# exactly what would have to change.
PEDAGOGICAL_ACTION_LEDGER_READY = False

# The choices the product really makes on an AI turn, and what each one actually is.
AUDITED_PRODUCT_DECISIONS = (
    {"decision": "ai.orchestrator capability selection", "kind": "AI_OPERATION",
     "recorded": True, "recorded_where": "ai_requests.capability",
     "pedagogical_action": False,
     "why_not": "names the AI operation requested (tutor.chat / question.explain / "
                "programming.debug), not a tutoring strategy"},
    {"decision": "ai.orchestrator model selection within the qualified pool",
     "kind": "INFRASTRUCTURE", "recorded": True, "recorded_where": "ai_requests / router",
     "pedagogical_action": False,
     "why_not": "which model serves a capability is an infrastructure choice with no "
                "pedagogical ontology entry"},
    {"decision": "prompts.detect_question_type -> response structure", "kind":
     "RESPONSE_TEMPLATE", "recorded": False, "recorded_where": None,
     "pedagogical_action": False,
     "why_not": "classifies what the learner ASKED FOR into a question type; it is not a "
                "choice in the focus/generic/probing/telling ontology, and it is not "
                "persisted, so there is no history either"},
)


def pedagogical_action_ledger_status() -> dict:
    """PART M: whether a TutorPolicy training ledger could be built from real choices.

    Read-only and pure. It reports the audit, not a plan: this sprint does not redesign
    tutoring, and it does not promote tutor_policy.
    """
    return {
        "component": COMPONENT,
        "ledger_ready": PEDAGOGICAL_ACTION_LEDGER_READY,
        "action_ontology": list(ACTION_ONTOLOGY),
        "audited_decisions": [dict(d) for d in AUDITED_PRODUCT_DECISIONS],
        "recorded_pedagogical_actions": 0,
        "why_not": ("the product selects a capability and a model, and derives a "
                    "question-type response structure; none of the three is an action in "
                    "the frozen focus/generic/probing/telling ontology, and none of the "
                    "three is persisted as a per-turn pedagogical choice"),
        "what_would_change_it": (
            "a surface that genuinely chooses among pedagogical actions AND records which "
            "one it took per turn, so prev_actions has a real value"),
        "product_mode_unchanged": PRODUCT_MODE,
        "tutor_policy_promoted": False,
        "note": ("no ledger is invented. A fabricated prev_actions column would fabricate "
                 "the dominant input signal of the model it is meant to train"),
    }


def build_turn_state(db: DbSession, user_id: int, *, turn_ref: str | None = None):
    """The full turn state needed by the model, from real product facts.

    Returns ``(state, blockers)``. ``state`` is ``None`` today: the ledger and the research
    fields do not exist in the product, so there is nothing honest to send. This function
    is the ONE place that would change when they do — no caller fabricates a fallback.
    """
    blockers = [BLOCKER_NO_ACTION_LEDGER, BLOCKER_NO_RESEARCH_FIELDS]
    if turn_ref is None:
        blockers.append(BLOCKER_NOT_A_TUTOR_TURN)
    return None, blockers


def shadow_suggest(db: DbSession, user_id: int, *, turn_ref: str | None = None,
                   client: ScientificClient | None = None) -> dict:
    """Compute (or decline to compute) a suggested tutoring action.

    Always returns; never raises for an unavailable runtime; never affects a response.
    """
    state, blockers = build_turn_state(db, user_id, turn_ref=turn_ref)
    result = {
        "metadata": metadata.metadata(
            component=COMPONENT, mode=PRODUCT_MODE, blockers=blockers,
            semantics="suggested pedagogical action, SHADOW only; it controls no tutor "
                      "response"),
        "controls_response": TUTOR_POLICY_CONTROLS_RESPONSE,
        "action_ontology": list(ACTION_ONTOLOGY),
        "suggested_action": None,
        "action_probabilities": None,
        "available": False,
    }
    if state is None:
        return result
    return {**result, **_call_runtime(state, blockers=blockers, client=client)}


def suggest_for_explicit_state(state: dict,
                               client: ScientificClient | None = None) -> dict:
    """SHADOW bridge call for an EXPLICITLY SUPPLIED turn state.

    This is the verification surface for the bridge: it exists so the runtime integration
    can be proven end to end without pretending the product has a turn state it does not.
    It takes the caller's state verbatim and is NOT reachable from any product flow.
    """
    blockers = ["EXPLICIT_STATE: caller-supplied turn state; not derived from product facts"]
    return _call_runtime(state, blockers=blockers, client=client)


def _call_runtime(state: dict, *, blockers: list[str],
                  client: ScientificClient | None = None) -> dict:
    request_id = new_request_id(COMPONENT)
    runtime_request = {
        "contract_version": CONTRACT_VERSION,
        "request_id": request_id,
        "problem": state["problem"],
        "wrong": state["wrong"],
        "profile": state.get("profile"),
        "confusion": state.get("confusion"),
        "prev_actions": list(state.get("prev_actions") or []),
        "history": [list(h) for h in (state.get("history") or [])],
    }

    client = client or get_client()
    try:
        body = client.infer(RUNTIME_PATH, runtime_request, component=COMPONENT)
    except ScientificUnavailable as exc:
        logger.warning("tutor_policy shadow unavailable request_id=%s detail=%s",
                       request_id, exc.detail)
        return {"available": False,
                "metadata": metadata.metadata(
                    component=COMPONENT, mode=PRODUCT_MODE, request_id=request_id,
                    blockers=blockers + ["SCIENTIFIC_RUNTIME_UNAVAILABLE"],
                    semantics="SHADOW only; controls no tutor response")}
    except ScientificRejected as exc:
        logger.warning("tutor_policy shadow rejected request_id=%s detail=%s",
                       request_id, exc.detail)
        return {"available": False,
                "metadata": metadata.metadata(
                    component=COMPONENT, mode=PRODUCT_MODE, request_id=request_id,
                    blockers=blockers + ["SCIENTIFIC_RUNTIME_REJECTED_REQUEST"],
                    semantics="SHADOW only; controls no tutor response")}

    ontology = list(body.get("action_ontology") or [])
    return {
        "available": True,
        # the ontology is read back rather than assumed: a runtime that returned a
        # different vocabulary would be visible here, not silently reinterpreted
        "action_ontology": ontology,
        "suggested_action": body.get("suggested_action"),
        "action_probabilities": body.get("action_probabilities"),
        "controls_response": TUTOR_POLICY_CONTROLS_RESPONSE,
        "metadata": metadata.from_runtime_response(
            COMPONENT, PRODUCT_MODE, body, blockers=blockers,
            semantics="suggested pedagogical action, SHADOW only; it controls no tutor "
                      "response"),
    }
