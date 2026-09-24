from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Video
from app.mongo import get_mongo
from app.seed import inject_corpus_if_needed
from app.services.corpus import CorpusActor, CorpusClip, generate_events
from app.telemetry.profile import apply_event, empty_profile


async def run_simulation(
    db: AsyncSession,
    users: int,
    days: int,
    events_per_user: int,
    pass_id: str = "",
) -> dict:
    await inject_corpus_if_needed(db)
    people = list((await db.execute(select(User).where(User.role.in_(["viewer", "creator"])))).scalars())
    videos = list((await db.execute(select(Video))).scalars())
    if not people or not videos:
        return {"events": 0, "users": 0, "regions": 0}

    actors = [CorpusActor(id=person.id, region=person.region or "", role=person.role) for person in people]
    clips = [
        CorpusClip(
            id=video.id,
            region=video.region or "",
            category=video.category,
            duration_ms=video.duration_ms,
            creator_id=video.creator_id,
            audio_id=video.audio_id,
            tags=tuple(video.tags or []),
        )
        for video in videos
    ]
    events = generate_events(
        actors,
        clips,
        users=users,
        days=days,
        events_per_user=events_per_user,
        pass_id=pass_id,
    )
    if not events:
        return {"events": 0, "users": 0, "regions": 0}

    # Re-running the same simulation is a new set of sessions, not a duplicate
    # of the previous pass with the same actor, day and feed position.
    run_id = uuid4().hex[:12]
    for event in events:
        event["session_id"] = f"{run_id}-{event['session_id']}"
        event["origin"] = "simulated"
        event["gender"] = "unspecified"

    mongo = get_mongo()
    stamped = datetime.now(timezone.utc)
    await mongo.events.insert_many([{**event, "ts": stamped} for event in events])

    by_video = {video.id: video for video in videos}
    profiles: dict[str, dict] = {}
    for event in events:
        user_id = event["user_id"]
        if user_id not in profiles:
            profile_doc = await mongo.user_profiles_online.find_one({"user_id": user_id})
            profiles[user_id] = profile_doc or empty_profile(user_id)
        video = by_video.get(event["video_id"])
        if video is None:
            continue
        profiles[user_id] = apply_event(
            profiles[user_id],
            event,
            list(video.embedding or []),
            video.category,
            video.audio_id,
            list(video.tags or []),
        )
    for user_id, profile in profiles.items():
        await mongo.user_profiles_online.update_one({"user_id": user_id}, {"$set": profile}, upsert=True)

    regions = {event["user_region"] for event in events if event.get("user_region")}
    regions.update(event["video_region"] for event in events if event.get("video_region"))
    return {
        "events": len(events),
        "users": len({event["user_id"] for event in events}),
        "days": days,
        "regions": len(regions),
        "pass_id": pass_id,
    }
