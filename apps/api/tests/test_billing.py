from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from mongomock_motor import AsyncMongoMockClient
from app.db import Base
from app.models import User, AdCampaign, AdClickReceipt, AdDailySpend, AdBudgetLedger
from app.ads.billing import record_click, sync_clicks, budget_day


@pytest.mark.asyncio
async def test_click_once_budget_limit_rollover_and_outbox_recovery():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)
    async with session() as db:
        db.add(User(id="u", email="u@test.local", display_name="u", password_hash="unused"))
        db.add(AdCampaign(id="c", advertiser_id="u", name="campaign", bid_cents=60, daily_budget_cents=100))
        await db.commit()
        e = {"_id": "one", "campaign_id": "c", "user_id": "u", "video_id": "v", "session_id": "s", "bid_cents": 60, "gender": "woman"}
        now = datetime(2026, 3, 5, 5, 59, tzinfo=timezone.utc)
        assert budget_day(now) == "2026-03-04"
        receipt = await record_click(db, e, now)
        await db.commit()
        assert receipt.amount_cents == 60
        again = await record_click(db, e, now)
        assert again.amount_cents == 60
        unpaid = await record_click(db, {**e, "_id": "two"}, now)
        await db.commit()
        assert unpaid.amount_cents == 0
        next_day = datetime(2026, 3, 5, 6, 1, tzinfo=timezone.utc)
        third = await record_click(db, {**e, "_id": "three"}, next_day)
        await db.commit()
        assert third.amount_cents == 60
        assert await db.scalar(select(func.count()).select_from(AdBudgetLedger)) == 2
        mongo = AsyncMongoMockClient().test
        await mongo.exposures.insert_many([{**e, "_id": key} for key in ("one", "two", "three")])
        await sync_clicks(db, mongo)
        await sync_clicks(db, mongo)
        assert await mongo.events.count_documents({}) == 3
        assert await mongo.exposures.count_documents({"clicked": True}) == 3
        assert await db.scalar(select(func.count()).select_from(AdClickReceipt).where(AdClickReceipt.synced.is_(False))) == 0
    await engine.dispose()
