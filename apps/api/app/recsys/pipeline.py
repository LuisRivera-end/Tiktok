from __future__ import annotations

from app.recsys.diversity import diversify
from app.recsys.filters import apply_filters, filter_reason
from app.recsys.scorer import score_candidate
from app.recsys.sources import gather_candidates
from app.recsys.types import PipelineConfig, ScoredCandidate, UserFeatures, VideoCandidate


def rank_organic_feed(
    user: UserFeatures,
    catalog: list[VideoCandidate],
    config: PipelineConfig | None = None,
) -> tuple[list[ScoredCandidate], dict]:
    cfg = config or PipelineConfig()
    sourced = gather_candidates(user, catalog, cfg)
    kept, dropped = apply_filters(user, sourced)
    recycled = 0
    if len(kept) < cfg.final_k:
        kept, extra_dropped, recycled = _recycle_seen(user, catalog, kept, cfg.final_k)
        dropped.extend(extra_dropped)
    scored = [score_candidate(user, video, source, cfg) for video, source in kept]
    scored.sort(key=lambda item: item.score, reverse=True)
    top = scored[: cfg.rank_keep]
    final = diversify(top, cfg.final_k)

    explore_count = sum(1 for item in final if item.source == "explore")
    trace = {
        "sourced": len(sourced),
        "kept": len(kept),
        "dropped": dropped[:40],
        "scored": len(scored),
        "final": len(final),
        "explore_in_final": explore_count,
        "recycled": recycled,
    }
    return final, trace


def _recycle_seen(
    user: UserFeatures,
    catalog: list[VideoCandidate],
    kept: list[tuple[VideoCandidate, str]],
    need: int,
) -> tuple[list[tuple[VideoCandidate, str]], list[tuple[str, str]], int]:
    """Small lab catalogs empty out once recent_video_ids hits ~80. Reuse older clips, skip the last 8."""
    kept_ids = {video.id for video, _ in kept}
    still_fresh = set(user.recent_video_ids[:8]) | set(user.session_video_ids[:8])
    extra_dropped: list[tuple[str, str]] = []
    recycled = 0
    filled = list(kept)
    for video in catalog:
        if len(filled) >= need:
            break
        if video.id in kept_ids:
            continue
        if video.id in still_fresh:
            extra_dropped.append((video.id, "still_fresh"))
            continue
        reason = filter_reason(user, video, allow_seen=True)
        if reason:
            extra_dropped.append((video.id, reason))
            continue
        filled.append((video, "recycle"))
        kept_ids.add(video.id)
        recycled += 1
    return filled, extra_dropped, recycled
