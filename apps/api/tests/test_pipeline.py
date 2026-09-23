from app.recsys.pipeline import rank_organic_feed
from app.recsys.types import PipelineConfig, UserFeatures, VideoCandidate
from app.recsys.vector import category_basis, video_embedding


def _video(idx: int, category: str, creator: str, audio: str, plays: int) -> VideoCandidate:
    ident = f"vid-{category}-{idx}"
    return VideoCandidate(
        id=ident,
        creator_id=creator,
        title=f"{category} {idx}",
        tags=[category],
        audio_id=audio,
        category=category,
        duration_ms=15000,
        status="active",
        play_count=plays,
        embedding=video_embedding(ident, category, audio),
        content_hash=ident,
    )


def test_new_user_gets_emerging_creator():
    catalog = []
    for i in range(12):
        catalog.append(_video(i, "comedia", f"c{i}", f"a{i}", 400))
    catalog.append(_video(99, "ciencia", "new-creator", "audio-x", 8))
    user = UserFeatures(user_id="u1", interest_vector=[], topic_affinity={}, audio_affinity={}, is_new=True)
    ranked, trace = rank_organic_feed(user, catalog, PipelineConfig(final_k=10, source_total=20))
    assert any(item.video.play_count < 100 for item in ranked)
    assert trace["explore_in_final"] >= 1


def test_inactive_video_is_not_scored():
    dead = _video(1, "musica", "c1", "a1", 20)
    dead.status = "inactive"
    live = _video(2, "musica", "c2", "a2", 20)
    user = UserFeatures(user_id="u1", interest_vector=category_basis("musica"), topic_affinity={"musica": 0.9}, audio_affinity={}, is_new=False)
    ranked, trace = rank_organic_feed(user, [dead, live], PipelineConfig(final_k=5, source_total=5))
    ids = {item.video.id for item in ranked}
    assert dead.id not in ids
    assert any(reason == "inactive" for _, reason in trace["dropped"])


def test_topic_source_uses_hashtag_overlap():
    from app.recsys.sources import source_topic

    tagged = _video(1, "ciencia", "c1", "a1", 10)
    tagged.tags = ["laboratorio"]
    other = _video(2, "ciencia", "c2", "a2", 10)
    other.tags = ["otro"]
    user = UserFeatures(
        user_id="u1",
        interest_vector=category_basis("ciencia"),
        topic_affinity={"ciencia": 0.2, "laboratorio": 0.9},
        audio_affinity={},
        is_new=False,
    )
    ranked = source_topic(user, [other, tagged], 2)
    assert ranked[0][0].id == tagged.id


def test_seen_catalog_recycles_instead_of_empty_feed():
    catalog = [_video(i, "comedia", f"c{i}", f"a{i}", 40) for i in range(12)]
    seen = [video.id for video in catalog]
    user = UserFeatures(
        user_id="u1",
        interest_vector=category_basis("comedia"),
        topic_affinity={"comedia": 0.8},
        audio_affinity={},
        recent_video_ids=seen,
        is_new=False,
    )
    ranked, trace = rank_organic_feed(user, catalog, PipelineConfig(final_k=6, source_total=12, rank_keep=12))
    assert len(ranked) >= 4
    assert trace["recycled"] >= 4
    recent8 = set(seen[:8])
    assert all(item.video.id not in recent8 for item in ranked)


def test_diversity_avoids_same_audio_in_a_row():
    catalog = [
        _video(1, "baile", "c1", "same-audio", 50),
        _video(2, "baile", "c2", "same-audio", 51),
        _video(3, "ciencia", "c3", "other-audio", 52),
        _video(4, "cocina", "c4", "third-audio", 53),
        _video(5, "arte", "c5", "fourth-audio", 54),
    ]
    user = UserFeatures(
        user_id="u1",
        interest_vector=category_basis("baile"),
        topic_affinity={"baile": 1, "ciencia": 0.4, "cocina": 0.4, "arte": 0.4},
        audio_affinity={"same-audio": 0.9},
        is_new=False,
    )
    ranked, _ = rank_organic_feed(user, catalog, PipelineConfig(final_k=4, source_total=8, rank_keep=8))
    for left, right in zip(ranked, ranked[1:]):
        same_audio = left.video.audio_id == right.video.audio_id
        same_creator = left.video.creator_id == right.video.creator_id
        if same_audio or same_creator:
            assert "diversity_fallback" in right.reasons


def test_ineligible_and_duplicate_clips_do_not_consume_retrieval_quota():
    inactive = [_video(i, "comedia", f"dead-{i}", f"dead-a{i}", 1000 - i) for i in range(5)]
    for video in inactive:
        video.status = "inactive"
    active = [_video(i + 10, "ciencia", f"live-{i}", f"live-a{i}", 100 - i) for i in range(5)]
    duplicate = _video(99, "ciencia", "duplicate", "duplicate-a", 90)
    duplicate.content_hash = active[0].content_hash
    user = UserFeatures(user_id="viewer", interest_vector=[], topic_affinity={}, audio_affinity={}, is_new=True)
    ranked, trace = rank_organic_feed(
        user, [*inactive, *active, duplicate], PipelineConfig(final_k=4, source_total=5, rank_keep=5)
    )
    assert len(ranked) == 4
    assert trace["recycled"] == 0
    assert len({row.video.content_hash for row in ranked}) == 4
    assert any(reason == "inactive" for _, reason in trace["dropped"])
    assert (duplicate.id, "duplicate") in trace["dropped"]
