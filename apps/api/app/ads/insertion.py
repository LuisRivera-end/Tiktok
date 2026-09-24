from __future__ import annotations

from app.ads.auction import run_auction
from app.ads.types import AdCandidate, InsertionPolicy
from app.recsys.types import ScoredCandidate, UserFeatures


def insert_ads(
    organic: list[ScoredCandidate],
    user: UserFeatures,
    ads: list[AdCandidate],
    policy: InsertionPolicy | None = None,
    recent_campaigns: list[str] | None = None,
) -> list[dict]:
    cfg = policy or InsertionPolicy()
    recent = list(recent_campaigns or [])
    feed: list[dict] = [
        {
            "kind": "organic",
            "video_id": item.video.id,
            "campaign_id": None,
            "creative_id": None,
            "source": item.source,
            "scores": {
                "y1": item.y1,
                "y2": item.y2,
                "y3": item.y3,
                "y4": item.y4,
                "y5": item.y5,
                "final": item.score,
            },
            "reasons": item.reasons,
            "predictions": item.predictions,
            "model_version": item.model_version,
        }
        for item in organic
    ]

    inserted = 0
    last_ad_at = -cfg.min_organic_between
    start = max(cfg.first_ad_min_position - 1, 0)
    cursor = start
    pool = list(ads)

    while inserted < cfg.max_ads_per_pack and cursor <= len(feed):
        if cursor - last_ad_at < cfg.min_organic_between and last_ad_at >= 0:
            cursor += 1
            continue
        winner = run_auction(user, pool, cfg, recent)
        if winner is None:
            break
        feed.insert(
            cursor,
            {
                "kind": "ad",
                "video_id": winner.ad.video_id,
                "campaign_id": winner.ad.campaign_id,
                "creative_id": winner.ad.creative_id,
                "source": "auction",
                "scores": {"ecpm": winner.ecpm, "quality": winner.quality, "p_click": winner.ad.p_click},
                "reasons": ["auction", "retention_gate"],
                "landing_url": winner.ad.landing_url,
                "bid_cents": winner.ad.bid_cents,
                "predictions": {"p_click": winner.ad.p_click, **winner.ad.predictions},
                "model_version": winner.ad.model_version,
                "selection_probability": winner.selection_probability,
                "selection_policy": winner.policy,
                "eligible_candidates": winner.eligible_ids,
            },
        )
        recent.append(winner.ad.campaign_id)
        pool = [ad for ad in pool if ad.campaign_id != winner.ad.campaign_id]
        last_ad_at = cursor
        inserted += 1
        cursor += cfg.min_organic_between + 1
    return feed
