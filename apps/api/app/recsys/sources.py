from __future__ import annotations

from app.recsys.types import PipelineConfig, UserFeatures, VideoCandidate
from app.recsys.vector import cosine


def _take_unique(items: list[VideoCandidate], seen: set[str], limit: int) -> list[VideoCandidate]:
    picked: list[VideoCandidate] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        picked.append(item)
        if len(picked) >= limit:
            break
    return picked


def source_vector(
    user: UserFeatures, catalog: list[VideoCandidate], limit: int
) -> list[tuple[VideoCandidate, str]]:
    if user.is_new or not user.interest_vector:
        return []
    ranked = sorted(catalog, key=lambda video: cosine(user.interest_vector, video.embedding), reverse=True)
    return [(video, "vector") for video in ranked[:limit]]


def source_topic(
    user: UserFeatures, catalog: list[VideoCandidate], limit: int
) -> list[tuple[VideoCandidate, str]]:
    def topic_score(video: VideoCandidate) -> float:
        cat = user.topic_affinity.get(video.category, 0.0)
        audio = user.audio_affinity.get(video.audio_id, 0.0)
        tags = [tag for tag in video.tags if tag and tag != "seed"]
        overlap = sum(1 for tag in tags if tag in user.topic_affinity) / max(len(tags), 1)
        return cat * 0.55 + audio * 0.25 + overlap * 0.20

    ranked = sorted(catalog, key=topic_score, reverse=True)
    return [(video, "topic") for video in ranked[:limit]]


def source_explore(
    catalog: list[VideoCandidate], limit: int, play_count_max: int
) -> list[tuple[VideoCandidate, str]]:
    emerging = [video for video in catalog if video.play_count < play_count_max]
    emerging.sort(key=lambda video: (video.play_count, video.id))
    return [(video, "explore") for video in emerging[:limit]]


def gather_candidates(
    user: UserFeatures, catalog: list[VideoCandidate], config: PipelineConfig
) -> list[tuple[VideoCandidate, str]]:
    n = min(config.source_total, max(len(catalog), 1))
    vector_n = max(1, round(n * config.vector_ratio))
    topic_n = max(1, round(n * config.topic_ratio))
    explore_n = max(1, n - vector_n - topic_n)

    seen: set[str] = set()
    ordered: list[tuple[VideoCandidate, str]] = []

    def absorb(batch: list[tuple[VideoCandidate, str]], cap: int) -> None:
        unique = _take_unique([item[0] for item in batch], seen, cap)
        source = batch[0][1] if batch else "vector"
        ordered.extend((video, source) for video in unique)

    if user.is_new or not user.interest_vector:
        popular = sorted(catalog, key=lambda video: video.play_count, reverse=True)
        absorb([(video, "popular") for video in popular], vector_n + topic_n)
    else:
        absorb(source_vector(user, catalog, vector_n * 2), vector_n)
        absorb(source_topic(user, catalog, topic_n * 2), topic_n)

    absorb(source_explore(catalog, explore_n * 3, config.explore_play_count_max), explore_n)
    return ordered
