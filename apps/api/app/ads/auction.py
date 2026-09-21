from __future__ import annotations

from app.ads.types import AdCandidate, AuctionWinner, InsertionPolicy
from app.recsys.types import UserFeatures


def is_targeted(user: UserFeatures, ad: AdCandidate) -> bool:
    if not ad.targeting_categories and not ad.targeting_tags:
        return True
    cats = set(ad.targeting_categories)
    if cats and any(user.topic_affinity.get(cat, 0) >= 0.08 for cat in cats):
        return True
    if cats and user.is_new:
        return True
    tags = set(ad.targeting_tags)
    return bool(tags and set(user.topic_affinity) & tags)


def passes_filters(ad: AdCandidate, policy: InsertionPolicy, recent_campaigns: list[str]) -> str | None:
    if ad.status != "active":
        return "inactive"
    if ad.spent_today_cents + max(ad.bid_cents, 1) > ad.daily_budget_cents:
        return "no_budget"
    if ad.impressions_last_hour >= policy.frequency_cap_hour:
        return "frequency_cap"
    if ad.campaign_id in recent_campaigns:
        return "session_repeat"
    return None


def quality_score(ad: AdCandidate) -> float:
    return 0.4 * ad.p_complete + 0.3 * (1.0 - ad.p_skip) + 0.3 * ad.p_post_retention


def ecpm(ad: AdCandidate) -> float:
    return ad.bid_cents * ad.p_click * quality_score(ad)


def session_abandon_risk(ad: AdCandidate) -> float:
    return min(1.0, 0.35 * ad.p_skip + 0.4 * (1 - ad.p_post_retention) + 0.1)


def run_auction(
    user: UserFeatures,
    ads: list[AdCandidate],
    policy: InsertionPolicy,
    recent_campaigns: list[str],
) -> AuctionWinner | None:
    eligible: list[AuctionWinner] = []
    for ad in ads:
        reason = passes_filters(ad, policy, recent_campaigns)
        if reason:
            continue
        if not is_targeted(user, ad):
            continue
        if session_abandon_risk(ad) > policy.session_abandon_threshold:
            continue
        eligible.append(AuctionWinner(ad=ad, ecpm=ecpm(ad), quality=quality_score(ad)))
    if not eligible:
        return None
    eligible.sort(key=lambda item: item.ecpm, reverse=True)
    return eligible[0]
