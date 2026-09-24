from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from app.deps import CurrentUser, DbDep
from app.models import Video, AdCampaign, AdCreative, AdDailySpend
from app.ads.billing import budget_day
from app.mongo import get_mongo
from app.schemas import ExposureIn
from app.ml.features import features_for, FEATURE_VERSION
from app.services.catalog import features_from_profile, to_candidate
from app.telemetry.online import online_profile
from app.recsys.filters import filter_reason
from sqlalchemy import select

router = APIRouter(prefix="/exposures", tags=["exposures"])


@router.post("")
async def start_exposure(payload: ExposureIn, db: DbDep, current: CurrentUser):
    mongo = get_mongo()
    key = str(payload.exposure_id)
    existing = await mongo.exposures.find_one({"_id": key})
    if existing:
        if existing["user_id"] != current.id or existing["video_id"] != payload.video_id or existing.get("session_root", existing["session_id"]) != payload.session_id:
            raise HTTPException(409, "Exposición incompatible")
        return {"exposure_id": key}
    now = datetime.now(timezone.utc)
    last = await mongo.exposures.find_one({"user_id": current.id, "session_root": payload.session_id}, sort=[("started_at", -1)])
    session_id = payload.session_id
    if last:
        last_seen = last.get("last_event_at", last["started_at"]).replace(tzinfo=timezone.utc)
        session_id = last["session_id"] if now - last_seen < timedelta(minutes=30) else f"{payload.session_id}:{uuid4().hex[:8]}"
    started_at = payload.started_at
    if started_at:
        started_at = started_at.replace(tzinfo=timezone.utc) if started_at.tzinfo is None else started_at.astimezone(timezone.utc)
        if abs((now - started_at).total_seconds()) > 300:
            raise HTTPException(422, "Reloj de exposición fuera de rango")
    if payload.decision_id:
        decision = await mongo.decisions.find_one({"_id": str(payload.decision_id), "user_id": current.id,
                                                   "video_id": payload.video_id, "expires_at": {"$gt": now}})
        if not decision or decision.get("gender") != current.gender:
            raise HTTPException(409, "Actualiza el feed: la decisión venció o cambió el perfil")
        if decision.get("campaign_id"):
            campaign = (await db.execute(select(AdCampaign).where(AdCampaign.id == decision["campaign_id"]).with_for_update())).scalar_one_or_none()
            # Resolve inactivity again under the campaign lock so concurrent
            # registrations cannot mint separate sessions to bypass frequency.
            last = await mongo.exposures.find_one({"user_id": current.id, "session_root": payload.session_id}, sort=[("started_at", -1)])
            if last and now - last.get("last_event_at", last["started_at"]).replace(tzinfo=timezone.utc) < timedelta(minutes=30):
                session_id = last["session_id"]
            if not campaign or campaign.status != "active" or (campaign.targeting_genders and current.gender not in campaign.targeting_genders):
                raise HTTPException(409, "Campaña no disponible")
            creative = await db.get(AdCreative, decision["creative_id"])
            if not creative or creative.status != "active":
                raise HTTPException(409, "Creatividad no disponible")
            spend = await db.get(AdDailySpend, (campaign.id, budget_day()))
            if (spend.amount_cents if spend else 0) + decision["bid_cents"] > campaign.daily_budget_cents:
                raise HTTPException(409, "Presupuesto insuficiente; actualiza el feed")
            count = await mongo.exposures.count_documents({"user_id": current.id, "campaign_id": campaign.id,
                                                            "started_at": {"$gte": now - timedelta(hours=1)}})
            repeated = await mongo.exposures.find_one({"user_id": current.id, "campaign_id": campaign.id,
                                                       "session_id": session_id})
            if repeated and repeated["_id"] == key:
                await db.commit()
                return {"exposure_id": key}
            if count >= 8 or repeated:
                raise HTTPException(409, "Límite de frecuencia")
    else:
        video = await db.get(Video, payload.video_id)
        if not video:
            raise HTTPException(404, "Video no disponible")
        profile = await online_profile(mongo, current.id)
        from app.models import Block
        blocked = list((await db.execute(select(Block.blocked_id).where(Block.blocker_id == current.id))).scalars())
        user = features_from_profile(current, profile, blocked)
        candidate = to_candidate(video)
        if filter_reason(user, candidate, allow_seen=True):
            raise HTTPException(403, "Video no elegible")
        decision = {"video_id": video.id, "campaign_id": None, "gender": current.gender,
                    "features": features_for(user, candidate), "duration_ms": video.duration_ms,
                    "embedding": candidate.embedding, "category": video.category, "audio_id": video.audio_id,
                    "tags": video.tags, "feature_version": FEATURE_VERSION, "model_version": "direct-clip"}
    document = {k: v for k, v in decision.items() if k not in {"_id", "expires_at"}}
    document.update(_id=key, user_id=current.id, session_id=session_id, session_root=payload.session_id, started_at=started_at or now,
                    last_event_at=now, origin="real", watch_ms=0, coverage_ms=0)
    await mongo.exposures.update_one({"_id": key}, {"$setOnInsert": document}, upsert=True)
    stored = await mongo.exposures.find_one({"_id": key})
    if stored["user_id"] != current.id or stored["video_id"] != payload.video_id or stored.get("session_root", stored["session_id"]) != payload.session_id:
        raise HTTPException(409, "Exposición incompatible")
    await db.commit()  # release the campaign lock only after exposure registration
    return {"exposure_id": key}
