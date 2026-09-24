from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, Video
from app.recsys.types import UserFeatures, VideoCandidate
from app.recsys.vector import video_embedding

WATCH_TYPES = {"play", "heartbeat", "complete", "skip"}


async def load_catalog(db: AsyncSession) -> list[Video]:
    result = await db.execute(select(Video).options(selectinload(Video.creator)))
    return list(result.scalars())


def skip_rates_by_video(events: Iterable[dict]) -> dict[str, float]:
    """Observed early-skip rate: skips under 2s divided by watch-like events."""
    plays: dict[str, int] = {}
    early: dict[str, int] = {}
    for event in events:
        video_id = event.get("video_id")
        if not video_id:
            continue
        event_type = str(event.get("event_type") or "")
        if event_type not in WATCH_TYPES:
            continue
        plays[video_id] = plays.get(video_id, 0) + 1
        watch_ms = int(event.get("watch_ms") or 0)
        if event_type == "skip" and watch_ms < 2000:
            early[video_id] = early.get(video_id, 0) + 1
    return {video_id: early.get(video_id, 0) / count for video_id, count in plays.items() if count}


def to_candidate(video: Video, *, skip_rate: float | None = None) -> VideoCandidate:
    embedding = video.embedding or video_embedding(video.id, video.category, video.audio_id)
    if skip_rate is None:
        rate = float(getattr(video, "skip_rate", 0.0) or 0.0)
    else:
        rate = float(skip_rate)
    return VideoCandidate(
        id=video.id,
        creator_id=video.creator_id,
        title=video.title,
        tags=list(video.tags or []),
        audio_id=video.audio_id,
        category=video.category,
        duration_ms=video.duration_ms,
        status=video.status,
        play_count=video.play_count,
        embedding=list(embedding),
        age_restricted=bool(getattr(video, "age_restricted", False)),
        content_hash=str(getattr(video, "content_hash", "") or ""),
        skip_rate=rate,
        region=str(getattr(video, "region", "") or ""),
    )


def features_from_profile(
    user: User,
    profile: dict,
    blocked: list[str],
    followees: list[str] | None = None,
) -> UserFeatures:
    vector = profile.get("interest_vector") or []
    return UserFeatures(
        user_id=user.id,
        interest_vector=vector,
        topic_affinity=dict(profile.get("topic_affinity") or {}),
        audio_affinity=dict(profile.get("audio_affinity") or {}),
        recent_video_ids=list(profile.get("recent_video_ids") or []),
        session_video_ids=[],
        blocked_creator_ids=blocked,
        followed_creator_ids=list(followees or []),
        age=user.age,
        is_new=not vector,
        region=str(getattr(user, "region", "") or ""),
        gender=str(getattr(user, "gender", "unspecified") or "unspecified"),
    )


def catalog_for_lane(
    catalog: list[VideoCandidate],
    followees: Iterable[str],
    lane: str,
) -> list[VideoCandidate]:
    if lane not in {"following", "friends"}:
        return catalog
    allowed = set(followees)
    return [item for item in catalog if item.creator_id in allowed]
