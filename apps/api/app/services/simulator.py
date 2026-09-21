from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Video
from app.mongo import get_mongo
from app.recsys.pipeline import rank_organic_feed
from app.recsys.types import PipelineConfig
from app.services.catalog import features_from_profile, to_candidate
from app.telemetry.profile import apply_event, empty_profile


async def run_simulation(db: AsyncSession, users: int, days: int, events_per_user: int) -> dict:
    people = list((await db.execute(select(User).where(User.role.in_(["viewer", "creator"])))).scalars())
    videos = list((await db.execute(select(Video))).scalars())
    if not people or not videos:
        return {"events": 0, "users": 0}

    mongo = get_mongo()
    catalog = [to_candidate(video) for video in videos]
    by_id = {video.id: video for video in videos}
    rng = random.Random(42)
    sample = people[:users]
    written = 0

    for person in sample:
        profile_doc = await mongo.user_profiles_online.find_one({"user_id": person.id})
        profile = profile_doc or empty_profile(person.id)
        for _day in range(days):
            features = features_from_profile(person, profile, [])
            ranked, _trace = rank_organic_feed(features, catalog, PipelineConfig(final_k=12))
            if not ranked:
                continue
            picks = ranked[: min(6, len(ranked))]
            for step in range(events_per_user):
                item = picks[step % len(picks)]
                video = by_id[item.video.id]
                roll = rng.random()
                context: dict = {}
                if roll < 0.10:
                    event_type = "skip"
                    watch_ms = rng.randint(400, 1800)
                elif roll < 0.48:
                    event_type = "complete"
                    watch_ms = video.duration_ms
                elif roll < 0.60:
                    event_type = "like"
                    watch_ms = int(video.duration_ms * 0.9)
                elif roll < 0.68:
                    event_type = "comment"
                    watch_ms = int(video.duration_ms * 0.7)
                elif roll < 0.76:
                    event_type = "share"
                    watch_ms = int(video.duration_ms * 0.6)
                elif roll < 0.82:
                    event_type = "follow"
                    watch_ms = 2000
                elif roll < 0.88:
                    event_type = "hashtag_tap"
                    watch_ms = 1500
                    tags = [tag for tag in (video.tags or []) if tag != "seed"]
                    context = {"hashtag": tags[0] if tags else video.category}
                else:
                    event_type = "heartbeat"
                    watch_ms = rng.randint(3000, video.duration_ms)
                event = {
                    "user_id": person.id,
                    "session_id": f"sim-{person.id}-{_day}",
                    "video_id": video.id,
                    "event_type": event_type,
                    "ts": datetime.now(timezone.utc),
                    "watch_ms": watch_ms,
                    "duration_ms": video.duration_ms,
                    "completion_ratio": watch_ms / max(video.duration_ms, 1),
                    "loop_count": 1 if event_type == "replay" else 0,
                    "feed_position": step,
                    "is_ad": False,
                    "campaign_id": None,
                    "simulated": True,
                    "context": context,
                }
                await mongo.events.insert_one(event)
                profile = apply_event(
                    profile,
                    event,
                    video.embedding,
                    video.category,
                    video.audio_id,
                    list(video.tags or []),
                )
                written += 1
        await mongo.user_profiles_online.update_one(
            {"user_id": person.id}, {"$set": profile}, upsert=True
        )

    return {"events": written, "users": len(sample), "days": days}
