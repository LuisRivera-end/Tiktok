from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    advertiser_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    bid_cents: Mapped[int] = mapped_column(Integer, default=80)
    daily_budget_cents: Mapped[int] = mapped_column(Integer, default=5000)
    spent_today_cents: Mapped[int] = mapped_column(Integer, default=0)
    targeting_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    targeting_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    targeting_genders: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    advertiser = relationship("User", back_populates="campaigns")
    creatives = relationship("AdCreative", back_populates="campaign")


class AdCreative(Base):
    __tablename__ = "ad_creatives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), index=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))
    landing_url: Mapped[str] = mapped_column(String(255), default="https://example.edu")
    status: Mapped[str] = mapped_column(String(20), default="active")

    campaign = relationship("AdCampaign", back_populates="creatives")


class AdBudgetLedger(Base):
    __tablename__ = "ad_budget_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40), default="impression")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdClickReceipt(Base):
    """Durable click + outbox; one transaction with the daily budget ledger."""
    __tablename__ = "ad_click_receipts"
    exposure_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    gender: Mapped[str] = mapped_column(String(24))
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON)
    synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdDailySpend(Base):
    __tablename__ = "ad_daily_spend"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
