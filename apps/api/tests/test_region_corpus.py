import csv
import io
from datetime import date, datetime, timezone
from pathlib import Path

from app.recsys.pipeline import rank_organic_feed
from app.recsys.types import PipelineConfig
from app.recsys.vector import CATEGORIES, category_basis, video_embedding
from app.seed import PASSWORD
from app.services.catalog import (
    catalog_for_lane,
    features_from_profile,
    skip_rates_by_video,
    to_candidate,
)
from app.services.corpus import (
    DEMO_REGIONS,
    LAB_SIM_DAYS,
    LAB_SIM_EVENTS_PER_USER,
    LAB_SIM_USERS,
    REGIONS,
    build_orange_csv,
    dashboard_slice,
    daily_breakdown,
    generate_events,
    injection_plan,
    metrics_from_events,
    orange_pass,
    pending_injection,
    planned_population,
)
from app.telemetry.profile import empty_profile

ROOT = Path(__file__).resolve().parents[3]


class _Account:
    def __init__(self, user_id: str, region: str | None = "", age: int = 22):
        self.id = user_id
        self.region = region
        self.age = age


class _Clip:
    def __init__(
        self,
        video_id: str,
        *,
        region: str | None,
        creator_id: str = "creator",
        category: str = "musica",
        audio_id: str = "audio-musica",
        play_count: int = 40,
        embedding: list[float] | None = None,
        status: str = "active",
    ):
        self.id = video_id
        self.creator_id = creator_id
        self.title = video_id
        self.tags = [category, "laboratorio"]
        self.audio_id = audio_id
        self.category = category
        self.duration_ms = 15000
        self.status = status
        self.play_count = play_count
        self.embedding = embedding if embedding is not None else video_embedding(video_id, category, audio_id)
        self.age_restricted = False
        self.content_hash = video_id
        self.region = region


def _features(region: str | None, *, interest: str | None = None, followees: list[str] | None = None):
    profile = empty_profile("viewer")
    if interest:
        profile["interest_vector"] = category_basis(interest)
        profile["topic_affinity"] = {interest: 0.9}
        profile["audio_affinity"] = {f"audio-{interest}": 0.4}
    return features_from_profile(_Account("viewer", region), profile, [], followees=followees or [])


def _pair(region_a: str, region_b: str, *, embedding: list[float], category: str = "musica"):
    audio = f"audio-{category}"
    left = to_candidate(_Clip("left", region=region_a, category=category, audio_id=audio, embedding=embedding))
    right = to_candidate(_Clip("right", region=region_b, category=category, audio_id=audio, embedding=embedding))
    return [right, left]


def test_same_region_scores_above_an_equal_clip():
    embedding = video_embedding("shared-region", "musica", "audio-musica")
    features = _features("México", interest="musica")
    catalog = _pair("México", "Chile", embedding=embedding)
    ranked, _ = rank_organic_feed(features, catalog, PipelineConfig(final_k=2, source_total=4, rank_keep=4))
    assert ranked[0].video.region == "México"
    assert ranked[0].score > ranked[1].score
    assert "same_region" in ranked[0].reasons


def test_cold_start_region_breaks_a_popularity_tie():
    embedding = video_embedding("shared-cold", "ciencia", "audio-ciencia")
    features = _features("México")
    assert features.is_new
    same = _Clip("cold-same", region="México", category="ciencia", audio_id="audio-ciencia", play_count=80, embedding=embedding)
    other = _Clip("cold-other", region="Perú", category="ciencia", audio_id="audio-ciencia", play_count=80, embedding=embedding)
    ranked, _ = rank_organic_feed(
        features,
        [to_candidate(other), to_candidate(same)],
        PipelineConfig(final_k=2, source_total=4, rank_keep=4),
    )
    assert ranked[0].video.id == "cold-same"
    assert ranked[0].score > ranked[1].score


