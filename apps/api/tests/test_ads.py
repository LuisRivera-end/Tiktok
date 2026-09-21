from app.ads.auction import ecpm, quality_score, run_auction
from app.ads.insertion import insert_ads
from app.ads.types import AdCandidate, InsertionPolicy
from app.recsys.scorer import score_candidate
from app.recsys.types import PipelineConfig, UserFeatures, VideoCandidate
from app.recsys.vector import category_basis


def _ad(**overrides) -> AdCandidate:
    base = dict(
        campaign_id="camp-1",
        creative_id="cr-1",
        video_id="ad-video",
        bid_cents=100,
        daily_budget_cents=5000,
        spent_today_cents=0,
        targeting_tags=[],
        targeting_categories=["ciencia"],
        p_click=0.2,
        p_skip=0.1,
        p_complete=0.5,
        p_post_retention=0.8,
    )
    base.update(overrides)
    return AdCandidate(**base)


def test_zero_budget_never_wins():
    user = UserFeatures(user_id="u", interest_vector=[], topic_affinity={"ciencia": 1}, audio_affinity={}, is_new=True)
    winner = run_auction(user, [_ad(daily_budget_cents=0)], InsertionPolicy(), [])
    assert winner is None


def test_high_skip_ad_is_vetoed():
    user = UserFeatures(user_id="u", interest_vector=[], topic_affinity={"ciencia": 1}, audio_affinity={}, is_new=True)
    risky = _ad(p_skip=0.95, p_post_retention=0.05, p_complete=0.05)
    winner = run_auction(user, [risky], InsertionPolicy(), [])
    assert winner is None


def test_ecpm_prefers_higher_quality_same_bid():
    weak = _ad(campaign_id="a", p_click=0.2, p_complete=0.1, p_skip=0.5, p_post_retention=0.2)
    strong = _ad(campaign_id="b", p_click=0.2, p_complete=0.8, p_skip=0.05, p_post_retention=0.9)
    assert ecpm(strong) > ecpm(weak)
    assert quality_score(strong) > quality_score(weak)


def test_insertion_keeps_first_slots_organic_and_preserves_explore():
    user = UserFeatures(
        user_id="u",
        interest_vector=category_basis("ciencia"),
        topic_affinity={"ciencia": 1},
        audio_affinity={},
        is_new=False,
    )
    organic = []
    for i in range(12):
        video = VideoCandidate(
            id=f"v{i}",
            creator_id=f"c{i}",
            title="t",
            tags=["ciencia"],
            audio_id=f"a{i}",
            category="ciencia",
            duration_ms=12000,
            status="active",
            play_count=5 if i == 0 else 200,
            embedding=category_basis("ciencia"),
        )
        item = score_candidate(user, video, "explore" if i == 0 else "vector", PipelineConfig())
        organic.append(item)
    feed = insert_ads(organic, user, [_ad()], InsertionPolicy(first_ad_min_position=3, min_organic_between=6, max_ads_per_pack=2))
    assert feed[0]["kind"] == "organic"
    assert feed[1]["kind"] == "organic"
    ad_positions = [idx + 1 for idx, row in enumerate(feed) if row["kind"] == "ad"]
    assert ad_positions
    assert min(ad_positions) >= 3
    assert any(row["source"] == "explore" for row in feed if row["kind"] == "organic")
