from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.deps import CurrentUser, DbDep
from app.models import ExplicitLike, Video
from app.mongo import get_mongo
from app.schemas import EventBatchIn
from app.telemetry.profile import apply_event, empty_profile

router = APIRouter(prefix="/events", tags=["events"])


async def ingest_exposure_event(item, mongo, current):
    if not item.event_id or not item.exposure_id:
        raise HTTPException(422, "event_id y exposure_id son obligatorios juntos")
    event_id, exposure_id = str(item.event_id), str(item.exposure_id)
    e = await mongo.exposures.find_one({"_id": exposure_id, "user_id": current.id})
    if not e or e["video_id"] != item.video_id or e.get("session_root", e["session_id"]) != item.session_id:
        raise HTTPException(409, "La exposición no corresponde al evento")
    allowed = {"impression", "play", "heartbeat", "close", "like", "share", "comment", "follow", "comment_open", "share_open", "hashtag_tap"}
    if item.event_type not in allowed:
        raise HTTPException(422, "Tipo de evento no permitido para exposiciones")
    now = datetime.now(timezone.utc)
    event_time = item.event_ts or now
    event_time = event_time.replace(tzinfo=timezone.utc) if event_time.tzinfo is None else event_time.astimezone(timezone.utc)
    if abs((now - event_time).total_seconds()) > 300:
        raise HTTPException(422, "Reloj de evento fuera de rango")
    doc = {**item.model_dump(mode="json"), "event_id": event_id, "exposure_id": exposure_id,
           "user_id": current.id, "ts": event_time, "received_at": now, "gender": e["gender"],
           "origin": e["origin"], "is_ad": bool(e.get("campaign_id")), "campaign_id": e.get("campaign_id"),
           "creative_id": e.get("creative_id"), "duration_ms": e["duration_ms"]}
    doc["session_id"] = e["session_id"]
    await mongo.events.update_one({"event_id": event_id}, {"$setOnInsert": doc}, upsert=True)
    # Always reduce the stored event, not retry payloads. A crash between insert
    # and reduction is repaired by the same retry; operators are idempotent.
    stored = await mongo.events.find_one({"event_id": event_id})
    if stored["exposure_id"] != exposure_id or stored["user_id"] != current.id:
        raise HTTPException(409, "event_id ya pertenece a otra exposición")
    now = stored["ts"]
    duration = e["duration_ms"]
    watch = min(max(int(stored.get("watch_ms", 0)), 0), duration * 10)
    coverage = min(max(int(stored.get("coverage_ms", 0)), 0), duration, watch)
    values = {}
    kind = stored["event_type"]
    if kind == "play":
        values["played"] = True
    for key, event_type in [("liked", "like"), ("shared", "share"), ("commented", "comment"), ("followed", "follow")]:
        if kind == event_type:
            values[key] = True
    update = {"$max": {"watch_ms": watch, "coverage_ms": coverage, "last_event_at": now}}
    if values:
        update["$set"] = values
    await mongo.exposures.update_one({"_id": exposure_id}, update)
    if kind == "close":
        await mongo.exposures.update_one({"_id": exposure_id, "closed_at": {"$exists": False}},
                                        {"$set": {"closed_at": now, "close_reason": stored.get("close_reason") or "exit"}})
    return stored


@router.post("")
async def ingest_events(payload: EventBatchIn, db: DbDep, current: CurrentUser) -> dict:
    mongo = get_mongo()
    profile_doc = await mongo.user_profiles_online.find_one({"user_id": current.id})
    profile = profile_doc or empty_profile(current.id)
    accepted = 0

    for item in payload.events:
        if item.exposure_id or item.event_id:
            stored_event = await ingest_exposure_event(item, mongo, current)
            if stored_event["event_type"] == "like":
                try:
                    async with db.begin_nested():
                        existing = await db.scalar(select(ExplicitLike.id).where(ExplicitLike.user_id == current.id, ExplicitLike.video_id == item.video_id))
                        if not existing:
                            db.add(ExplicitLike(user_id=current.id, video_id=item.video_id))
                            await db.flush()
                except IntegrityError:
                    pass  # unique user/video constraint handles concurrent retries
            accepted += 1
            continue
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
            "origin": "legacy",
            "gender": "unspecified",
        }
        await mongo.events.insert_one(doc)
        profile = apply_event(profile, doc, video.embedding, video.category, video.audio_id, list(video.tags or []))
        if item.event_type == "like":
            db.add(ExplicitLike(user_id=current.id, video_id=video.id))
        if item.event_type in {"play", "complete", "heartbeat"}:
            video.play_count += 1
        accepted += 1

    if any(not e.exposure_id for e in payload.events):
        profile.pop("_id", None)
        await mongo.user_profiles_online.update_one({"user_id": current.id}, {"$set": profile}, upsert=True)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return {"accepted": accepted}
