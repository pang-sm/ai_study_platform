"""Course Learning API — /course-learning/courses/{course_id}/...

The canonical COURSE-SCOPED reads over the Shared Learning Core. The course direction's
business routes (materials, practice, knowledge map, AI, study plan) already exist in
``main.py`` under ``/course-learning/*`` and are untouched; this module adds the one thing
they never had — a single place where a course's RECORDS, WRONG ANSWERS, STATE, MATERIALS,
PRACTICE and TODAY PLAN are addressed under one unambiguous identity.

DELEGATION, NOT REIMPLEMENTATION
--------------------------------
The materials upload, the question generation, the workbook and the submit grading keep
their single implementation in ``main.py``. The course-scoped handlers here resolve the
course, assert that it belongs to the caller, and then CALL that implementation with the
identity the path established — they never copy a parsing pipeline, an AI prompt or a
grading rule. One behaviour, one place to fix it.

WHAT THE PATH ADDS
------------------
``{course_id}`` is the course's own identity (the key ``course_learning_preferences``
stores — the same one the workspace's records/state routes use), and it is checked against
the caller BEFORE anything is read or written. That is what makes the answer to "does this
attempt belong to the course I am looking at?" decidable: an attempt whose stored course
identity is not one of this course's exact forms is a 404, never a silent submit into
whichever course the client happened to name.

WHY ``/courses/{course_id}/`` IS PART OF THE PATH
-------------------------------------------------
A course is an identity, not a query parameter. Putting it in the path means the isolation
boundary is visible in the route itself: every handler resolves the course through
``assert_owned_course`` BEFORE it reads anything, so a course the caller does not have is a
404 rather than a silently empty list, and a course-scoped page can never be assembled from
another course's rows.

WHAT THIS SURFACE WILL NOT DO
-----------------------------
It writes nothing, and it computes no prediction. The state projection reports stored
facts and counts over stored facts; there is no mastery probability, no readiness score,
and no model output, because the course space has no scientific capability. Student Twin is
NOT wired here — it is an exam-space experiment with its own gate.

Every handler is scoped to the caller's identity from the session cookie.
"""
from __future__ import annotations

from typing import Literal

from fastapi import (APIRouter, BackgroundTasks, Depends, File, HTTPException, Query,
                     Request, UploadFile)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning.records import service as records_service
from learning.records.contract import RecordPage, RecordsSummaryResponse, RecordView
from learning.spaces.course_learning import service as course_service
from learning.spaces.course_learning import wrong_answers as course_wrong
from learning.spaces.course_learning.context import (
    CourseContextError,
    course_identity_forms,
)

router = APIRouter(prefix="/course-learning/courses", tags=["course-learning"])

WrongAnswerStatus = Literal["active", "resolved"]
WrongAnswerSourceKind = Literal["ai_generated", "course_material", "other"]

# ``ai_question_attempts.mode`` for this direction — the value the course generation and
# restart routes write, and therefore the only rows a course attempt may be.
COURSE_ATTEMPT_MODE = "course_learning"


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


def _owned_course(db: Session, user, course_id: str) -> str:
    """Resolve the course for THIS caller, or 404.

    404 rather than 403 on purpose: whether another learner's course exists is not this
    caller's information.
    """
    try:
        return course_service.assert_owned_course(db, user, course_id)
    except CourseContextError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _owned_course_attempt(db: Session, user, course_id: str, attempt_id: int):
    """The caller's OWN attempt for THIS course, or 404.

    Both halves are required and both are checked against stored facts: the attempt must be
    the caller's, and the course it was recorded under must be one of the path course's
    exact identity forms. A course-A attempt addressed through a course-B path is a 404 —
    the alternative would be grading an answer into a course the learner never practised.
    """
    from models import AIQuestionAttempt

    attempt = (db.query(AIQuestionAttempt)
               .filter(AIQuestionAttempt.id == attempt_id,
                       AIQuestionAttempt.username == user.username,
                       AIQuestionAttempt.mode == COURSE_ATTEMPT_MODE).first())
    if attempt is None:
        raise HTTPException(status_code=404, detail="课程练习不存在")
    if str(attempt.subject_key or "").strip() not in course_identity_forms(course_id):
        raise HTTPException(status_code=404, detail="课程练习不属于当前课程")
    return attempt


# ---------------------------------------------------------------- response models
#
# These declare the FROZEN runtime contract so ``/openapi.json`` produces real typed
# responses instead of ``unknown``. They are a transcription of what the handlers below
# already return; the services remain the single source of the values.
#
# Deliberately NOT here: any mastery / probability / readiness / model field. There is no
# such capability in the course space, and a field for one would be the fabrication the
# SSOT forbids.

