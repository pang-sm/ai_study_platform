"""Exam Prep API (STEP 7H4) — /exam/prep/...

The canonical surface for the Exam Prep FRAMEWORK: the catalog (versioned config) and the
learner's profile (which direction and which subjects they are preparing for).

Two rules this module exists to enforce:

  1. A learner may SELECT a ``framework_only`` subject. A goal is a goal even when the
     content for it does not exist yet.
  2. Reaching CONTENT is a different question, and it is answered by the availability gate:
     a framework-only subject returns an explicit ``EXAM_CONTENT_NOT_AVAILABLE`` rather
     than ``200 + []``, so no client can mistake "not launched" for "no data".

Legacy ``/exam/11408/*`` routes are untouched and keep working.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

import models
from core.learning_context import ServiceNamespace
from database import get_db
from learning.records import service as records_service
from learning.records.contract import RecordPage
from learning.spaces.exam_prep import catalog
from science import capabilities as science_capabilities
from science import evidence_reliability, kt_dataset, learner_state, student_twin
from science.contract import (
    EvidenceReliabilityPreviewResponse,
    KtDatasetAuditResponse,
    LearnerStatePreviewResponse,
    ScientificCapabilitiesResponse,
    StudentTwinPreviewResponse,
)

router = APIRouter(prefix="/exam/prep", tags=["exam-prep"])

EXAM_TYPE = catalog.EXAM_TYPE_POSTGRADUATE


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


# ---------------------------------------------------------------- availability gate

def require_subject_content(subject_id: str | None):
    """Fail closed when a subject has no real content.

    404 is deliberately NOT used: the subject exists and is selectable, it simply has no
    content yet, and that is a different answer.
    """
    subject = catalog.get_subject(subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"unknown exam subject {subject_id!r}")
    if not subject.is_active:
        raise HTTPException(status_code=409, detail={
            "code": catalog.NOT_AVAILABLE_REASON,
            "subject_id": subject.id,
            "availability": subject.availability,
            "message": "该科目已开放选择，但内容尚未上线。",
        })
    return subject


def content_status_for(subject_id: str | None) -> str:
    subject = catalog.get_subject(subject_id)
    return subject.availability if subject else "unknown"


# ---------------------------------------------------------------- response models
#
# These declare the FROZEN runtime contract so `/openapi.json` produces real typed
# responses instead of `unknown`. They are a transcription of what the handlers below
# already return — field names, order, nullability and nesting must stay byte-identical
# to the payloads, which is why the declared order mirrors the dict insertion order.
#
# Deliberately NOT here: any error model. 400/401/404/409 are unchanged and are not
# re-declared, so the error contract is untouched.

# The two states a catalog entry can be in. Derived from CONFIG (catalog.ACTIVE /
# catalog.FRAMEWORK_ONLY), never from counting rows.
Availability = Literal["active", "framework_only"]


class ExamModuleSummary(BaseModel):
    """One teaching unit of a subject — ``catalog.ExamModuleDefinition``."""

    id: str
    display_name: str


class ExamSubjectSummary(BaseModel):
    """``catalog.ExamSubjectDefinition.to_dict()`` — a national standardized exam paper."""

    id: str
    display_name: str
    category: str
    availability: Availability
    has_questions: bool
    has_past_papers: bool
    has_knowledge_tree: bool
    description: str
    suggested_tracks: list[str]
    modules: list[ExamModuleSummary]


class ExamTrackSummary(BaseModel):
    """``catalog.ExamTrackDefinition.to_dict()`` — a preparation direction / bundle."""

    id: str
    display_name: str
    exam_type: str
    availability: Availability
    has_content: bool
    description: str
    subject_options: list[str]
    suggested_subjects: list[str]


class UnknownExamSubject(BaseModel):
    """A stored subject id that is no longer in the catalog.

    ``_profile_payload`` degrades to this 2-key shape rather than fabricating catalog
    metadata for an id it cannot resolve. ``extra="forbid"`` keeps the union in
    ``ExamPrepProfileResponse`` unambiguous: a full catalog payload can never be
    deserialized as this model, so it always serializes back at full width.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    availability: str


class ExamPrepProfileResponse(BaseModel):
    """``_profile_payload`` — the learner's Exam Prep profile.

    ``subjects`` carries each selected subject's own availability and capability flags, so
    a client never has to guess which of them can actually be entered. An unconfigured
    profile is NOT an error: every field is explicitly null/empty and ``configured`` says
    which case it is.
    """

    configured: bool
    exam_type: str
    selected_track: str | None
    selected_subjects: list[str]
    target_exam_year: int | None
    subjects: list[ExamSubjectSummary | UnknownExamSubject]