def test_empty_region_does_not_match_or_crash():
    embedding = video_embedding("shared-empty", "arte", "audio-arte")
    blank = _features("")
    named = _features("México")
    catalog = [
        to_candidate(_Clip("blank", region="", category="arte", audio_id="audio-arte", embedding=embedding)),
        to_candidate(_Clip("mx", region="México", category="arte", audio_id="audio-arte", embedding=embedding)),
        to_candidate(_Clip("cl", region="Chile", category="arte", audio_id="audio-arte", embedding=embedding)),
    ]
    config = PipelineConfig(final_k=3, source_total=6, rank_keep=6)
    blank_scores = {item.video.id: item.score for item in rank_organic_feed(blank, catalog, config)[0]}
    assert blank_scores["blank"] == blank_scores["mx"] == blank_scores["cl"]
    named_scores = {item.video.id: item.score for item in rank_organic_feed(named, catalog, config)[0]}
    assert named_scores["mx"] > named_scores["blank"]
    assert named_scores["blank"] == named_scores["cl"]

    account = _Account("viewer", None)
    clip = _Clip("none-region", region=None, category="arte", audio_id="audio-arte", embedding=embedding)
    features = features_from_profile(account, empty_profile("viewer"), [])
    ranked, _ = rank_organic_feed(features, [to_candidate(clip)], PipelineConfig(final_k=1, source_total=2, rank_keep=2))
    assert ranked
    assert "same_region" not in ranked[0].reasons


def test_other_regions_stay_eligible():
    features = _features("México")
    catalog = [
        to_candidate(_Clip(f"cl-{index}", region="Chile", creator_id=f"c{index}", play_count=50 + index, category="comedia", audio_id=f"a{index}"))
        for index in range(6)
    ]
    ranked, _ = rank_organic_feed(features, catalog, PipelineConfig(final_k=4, source_total=8, rank_keep=8))
    assert ranked
    assert all(item.video.region == "Chile" for item in ranked)


def test_for_you_includes_one_same_region_clip_when_retrieval_misses_it():
    features = _features("México")
    others = [
        _Clip(f"pop-{index}", region="Chile", creator_id=f"c{index}", play_count=400, category="comedia", audio_id=f"a{index}")
        for index in range(12)
    ]
    hidden = _Clip("local", region="México", creator_id="local-creator", play_count=400, category="comedia", audio_id="a-local")
    catalog = [to_candidate(video) for video in [*others, hidden]]
    ranked, _ = rank_organic_feed(features, catalog, PipelineConfig(final_k=4, source_total=5, rank_keep=5))
    assert any(item.video.region == "México" for item in ranked)
    assert any(item.video.region != "México" for item in ranked)


def test_inactive_same_region_clip_is_not_forced_in():
    features = _features("México")
    dead = _Clip("dead-local", region="México", status="inactive", play_count=10)
    live = _Clip("live-other", region="Chile", play_count=20, category="cine", audio_id="audio-cine")
    ranked, _ = rank_organic_feed(
        features,
        [to_candidate(dead), to_candidate(live)],
        PipelineConfig(final_k=2, source_total=4, rank_keep=4),
    )
    assert all(item.video.id != "dead-local" for item in ranked)


def test_observed_skip_rate_lowers_rank_through_the_candidate_builder():
    embedding = video_embedding("shared-skip", "musica", "audio-musica")
    high = _Clip("high-skip", region="Chile", embedding=embedding)
    low = _Clip("low-skip", region="Chile", embedding=embedding)
    events = [{"video_id": "high-skip", "event_type": "skip", "watch_ms": 400} for _ in range(8)]
    events += [{"video_id": "low-skip", "event_type": "complete", "watch_ms": 15000} for _ in range(8)]
    rates = skip_rates_by_video(events)
    catalog = [
        to_candidate(high, skip_rate=rates["high-skip"]),
        to_candidate(low, skip_rate=rates["low-skip"]),
    ]
    assert catalog[0].skip_rate > catalog[1].skip_rate
    features = _features("Argentina", interest="musica")
    ranked, _ = rank_organic_feed(features, catalog, PipelineConfig(final_k=2, source_total=4, rank_keep=4))
    by_id = {item.video.id: item for item in ranked}
    assert by_id["low-skip"].score > by_id["high-skip"].score


