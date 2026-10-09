"""Minimal per-user snooze overlay for deterministic review recommendations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from database import Base


class ReviewRecommendationSnooze(Base):
    __tablename__ = "review_recommendation_snoozes"
    __table_args__ = (
        UniqueConstraint("user_id", "recommendation_key", name="uq_review_snooze_user_key"),
        Index("ix_review_snooze_user_until", "user_id", "snoozed_until"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recommendation_key = Column(String(64), nullable=False)
    snoozed_until = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def snooze(db: Session, user, recommendation_key: str, *, until: datetime | None = None,
           as_of: datetime | None = None, duration: timedelta = timedelta(hours=24)) -> datetime:
    """Idempotently suppress a current key for the caller; never writes learning state."""
    now = _utc_naive(as_of or datetime.now(timezone.utc))
    expiry = _utc_naive(until) if until is not None else now + duration
    if not recommendation_key or len(recommendation_key) != 64:
        raise ValueError("invalid_recommendation_key")
    if expiry <= now:
        raise ValueError("snooze_expiry_must_be_future")
    statement = sqlite_insert(ReviewRecommendationSnooze).values(
        user_id=user.id,
        recommendation_key=recommendation_key,
        snoozed_until=expiry,
        updated_at=now,
    ).on_conflict_do_update(
        index_elements=["user_id", "recommendation_key"],
        set_={"snoozed_until": expiry, "updated_at": now},
    )
    db.execute(statement)
    db.flush()
    return expiry


def active_keys(db: Session, user, *, as_of: datetime | None = None) -> set[str]:
    now = _utc_naive(as_of or datetime.now(timezone.utc))
    rows = (db.query(ReviewRecommendationSnooze.recommendation_key)
            .filter(ReviewRecommendationSnooze.user_id == user.id,
                    ReviewRecommendationSnooze.snoozed_until > now).all())
    return {row[0] for row in rows}