class ExamPrepCatalogResponse(BaseModel):
    """The whole Exam Prep taxonomy: tracks, subjects and which side of the gate each is on."""

    catalog_version: str
    exam_type: str
    tracks: list[ExamTrackSummary]
    subjects: list[ExamSubjectSummary]
    active_subject_ids: list[str]
    framework_only_subject_ids: list[str]


class ExamCatalogTracksResponse(BaseModel):
    catalog_version: str
    tracks: list[ExamTrackSummary]


class ExamCatalogSubjectsResponse(BaseModel):
    catalog_version: str
    subjects: list[ExamSubjectSummary]


class ExamContentStatusResponse(BaseModel):
    """The 200 body of the availability gate — an ACTIVE subject with its module list.

    A framework-only subject never reaches this model: it answers 409 with
    ``EXAM_CONTENT_NOT_AVAILABLE`` instead. ``display_name`` is intentionally absent
    because the handler does not return it.
    """

    subject_id: str
    availability: Availability
    has_questions: bool
    has_past_papers: bool
    has_knowledge_tree: bool
    modules: list[ExamModuleSummary]


# ---------------------------------------------------------------- profile

class ExamPrepProfileUpsert(BaseModel):
    selected_track: str | None = None
    selected_subjects: list[str] = Field(default_factory=list)
    target_exam_year: int | None = None


def _profile_payload(profile: "models.ExamPrepProfile | None") -> dict:
    if profile is None:
        # No profile is not an error, and it is not a fabricated one either: every field is
        # explicitly null/empty and ``configured`` says which it is.
        return {
            "configured": False,
            "exam_type": EXAM_TYPE,
            "selected_track": None,
            "selected_subjects": [],
            "target_exam_year": None,
            "subjects": [],
        }
    selected = _load_subjects(profile.selected_subjects_json)
    return {
        "configured": True,
        "exam_type": profile.exam_type,
        "selected_track": profile.selected_track,
        "selected_subjects": selected,
        "target_exam_year": profile.target_exam_year,
        # each subject carries its own availability + capability flags so the client never
        # has to guess which of them can actually be entered
        "subjects": [(catalog.get_subject(s).to_dict() if catalog.get_subject(s) else
                      {"id": s, "availability": "unknown"}) for s in selected],
    }


def _load_subjects(raw) -> list[str]:
    import json
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(item) for item in data if isinstance(item, str)] if isinstance(data, list) else []


@router.get("/profile", response_model=ExamPrepProfileResponse)
def get_exam_prep_profile(db: Session = Depends(get_db), current_user=Depends(_require_user)):
    profile = (db.query(models.ExamPrepProfile)
               .filter(models.ExamPrepProfile.user_id == current_user.id).first())
    return _profile_payload(profile)


