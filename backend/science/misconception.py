"""misconception_v2 product integration (PART D) — ADVISORY, and today SHADOW-ONLY.

WHAT THE MODEL IS
-----------------
``misconception_v2`` is a dual-encoder retrieval model: BGE-M3 encodes
``"{question} [ANS] {answer}"``, L2-normalizes, and searches a FAISS ``IndexFlatIP`` over
the scientific misconception ontology. Its output number is a **similarity** — a
cosine-like normalized inner product. It is NOT a probability, NOT a confidence, NOT
``P(misconception)``, and NOT a diagnosis. The retrieved entry is a WEAK label, not ground
truth. The product contract preserves that distinction in the field NAME (``similarity``)
and in the field SEMANTICS (``score_semantics``).

WHY IT IS NOT USER-VISIBLE TODAY
--------------------------------
Two blockers, both recorded rather than worked around:

1. ``ONTOLOGY_MISMATCH`` — the runtime's ontology is the Eedi misconception set (2587
   entries, English). The product's ontology is Chinese CS/11408. There is no honest
   mapping between them, and inventing one would turn a weak retrieved label into a
   fabricated diagnosis. This matches the frozen productization matrix
   (``data_plane.eligibility``: ``misconception_v2 = ONTOLOGY_MISMATCH``).
2. ``RUNTIME_COMPONENT_NOT_PROVISIONED`` — the deployed runtime environment carries the
   StudentTwin stack but not ``torch`` / ``transformers`` / ``faiss``, so the component
   cannot execute there yet.

The bridge is nevertheless WIRED: the request is built from real product facts and the
call is made. Nothing it returns is shown to a learner, and nothing it returns is written.
"""
from __future__ import annotations

import json
import logging

import models
from sqlalchemy.orm import Session as DbSession

from . import metadata
from .client import (
    ScientificClient,
    ScientificRejected,
    ScientificUnavailable,
    get_client,
    new_request_id,
)

logger = logging.getLogger("science.misconception")

COMPONENT = "misconception_v2"
CONTRACT_VERSION = 1
RUNTIME_PATH = "/v1/inference/misconception-v2"
TOP_K_DEFAULT = 3
TOP_K_MAX = 10

# D5: no ACTIVE mode in this sprint, and no ADVISORY until the ontology maps honestly.
PRODUCT_MODE = metadata.MODE_SHADOW_NOT_USER_VISIBLE

BLOCKER_ONTOLOGY = (
    "ONTOLOGY_MISMATCH: runtime ontology is the Eedi misconception set (2587 entries, "
    "English); the product ontology is Chinese CS/11408. No honest mapping exists, so a "
    "retrieved id cannot be presented as a diagnosis (SSOT §36.3).")
BLOCKER_PROVISIONING = (
    "RUNTIME_COMPONENT_NOT_PROVISIONED: the scientific runtime environment installs "
    "numpy but not torch/transformers/faiss, so misconception_v2 cannot execute there yet.")

SCORE_SEMANTICS = ("cosine-like normalized inner product between the encoded "
                   "(question, wrong answer) query and an ontology entry. A SIMILARITY, "
                   "not a probability, not a confidence, not a diagnosis.")

# The only source whose question text this module can resolve authoritatively today.
STATIC_QUESTION_BANK = "static_question_bank"


def resolve_question_text(db: DbSession, question_source_type: str | None,
                          question_source_id: str | None) -> tuple[str | None, list[str]]:
    """The question's real text, from the table that owns it.

    Returns ``(text, blockers)``. A source this module cannot resolve yields ``None`` plus
    the reason — it never falls back to a guess, and the caller must not call the runtime
    with a fabricated question.
    """
    if not question_source_type or not question_source_id:
        return None, ["QUESTION_SOURCE_UNRESOLVED: the record carries no question reference"]

    if question_source_type != STATIC_QUESTION_BANK:
        return None, [
            f"QUESTION_SOURCE_UNSUPPORTED: {question_source_type!r} question text is not "
            "resolvable through the canonical bank reader yet"]

    try:
        question_id = int(question_source_id)
    except (TypeError, ValueError):
        return None, [f"QUESTION_SOURCE_UNRESOLVED: non-numeric id {question_source_id!r}"]

    item = (db.query(models.ExamQuestionBank)
            .filter(models.ExamQuestionBank.id == question_id).first())
    if item is None or not (item.stem or "").strip():
        return None, [f"QUESTION_SOURCE_UNRESOLVED: question {question_id} not found"]

    stem = item.stem.strip()
    options = {}
    try:
        parsed = json.loads(item.options_json or "{}")
        options = parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        options = {}
    if options:
        stem = stem + "\n" + "\n".join(f"{k}. {v}" for k, v in sorted(options.items()))
    return stem, []


