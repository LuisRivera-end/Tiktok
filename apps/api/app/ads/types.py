from dataclasses import dataclass, field


@dataclass
class AdCandidate:
    campaign_id: str
    creative_id: str
    video_id: str
    bid_cents: int
    daily_budget_cents: int
    spent_today_cents: int
    targeting_tags: list[str]
    targeting_categories: list[str]
    status: str = "active"
    impressions_last_hour: int = 0
    p_click: float = 0.08
    p_skip: float = 0.18
    p_complete: float = 0.42
    p_post_retention: float = 0.7


@dataclass
class AuctionWinner:
    ad: AdCandidate
    ecpm: float
    quality: float


@dataclass
class InsertionPolicy:
    first_ad_min_position: int = 3
    min_organic_between: int = 6
    max_ads_per_pack: int = 2
    session_abandon_threshold: float = 0.62
    frequency_cap_hour: int = 8
