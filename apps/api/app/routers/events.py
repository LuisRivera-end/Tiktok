from datetime import datetime, timezone

from fastapi import APIRouter

from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbDep
from app.models import ExplicitLike, Video
from app.mongo import get_mongo
from app.schemas import EventBatchIn
from app.telemetry.profile import apply_event, empty_profile

router = APIRouter(prefix="/events", tags=["events"])


@router.post("")
async def ingest_events(payload: EventBatchIn, db: DbDep, current: CurrentUser) -> dict:
    mongo = get_mongo()
    profile_doc = await mongo.user_profiles_online.find_one({"user_id": current.id})
    profile = profile_doc or empty_profile(current.id)
    accepted = 0

    for item in payload.events:
        video = await db.get(Video, item.video_id)
        if video is None:
            continue
        doc = {
            "user_id": current.id,
            "session_id": item.session_id,
            "video_id": item.video_id,
            "event_type": item.event_type,
            "ts": datetime.now(timezone.utc),
            "watch_ms": item.watch_ms,
            "duration_ms": item.duration_ms or video.duration_ms,
            "completion_ratio": item.completion_ratio,
            "loop_count": item.loop_count,
            "feed_position": item.feed_position,
            "is_ad": item.is_ad,
            "campaign_id": item.campaign_id,
            "device": item.device,
            "context": item.context,
        }
        await mongo.events.insert_one(doc)
        profile = apply_event(profile, doc, video.embedding, video.category, video.audio_id, list(video.tags or []))
        if item.event_type == "like":
            db.add(ExplicitLike(user_id=current.id, video_id=video.id))
        if item.event_type in {"play", "complete", "heartbeat"}:
            video.play_count += 1
        accepted += 1

    await mongo.user_profiles_online.update_one({"user_id": current.id}, {"$set": profile}, upsert=True)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return {"accepted": accepted}
