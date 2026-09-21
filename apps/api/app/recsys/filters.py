from __future__ import annotations

from app.recsys.types import UserFeatures, VideoCandidate

DENYLIST = {"spam", "clickbait-extremo", "prohibido"}


def filter_reason(user: UserFeatures, video: VideoCandidate, *, allow_seen: bool = False) -> str | None:
    if video.status != "active":
        return "inactive"
    if video.creator_id == user.user_id:
        return "self"
    if not allow_seen and (video.id in user.recent_video_ids or video.id in user.session_video_ids):
        return "already_seen"
    if video.creator_id in user.blocked_creator_ids:
        return "blocked"
    if video.age_restricted and user.age < 18:
        return "age_gate"
    tags = {tag.lower() for tag in video.tags}
    if tags & DENYLIST:
        return "denylist"
    return None


def apply_filters(
    user: UserFeatures, candidates: list[tuple[VideoCandidate, str]]
) -> tuple[list[tuple[VideoCandidate, str]], list[tuple[str, str]]]:
    kept: list[tuple[VideoCandidate, str]] = []
    dropped: list[tuple[str, str]] = []
    seen_hash: set[str] = set()
    for video, source in candidates:
        reason = filter_reason(user, video)
        if reason:
            dropped.append((video.id, reason))
            continue
        if video.content_hash and video.content_hash in seen_hash:
            dropped.append((video.id, "duplicate"))
            continue
        if video.content_hash:
            seen_hash.add(video.content_hash)
        kept.append((video, source))
    return kept, dropped