@router.put("/profile", response_model=ExamPrepProfileResponse)
def put_exam_prep_profile(req: ExamPrepProfileUpsert, db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    track_id = (req.selected_track or "").strip() or None
    if track_id is not None and catalog.get_track(track_id) is None:
        raise HTTPException(status_code=400, detail=f"unknown exam track {track_id!r}")

    subjects: list[str] = []
    for raw in req.selected_subjects or []:
        subject_id = str(raw or "").strip()
        if not subject_id:
            continue
        if catalog.get_subject(subject_id) is None:
            raise HTTPException(status_code=400, detail=f"unknown exam subject {subject_id!r}")
        if subject_id not in subjects:
            subjects.append(subject_id)

    # A framework-only subject is SELECTABLE on purpose: the profile records the learner's
    # goal, and the availability gate is what stops content access later.
    year = req.target_exam_year
    if year is not None and not (2000 <= int(year) <= 2100):
        raise HTTPException(status_code=400, detail="target_exam_year is out of range")

    profile = (db.query(models.ExamPrepProfile)
               .filter(models.ExamPrepProfile.user_id == current_user.id).first())
    if profile is None:
        profile = models.ExamPrepProfile(user_id=current_user.id, exam_type=EXAM_TYPE)
        db.add(profile)

    import json
    profile.exam_type = EXAM_TYPE
    profile.selected_track = track_id
    profile.selected_subjects_json = json.dumps(subjects, ensure_ascii=False)
    profile.target_exam_year = int(year) if year is not None else None
    db.commit()
    db.refresh(profile)
    return _profile_payload(profile)


# ---------------------------------------------------------------- catalog

@router.get("/catalog", response_model=ExamPrepCatalogResponse)
def get_exam_prep_catalog():
    tracks = [t.to_dict() for t in catalog.all_tracks()]
    subjects = [s.to_dict() for s in catalog.all_subjects()]
    return {
        "catalog_version": catalog.CATALOG_VERSION,
        "exam_type": EXAM_TYPE,
        "tracks": tracks,
        "subjects": subjects,
        "active_subject_ids": [s.id for s in catalog.active_subjects()],
        "framework_only_subject_ids": [s.id for s in catalog.framework_only_subjects()],
    }


@router.get("/catalog/tracks", response_model=ExamCatalogTracksResponse)
def get_exam_prep_tracks():
    return {"catalog_version": catalog.CATALOG_VERSION,
            "tracks": [t.to_dict() for t in catalog.all_tracks()]}


@router.get("/catalog/subjects", response_model=ExamCatalogSubjectsResponse)
def get_exam_prep_subjects():
    return {"catalog_version": catalog.CATALOG_VERSION,
            "subjects": [s.to_dict() for s in catalog.all_subjects()]}


# ---------------------------------------------------------------- content availability

@router.get("/subjects/{subject_id}/content-status",
            response_model=ExamContentStatusResponse)
def get_subject_content_status(subject_id: str):
    """The ONE honest answer to "can I study this subject yet?".

    An ACTIVE subject answers with its module list (metadata only — the questions and the
    knowledge tree live behind the subject's own routes). A framework-only subject answers
    with an explicit ``EXAM_CONTENT_NOT_AVAILABLE`` and 409, never an empty success.
    """
    subject = catalog.get_subject(subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"unknown exam subject {subject_id!r}")
    if not subject.is_active:
        raise HTTPException(status_code=409, detail={
            "code": catalog.NOT_AVAILABLE_REASON,
            "subject_id": subject.id,
            "availability": subject.availability,
            "message": "该科目已开放选择，但内容尚未上线。",
        })
    return {
        "subject_id": subject.id,
        "availability": subject.availability,
        "has_questions": subject.to_dict()["has_questions"],
        "has_past_papers": subject.to_dict()["has_past_papers"],
        "has_knowledge_tree": subject.to_dict()["has_knowledge_tree"],
        "modules": [{"id": m.id, "display_name": m.display_name} for m in subject.modules],
    }


# ---------------------------------------------------------------- study timeline
#
# The canonical EXAM-SCOPED study timeline. It is a different surface from the general
# ``/learning-records`` prefix (which is also used by the legacy course notebook) so the
# exam records page never depends on an ambiguous route namespace, and it is
# module-filterable in SQL — an unknown module is a 400, never a silently unfiltered page.

@router.get("/records", response_model=RecordPage)
def list_exam_study_records(
        exam_module_id: str = "",
        event_type: str = "",
        start_at: str = "",
        end_at: str = "",
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str = "",
        db: Session = Depends(get_db),
        current_user=Depends(_require_user)):
    """Newest-first page of the caller's exam-space study history.

    Audit-only facts (AI accounting) are never part of this timeline. Wrong answers are
    honestly derivable by the client from ``question_answered`` records with
    ``summary.correct == false`` — there is no synthetic wrong-answer event.
    """
    module = (exam_module_id or "").strip()
    if module and not catalog.is_known_module(module):
        raise HTTPException(status_code=400, detail=f"unknown exam module {module!r}")
    try:
        return records_service.list_records(
            db, current_user.id,
            start_at=start_at or None, end_at=end_at or None,
            service_namespace=ServiceNamespace.EXAM_PREP.value,
            event_type=event_type or None,
            exam_module_id=module or None,
            limit=limit, cursor=cursor or None)
    except records_service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------- scientific preview

@router.get("/scientific/student-twin", response_model=StudentTwinPreviewResponse)
def get_student_twin_preview(exam_module_id: str = "",
                             db: Session = Depends(get_db),
                             current_user=Depends(_require_user)):
    """The caller's CS408 learning-state EXPERIMENT view (PART C).

    Student Twin is a deterministic rule-based state engine written in Python — NOT a
    neural network, NOT an AI prediction model, and its output is NOT a mastery score. It
    replays the caller's REAL practice facts and returns the resulting state.

    PREVIEW ONLY: this writes nothing. Knowledge status, mastery, wrong-answer state, plan
    status and grades are untouched, and the result controls no product decision. If the
    Scientific Runtime is unavailable the response is an explicit bounded ``UNAVAILABLE``
    state — the rest of the platform is unaffected.
    """
    module = (exam_module_id or "").strip()
    if module and not catalog.is_known_module(module):
        raise HTTPException(status_code=400, detail=f"unknown exam module {module!r}")
    return student_twin.preview(db, current_user.id,
                                service_namespace=ServiceNamespace.EXAM_PREP.value,
                                exam_module_id=module or None)


@router.get("/scientific/learner-state", response_model=LearnerStatePreviewResponse)
def get_learner_state_gate(exam_module_id: str = "",
                           probe_runtime: bool = False,
                           db: Session = Depends(get_db),
                           current_user=Depends(_require_user)):
    """The caller's learner_state capability report. PRODUCES NO NUMBER, by design.

    learner_state is a real trained knowledge-tracing model that outputs the probability
    the learner's NEXT response is correct. The product cannot honestly feed it: the model
    reads an index in its own ontology (ASSISTments 123 skills / Junyi 835 concepts) and
    the product has CS408 knowledge points with no mapping between them, so any index
    would be invented. This endpoint states that gate and the real evidence that exists
    rather than fabricating the missing input.

    READ-ONLY: writes nothing, changes no knowledge status, wrong state, plan or grade,
    and controls no product decision.
    """
    module = (exam_module_id or "").strip()
    if module and not catalog.is_known_module(module):
        raise HTTPException(status_code=400, detail=f"unknown exam module {module!r}")
    return learner_state.preview(db, current_user.id,
                                 service_namespace=ServiceNamespace.EXAM_PREP.value,
                                 exam_module_id=module or None,
                                 probe_runtime=probe_runtime)


@router.get("/scientific/evidence-reliability",
            response_model=EvidenceReliabilityPreviewResponse)
def get_evidence_reliability_gate(exam_module_id: str = "",
                                  probe_runtime: bool = False,
                                  db: Session = Depends(get_db),
                                  current_user=Depends(_require_user)):
    """The caller's evidence_reliability capability report. PRODUCES NO WEIGHT, by design.

    evidence_reliability scores how much ONE observation should count in a
    reliability-weighted learner-state update. Its output is a weight ``w in (0,1)`` — NOT
    the probability the response is correct, NOT a confidence, NOT a judgement about the
    learner.

    The five checkpoints are real and executable, but the product cannot honestly build
    their input: it persists no hint signal, does not guarantee a response time or an
    attempt count, and has no mapping from CS408 knowledge points to the scientific skill
    ontology that ``log_opp`` and ``b_s`` are indexed by. The IRT ``b_map`` and the
    training-set standardization statistics are not bundled either, and the dynamic feature
    ``p_t`` is the component's own running prediction. This endpoint states that gate and
    the real evidence that exists rather than inventing any of it.

    READ-ONLY: writes nothing, changes no knowledge status, wrong state, plan or grade,
    and controls no product decision.
    """
    module = (exam_module_id or "").strip()
    if module and not catalog.is_known_module(module):
        raise HTTPException(status_code=400, detail=f"unknown exam module {module!r}")
    return evidence_reliability.preview(db, current_user.id,
                                        service_namespace=ServiceNamespace.EXAM_PREP.value,
                                        exam_module_id=module or None,
                                        probe_runtime=probe_runtime)


@router.get("/scientific/kt-dataset-audit",
            response_model=KtDatasetAuditResponse)
def get_kt_dataset_audit(db: Session = Depends(get_db),
                         current_user=Depends(_require_user)):
    """Whether a CS408-NATIVE knowledge-tracing model could be trained from real facts yet.

    This is the dataset contract's health, not the dataset. It reports how many ordered
    interactions the product actually holds under a STABLE NATIVE CONCEPT identity, at
    which concept level, and what was excluded and why — because "the export is thin" and
    "the export silently dropped half the facts" look identical from a row count.

    It trains nothing and predicts nothing: no model exists behind this endpoint, and none
    is claimed. The full export is an offline path (``science.kt_dataset.build``) that
    carries rows; this surface deliberately does not, so no learner data leaves through it.

    READ-ONLY: writes nothing, changes no learner fact, grade, plan or knowledge status.
    """
    return kt_dataset.audit(db, service_namespace=ServiceNamespace.EXAM_PREP.value)


@router.get("/scientific/capabilities",
            response_model=ScientificCapabilitiesResponse)
def get_scientific_capabilities(current_user=Depends(_require_user)):
    """Which scientific capabilities this product can actually use, and their authority.

    This reports PRODUCT-FACING readiness, not the existence of a runtime endpoint: a
    component is ``available`` only when the product can produce its output from real
    facts it holds. Every entry states its mode, whether the learner may be shown it,
    whether it may control a product decision or write a learner fact, and the stable
    reason codes for any blocker.

    It calls no runtime and exposes no filesystem path or internal stack trace. Read-only
    and deterministic for a given build.
    """
    return science_capabilities.summary()
