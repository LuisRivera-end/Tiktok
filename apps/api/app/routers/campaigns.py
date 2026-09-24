from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.deps import CurrentUser, DbDep
from app.models import AdCampaign, AdCreative, Video
from app.schemas import CampaignIn, CampaignOut, CampaignUpdateIn, AdClickIn
from app.models import AdDailySpend, AdClickReceipt
from app.ads.billing import budget_day, record_click, sync_clicks
from app.mongo import get_mongo
from app.telemetry.exposures import dataset_rows, metrics_for
from datetime import datetime, timedelta, timezone
from fastapi import Query
from app.demographics import Gender, GENDERS

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(db: DbDep, current: CurrentUser) -> list[CampaignOut]:
    query = select(AdCampaign)
    if current.role not in {"admin"}:
        query = query.where(AdCampaign.advertiser_id == current.id)
    rows = list((await db.execute(query.order_by(AdCampaign.created_at.desc()))).scalars())
    result = []
    for row in rows:
        spend = await db.get(AdDailySpend, (row.id, budget_day()))
        out = CampaignOut.model_validate(row)
        out.spent_today_cents = spend.amount_cents if spend else 0
        result.append(out)
    return result


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignIn, db: DbDep, current: CurrentUser) -> CampaignOut:
    if current.role not in {"advertiser", "admin"}:
        raise HTTPException(status_code=403, detail="Solo un anunciante puede crear campañas")
    video = await db.get(Video, payload.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="El creative necesita un video existente")
    if current.role != "admin" and video.creator_id != current.id:
        raise HTTPException(403, "Selecciona un video propio")
    campaign = AdCampaign(
        advertiser_id=current.id,
        name=payload.name,
        bid_cents=payload.bid_cents,
        daily_budget_cents=payload.daily_budget_cents,
        targeting_tags=payload.targeting_tags,
        targeting_categories=payload.targeting_categories,
        targeting_genders=payload.targeting_genders,
    )
    db.add(campaign)
    await db.flush()
    db.add(AdCreative(campaign_id=campaign.id, video_id=payload.video_id, landing_url=str(payload.landing_url)))
    await db.commit()
    await db.refresh(campaign)
    return CampaignOut.model_validate(campaign)


async def owned_campaign(db, current, campaign_id):
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign or (current.role != "admin" and campaign.advertiser_id != current.id):
        raise HTTPException(404, "Campaña no encontrada")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(campaign_id: str, payload: CampaignUpdateIn, db: DbDep, current: CurrentUser):
    campaign = await owned_campaign(db, current, campaign_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(campaign, key, value)
    await db.commit()
    return CampaignOut.model_validate(campaign)


@router.get("/{campaign_id}/metrics")
async def campaign_metrics(campaign_id: str, db: DbDep, current: CurrentUser,
                           days: int = Query(default=7, ge=1, le=365), gender: Gender | None = None):
    campaign = await owned_campaign(db, current, campaign_id)
    mongo = get_mongo()
    await sync_clicks(db, mongo)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = {"campaign_id": campaign_id, "started_at": {"$gte": since}, "origin": "real"}
    if gender:
        query["gender"] = gender
    exposures = [e async for e in mongo.exposures.find(query)]
    # Continuity needs the following organic exposure as well.
    users = list({e["user_id"] for e in exposures})
    context = [e async for e in mongo.exposures.find({"user_id": {"$in": users}, "started_at": {"$gte": since}})]
    rows = [r for r in dataset_rows(context) if r["campaign_id"] == campaign_id and (not gender or r["gender"] == gender)]
    receipts = list((await db.execute(select(AdClickReceipt).where(AdClickReceipt.campaign_id == campaign_id,
                                                       AdClickReceipt.created_at >= since))).scalars())
    if gender:
        receipts = [r for r in receipts if r.gender == gender]
    amount = sum(r.amount_cents for r in receipts)
    billed = sum(r.amount_cents > 0 for r in receipts)
    spend = await db.get(AdDailySpend, (campaign_id, budget_day()))
    reasons = {}
    async for trace in mongo.ranking_traces.find({"ts": {"$gte": since}}, {"trace.ad_rejections": 1}):
        for rejected in trace.get("trace", {}).get("ad_rejections", []):
            if rejected["campaign_id"] == campaign_id:
                reasons[rejected["reason"]] = reasons.get(rejected["reason"], 0) + 1
    return {**metrics_for(rows), "days": days, "spend_cents": amount, "billed_clicks": billed,
            "cpc_cents": amount / billed if billed else None,
            "remaining_cents": max(0, campaign.daily_budget_cents - (spend.amount_cents if spend else 0)),
            "genders": [{"gender": g, **metrics_for([r for r in rows if r["gender"] == g])} for g in GENDERS],
            "delivery": "paused" if campaign.status != "active" else "no_budget" if campaign.daily_budget_cents < (spend.amount_cents if spend else 0) + campaign.bid_cents else "eligible_subject_to_targeting",
            "rejections": reasons, "period_basis": "exposures_started_in_period; spend_by_click_time"}


@router.post("/click")
async def click_ad(payload: AdClickIn, db: DbDep, current: CurrentUser):
    mongo = get_mongo()
    e = await mongo.exposures.find_one({"_id": str(payload.exposure_id), "user_id": current.id})
    if not e or not e.get("campaign_id"):
        raise HTTPException(404, "Exposición publicitaria no encontrada")
    previous = await db.get(AdClickReceipt, e["_id"])
    if not previous and datetime.now(timezone.utc) - e["started_at"].replace(tzinfo=timezone.utc) > timedelta(hours=24):
        raise HTTPException(409, "La ventana del clic terminó")
    receipt = await record_click(db, e)
    await db.commit()
    charged = receipt.amount_cents
    try:
        await sync_clicks(db, mongo)
    except Exception:
        await db.rollback()  # durable receipt is retried by the background outbox
    return {"landing_url": e["landing_url"], "charged_cents": charged}
