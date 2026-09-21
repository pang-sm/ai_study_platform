"""Structured Learning Report API — POST /ai/learning-report.

The deterministic report is computed for the CALLER's own data in one learning space; the AI
narrative is optional and is composed only from that computed data. No dashboard CRUD is added
here: this endpoint reads the facts the product already stores and returns them structured.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from learning import report as report_service
from ops import feature_flags

router = APIRouter(tags=["ai-workflows"])


def _require_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user  # lazy import to avoid a circular import
    return get_current_user(request, db)


class LearningReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_key: Literal["course_learning", "exam_11408", "programming"] = "course_learning"
    period_days: int = Field(default=report_service.DEFAULT_PERIOD_DAYS, ge=1,
                             le=report_service.MAX_PERIOD_DAYS)
    course_id: str = ""
    exam_module_id: str = ""
    language: str = ""
    include_narrative: bool = False


class ReportNarrativeView(BaseModel):
    """The AI half of a report. Labelled `origin: ai` so it is never read as a metric."""

    model_config = ConfigDict(extra="allow")

    text: str
    origin: str = "ai"
    capability: str
    request_id: str
    usage: dict = Field(default_factory=dict)


class LearningReportResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_id: str
    report_period: dict
    context: dict
    structured_metrics: dict
    highlights: list[dict] = Field(default_factory=list)
    attention_items: list[dict] = Field(default_factory=list)
    data_coverage: dict
    narrative: ReportNarrativeView | None = None
    narrative_error: str | None = None
    generated_at: str


@router.post("/ai/learning-report", response_model=LearningReportResponse)
def generate_learning_report(payload: LearningReportRequest, db: Session = Depends(get_db),
                             current_user=Depends(_require_user)):
    """ONE structured report for the caller.

    ``include_narrative=false`` returns the deterministic report alone — every metric computed
    by SQL from the caller's own rows. ``include_narrative=true`` adds an AI composition over
    exactly those metrics, gated by the unified ``report.generate`` capability: a tier without
    it gets 403, and a budget refusal gets 429. A technical failure of the narrative returns
    the deterministic report with ``narrative_error`` set rather than discarding the metrics.
    """
    feature_flags.ensure_feature_allowed(db, current_user, "learning_report")
    try:
        return report_service.generate_learning_report(
            db, current_user, service_key=payload.service_key,
            period_days=payload.period_days,
            course_id=payload.course_id or None,
            exam_module_id=payload.exam_module_id or None,
            language=payload.language or None,
            include_narrative=payload.include_narrative)
    except report_service.ReportRefusal as exc:
        raise HTTPException(status_code=400, detail={"code": exc.reason,
                                                     "message": exc.message})