def test_finish_signal_beats_a_region_only_match():
    embedding = video_embedding("shared-finish", "musica", "audio-musica")
    same = _Clip("same-weak", region="México", embedding=embedding)
    other = _Clip("other-strong", region="Chile", embedding=embedding)
    events = [{"video_id": "same-weak", "event_type": "skip", "watch_ms": 300} for _ in range(10)]
    events += [{"video_id": "other-strong", "event_type": "complete", "watch_ms": 15000} for _ in range(10)]
    rates = skip_rates_by_video(events)
    catalog = [
        to_candidate(same, skip_rate=rates["same-weak"]),
        to_candidate(other, skip_rate=rates["other-strong"]),
    ]
    features = _features("México", interest="musica")
    ranked, _ = rank_organic_feed(features, catalog, PipelineConfig(final_k=2, source_total=4, rank_keep=4))
    by_id = {item.video.id: item for item in ranked}
    assert by_id["other-strong"].score > by_id["same-weak"].score
    assert "same_region" in by_id["same-weak"].reasons


def test_followed_creator_ranks_above_an_equal_stranger():
    embedding = video_embedding("shared-follow", "baile", "audio-baile")
    friend = to_candidate(
        _Clip("friend-clip", region="Argentina", creator_id="friend", category="baile", audio_id="audio-baile", embedding=embedding)
    )
    stranger = to_candidate(
        _Clip("stranger-clip", region="Argentina", creator_id="stranger", category="baile", audio_id="audio-baile", embedding=embedding)
    )
    features = _features("Colombia", interest="baile", followees=["friend"])
    assert features.followed_creator_ids == ["friend"]
    ranked, _ = rank_organic_feed(features, [stranger, friend], PipelineConfig(final_k=2, source_total=4, rank_keep=4))
    assert ranked[0].video.creator_id == "friend"
    assert any(item.video.creator_id == "stranger" for item in ranked)
    assert "followed" in ranked[0].reasons


def test_following_and_friends_show_only_followed_accounts():
    friend = to_candidate(_Clip("f", region="México", creator_id="friend"))
    stranger = to_candidate(_Clip("s", region="México", creator_id="stranger"))
    catalog = [friend, stranger]
    assert {item.creator_id for item in catalog_for_lane(catalog, ["friend"], "following")} == {"friend"}
    assert {item.creator_id for item in catalog_for_lane(catalog, ["friend"], "friends")} == {"friend"}
    assert {item.creator_id for item in catalog_for_lane(catalog, ["friend"], "foryou")} == {"friend", "stranger"}


def test_published_weights_and_abandon_penalty_still_apply():
    config = PipelineConfig()
    assert config.weights == (0.35, 0.30, 0.15, 0.12, 0.08)
    embedding = video_embedding("shared-penalty", "cocina", "audio-cocina")
    calm = _Clip("calm", region="México", creator_id="friend", category="cocina", audio_id="audio-cocina", embedding=embedding)
    harsh = _Clip("harsh", region="México", creator_id="friend", category="cocina", audio_id="audio-cocina", embedding=embedding)
    events = [{"video_id": "harsh", "event_type": "skip", "watch_ms": 200} for _ in range(6)]
    events += [{"video_id": "calm", "event_type": "complete", "watch_ms": 15000} for _ in range(6)]
    rates = skip_rates_by_video(events)
    catalog = [
        to_candidate(calm, skip_rate=rates.get("calm", 0.0)),
        to_candidate(harsh, skip_rate=rates["harsh"]),
    ]
    features = features_from_profile(_Account("viewer", "México"), empty_profile("viewer"), [], followees=["friend"])
    ranked, _ = rank_organic_feed(features, catalog, PipelineConfig(final_k=2, source_total=4, rank_keep=4))
    by_id = {item.video.id: item for item in ranked}
    assert "early_abandon_penalty" in by_id["harsh"].reasons
    assert "early_abandon_penalty" not in by_id["calm"].reasons
    assert by_id["calm"].score - by_id["harsh"].score >= config.severe_penalty


