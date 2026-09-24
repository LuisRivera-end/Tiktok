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
    targeting_genders: list[str] = field(default_factory=list)
    mature_exposures: int = 100
    landing_url: str = ""
    model_version: str = "smoothed-ctr-v1"
    predictions: dict[str, float] = field(default_factory=dict)


@dataclass
class AuctionWinner:
    ad: AdCandidate
    ecpm: float
    quality: float
    selection_probability: float = 1.0
    policy: str = "value"
    eligible_ids: list[str] = field(default_factory=list)


@dataclass
class InsertionPolicy:
    first_ad_min_position: int = 3
    min_organic_between: int = 6
    max_ads_per_pack: int = 2
    session_abandon_threshold: float = 0.62
    frequency_cap_hour: int = 8
    exploration_rate: float = 0.1