def advise(db: DbSession, user_id: int, state_id: int, *, top_k: int = TOP_K_DEFAULT,
           client: ScientificClient | None = None) -> dict:
    """Candidate misconceptions for one canonical wrong-answer record.

    READ-ONLY. The wrong-answer state, its attempts, knowledge status, plan and grades are
    all untouched. Raises ``learning.wrong_answers.service.StateNotFound`` for an unknown
    or cross-user state, so ownership is enforced by the canonical owner.
    """
    from learning.wrong_answers import service as wrong_service

    top_k = max(1, min(int(top_k or TOP_K_DEFAULT), TOP_K_MAX))
    detail = wrong_service.state_detail(db, user_id, state_id)
    state = detail["state"]

    blockers = [BLOCKER_ONTOLOGY, BLOCKER_PROVISIONING]
    question_text, resolve_blockers = resolve_question_text(
        db, state.get("question_source_type"), state.get("question_source_id"))
    blockers.extend(resolve_blockers)

    answer_text = (detail.get("user_answer") or "").strip()
    if not answer_text:
        # the retrieval query is (question, wrong answer); no wrong answer means there is
        # nothing to retrieve against, and inventing one would fabricate the query
        blockers.append("NO_WRONG_ANSWER_ON_RECORD")

    wrong_record = {
        "state_id": state.get("id"),
        "service_namespace": state.get("service_namespace"),
        "status": state.get("status"),
        "question_source_type": state.get("question_source_type"),
        "question_source_id": state.get("question_source_id"),
    }

    base = {
        "metadata": metadata.metadata(
            component=COMPONENT, mode=PRODUCT_MODE, blockers=blockers,
            semantics=SCORE_SEMANTICS),
        "wrong_record": wrong_record,
        "score_semantics": SCORE_SEMANTICS,
        "candidates": [],
        "available": False,
    }

    if question_text is None or not answer_text:
        return base

    request_id = new_request_id(COMPONENT)
    runtime_request = {
        "contract_version": CONTRACT_VERSION,
        "request_id": request_id,
        "question": question_text,
        "answer": answer_text,
        "top_k": top_k,
    }

    client = client or get_client()
    try:
        body = client.infer(RUNTIME_PATH, runtime_request, component=COMPONENT)
    except ScientificUnavailable as exc:
        logger.warning("misconception advisory unavailable request_id=%s detail=%s",
                       request_id, exc.detail)
        base["metadata"] = metadata.metadata(
            component=COMPONENT, mode=PRODUCT_MODE, request_id=request_id,
            blockers=blockers + ["SCIENTIFIC_RUNTIME_UNAVAILABLE"],
            semantics=SCORE_SEMANTICS)
        return base
    except ScientificRejected as exc:
        logger.warning("misconception advisory rejected request_id=%s detail=%s",
                       request_id, exc.detail)
        base["metadata"] = metadata.metadata(
            component=COMPONENT, mode=PRODUCT_MODE, request_id=request_id,
            blockers=blockers + ["SCIENTIFIC_RUNTIME_REJECTED_REQUEST"],
            semantics=SCORE_SEMANTICS)
        return base

    # the ONLY field names allowed out: rank, candidate identity, and a similarity
    candidates = [
        {
            "rank": m.get("rank"),
            "candidate_id": m.get("misconception_id"),
            "candidate_label": m.get("misconception_text"),
            "similarity": m.get("similarity"),
        }
        for m in (body.get("matches") or [])
    ]
    base["candidates"] = candidates
    base["available"] = True
    base["metadata"] = metadata.from_runtime_response(
        COMPONENT, PRODUCT_MODE, body, blockers=blockers, semantics=SCORE_SEMANTICS)
    if body.get("ontology_domain"):
        base["ontology_domain"] = body["ontology_domain"]
    if body.get("weak_label") is not None:
        base["weak_label"] = bool(body["weak_label"])
    return base