class CourseWrongAnswerResource(BaseModel):
    """A figure reference, relative to the API base URL — the same contract BC6/BC7 use."""

    model_config = ConfigDict(extra="forbid")

    url: str


class CourseWrongAnswerRecord(BaseModel):
    """ONE canonical COURSE wrong-answer record.

    The course counterpart of the exam record: the same factual status, the learner's own
    answer, the reference answer and the question content — but scoped by ``course_id``,
    with the exam module/year fields absent because a course question has neither.

    ``question_id`` is the id the course redo contract takes (an AI 题册 question). It is
    ``None`` for a source that has no such identity; it is never a renumbered stand-in.
    """

    model_config = ConfigDict(extra="forbid")

    wrong_record_id: int
    status: WrongAnswerStatus

    service_namespace: str
    course_id: str

    source_kind: WrongAnswerSourceKind
    source_label: str

    question_type: str | None = None
    stem: str = ""
    options: dict[str, str] = Field(default_factory=dict)

    user_answer: str = ""
    reference_answer: str = ""
    analysis: str | None = None

    question_id: int | None = None
    knowledge_point_id: str | None = None
    knowledge_point_name: str | None = None
    knowledge_point_path: str | None = None

    first_wrong_at: str | None = None
    last_wrong_at: str | None = None
    resolved_at: str | None = None
    repeat_wrong_count: int = 0


class CourseWrongAnswerAttemptView(BaseModel):
    """One factual attempt behind a state. Read from ``practice_attempts`` only."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: int
    submitted_at: str | None = None
    answer: str | None = None
    correct: bool | None = None
    score: float | None = None
    max_score: float | None = None
    source_attempt_type: str | None = None


class CourseWrongAnswerListResponse(BaseModel):
    items: list[CourseWrongAnswerRecord]
    total: int
    limit: int
    offset: int


class CourseWrongAnswerDetailResponse(CourseWrongAnswerRecord):
    """The record plus the factual history the record was derived from."""

    attempt_history: list[CourseWrongAnswerAttemptView] = Field(default_factory=list)
    error_analysis: str | None = None


class CourseIdentity(BaseModel):
    """Which course this state is about.

    ``declared_level`` is the learner's OWN onboarding answer (the stored
    ``course_learning_preferences.mastery_level``), deliberately renamed on the wire so no
    reader can mistake a self-report for a measured ability.
    """

    model_config = ConfigDict(extra="forbid")

    course_id: str
    display_name: str
    is_started: bool
    declared_level: str | None = None
    learning_goal: str | None = None


class CourseKnowledgeProgressBlock(BaseModel):
    """Deterministic knowledge-status counts, from the stored progress rows."""

    total_points: int
    by_status: dict[str, int]
    status_semantics: str


class CoursePracticeBlock(BaseModel):
    """Factual attempt counts. ``ungraded`` is a real third state, never a zero score."""

    attempts: int
    graded_attempts: int
    factual_correct: int
    factual_incorrect: int
    ungraded_attempts: int


class CourseWrongAnswerCounts(BaseModel):
    active: int
    resolved: int


class CourseReviewPoint(BaseModel):
    knowledge_point_id: int | None = None
    knowledge_point_code: str | None = None
    title: str | None = None
    review_due_at: str | None = None


class CourseReviewBlock(BaseModel):
    """What the STORED review dates say — no schedule is computed here."""

    scheduled: int
    due: int
    due_points: list[CourseReviewPoint]
    review_semantics: str


class CoursePlanBlock(BaseModel):
    """The course's study tasks, from the shared per-direction task table."""

    subject_key: str
    total: int
    by_status: dict[str, int]
    open: int


class CourseStateResponse(BaseModel):
    """The deterministic state of ONE course.

    There is no field for mastery probability, readiness, predicted grade or any model
    output, and none may be added: the course space has no scientific capability.
    """

    model_config = ConfigDict(extra="forbid")

    service_namespace: str
    course: CourseIdentity
    knowledge_progress: CourseKnowledgeProgressBlock
    practice: CoursePracticeBlock
    wrong_answers: CourseWrongAnswerCounts
    review: CourseReviewBlock
    plan: CoursePlanBlock
    recent_activity: list[RecordView]
    recent_activity_has_more: bool
    state_semantics: str


