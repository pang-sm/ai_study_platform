"""Deep Study API — POST /ai/deep-study.

ONE endpoint for the strong-reasoning workflow in BOTH spaces that have it (course_learning
and exam_11408). The capability is chosen SERVER-SIDE (``tutor.strong_reasoning``); the client
names a question and a scope and never a model, a provider or a capability.

The response carries what the learner is entitled to see about the run: the answer, the
citations it was built from, the materials that were used or refused, the context identity,
a user-safe model label, and the usage summary. It never carries the provider registry.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import deep_study
from ops import feature_flags

router = APIRouter(tags=["ai-workflows"])

MAX_MATERIAL_IDS = 20


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


# ---------------------------------------------------------------- request


class DeepStudyRequest(BaseModel):
    """What to study and where. The CALLER is the session, never a body field."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=deep_study.MAX_QUESTION_CHARS)
    service_key: Literal["course_learning", "exam_11408"] = "course_learning"
    course_id: str = ""
    subject_key: str = ""
    chapter_id: str = ""
    knowledge_point_id: str = ""
    material_ids: list[int] = Field(default_factory=list, max_length=MAX_MATERIAL_IDS)
    max_tokens: int | None = Field(default=None, ge=256, le=4096)


# ---------------------------------------------------------------- response
#
# Declared so /openapi.json produces real typed responses (the frontend generates its API
# types from this). No provider registry, no model ids, no internal cost.


class DeepStudyCitation(BaseModel):
    model_config = ConfigDict(extra="allow")

    material_id: int
    filename: str = ""
    subject: str = ""
    file_type: str = ""
    snippet: str = ""
    score: float | None = None


class DeepStudyMaterialRef(BaseModel):
    material_id: int
    filename: str = ""


class DeepStudyMaterials(BaseModel):
    """``excluded`` is part of the contract: a refused material is stated, not hidden."""

    requested: list[int] = Field(default_factory=list)
    used: list[int] = Field(default_factory=list)
    excluded: list[int] = Field(default_factory=list)


class DeepStudyContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    service_namespace: str
    course_id: str | None = None
    chapter_id: str | None = None
    knowledge_point_id: str | None = None
    exam_subject_id: str | None = None
    exam_module_id: str | None = None


class DeepStudyModelOption(BaseModel):
    """ONE qualified model option, exactly as ``GET /ai/models`` already serves it.

    Declared so the frontend gets real fields instead of an untyped object. It is the
    QUALIFIED subset for the caller's tier + capability — never the provider registry.
    """

    provider: str
    model: str
    eligible_tiers: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    cost_profile: str | None = None
    quality_class: str | None = None
    latency_class: str | None = None
    available: bool = True
    high_cost: bool = False
    thinking: bool = False
    deployment_eligibility: str = "PRODUCTION"
    pricing_verified: bool = False


class DeepStudyModelInfo(BaseModel):
    """User-safe model information: a strength label + the qualified options this tier has."""

    model_config = ConfigDict(extra="allow")

    display_name: str
    selection: str = "auto"
    tier: str
    quality_class: str | None = None
    options: list[DeepStudyModelOption] = Field(default_factory=list)


class DeepStudyUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    estimated_credits: int | None = None
    actual_credits: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    usage_source: str | None = None


class DeepStudyEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_count: int = 0
    material_count: int = 0
    retrieval: str = "fts_bm25"


class DeepStudyResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    capability: str
    request_id: str
    status: str
    answer: str

    citations: list[DeepStudyCitation] = Field(default_factory=list)
    material_refs: list[DeepStudyMaterialRef] = Field(default_factory=list)
    materials: DeepStudyMaterials

    context: DeepStudyContext
    model: DeepStudyModelInfo
    usage: DeepStudyUsage
    evidence: DeepStudyEvidence


# ---------------------------------------------------------------- endpoint


@router.post("/ai/deep-study", response_model=DeepStudyResponse)
def run_deep_study(payload: DeepStudyRequest, db: Session = Depends(get_db),
                   current_user=Depends(_require_user)):
    """One grounded strong-reasoning answer, in the caller's own learning context.

    A tier that does not permit ``tutor.strong_reasoning`` gets 403 and a budget refusal gets
    429 — raised by the unified AI boundary, not decided here. A material the caller may not
    ground an answer in is listed in ``materials.excluded``; it is never silently read.
    """
    from main import serialize_reference_item  # lazy: the shared citation shape

    feature_flags.ensure_feature_allowed(db, current_user, "deep_study")
    try:
        result = deep_study.run_deep_study(
            db, current_user, question=payload.question,
            service_key=payload.service_key,
            course_id=payload.course_id or None,
            subject_key=payload.subject_key or None,
            chapter_id=payload.chapter_id or None,
            knowledge_point_id=payload.knowledge_point_id or None,
            material_ids=payload.material_ids or None,
            max_tokens=payload.max_tokens)
    except deep_study.DeepStudyRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})

    chunks = result.pop("chunks", [])
    result["citations"] = [serialize_reference_item(chunk) for chunk in chunks]
    result["material_refs"] = _material_refs(chunks)
    return result


def _material_refs(chunks: list[dict]) -> list[dict]:
    """One reference per MATERIAL (a material with several cited chunks appears once)."""
    seen: dict[int, dict] = {}
    for chunk in chunks:
        material_id = chunk.get("material_id")
        if material_id is None or material_id in seen:
            continue
        seen[material_id] = {"material_id": material_id,
                             "filename": chunk.get("source_filename") or ""}
    return list(seen.values())
