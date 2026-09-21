from app.recsys.vector import cosine, video_embedding
from app.telemetry.profile import apply_event, empty_profile


def test_skip_moves_interest_away_from_video():
    video_vec = video_embedding("vid-1", "comedia", "audio-1")
    profile = empty_profile("user-1")
    profile["interest_vector"] = video_vec
    before = cosine(profile["interest_vector"], video_vec)
    apply_event(
        profile,
        {"event_type": "skip", "watch_ms": 800, "duration_ms": 15000, "video_id": "vid-1"},
        video_vec,
        "comedia",
        "audio-1",
    )
    after = cosine(profile["interest_vector"], video_vec)
    assert after < before


def test_like_increases_topic_affinity():
    profile = empty_profile("user-1")
    apply_event(
        profile,
        {"event_type": "like", "watch_ms": 12000, "duration_ms": 15000, "video_id": "vid-2"},
        video_embedding("vid-2", "ciencia", "audio-2"),
        "ciencia",
        "audio-2",
        ["laboratorio", "seed"],
    )
    assert profile["topic_affinity"]["ciencia"] > 0
    assert profile["topic_affinity"]["laboratorio"] == profile["topic_affinity"]["ciencia"]
    assert "seed" not in profile["topic_affinity"]
    assert "vid-2" in profile["recent_video_ids"]


def test_comment_share_follow_have_distinct_affinity_deltas():
    vec = video_embedding("vid-3", "musica", "audio-3")
    tags = ["corto"]
    for event_type, expected in (("comment", 0.07), ("share", 0.09), ("follow", 0.05)):
        profile = empty_profile("user-1")
        apply_event(
            profile,
            {"event_type": event_type, "watch_ms": 8000, "duration_ms": 15000, "video_id": "vid-3"},
            vec,
            "musica",
            "audio-3",
            tags,
        )
        assert abs(profile["topic_affinity"]["musica"] - expected) < 1e-9
        assert abs(profile["topic_affinity"]["corto"] - expected) < 1e-9
        assert profile["interest_vector"]


def test_hashtag_tap_boosts_tag_more_than_category():
    profile = empty_profile("user-1")
    apply_event(
        profile,
        {
            "event_type": "hashtag_tap",
            "watch_ms": 400,
            "duration_ms": 15000,
            "video_id": "vid-4",
            "context": {"hashtag": "laboratorio"},
        },
        video_embedding("vid-4", "ciencia", "audio-4"),
        "ciencia",
        "audio-4",
        ["laboratorio"],
    )
    assert profile["topic_affinity"]["laboratorio"] > profile["topic_affinity"]["ciencia"]
    assert abs(profile["topic_affinity"]["laboratorio"] - 0.10) < 1e-9


def test_skip_lowers_hashtag_affinity():
    profile = empty_profile("user-1")
    profile["topic_affinity"] = {"ciencia": 0.5, "corto": 0.4}
    apply_event(
        profile,
        {"event_type": "skip", "watch_ms": 800, "duration_ms": 15000, "video_id": "vid-5"},
        video_embedding("vid-5", "ciencia", "audio-5"),
        "ciencia",
        "audio-5",
        ["corto"],
    )
    assert profile["topic_affinity"]["ciencia"] == 0.44
    assert abs(profile["topic_affinity"]["corto"] - 0.34) < 1e-9


def test_comment_open_does_not_move_vector():
    profile = empty_profile("user-1")
    apply_event(
        profile,
        {"event_type": "comment_open", "watch_ms": 0, "duration_ms": 15000, "video_id": "vid-6"},
        video_embedding("vid-6", "arte", "audio-6"),
        "arte",
        "audio-6",
        ["veta"],
    )
    apply_event(
        profile,
        {"event_type": "share_open", "watch_ms": 0, "duration_ms": 15000, "video_id": "vid-6"},
        video_embedding("vid-6", "arte", "audio-6"),
        "arte",
        "audio-6",
        ["veta"],
    )
    assert profile["topic_affinity"] == {}
    assert profile["interest_vector"] == []
    assert profile["counters_24h"]["comment_opens"] == 1
    assert profile["counters_24h"]["share_opens"] == 1