# ---------------------------------------------------------------- practice & material models
#
# The delegated payloads (material library, workbook, submit result) are declared with
# ``extra="allow"``: they are the LEGACY serializers' output, and this module has no
# business narrowing a shape it does not own. What is declared here is what a course-
# scoped page is entitled to rely on — the course identity every response echoes, and the
# question/attempt fields the practice loop needs in order to render a question and its
# verdict. Everything else passes through untouched rather than being dropped.


class CourseQuestionView(BaseModel):
    """ONE course workbook question, as the learner sees it.

    No ``standard_answer`` and no ``analysis``: those are the grading side of the question
    and are returned only in a submit's result. A workbook read cannot leak the answer.
    """

    model_config = ConfigDict(extra="allow")

    id: int
    subject_key: str | None = None
    subject_name: str | None = None
    knowledge_point_id: str | None = None
    knowledge_point_name: str | None = None
    knowledge_point_path: str | None = None
    question_type: str | None = None
    stem: str | None = None
    options: dict[str, str] = Field(default_factory=dict)
    difficulty: str | None = None
    generation_mode: str | None = None
    created_at: str | None = None


class CourseAttemptView(BaseModel):
    """One factual attempt on a question — status and verdict, never a prediction."""

    model_config = ConfigDict(extra="allow")

    id: int
    status: str | None = None
    correct: bool | None = None
    accuracy: float | None = None
    created_at: str | None = None
    submitted_at: str | None = None


class CourseWorkbookQuestionView(CourseQuestionView):
    """A workbook question plus its own attempt history and derived workbook status."""

    attempt_count: int = 0
    latest_attempt: CourseAttemptView | None = None
    attempts: list[CourseAttemptView] = Field(default_factory=list)
    workbook_status: Literal["unanswered", "correct", "wrong"] | None = None


class CourseWorkbookResponse(BaseModel):
    """The course's AI question book, course-scoped in SQL before the limit."""

    course_id: str
    items: list[CourseWorkbookQuestionView]
    total: int


class CoursePracticeHistoryItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    question_id: int | None = None
    course_id: str | None = None
    chapter: str = ""
    knowledge_point_name: str = ""
    status: str | None = None
    correct_count: int | None = None
    accuracy: float | None = None
    correct: bool | None = None
    stem: str = ""
    generation_mode: str | None = None
    created_at: str | None = None
    submitted_at: str | None = None


class CoursePracticeHistoryResponse(BaseModel):
    course_id: str
    items: list[CoursePracticeHistoryItem]
    total: int


class CourseAttemptStartedResponse(BaseModel):
    """A freshly opened attempt on one of this course's questions."""

    course_id: str
    success: bool = True
    attempt_id: int
    question: CourseQuestionView


class CourseSubmitResult(BaseModel):
    """The verdict for one submitted answer. The reference answer and analysis belong
    here — the learner has answered, so withholding them would help nobody."""

    model_config = ConfigDict(extra="allow")

    question_id: int
    user_answer: str
    standard_answer: str
    correct: bool
    analysis: str = ""
    generation_mode: str | None = None


class CoursePracticeSubmitResponse(BaseModel):
    course_id: str
    success: bool = True
    attempt_id: int
    result: CourseSubmitResult


class CourseQuestionGeneratedResponse(BaseModel):
    """A generated course question plus the attempt that was opened for it.

    ``generation_mode`` is part of the contract, not telemetry: ``fallback`` means the
    model was unavailable and the question came from the deterministic local bank, and a
    client must be able to say so rather than present it as generated content.
    """

    course_id: str
    success: bool = True
    generation_mode: str
    fallback_reason: str = ""
    attempt_id: int
    chapter: str = ""
    knowledge_point: dict[str, str] = Field(default_factory=dict)
    question: CourseQuestionView


class CourseMaterialView(BaseModel):
    """ONE material in the course library."""

    model_config = ConfigDict(extra="allow")

    id: int
    course_id: str = ""
    subject_key: str = ""
    subject: str | None = None
    file_type: str | None = None
    original_filename: str | None = None
    file_size: int = 0
    parse_status: str | None = None
    parse_progress: int = 0
    chunk_count: int = 0
    created_at: str | None = None


class CourseMaterialListResponse(BaseModel):
    course_id: str
    items: list[CourseMaterialView]
    total: int