def _means(events: list[dict]) -> tuple[float, float]:
    same: list[float] = []
    cross: list[float] = []
    for event in events:
        user_region = event["user_region"]
        video_region = event["video_region"]
        if not user_region or not video_region:
            continue
        (same if user_region == video_region else cross).append(float(event["completion_ratio"]))
    return sum(same) / len(same), sum(cross) / len(cross)


def test_injection_plan_is_idempotent_and_covers_every_region():
    users, clips = injection_plan()
    assert len(REGIONS) >= 4
    assert {user.region for user in users} >= set(REGIONS)
    assert {clip.region for clip in clips} >= set(REGIONS)
    for region in REGIONS:
        assert any(user.region == region for user in users)
        assert any(clip.region == region for clip in clips)
    assert set(CATEGORIES) <= {clip.category for clip in clips}
    emails = {user.email for user in users}
    assert emails.isdisjoint(DEMO_REGIONS)
    assert PASSWORD == "veta1234"
    again_users, again_clips = pending_injection(emails, {clip.content_hash for clip in clips})
    assert again_users == []
    assert again_clips == []
    assert injection_plan() == (users, clips)


def test_generator_completion_gap_and_orange_csv():
    assert LAB_SIM_USERS * LAB_SIM_DAYS * LAB_SIM_EVENTS_PER_USER >= 2000
    actors, clips = planned_population()
    events = generate_events(
        actors,
        clips,
        users=LAB_SIM_USERS,
        days=LAB_SIM_DAYS,
        events_per_user=LAB_SIM_EVENTS_PER_USER,
    )
    assert len(events) >= 2000
    regions = {event["user_region"] for event in events} | {event["video_region"] for event in events}
    assert len(regions) >= 4
    assert set(REGIONS) <= regions
    same_mean, cross_mean = _means(events)
    assert same_mean >= cross_mean + 0.10

    decoded = build_orange_csv(events).encode("utf-8").decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    assert reader.fieldnames is not None
    for column in (
        "user_region",
        "video_region",
        "watch_ms",
        "duration_ms",
        "completion_ratio",
        "early_skip",
        "category",
        "event_type",
    ):
        assert column in reader.fieldnames
    rows = list(reader)
    assert len(rows) >= 2000
    assert {row["early_skip"] for row in rows} >= {"0", "1"}
    assert "México" in decoded

    report = metrics_from_events(events)
    rates = [row["completion_rate"] for row in report["regions"]]
    assert len(report["regions"]) >= 4
    assert len(set(rates)) > 1
    assert "retention_minutes" in report
    assert "completion_rate" in report
    assert "early_abandon_rate" in report


def test_early_skip_flag_is_only_a_short_skip():
    rows = [
        {"user_id": "u", "event_type": "skip", "watch_ms": 1999, "duration_ms": 15000, "completion_ratio": 0.1, "user_region": "México", "video_region": "México", "category": "musica"},
        {"user_id": "u", "event_type": "skip", "watch_ms": 2000, "duration_ms": 15000, "completion_ratio": 0.2, "user_region": "Chile", "video_region": "México", "category": "musica"},
        {"user_id": "u", "event_type": "complete", "watch_ms": 100, "duration_ms": 15000, "completion_ratio": 1, "user_region": "Chile", "video_region": "Chile", "category": "ciencia"},
        {"user_id": "u", "event_type": "heartbeat", "watch_ms": 100, "duration_ms": 15000, "completion_ratio": 0.01, "user_region": "México", "video_region": "Chile", "category": "ciencia"},
    ]
    parsed = list(csv.DictReader(io.StringIO(build_orange_csv(rows))))
    assert [row["early_skip"] for row in parsed] == ["1", "0", "0", "0"]


def test_orange_csv_keeps_event_order_fields_for_future_sequence_models():
    now = datetime(2026, 9, 23, 12, 30, tzinfo=timezone.utc)
    rows = [
        {"_id": "event-1", "ts": now, "user_id": "u", "video_id": "v",
         "session_id": "s", "event_type": "impression", "feed_position": 0},
        {"_id": "event-2", "ts": now, "user_id": "u", "video_id": "w",
         "session_id": "s", "event_type": "impression", "feed_position": 1},
    ]
    parsed = list(csv.DictReader(io.StringIO(build_orange_csv(rows))))
    assert [row["event_id"] for row in parsed] == ["event-1", "event-2"]
    assert [row["event_ts"] for row in parsed] == [now.isoformat(), now.isoformat()]
    assert [row["feed_position"] for row in parsed] == ["0", "1"]


