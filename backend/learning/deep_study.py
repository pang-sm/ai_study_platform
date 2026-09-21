"""Deep Study — the ONE strong-reasoning workflow over the shared Learning Core.

WHAT IT IS
----------
A learner asks a hard question and gets an answer GROUNDED in their own materials: relevant
chunks are retrieved with the platform's EXISTING retrieval (FTS5/BM25 + keyword bonus — no
vector database is introduced), assembled into a bounded evidence context, and answered by a
strong-reasoning model through the unified AI boundary. The answer comes back with the
citations it was built from, so nothing it says is unattributable.

WHY IT IS NOT A SECOND AI SYSTEM
--------------------------------
There is no ``deep_study_quota``, no second provider client and no per-space copy of it. The
whole workflow runs through ``ai.orchestrator``:

    Subscription → Capability Permission (``tutor.strong_reasoning``) → Usage estimate /
    reserve → Qualified Model Pool → Router → Gateway → actual cost → settle → AI event

The capability is requested BY NAME; this module never names a provider or a model. It uses
the space's own narrow adapter (``execute_course_ai`` / ``execute_exam_ai``) so the request
carries a canonical ``LearningContext`` for the space it belongs to.

MATERIAL ISOLATION
------------------
Every chunk is read through the SAME access rule the rest of the product uses (``rag``),
which admits only the caller's own materials (that allow private RAG) and system materials
that explicitly allow public RAG. On top of that, a COURSE-scoped request admits an explicit
``material_ids`` entry only when the material also belongs to that course — so one course can
never be grounded in another course's material. A material that fails the rule is reported in
``materials.excluded``: refused, not silently dropped.

WHAT IT DOES NOT DO
-------------------
No mastery claim, no weakness inference, no fabricated citation: a citation exists only when
a real chunk was retrieved and put in front of the model. If retrieval finds nothing, the
answer is a plain strong-reasoning answer and ``citations`` is empty — the response says so.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session as DbSession

from core.learning_context import LearningContext, ServiceNamespace, normalize_service_namespace

logger = logging.getLogger("learning.deep_study")

CAPABILITY = "tutor.strong_reasoning"
DEFAULT_MAX_TOKENS = 2400
MAX_QUESTION_CHARS = 2000
DEFAULT_TOP_K = 4

COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value

# User-safe quality labels. A learner may know how strong the model that answered is; the
# provider and the raw model id are NOT part of this name (see ``user_safe_model_info``).
_QUALITY_LABELS = {"premium": "高级", "standard": "标准", "basic": "基础"}


class DeepStudyRefusal(ValueError):
    """The workflow cannot be built for this request (a caller-facing 4xx reason)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


# ---------------------------------------------------------------- material scope

def _visibility_of(material) -> tuple[bool, bool]:
    """(owner_rag_allowed, public_rag_allowed) — mirroring ``rag.accessible_chunk_filter``.

    The SQL filter coalesces a legacy NULL ``visibility`` to ``private`` and a NULL
    ``allow_private_rag`` to allowed; the same reading is kept here so this gate can never be
    LOOSER than the query the chunks actually come from.
    """
    visibility = (getattr(material, "visibility", None) or "private").strip()
    if visibility == "private":
        allow_private = getattr(material, "allow_private_rag", None)
        return (True if allow_private is None else bool(allow_private)), False
    if visibility == "system_public_fulltext":
        return False, bool(getattr(material, "allow_public_rag", False))
    return False, False


def resolve_material_scope(db: DbSession, user, material_ids, *,
                           course_forms: frozenset[str] | None = None) -> dict:
    """Which of the requested materials this caller may ground THIS request in.

    Returns ``{"requested": [...], "allowed": [...], "excluded": [...]}`` — this is the ONE
    place material ids are parsed, so the response and the gate can never disagree about what
    was asked for. ``excluded`` is part of the contract: a caller learns that a material was
    refused instead of silently receiving an answer that never saw it.
    """
    wanted: list[int] = []
    for value in material_ids or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in wanted:
            wanted.append(number)
    if not wanted:
        return {"requested": [], "allowed": [], "excluded": []}

    from models import StudyMaterial
    rows = (db.query(StudyMaterial)
            .filter(StudyMaterial.id.in_(sorted(wanted)),
                    StudyMaterial.is_deleted.is_(False)).all())
    by_id = {row.id: row for row in rows}

    allowed, excluded = [], []
    for material_id in wanted:
        row = by_id.get(material_id)
        if row is None:
            excluded.append(material_id)
            continue
        owner_allowed, public_allowed = _visibility_of(row)
        owns_it = owner_allowed and (row.username == user.username)
        in_course = (course_forms is None
                     or str(row.course_id or "").strip() in course_forms
                     or str(row.subject_key or "").strip() in course_forms)
        if owns_it and in_course:
            allowed.append(material_id)
        elif public_allowed:
            allowed.append(material_id)
        else:
            excluded.append(material_id)
    return {"requested": wanted, "allowed": allowed, "excluded": excluded}