class CourseMaterialUploadResponse(BaseModel):
    """The upload result, in the material pipeline's own shape plus the course identity.

    ``course_id`` is echoed because the client did NOT supply it as an authority — the
    path did — so the response is where a page learns which course the file landed in.
    """

    model_config = ConfigDict(extra="allow")

    course_id: str
    success: bool = True
    material_id: int | None = None
    filename: str | None = None
    parse_status: str | None = None
    parse_progress: int = 0
    message: str = ""
    material: dict | None = None


class CourseTodayPlanItem(BaseModel):
    """ONE thing to do today, for THIS course.

    Same field names and the same item ids as the global today-plan: ``user_order`` is
    stored by item id, so a reordering made on either surface has to mean the same thing
    on the other.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    raw_id: int
    source: Literal["course_study_plan", "learning_tasks"]
    course_id: str
    course_name: str
    title: str
    mode: str
    mode_label: str
    due_date: str = ""
    urgency_rank: int
    urgency_label: str
    user_order: int = 9999
    status: str
    task_type: str


class CourseTodayPlanResponse(BaseModel):
    """Today's work for ONE course. Every item is attributable to this course."""

    service_namespace: str
    course_id: str
    items: list[CourseTodayPlanItem]
    total: int
    empty: bool


# ---------------------------------------------------------------- request models
#
# Neither of these accepts a username or a course_id. The caller is the session, the course
# is the path, and an authority field the server would then have to reconcile is exactly
# how a request ends up describing a different course than the URL does.


class CourseQuestionGenerateRequest(BaseModel):
    """What to generate. The question identity is the knowledge point, not a course."""

    model_config = ConfigDict(extra="forbid")

    knowledge_point_code: str = ""
    knowledge_point_id: str = ""
    knowledge_point_title: str = ""
    chapter: str = ""
    difficulty: str = "基础"
    material_ids: list[int] = Field(default_factory=list)


