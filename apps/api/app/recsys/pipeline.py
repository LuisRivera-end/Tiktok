from __future__ import annotations

from app.recsys.diversity import diversify
from app.recsys.filters import apply_filters, filter_reason
from app.recsys.scorer import score_candidate
from app.recsys.sources import gather_candidates
from app.recsys.types import (
    PipelineConfig,
    ScoredCandidate,
    UserFeatures,
    VideoCandidate,
    normalized_region,
)


def rank_organic_feed(
    user: UserFeatures,
    catalog: list[VideoCandidate],
    config: PipelineConfig | None = None,
) -> tuple[list[ScoredCandidate], dict]:
    cfg = config or PipelineConfig()
    # Filter before retrieval: an inactive, blocked or recently seen clip must
    # never consume a source quota that could hold an eligible candidate.
    eligible: list[VideoCandidate] = []
    dropped: list[tuple[str, str]] = []
    eligible_hashes: set[str] = set()
    for video in catalog:
        reason = filter_reason(user, video)
        if reason:
            dropped.append((video.id, reason))
        elif video.content_hash and video.content_hash in eligible_hashes:
            dropped.append((video.id, "duplicate"))
        else:
            eligible.append(video)
            if video.content_hash:
                eligible_hashes.add(video.content_hash)
    sourced = gather_candidates(user, eligible, cfg)
    kept, duplicate_drops = apply_filters(user, sourced)
    dropped.extend(duplicate_drops)
    recycled = 0
    if len(kept) < cfg.final_k:
        kept, extra_dropped, recycled = _recycle_seen(user, catalog, kept, cfg.final_k)
        dropped.extend(extra_dropped)
    scored = [score_candidate(user, video, source, cfg) for video, source in kept]
    scored.sort(key=lambda item: item.score, reverse=True)
    top = scored[: cfg.rank_keep]
    final = diversify(top, cfg.final_k)
    final = _ensure_same_region(user, catalog, final, cfg)

    explore_count = sum(1 for item in final if item.source == "explore")
    trace = {
        "sourced": len(sourced),
        "kept": len(kept),
        "dropped": dropped[:40],
        "scored": len(scored),
        "final": len(final),
        "explore_in_final": explore_count,
        "recycled": recycled,
        "candidate_ids": [video.id for video, _source in kept],
    }
    return final, trace


def _ensure_same_region(
    user: UserFeatures,
    catalog: list[VideoCandidate],
    final: list[ScoredCandidate],
    cfg: PipelineConfig,
) -> list[ScoredCandidate]:
    """Keep one eligible same-region clip in For You without dropping a stronger finish."""
    region = normalized_region(user.region)
    if not region or not final:
        return final
    if any(normalized_region(item.video.region) == region for item in final):
        return final
    fresh = set(user.recent_video_ids[:8]) | set(user.session_video_ids[:8])
    present = {item.video.id for item in final}
    present_hashes = {item.video.content_hash for item in final if item.video.content_hash}
    best: ScoredCandidate | None = None
    for video in catalog:
        if normalized_region(video.region) != region or video.id in present or video.id in fresh:
            continue
        if video.content_hash and video.content_hash in present_hashes:
            continue
        if filter_reason(user, video, allow_seen=True):
            continue
        scored = score_candidate(user, video, "region", cfg)
        if best is None or scored.score > best.score:
            best = scored
    if best is None:
        return final
    if len(final) < cfg.final_k:
        final.append(best)
        return final
    if cfg.final_k <= 1:
        if best.score >= final[0].score:
            final[0] = best
        return final
    weakest = min(range(len(final)), key=lambda index: final[index].score)
    final[weakest] = best
    return final


def _recycle_seen(
    user: UserFeatures,
    catalog: list[VideoCandidate],
    kept: list[tuple[VideoCandidate, str]],
    need: int,
) -> tuple[list[tuple[VideoCandidate, str]], list[tuple[str, str]], int]:
    """Small lab catalogs empty out once recent_video_ids hits ~80. Reuse older clips, skip the last 8."""
    kept_ids = {video.id for video, _ in kept}
    kept_hashes = {video.content_hash for video, _ in kept if video.content_hash}
    still_fresh = set(user.recent_video_ids[:8]) | set(user.session_video_ids[:8])
    extra_dropped: list[tuple[str, str]] = []
    recycled = 0
    filled = list(kept)
    for video in catalog:
        if len(filled) >= need:
            break
        if video.id in kept_ids:
            continue
        if video.content_hash and video.content_hash in kept_hashes:
            extra_dropped.append((video.id, "duplicate"))
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
        if video.content_hash:
            kept_hashes.add(video.content_hash)
        recycled += 1
    return filled, extra_dropped, recycled
