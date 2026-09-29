"""CS408 past-paper product contract (BC6) — ONE public shape over two real sources.

Two real sources exist and both are preserved:

  * **bank**     — ``exam_question_bank`` rows with ``source_type='past_paper' AND is_active``.
    Curated and reconciled; covers ``computer_organization`` / ``operating_system`` /
    ``computer_network``.
  * **document** — the docx parse plus ``cache/exam_papers/11408/{subject}/{year}.ocr.json``.
    The only source that carries ``data_structure``.

Which source answers is decided per paper, by the same rule the runtime already used: the bank
answers when it has active rows for that (subject, year); otherwise the document source does. That
is reconciliation, not an arbitrary pick — the bank rows were derived from the document material.

**Public identity is source-independent**: ``(subject_key, year, question_number)`` for a question
and ``(subject_key, year)`` for a paper. Internal ids (``ExamQuestionBank.id``, the document's
``"{subject}_{year}_{number}"``) never reach the frontend.

Everything answer-bearing is projected HERE, server-side: a pre-submit question carries no
``standard_answer``, no ``analysis`` and no grading state, from either source.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

import exam_paper_scores

BASE_DIR = Path(__file__).resolve().parent

# Static paper images. NOTE: ``main.py`` deliberately leaves the ``/static/exam_papers`` mount
# commented out because the deployment serves the SPA from that prefix; images are therefore
# delivered through the application route below, which is the ONE URL format the frontend sees.
EXAM_STATIC_DIR = BASE_DIR / "static" / "exam_papers" / "11408"
EXAM_RESOURCES_DIR = BASE_DIR / "exam_resources" / "11408"

SUBJECT_NAMES = {
    "data_structure": "数据结构",
    "computer_organization": "计算机组成原理",
    "operating_system": "操作系统",
    "computer_network": "计算机网络",
}

# The public resource route. Callers get this path relative to the API base URL, so the same string
# works locally (api base = http://127.0.0.1:8000) and behind nginx (api base = /api).
IMAGE_ROUTE = "/exam/11408/past-paper-images/{subject_key}/{year}/{filename}"

PastPaperQuestionType = Literal["choice", "big"]
PastPaperJudge = Literal["self_review", "ai_graded"]
PastPaperSource = Literal["bank", "document"]

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")


class PastPaperSummary(BaseModel):
    """One available paper. Availability is factual, never inferred from a hardcoded year list."""

    model_config = ConfigDict(extra="forbid")

    year: int
    question_count: int
    choice_count: int
    big_count: int
    source: PastPaperSource


class PastPaperIndexResponse(BaseModel):
    subject_key: str
    subject_name: str
    papers: list[PastPaperSummary]


class PastPaperResource(BaseModel):
    """A figure reference. ``url`` is relative to the API base URL — never a filesystem path."""

    model_config = ConfigDict(extra="forbid")

    url: str


class PastPaperQuestion(BaseModel):
    """A past-paper question BEFORE submission.

    Carries no ``standard_answer``, no ``analysis`` and no grading state: the projection happens in
    :func:`public_question`, so neither source can leak through this model.
    """

    model_config = ConfigDict(extra="forbid")

    subject_key: str
    year: int
    question_number: int
    question_type: PastPaperQuestionType
    stem: str
    options: dict[str, str]
    resources: list[PastPaperResource]
    full_score: int | None = None
    # A question whose source references a figure that cannot be resolved is reported honestly
    # rather than silently rendered without it, so the product can say so instead of guessing.
    # Empty for every question today; the field exists so a future broken reference surfaces in the
    # contract instead of as a 404 behind an <img>.
    missing_resources: list[str] = Field(default_factory=list)


class PastPaperQuestionsResponse(BaseModel):
    subject_key: str
    subject_name: str
    year: int
    source: PastPaperSource
    questions: list[PastPaperQuestion]


class PastPaperAttemptSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    attempt_no: int
    subject_key: str
    year: int
    status: Literal["in_progress", "submitted"]
    total_questions: int
    started_at: str | None
    submitted_at: str | None


class PastPaperQuestionResult(BaseModel):
    """The authoritative per-question outcome, keyed by public identity.

    One canonical model for both branches:

    * ``choice``     — ``correct`` is a bool, ``judge`` is null;
    * ``self_review``— ``correct`` is null, ``judge`` is ``self_review``, ``score`` is null because
      no authoritative grading was applied;
    * ``ai_graded``  — ``correct`` is null, ``judge`` is ``ai_graded``, ``score`` is the model's
      real authoritative score.
    """

    subject_key: str
    year: int
    question_number: int
    question_type: PastPaperQuestionType
    user_answer: str
    correct: bool | None
    judge: PastPaperJudge | None
    standard_answer: str
    analysis: str | None
    score: int | None
    full_score: int | None
    feedback: str | None


class PastPaperAttemptDetailResponse(BaseModel):
    """Attempt detail. ``results`` is present only once the attempt is submitted, and is a replay
    of what submit persisted — this endpoint never grades."""

    attempt: PastPaperAttemptSummary
    questions: list[PastPaperQuestion]
    saved_answers: dict[str, str]
    results: list[PastPaperQuestionResult] = Field(default_factory=list)


class PastPaperAttemptCreateRequest(BaseModel):
    year: int
    username: str | None = None


class PastPaperAttemptCreateResponse(BaseModel):
    attempt_id: int
    attempt_no: int
    subject_key: str
    year: int
    status: Literal["in_progress"]
    total_questions: int


class PastPaperWriteRequest(BaseModel):
    """Shared body of `answers` (save) and `submit`.

    Keyed by ``question_number`` as a string — the public identity — so the frontend never handles a
    source-specific id.
    """

    answers: dict[str, str] = Field(default_factory=dict)
    username: str | None = None


class PastPaperAnswerSaveResponse(BaseModel):
    success: bool
    attempt_id: int


class PastPaperAnswerGrade(BaseModel):
    """Whether an authoritative AI grade was actually applied, and why not when it was not.

    Same runtime semantics submit already reported; ``applied=False`` now never yields a learner
    score — the affected question becomes ``self_review`` instead.
    """

    model_config = ConfigDict(extra="forbid")

    applied: bool
    reason: str | None = None


class PastPaperSubmitResponse(BaseModel):
    attempt_id: int
    attempt_no: int
    subject_key: str
    year: int
    total_questions: int
    choice_total: int
    choice_correct: int
    self_review_count: int
    ai_graded_count: int
    total_score: int
    max_score: int
    answer_grade: PastPaperAnswerGrade
    results: list[PastPaperQuestionResult]


# ---------------------------------------------------------------- normalization


def subject_name(subject_key: str) -> str:
    return SUBJECT_NAMES.get(subject_key, subject_key)


def canonical_image_url(subject_key: str, year: int, filename: str) -> str | None:
    """The ONE public resource path for a figure, relative to the API base URL."""
    if not filename or not _SAFE_FILENAME.match(filename):
        return None
    return IMAGE_ROUTE.format(subject_key=subject_key, year=int(year), filename=filename)


class ResolvedQuestion:
    """Internal normalized question — one shape for both sources."""

    __slots__ = ("question_number", "question_type", "stem", "options", "standard_answer",
                 "analysis", "full_score", "resource_filenames")

    def __init__(self, *, question_number: int, question_type: str, stem: str,
                 options: dict[str, str], standard_answer: str, analysis: str,
                 full_score: int | None, resource_filenames: list[str]):
        self.question_number = question_number
        self.question_type = question_type
        self.stem = stem
        self.options = options
        self.standard_answer = standard_answer
        self.analysis = analysis
        self.full_score = full_score
        self.resource_filenames = resource_filenames


class ResolvedPaper:
    __slots__ = ("subject_key", "year", "source", "questions")

    def __init__(self, subject_key: str, year: int, source: str, questions: list[ResolvedQuestion]):
        self.subject_key = subject_key
        self.year = year
        self.source = source
        self.questions = questions


def _parse_options(raw) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _document_type(raw_type) -> str:
    return "big" if str(raw_type or "").strip() in {"大题", "big", "简答题"} else "choice"


_CLEAN_FIGURE_ROOT = "figures"
_CLEAN_FIGURE_EXTENSIONS = (".svg",)


def _clean_figure_filenames(subject_key: str, year: int, question_number: int) -> list[str]:
    """The watermark-free figures drawn for one question — the ONLY figures that may be served.

    This replaces three legacy sources (a curated ``image_mapping.json``, an on-disk asset
    convention, and the OCR document's ``image_urls``). All three pointed into the scraped
    ``assets/`` and ``images/`` trees, and those trees are not usable: measured on 2026-09-28,
    every file is a watermarked screenshot taken from a commercial exam-prep site, AND every
    file attached to a question is a screenshot of a DIFFERENT question (``2025_q33_1.jpg``
    holds question 37, ``2026_q37_1.jpg`` holds question 40). They could not be shown, and
    because they were not the right figure they could not be redrawn from either.

    So the source is the ``figures/{year}/`` tree, which holds vectors drawn from each
    question's own text by ``exam_resources/11408/build_clean_figures.py``. A question with no
    file there has no figure, and says so through ``missing_resources`` — never a watermark,
    never another question's diagram, and nothing invented.
    """
    directory = EXAM_RESOURCES_DIR / subject_key / "past_papers" / _CLEAN_FIGURE_ROOT / str(year)
    if not directory.is_dir():
        return []
    number = int(question_number)
    patterns = (
        re.compile(rf"^q{number}_(\d+)$"),
        re.compile(rf"^{year}_q{number}_(\d+)$"),
        re.compile(rf"^{year}_{number}_(\d+)$"),
    )
    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    found = []
    for entry in entries:
        if not entry.is_file():
            continue
        stem, dot, extension = entry.name.rpartition(".")
        if not dot or f".{extension.lower()}" not in _CLEAN_FIGURE_EXTENSIONS:
            continue
        if any(pattern.match(stem) for pattern in patterns):
            found.append(entry.name)
    return found


def _bank_resources(subject_key: str, year: int, question_number: int) -> list[str]:
    """Filenames this question's figures resolve to — see ``_clean_figure_filenames``."""
    return _clean_figure_filenames(subject_key, year, question_number)


def bank_questions(db, subject_key: str, year: int):
    """Active bank rows for one paper, ordered by question number."""
    from models import ExamQuestionBank

    return (db.query(ExamQuestionBank)
            .filter(ExamQuestionBank.subject_key == subject_key,
                    ExamQuestionBank.source_type == "past_paper",
                    ExamQuestionBank.year == year,
                    ExamQuestionBank.is_active == True)  # noqa: E712 — SQLAlchemy comparison
            .order_by(ExamQuestionBank.question_number)
            .all())


def document_questions(subject_key: str, year: int) -> list[dict]:
    """Questions from the document/OCR source for one paper."""
    import exam_paper_parser

    cache_file = exam_paper_parser._ocr_cache_path(subject_key, year)
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            questions = cached.get("questions", [])
            if questions:
                return questions
        except (OSError, ValueError):
            pass
    return exam_paper_parser.get_year_questions(subject_key, year).get("questions", []) or []


def _from_bank(db, subject_key: str, year: int, rows) -> list[ResolvedQuestion]:
    out = []
    for item in rows:
        try:
            number = int(item.question_number)
        except (TypeError, ValueError):
            continue
        qtype = "big" if item.question_type == "big" else "choice"
        out.append(ResolvedQuestion(
            question_number=number,
            question_type=qtype,
            stem=item.stem or "",
            options=_parse_options(item.options_json),
            standard_answer=(item.standard_answer or "").strip(),
            analysis=(item.analysis or "").strip(),
            full_score=exam_paper_scores.full_score(subject_key, year, number, qtype),
            resource_filenames=_bank_resources(subject_key, year, number),
        ))
    return out


def _from_document(raw_questions, subject_key: str, year: int) -> list[ResolvedQuestion]:
    out = []
    for raw in raw_questions:
        try:
            number = int(raw.get("number"))
        except (TypeError, ValueError):
            continue
        qtype = _document_type(raw.get("type"))
        out.append(ResolvedQuestion(
            question_number=number,
            question_type=qtype,
            stem=raw.get("stem") or raw.get("content") or "",
            options=_parse_options(raw.get("options")),
            standard_answer=str(raw.get("answer") or raw.get("standard_answer") or "").strip(),
            analysis=str(raw.get("analysis") or "").strip(),
            full_score=exam_paper_scores.full_score(subject_key, year, number, qtype),
            resource_filenames=_clean_figure_filenames(subject_key, year, number),
        ))
    return out


def answer_payload(paper: ResolvedPaper, answer_map: dict[str, str]) -> list[dict]:
    """Translate public-number answers into whatever id space the owning source uses.

    The frontend only ever sends `question_number`; the document source keys its own questions by
    an internal string id, so the adapter performs that mapping here rather than leaking it outward.
    """
    if paper.source == "document":
        internal = {str(int(q.get("number"))): str(q.get("id"))
                    for q in document_questions(paper.subject_key, paper.year)
                    if q.get("number") is not None}
    else:
        internal = {}
    out = []
    for question in paper.questions:
        number = str(question.question_number)
        out.append({
            "question_id": internal.get(number, number),
            "user_answer": answer_map.get(number, ""),
        })
    return out


def resolve_paper(db, subject_key: str, year: int) -> ResolvedPaper:
    """Resolve one paper from whichever real source owns it.

    The bank answers when it holds active rows for this paper; otherwise the document source does.
    Within the chosen source question numbers are unique, so public identity never collides.
    """
    rows = bank_questions(db, subject_key, year)
    if rows:
        return ResolvedPaper(subject_key, year, "bank", _from_bank(db, subject_key, year, rows))
    return ResolvedPaper(subject_key, year, "document",
                         _from_document(document_questions(subject_key, year), subject_key, year))


def available_papers(db, subject_key: str) -> list[PastPaperSummary]:
    """Every paper that actually has usable questions, from either source, for one subject."""
    from models import ExamQuestionBank

    fresh = {}
    for year, number, qtype in db.query(
            ExamQuestionBank.year, ExamQuestionBank.question_number, ExamQuestionBank.question_type
    ).filter(ExamQuestionBank.subject_key == subject_key,
             ExamQuestionBank.source_type == "past_paper",
             ExamQuestionBank.is_active == True):  # noqa: E712
        if year is None or number is None:
            continue
        fresh.setdefault(int(year), []).append(qtype)

    all_years = set(fresh)
    try:
        import exam_paper_parser
        all_years |= {int(y) for y in exam_paper_parser.parse_docx_questions(subject_key).keys()}
    except Exception:  # noqa: BLE001 — a missing document must not break the index
        pass

    summaries = []
    for year in sorted(all_years):
        if year in fresh:
            types = fresh[year]
            summaries.append(PastPaperSummary(
                year=year, question_count=len(types),
                choice_count=sum(1 for t in types if t != "big"),
                big_count=sum(1 for t in types if t == "big"),
                source="bank"))
            continue
        resolved = resolve_paper(db, subject_key, year)
        if not resolved.questions:
            continue
        summaries.append(PastPaperSummary(
            year=year, question_count=len(resolved.questions),
            choice_count=sum(1 for q in resolved.questions if q.question_type == "choice"),
            big_count=sum(1 for q in resolved.questions if q.question_type == "big"),
            source=resolved.source))
    return summaries


# ---------------------------------------------------------------- projections


def public_question(question: ResolvedQuestion, subject_key: str, year: int) -> PastPaperQuestion:
    """PRE-SUBMIT projection — the single place a question becomes frontend-visible.

    A resource enters `resources` only when it actually resolves on disk, so the frontend never
    receives a URL that would 404. A referenced-but-unresolvable figure is reported in
    `missing_resources` instead of being dropped silently.
    """
    resources = []
    missing = []
    for filename in question.resource_filenames:
        url = canonical_image_url(subject_key, year, filename)
        if url and resolve_resource_file(subject_key, year, filename) is not None:
            resources.append(PastPaperResource(url=url))
        else:
            missing.append(filename)
    return PastPaperQuestion(
        subject_key=subject_key,
        year=int(year),
        question_number=question.question_number,
        question_type=question.question_type,
        stem=question.stem,
        options=question.options,
        resources=resources,
        full_score=question.full_score,
        missing_resources=missing,
    )


def public_questions(paper: ResolvedPaper) -> list[PastPaperQuestion]:
    return [public_question(q, paper.subject_key, paper.year) for q in paper.questions]


def resources_for(subject_key: str, year: int, question_number: int) -> list[PastPaperResource]:
    """The resolvable figure references for ONE past-paper question, by public identity.

    Same resolution order and the same URL contract as ``public_question`` — a figure is
    emitted only when it actually resolves on disk. The wrong-answer surface reuses this
    rather than assembling a second resource format, which is the only way the two
    surfaces can be guaranteed to agree.
    """
    out: list[PastPaperResource] = []
    for filename in _bank_resources(subject_key, year, question_number):
        url = canonical_image_url(subject_key, year, filename)
        if url and resolve_resource_file(subject_key, year, filename) is not None:
            out.append(PastPaperResource(url=url))
    return out


def document_question_by_internal_id(subject_key: str, year: int, internal_id: str) -> dict | None:
    """One document-source question by its INTERNAL id, for resolving a past-paper attempt.

    The internal id is never public (BC6 public identity is subject + year + question
    number); it exists only so a surface holding an attempt can find the question the
    attempt was about.
    """
    for raw in document_questions(subject_key, year):
        if str(raw.get("id")) == str(internal_id):
            return raw
    return None


def public_result(*, subject_key: str, year: int, question_number: int, question_type: str,
                  user_answer: str, correct: bool | None, judge: str | None,
                  standard_answer: str, analysis: str, score: int | None,
                  full_score: int | None, feedback: str | None) -> PastPaperQuestionResult:
    return PastPaperQuestionResult(
        subject_key=subject_key, year=int(year), question_number=int(question_number),
        question_type="big" if question_type == "big" else "choice",
        user_answer=user_answer, correct=correct, judge=judge,
        standard_answer=standard_answer, analysis=analysis or None,
        score=score, full_score=full_score, feedback=feedback or None)


def replay_results(attempt, subject_key: str, year: int,
                   paper: ResolvedPaper | None = None) -> list[PastPaperQuestionResult]:
    """Decode the authoritative results submit already persisted into ``result_json``.

    This is a REPLAY. Nothing here re-compares an answer against the reference; the stored verdict
    is decoded and re-keyed onto the public identity. An attempt with nothing persisted yields [].

    ``paper`` is optional and only supplies the static ``analysis`` the submit payload does not
    carry — reading a question's explanation is not grading.
    """
    if not getattr(attempt, "result_json", None):
        return []
    try:
        blob = json.loads(attempt.result_json)
    except (TypeError, ValueError):
        return []
    raw_results = blob.get("results") if isinstance(blob, dict) else None
    if not isinstance(raw_results, list):
        return []

    analysis_by_number = {}
    if paper is not None:
        analysis_by_number = {q.question_number: (q.analysis or "")
                              for q in paper.questions}

    out = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        try:
            number = int(raw.get("number"))
        except (TypeError, ValueError):
            continue
        analysis = str(raw.get("analysis") or "") or analysis_by_number.get(number, "")
        qtype = "big" if str(raw.get("type") or "").strip() in {"大题", "big"} else "choice"
        if qtype == "big":
            scored = raw.get("score")
            has_score = isinstance(scored, (int, float))
            out.append(public_result(
                subject_key=subject_key, year=year, question_number=number, question_type="big",
                user_answer=str(raw.get("user_answer") or ""),
                correct=None,
                judge="ai_graded" if has_score else "self_review",
                standard_answer=str(raw.get("standard_answer") or ""),
                analysis=analysis,
                score=int(scored) if has_score else None,
                full_score=raw.get("full_score") if isinstance(raw.get("full_score"), (int, float)) else None,
                feedback=raw.get("feedback")))
        else:
            out.append(public_result(
                subject_key=subject_key, year=year, question_number=number, question_type="choice",
                user_answer=str(raw.get("user_answer") or ""),
                # Tri-state, preserved: an unanswered objective question carries NO verdict, and
                # `bool(None)` turned that into "wrong" on the way out of submit. Grading already
                # kept them apart (the wrong book is fed from the internal None); only this
                # projection collapsed them.
                correct=None if raw.get("correct") is None else bool(raw.get("correct")),
                judge=None,
                standard_answer=str(raw.get("standard_answer") or ""),
                analysis=analysis,
                score=raw.get("score") if isinstance(raw.get("score"), (int, float)) else None,
                full_score=raw.get("full_score") if isinstance(raw.get("full_score"), (int, float)) else None,
                feedback=raw.get("feedback")))
    return out


def resolve_resource_file(subject_key: str, year: int, filename: str) -> Path | None:
    """Resolve a figure to a real file inside an allowed root, or None.

    Rejects anything that is not a bare filename and anything that escapes its root, so no caller
    can traverse out of the asset directories.
    """
    if not filename or not _SAFE_FILENAME.match(filename):
        return None
    if subject_key not in SUBJECT_NAMES:
        return None
    past_papers = EXAM_RESOURCES_DIR / subject_key / "past_papers"
    # The drawn figures are the ONLY figure root. The three scraped trees — `past_papers/assets`,
    # `past_papers/images` and `static/exam_papers/11408` — are all the same unusable set: every
    # file is a watermarked screenshot of some OTHER question (see `_clean_figure_filenames`).
    # `static/` was reachable only from here (main.py deliberately leaves the `/static/exam_papers`
    # mount off), so dropping it closes the last URL that could serve a watermark. The static
    # tree itself is a protected asset and is NOT deleted — it is simply no longer served.
    candidates = ((past_papers / _CLEAN_FIGURE_ROOT / str(year), filename),)
    # A curated reference may name the right asset with the wrong extension. Retry the same stem
    # across the known extensions so an existing figure is still delivered — this repairs
    # delivery, it does not invent a file.
    stem = filename.rsplit(".", 1)[0]
    attempts = [(root, name) for root, name in candidates]
    attempts += [(root, stem + ext) for root, _ in candidates
                 for ext in (".svg", ".jpeg", ".jpg", ".png", ".webp", ".gif")
                 if stem + ext != filename]
    for root, name in attempts:
        try:
            resolved_root = root.resolve()
            resolved = (root / name).resolve()
            resolved.relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved.is_file():
            return resolved
    return None
