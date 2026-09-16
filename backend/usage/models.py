"""SQLAlchemy models for Unified Subscription + Usage (STEP 7B).

Normalized credits are integers (an internal cost unit, NOT tokens / request count /
raw currency). Provider currency cost is preserved separately in ai_cost_records.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Index, Integer, String, UniqueConstraint,
)

from database import Base
from models import utc_now


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    tier = Column(String(20), nullable=False)          # free / standard / advanced
    status = Column(String(20), nullable=False)         # active / cancelled / expired / pending
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=True)
    source = Column(String(30), nullable=False, default="manual")  # redemption / payment / migration
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class UsageBudget(Base):
    __tablename__ = "usage_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    period_type = Column(String(10), nullable=False)    # daily / weekly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    budget_amount = Column(Integer, nullable=False)      # credits granted for the period
    reserved_amount = Column(Integer, nullable=False, default=0)
    settled_amount = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_start",
                         name="uq_usage_budget_period"),
    )


class UsageLedger(Base):
    __tablename__ = "usage_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    request_id = Column(String(64), nullable=True)
    entry_type = Column(String(20), nullable=False)     # reserve / settle / release / adjustment
    amount = Column(Integer, nullable=False)            # credits; positive debit, negative credit
    reference_key = Column(String(255), nullable=False, unique=True)  # idempotency
    created_at = Column(DateTime, default=utc_now)


class AIRequest(Base):
    __tablename__ = "ai_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, unique=True)
    user_id = Column(Integer, nullable=False, index=True)
    capability = Column(String(50), nullable=False)
    tier = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False)         # reserved / executing / settled / released / failed
    estimated_credits = Column(Integer, nullable=True)
    reserved_credits = Column(Integer, nullable=True)
    actual_credits = Column(Integer, nullable=True)
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)          # nullable until Router (STEP 7C)
    error_category = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class AICostRecord(Base):
    __tablename__ = "ai_cost_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    provider_cost = Column(Float, nullable=True)        # actual provider currency cost
    currency = Column(String(10), nullable=False)
    normalized_credits = Column(Integer, nullable=False)  # normalized cost unit
    pricing_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now)