# ---------------------------------------------------------------- retrieval

def retrieve_evidence(username: str, question: str, *, allowed_material_ids: list[int],
                      course_forms: frozenset[str] | None = None,
                      exam_module_id: str | None = None,
                      top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Relevant chunks from the EXISTING retrieval. FTS5/BM25 only — no vector store.

    ``allowed_material_ids`` is the resolved, already-validated scope; when it is empty the
    search runs over the space's own material set, still scoped by the caller's username and
    by the course (or exam module) the request belongs to.
    """
    from rag import retrieve_chunks_for_materials, search_relevant_material_chunks

    if allowed_material_ids:
        return retrieve_chunks_for_materials(
            username=username, subject=None, question=question,
            material_ids=allowed_material_ids, top_k=top_k)
    if course_forms:
        return search_relevant_material_chunks(
            username=username, subject=None, question=question, top_k=top_k,
            course_ids=sorted(course_forms))
    if exam_module_id:
        return search_relevant_material_chunks(
            username=username, subject=None, question=question, top_k=top_k,
            subject_key=exam_module_id)
    return []


# ---------------------------------------------------------------- context

def build_context(user, *, service_key: str, course_id: str | None = None,
                  subject_key: str | None = None, chapter_id: str | None = None,
                  knowledge_point_id: str | None = None,
                  material_ids: list | None = None) -> tuple[LearningContext, dict]:
    """The canonical LearningContext for this request + the identity the response states."""
    namespace = normalize_service_namespace(service_key or COURSE)
    material_refs = [str(m) for m in material_ids] if material_ids else None

    if namespace == COURSE:
        from learning.spaces.course_learning.context import (
            build_course_context, course_identity_forms, normalize_course_id,
        )
        if not course_id:
            raise DeepStudyRefusal("course_required", "课程深度研习需要 course_id")
        key = normalize_course_id(course_id)
        context = build_course_context(
            user, course_id=key, chapter_id=chapter_id,
            knowledge_point_id=knowledge_point_id, material_ids=material_refs)
        identity = {"service_namespace": namespace, "course_id": key,
                    "chapter_id": context.chapter_id,
                    "knowledge_point_id": context.knowledge_point_id}
        return context, identity

    if namespace == EXAM:
        from learning.spaces.exam_prep.context import cs408_context
        context = cs408_context(user, module_key=subject_key,
                                knowledge_point_id=knowledge_point_id)
        identity = {"service_namespace": namespace,
                    "exam_subject_id": context.exam_subject_id,
                    "exam_module_id": context.exam_module_id,
                    "knowledge_point_id": context.knowledge_point_id}
        return context, identity

    raise DeepStudyRefusal("unsupported_space",
                           f"深度研习暂不支持该学习空间: {namespace}")


# ---------------------------------------------------------------- model info

def user_safe_model_info(tier: str, provider: str | None, model: str | None) -> dict:
    """Which model answered, in the product's own user-safe vocabulary.

    ``display_name`` is a strength label derived from the pool entry's quality class — no
    provider name and no raw model id. ``options`` is the SAME qualified subset
    ``GET /ai/models`` already serves for this tier + capability: never the full registry.
    """
    from ai import pool

    entry = next((e for e in pool.QUALIFIED_POOL
                  if e.provider == provider and e.model == model), None)
    quality = entry.quality_class if entry is not None else "standard"
    return {
        "display_name": f"智学强力推理模型 · {_QUALITY_LABELS.get(quality, '标准')}",
        "selection": "auto",
        "tier": tier,
        "quality_class": quality,
        "options": pool.user_visible_options(tier, CAPABILITY),
    }


# ---------------------------------------------------------------- the workflow

def run_deep_study(db: DbSession, user, *, question: str, service_key: str = COURSE,
                   course_id: str | None = None, subject_key: str | None = None,
                   chapter_id: str | None = None, knowledge_point_id: str | None = None,
                   material_ids: list | None = None,
                   max_tokens: int | None = None) -> dict:
    """One grounded strong-reasoning answer, with its citations and its usage.

    Raises the AI boundary's HTTPException unchanged when the tier does not permit the
    capability or the budget refuses it: a denied capability is an ANSWER, not a degraded
    answer. A technical failure after the request was accepted is a 502 from the same place.
    """
    text = str(question or "").strip()
    if not text:
        raise DeepStudyRefusal("question_required", "请输入问题")
    text = text[:MAX_QUESTION_CHARS]

    context, identity = build_context(
        user, service_key=service_key, course_id=course_id, subject_key=subject_key,
        chapter_id=chapter_id, knowledge_point_id=knowledge_point_id,
        material_ids=material_ids)

    course_forms = None
    if context.service_namespace == ServiceNamespace.COURSE_LEARNING:
        from learning.spaces.course_learning.context import course_identity_forms
        course_forms = course_identity_forms(context.course_id)

    from usage import service as usage_service
    from ops import feature_flags

    tier = usage_service.effective_subscription(db, user.id)
    # Policy first, then any ops grant — the SAME composition the orchestrator applies, so a
    # flag that opens the capability cannot be refused here on the way to the model call.
    permission = feature_flags.capability_permitted(db, user.id, tier, CAPABILITY)
    if not permission["allowed"]:
        # A denied capability is an ANSWER: refused here, BEFORE any retrieval work and
        # before any event, with the same policy module the orchestrator gates on.
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="AI capability unavailable")

    scope = resolve_material_scope(db, user, material_ids, course_forms=course_forms)
    chunks = retrieve_evidence(
        user.username, text, allowed_material_ids=scope["allowed"],
        course_forms=course_forms,
        exam_module_id=(context.exam_module_id
                        if context.service_namespace == ServiceNamespace.EXAM_PREP else None))

    from prompts import build_deep_study_messages
    messages = build_deep_study_messages(
        question=text, subject=(context.course_id or context.exam_module_id or ""),
        rag_chunks=chunks,
        knowledge_point_id=context.knowledge_point_id)

    run_id = uuid.uuid4().hex
    _emit_requested(user, run_id=run_id, context=context, question_len=len(text),
                    material_ids=scope["allowed"])

    if context.service_namespace == ServiceNamespace.EXAM_PREP:
        from learning.spaces.exam_prep.ai import execute_exam_ai as execute
    else:
        from learning.spaces.course_learning.ai import execute_course_ai as execute

    result = execute(db, user, CAPABILITY, messages, learning_context=context,
                     max_tokens=max_tokens or DEFAULT_MAX_TOKENS, temperature=0.3)

    _emit_completed(user, run_id=run_id, request_id=result.request_id,
                    status=result.status, context=context, chunk_count=len(chunks))

    usage = result.usage or {}
    return {
        "capability": CAPABILITY,
        "run_id": run_id,
        "request_id": result.request_id,
        "status": result.status,
        "answer": result.content or "",
        "chunks": chunks,
        "materials": {
            "requested": scope["requested"],
            "used": scope["allowed"],
            "excluded": scope["excluded"],
        },
        "context": identity,
        "model": user_safe_model_info(tier, result.provider, result.model),
        "usage": {
            "status": result.status,
            "estimated_credits": result.estimated_credits,
            "actual_credits": result.actual_credits,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"),
            "usage_source": usage.get("usage_source"),
        },
        "evidence": {
            "chunk_count": len(chunks),
            "material_count": len({c.get("material_id") for c in chunks}),
            "retrieval": "fts_bm25",
        },
    }


# ---------------------------------------------------------------- events
#
# Two canonical facts for one workflow: it was requested, and it completed. A request that
# FAILS emits nothing user-facing — the accounting fact for it is the orchestrator's own
# ``ai_called`` (AUDIT_ONLY), which is the honest home for a call that produced no answer.
# Failure-isolated on the producers' side: a records problem never fails the answer itself.

def _emit_requested(user, *, run_id: str, context: LearningContext, question_len: int,
                    material_ids: list) -> None:
    try:
        from learning.records import producers
        producers.emit_strong_reasoning_requested(
            user_id=user.id, run_id=run_id, capability=CAPABILITY,
            service_namespace=context.service_namespace.value,
            question_len=question_len, material_ids=material_ids,
            learning_context=context, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("deep_study.requested_event_failed error=%s", type(exc).__name__)


def _emit_completed(user, *, run_id: str, request_id: str, status: str,
                    context: LearningContext, chunk_count: int) -> None:
    try:
        from learning.records import producers
        producers.emit_strong_reasoning_completed(
            user_id=user.id, run_id=run_id, request_id=request_id, status=status,
            capability=CAPABILITY, service_namespace=context.service_namespace.value,
            chunk_count=chunk_count, learning_context=context, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("deep_study.completed_event_failed error=%s", type(exc).__name__)