class CourseAnswerSubmitRequest(BaseModel):
    """The learner's answer to ONE question. One choice, A/B/C/D."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=4)


# ---------------------------------------------------------------- records


@router.get("/{course_id}/records", response_model=RecordPage)
def list_course_records(course_id: str, event_type: str = "", start_at: str = "",
                        end_at: str = "",
                        limit: int = Query(default=50, ge=1, le=200), cursor: str = "",
                        db: Session = Depends(get_db), current_user=Depends(_require_user)):
    """Newest-first page of THIS course's study history.

    The namespace AND the course are both applied in SQL, before pagination: an exam or
    programming event, or another course's event, cannot appear on this page.

    Audit-only facts (AI accounting) are never part of a study timeline.
    """
    key = _owned_course(db, current_user, course_id)
    try:
        return course_service.course_records(
            db, current_user, key, limit=limit, cursor=cursor or None,
            event_type=event_type or None, start_at=start_at or None, end_at=end_at or None)
    except records_service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{course_id}/records/summary", response_model=RecordsSummaryResponse)
def get_course_records_summary(course_id: str, start_at: str = "", end_at: str = "",
                               db: Session = Depends(get_db),
                               current_user=Depends(_require_user)):
    """Deterministic study-history counts for THIS course.

    Course-scoped for the same reason the page is: a summary that counted every namespace
    would report a learner's exam and programming history under their course.
    """
    key = _owned_course(db, current_user, course_id)
    try:
        return course_service.course_records_summary(
            db, current_user, key, start_at=start_at or None, end_at=end_at or None)
    except records_service.RecordsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------- wrong answers


@router.get("/{course_id}/wrong-answers", response_model=CourseWrongAnswerListResponse)
def list_course_wrong_answers(
    course_id: str,
    status: str = Query("", description="active | resolved | empty for all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(_require_user),
):
    """The course's wrong-answer book, read from the canonical state rows.

    Scoped by course through the state's own scope discriminator, so the same question id
    answered in two courses yields two independent records and neither can surface here.
    """
    from learning.wrong_answers.models import STATUSES

    key = _owned_course(db, current_user, course_id)
    if status and status not in STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"status must be one of {list(STATUSES)}")
    page = course_service.course_wrong_page(db, current_user, key, status=status or None,
                                            limit=limit, offset=offset)
    return {"items": course_wrong.build_records(db, page["states"]),
            "total": page["total"], "limit": limit, "offset": offset}


@router.get("/{course_id}/wrong-answers/{wrong_record_id}",
            response_model=CourseWrongAnswerDetailResponse)
def get_course_wrong_answer(course_id: str, wrong_record_id: int,
                            db: Session = Depends(get_db),
                            current_user=Depends(_require_user)):
    """ONE course wrong-answer record plus the factual attempts behind it."""
    from learning.wrong_answers import service as wrong_service

    key = _owned_course(db, current_user, course_id)
    try:
        state = wrong_service.get_state(db, current_user.id, wrong_record_id,
                                        service_namespace="course_learning")
    except wrong_service.StateNotFound:
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    # The state must ALSO belong to this course — otherwise a state id from another
    # course would be readable through this course's path.
    if not course_service.course_owns_wrong_state(state, key):
        raise HTTPException(status_code=404, detail="wrong answer state not found")
    record = course_wrong.build_record(db, state)
    record["attempt_history"] = course_wrong.attempt_history(db, state)
    record["error_analysis"] = course_wrong.error_analysis(db, state)
    return record


# ---------------------------------------------------------------- state


@router.get("/{course_id}/state", response_model=CourseStateResponse)
def get_course_state(course_id: str, db: Session = Depends(get_db),
                     current_user=Depends(_require_user)):
    """The deterministic state of ONE course. READ-ONLY; writes nothing.

    Every figure is a stored fact or a count over stored facts: knowledge status, real
    practice attempts, wrong-answer states, recorded study tasks, and the recent canonical
    events. There is deliberately NO mastery probability, NO readiness score, NO predicted
    grade and NO model output — the course space has no scientific capability, and Student
    Twin is not wired here.
    """
    key = _owned_course(db, current_user, course_id)
    return course_service.course_state(db, current_user, key)


# ---------------------------------------------------------------- materials


@router.get("/{course_id}/materials", response_model=CourseMaterialListResponse)
def list_course_materials(course_id: str, db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    """This course's material library. READ-ONLY.

    Scoped by the course's own identity forms, so an exam scope or a programming course
    that shares a spelling cannot be listed as this course's material.
    """
    key = _owned_course(db, current_user, course_id)
    return course_service.course_materials(db, current_user, key)


@router.post("/{course_id}/materials", response_model=CourseMaterialUploadResponse)
async def upload_course_material(course_id: str, background_tasks: BackgroundTasks,
                                 file: UploadFile = File(...),
                                 db: Session = Depends(get_db),
                                 current_user=Depends(_require_user)):
    """Upload ONE file into THIS course's library.

    WHO and WHICH COURSE are both decided here, from the session and the path — the client
    supplies neither. The scope handed to the ingestion pipeline is the course's own
    canonical identity, so no ``subject_key`` is invented for the course and no display
    label is read back out of the request.

    The ingestion itself is the EXISTING ``/materials/upload`` pipeline, called with that
    resolved scope: the same quota resolution, the same duplicate detection, the same
    storage, the same parse dispatch and the same background task. There is no second
    material system, and a fix to the pipeline fixes both entry points at once.

    Every form field is passed explicitly rather than left to the handler's defaults:
    those defaults are FastAPI ``Form`` markers, which only become values when the request
    is injected, so relying on them from a direct call would hand the pipeline a marker
    object instead of a value.

    Both gates are therefore kept, deliberately: this course must belong to the caller
    (asserted here, from the stored course), and it must still be one the learner has
    selected in course onboarding (asserted by the pipeline). A course that was deselected
    accepts no new files, even if a preference row for it is still on the account.
    """
    key = _owned_course(db, current_user, course_id)
    from main import upload_material  # lazy import to avoid a circular import

    payload = await upload_material(
        background_tasks=background_tasks,
        file=file,
        username=current_user.username,   # server-derived, never client-supplied
        course_id=key,
        subject_key=key,
        subject=key,
        track="course_learning",
        question="",
        conversation_id=None,
        save_to_materials=False,
        source_type=None,                 # a course upload is a plain user upload
        authorization=None,
        db=db,
        current_user=current_user,
    )
    return {**payload, "course_id": key}


# ---------------------------------------------------------------- practice


@router.get("/{course_id}/practice/workbook", response_model=CourseWorkbookResponse)
def get_course_workbook(course_id: str,
                        chapter: str = "",
                        knowledge_point_code: str = "",
                        status: str = Query("all", description="all | unanswered | correct | wrong"),
                        db: Session = Depends(get_db),
                        current_user=Depends(_require_user)):
    """The course's AI question book, with each question's own attempt history.

    Workbook questions carry no reference answer: the verdict belongs to a submit.
    """
    key = _owned_course(db, current_user, course_id)
    from main import get_course_learning_practice_workbook

    payload = get_course_learning_practice_workbook(
        username=current_user.username, course_id=key, chapter=chapter,
        knowledge_point_code=knowledge_point_code, status=status,
        db=db, current_user=current_user)
    return {**payload, "course_id": key}


@router.get("/{course_id}/practice/history", response_model=CoursePracticeHistoryResponse)
def get_course_practice_history(course_id: str, db: Session = Depends(get_db),
                                current_user=Depends(_require_user)):
    """This course's practice attempts, newest first."""
    key = _owned_course(db, current_user, course_id)
    from main import get_course_learning_practice_history

    payload = get_course_learning_practice_history(
        username=current_user.username, course_id=key, db=db, current_user=current_user)
    return {**payload, "course_id": key}


