from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.deps import CurrentUser, DbDep
from app.models import AdCampaign, AdCreative, Video
from app.schemas import CampaignIn, CampaignOut

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(db: DbDep, current: CurrentUser) -> list[CampaignOut]:
    query = select(AdCampaign)
    if current.role not in {"admin"}:
        query = query.where(AdCampaign.advertiser_id == current.id)
    rows = list((await db.execute(query.order_by(AdCampaign.created_at.desc()))).scalars())
    return [CampaignOut.model_validate(row) for row in rows]


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignIn, db: DbDep, current: CurrentUser) -> CampaignOut:
    if current.role not in {"advertiser", "admin"}:
        raise HTTPException(status_code=403, detail="Solo un anunciante puede crear campañas")
    video = await db.get(Video, payload.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="El creative necesita un video existente")
    campaign = AdCampaign(
        advertiser_id=current.id,
        name=payload.name,
        bid_cents=payload.bid_cents,
        daily_budget_cents=payload.daily_budget_cents,
        targeting_tags=payload.targeting_tags,
        targeting_categories=payload.targeting_categories,
    )
    db.add(campaign)
    await db.flush()
    db.add(AdCreative(campaign_id=campaign.id, video_id=payload.video_id, landing_url=payload.landing_url))
    await db.commit()
    await db.refresh(campaign)
    return CampaignOut.model_validate(campaign)
