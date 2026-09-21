from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, Video
from app.recsys.types import UserFeatures, VideoCandidate
from app.recsys.vector import video_embedding


async def load_catalog(db: AsyncSession) -> list[Video]:
    result = await db.execute(select(Video).options(selectinload(Video.creator)))
    return list(result.scalars())


def to_candidate(video: Video) -> VideoCandidate:
    embedding = video.embedding or video_embedding(video.id, video.category, video.audio_id)
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
        embedding=embedding,
        age_restricted=video.age_restricted,
        content_hash=video.content_hash,
    )


def features_from_profile(user: User, profile: dict, blocked: list[str]) -> UserFeatures:
    vector = profile.get("interest_vector") or []
    return UserFeatures(
        user_id=user.id,
        interest_vector=vector,
        topic_affinity=dict(profile.get("topic_affinity") or {}),
        audio_affinity=dict(profile.get("audio_affinity") or {}),
        recent_video_ids=list(profile.get("recent_video_ids") or []),
        session_video_ids=[],
        blocked_creator_ids=blocked,
        age=user.age,
        is_new=not vector,
    )