@router.post("/{course_id}/practice/questions/{question_id}/attempts",
             response_model=CourseAttemptStartedResponse)
def start_course_question_attempt(question_id: int, course_id: str,
                                  db: Session = Depends(get_db),
                                  current_user=Depends(_require_user)):
    """Open a NEW attempt on one of THIS course's questions ("下一题"/重做).

    A question from another course is not reachable through this path: it is resolved
    through the course-scoped workbook query first, so it is a 404 rather than an attempt
    filed under a course whose page the learner was not on. (The delegate it then calls
    is the existing route, which resolves the question by id alone — hence the check
    belongs here, where the course is known.)
    """
    key = _owned_course(db, current_user, course_id)
    from main import _course_workbook_question_query, restart_course_learning_workbook_question
    from models import AIGeneratedQuestion

    owned = _course_workbook_question_query(db, current_user.username, key).filter(
        AIGeneratedQuestion.id == question_id).first()
    if owned is None:
        raise HTTPException(status_code=404, detail="AI 题册题目不存在")

    payload = restart_course_learning_workbook_question(
        question_id, {"username": current_user.username}, db=db, current_user=current_user)
    return {**payload, "course_id": key}


@router.post("/{course_id}/practice/generate", response_model=CourseQuestionGeneratedResponse)
def generate_course_question(course_id: str, payload: CourseQuestionGenerateRequest,
                             db: Session = Depends(get_db),
                             current_user=Depends(_require_user)):
    """Generate ONE new question for this course and open an attempt on it.

    Delegates to the existing course generation route with the path's course. That route
    keeps its own capability/budget decision: an entitlement denial is an answer and is
    re-raised as such, while a model outage degrades to the deterministic local question
    and says so in ``generation_mode``.
    """
    key = _owned_course(db, current_user, course_id)
    from main import generate_course_learning_practice

    body = {
        "username": current_user.username,
        "course_id": key,
        "knowledge_point_code": payload.knowledge_point_code or payload.knowledge_point_id,
        "knowledge_point_title": payload.knowledge_point_title,
        "chapter": payload.chapter,
        "difficulty": payload.difficulty,
        "material_ids": payload.material_ids,
    }
    result = generate_course_learning_practice(body, db=db, current_user=current_user)
    return {**result, "course_id": key}


@router.post("/{course_id}/practice/{attempt_id}/submit",
             response_model=CoursePracticeSubmitResponse)
def submit_course_practice(attempt_id: int, course_id: str,
                           payload: CourseAnswerSubmitRequest,
                           db: Session = Depends(get_db),
                           current_user=Depends(_require_user)):
    """Submit ONE answer to THIS course's attempt.

    The attempt is resolved and its course ownership is checked BEFORE grading, so a
    course-A attempt cannot be submitted through a course-B path. Grading, the knowledge
    transition, the canonical learning record, the data-plane event and the practice
    mirror are the existing implementation's — this handler adds the identity check and
    nothing else.
    """
    key = _owned_course(db, current_user, course_id)
    _owned_course_attempt(db, current_user, key, attempt_id)
    from main import submit_course_learning_practice

    result = submit_course_learning_practice(
        attempt_id, {"username": current_user.username, "answer": payload.answer},
        db=db, current_user=current_user)
    return {**result, "course_id": key}


# ---------------------------------------------------------------- today plan


@router.get("/{course_id}/today-plan", response_model=CourseTodayPlanResponse)
def get_course_today_plan(course_id: str, db: Session = Depends(get_db),
                          current_user=Depends(_require_user)):
    """Today's tasks for THIS course. READ-ONLY.

    Every item is attributable to the course: plan tasks through the shared
    ``course_learning:<course>`` key, generic tasks only when their stored ``course_id``
    is one of this course's exact identity forms. A task that cannot be attributed is left
    out rather than guessed into the course.
    """
    key = _owned_course(db, current_user, course_id)
    return course_service.course_today_plan(db, current_user, key)