def test_region_completion_moves_when_the_events_change():
    base = [
        {"user_id": "u1", "video_id": "a", "video_region": "México", "user_region": "México", "event_type": "complete", "watch_ms": 14000, "duration_ms": 15000, "completion_ratio": 0.9},
        {"user_id": "u2", "video_id": "a", "video_region": "México", "user_region": "México", "event_type": "complete", "watch_ms": 13000, "duration_ms": 15000, "completion_ratio": 0.8},
        {"user_id": "u1", "video_id": "b", "video_region": "Chile", "user_region": "Chile", "event_type": "skip", "watch_ms": 400, "duration_ms": 15000, "completion_ratio": 0.1},
    ]
    before = metrics_from_events(base)
    changed = [dict(base[0], completion_ratio=0.2), dict(base[1], completion_ratio=0.15), base[2]]
    after = metrics_from_events(changed)
    before_mx = next(row for row in before["regions"] if row["region"] == "México")
    after_mx = next(row for row in after["regions"] if row["region"] == "México")
    assert before_mx["completion_rate"] > after_mx["completion_rate"]
    assert before["regions"] != after["regions"]


def test_dashboard_rates_share_view_denominator_and_ignore_social_actions():
    events = [
        {"user_id": "u", "video_id": "a", "video_region": "México", "category": "arte", "event_type": "complete", "watch_ms": 12000, "duration_ms": 15000, "completion_ratio": 0.8},
        {"user_id": "u", "video_id": "b", "video_region": "México", "category": "arte", "event_type": "skip", "watch_ms": 500, "duration_ms": 15000, "completion_ratio": 0.1},
        {"user_id": "u", "video_id": "c", "video_region": "México", "category": "arte", "event_type": "skip", "watch_ms": 3000, "duration_ms": 15000, "completion_ratio": 0.5},
        {"user_id": "u", "video_id": "a", "video_region": "México", "category": "arte", "event_type": "like", "watch_ms": 0, "duration_ms": 15000, "completion_ratio": 0},
    ]
    report = dashboard_slice(events, "México", category="arte")
    assert report["events"] == 4
    assert report["views"] == 3
    assert report["completion_rate"] == report["focus"]["completion_rate"] == report["selected"]["completion_rate"] == 0.4667
    assert report["categories"][0]["completion_rate"] == 0.4667
    assert report["early_abandon_rate"] == report["focus"]["early_abandon_rate"] == 0.3333


def test_daily_breakdown_counts_events_and_deduplicated_playbacks():
    stamp = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
    base = {"user_id": "u", "video_id": "v", "session_id": "s", "feed_position": 1, "ts": stamp}
    rows = daily_breakdown([
        {**base, "event_type": "play", "watch_ms": 0},
        {**base, "event_type": "heartbeat", "watch_ms": 3000},
        {**base, "event_type": "complete", "watch_ms": 9000},
        {**base, "event_type": "like", "watch_ms": 0},
        {**base, "event_type": "impression", "ts": datetime(2026, 9, 16, 12, tzinfo=timezone.utc)},
    ], today=date(2026, 9, 24))
    assert len(rows) == 8
    assert rows[-1] == {"date": "2026-09-24", "events": 4, "views": 1}
    assert sum(row["events"] for row in rows) == 4


