from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models import AdCampaign, AdClickReceipt, AdDailySpend, AdBudgetLedger


def budget_day(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("America/Mexico_City")).date().isoformat()


async def record_click(db, exposure, now=None):
    """Campaign row serializes budget + click deduplication across workers."""
    now = now or datetime.now(timezone.utc)
    campaign = (await db.execute(select(AdCampaign).where(AdCampaign.id == exposure["campaign_id"]).with_for_update())).scalar_one()
    previous = await db.get(AdClickReceipt, exposure["_id"])
    if previous:
        return previous
    day = budget_day(now)
    spend = await db.get(AdDailySpend, (campaign.id, day))
    if not spend:
        spend = AdDailySpend(campaign_id=campaign.id, day=day, amount_cents=0)
        db.add(spend)
    bid = max(int(exposure["bid_cents"]), 1)
    amount = bid if spend.amount_cents + bid <= campaign.daily_budget_cents else 0
    spend.amount_cents += amount
    campaign.spent_today_cents = spend.amount_cents
    payload = {"event_id": f"click:{exposure['_id']}", "exposure_id": exposure["_id"],
               "event_type": "ad_click", "user_id": exposure["user_id"], "video_id": exposure["video_id"],
               "campaign_id": campaign.id, "session_id": exposure["session_id"], "is_ad": True,
               "gender": exposure.get("gender", "unspecified"), "origin": "real", "ts": now.isoformat()}
    receipt = AdClickReceipt(exposure_id=exposure["_id"], campaign_id=campaign.id, user_id=exposure["user_id"],
                            gender=payload["gender"], amount_cents=amount, payload=payload, created_at=now)
    db.add(receipt)
    if amount:
        db.add(AdBudgetLedger(campaign_id=campaign.id, amount_cents=amount, reason="click", created_at=now))
    await db.flush()
    return receipt


async def sync_clicks(db, mongo):
    rows = list((await db.execute(select(AdClickReceipt).where(AdClickReceipt.synced.is_(False)).limit(500))).scalars())
    for receipt in rows:
        doc = dict(receipt.payload)
        doc["ts"] = datetime.fromisoformat(doc["ts"])
        await mongo.exposures.update_one({"_id": receipt.exposure_id}, {"$set": {"clicked": True}})
        await mongo.events.update_one({"event_id": doc["event_id"]}, {"$setOnInsert": doc}, upsert=True)
        receipt.synced = True
    await db.commit()