def test_one_real_playback_is_not_multiplied_by_its_events():
    base = {"user_id": "u", "session_id": "s", "video_id": "v", "feed_position": 2,
            "video_region": "México", "category": "arte", "duration_ms": 10000}
    events = [
        {**base, "event_type": "play", "watch_ms": 0, "completion_ratio": 0},
        {**base, "event_type": "like", "watch_ms": 3000, "completion_ratio": 0.3},
        {**base, "event_type": "complete", "watch_ms": 8000, "completion_ratio": 0.8},
    ]
    report = dashboard_slice(events, "México", category="arte")
    assert report["events"] == 3
    assert report["views"] == report["focus"]["views"] == 1
    assert report["completion_rate"] == 0.8
    assert report["retention_minutes"] == round(8000 / 60000, 2)

    # Older simulator passes reused session IDs; their batch timestamp keeps
    # separate runs from collapsing into one playback.
    simulated = [{**base, "event_type": "complete", "watch_ms": 8000,
                  "completion_ratio": 0.8, "simulated": True, "ts": stamp}
                 for stamp in ("run-1", "run-2")]
    assert dashboard_slice(simulated)["views"] == 2


def test_orange_pass_feeds_the_dashboard_slice():
    actors, clips = planned_population()
    events = orange_pass(actors, clips)
    assert 900 <= len(events) <= 1100
    regions = {event["user_region"] for event in events} | {event["video_region"] for event in events}
    assert len(regions) >= 4
    decoded = build_orange_csv(events).encode("utf-8").decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    assert reader.fieldnames is not None
    for column in ("user_region", "video_region", "early_skip"):
        assert column in reader.fieldnames
    rows = list(reader)
    assert 900 <= len(rows) <= 1100
    assert {row["early_skip"] for row in rows} >= {"0", "1"}

    mexico = dashboard_slice(events, "México")["selected"]
    chile = dashboard_slice(events, "Chile")["selected"]
    assert mexico["completion_rate"] != chile["completion_rate"] or mexico["retention_minutes"] != chile["retention_minutes"]
    changed = [
        dict(event, completion_ratio=0.05, watch_ms=500)
        if event.get("video_region") == "México"
        else event
        for event in events
    ]
    moved = dashboard_slice(changed, "México")["selected"]
    assert moved["completion_rate"] != mexico["completion_rate"]


def test_dashboard_cross_filter_recalculates_the_other_visual():
    actors, clips = planned_population()
    events = orange_pass(actors, clips)
    plain = dashboard_slice(events)
    mexico = dashboard_slice(events, "México")
    assert mexico["focus"]["events"] < plain["focus"]["events"]
    assert len(mexico["categories"]) > 1
    narrowed = dashboard_slice(events, "México", category="musica")
    assert narrowed["focus"]["events"] < mexico["focus"]["events"]
    assert narrowed["focus"]["category"] == "musica"
    assert len(narrowed["categories"]) > 1

    def region_events(report: dict, name: str) -> int:
        return next(row["events"] for row in report["regions"] if row["region"] == name)

    assert region_events(narrowed, "México") < region_events(plain, "México")
    changed = [
        dict(event, completion_ratio=0.01)
        if event.get("video_region") == "México" and event.get("category") == "musica"
        else event
        for event in events
    ]
    moved = dashboard_slice(changed, "México", category="musica")
    assert moved["focus"]["completion_rate"] != narrowed["focus"]["completion_rate"]


def test_lab_screen_and_orange_readme_follow_the_contract():
    lab = (ROOT / "apps/web/src/pages/Lab.tsx").read_text(encoding="utf-8")
    readme = (ROOT / "orange/README.md").read_text(encoding="utf-8")
    assert "users: 80" in lab
    assert "days: 5" in lab
    assert "events_per_user: 8" in lab
    assert "users: 25" in lab
    assert "orange-1000" in lab
    assert "metrics?.regions" in lab
    assert "metrics?.available_regions" in lab
    assert "metrics?.available_categories" in lab
    assert "<select" in lab
    assert "Extraer" in lab
    assert "Transformar" in lab
    assert "Cargar" in lab
    assert "Correlations" in lab
    assert "k = 4" in lab
    assert "58.7" not in lab
    assert "0.912" not in lab
    for token in (
        "user_region",
        "video_region",
        "watch_ms",
        "duration_ms",
        "completion_ratio",
        "early_skip",
        "category",
        "event_type",
        "File",
        "Correlations",
        "PCA",
        "k = 4",
    ):
        assert token in readme
    assert "58.7" not in readme
    assert "0.912" not in readme
