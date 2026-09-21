from __future__ import annotations

from datetime import datetime, timezone

from app.recsys.vector import blend, move_away

POSITIVE = {"complete", "replay", "like", "share", "ad_complete", "comment", "follow", "hashtag_tap"}
NEGATIVE = {"skip"}
LEARNING_RATES = {
    "complete": 0.08,
    "replay": 0.10,
    "like": 0.14,
    "share": 0.16,
    "comment": 0.12,
    "follow": 0.10,
    "hashtag_tap": 0.06,
    "ad_complete": 0.06,
    "skip": 0.12,
    "heartbeat": 0.015,
}
AFFINITY_DELTA = {
    "like": 0.08,
    "comment": 0.07,
    "share": 0.09,
    "follow": 0.05,
    "complete": 0.08,
    "replay": 0.08,
    "ad_complete": 0.08,
}
OPEN_COUNTERS = {
    "comment_open": "comment_opens",
    "share_open": "share_opens",
    "comment": "comments",
    "share": "shares",
    "follow": "follows",
    "hashtag_tap": "hashtag_taps",
}
SKIP_TAGS = {"seed"}


def empty_profile(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "interest_vector": [],
        "topic_affinity": {},
        "audio_affinity": {},
        "recent_video_ids": [],
        "recent_campaign_ids": [],
        "counters_24h": {
            "watch_ms": 0,
            "completes": 0,
            "early_skips": 0,
            "ad_impressions": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "follows": 0,
            "hashtag_taps": 0,
            "comment_opens": 0,
            "share_opens": 0,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _clean_tags(tags: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags or []:
        key = str(tag).strip().lower().lstrip("#")
        if not key or key in SKIP_TAGS or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def apply_event(
    profile: dict,
    event: dict,
    video_embedding: list[float] | None,
    category: str,
    audio_id: str,
    tags: list[str] | None = None,
) -> dict:
    event_type = event["event_type"]
    watch_ms = int(event.get("watch_ms") or 0)
    duration_ms = int(event.get("duration_ms") or 1)
    early = event_type == "skip" or (watch_ms > 0 and watch_ms < 2000 and event_type in {"skip", "heartbeat"})
    tag_list = _clean_tags(tags)

    counters = profile.setdefault("counters_24h", empty_profile(profile["user_id"])["counters_24h"])
    counters["watch_ms"] = int(counters.get("watch_ms", 0)) + watch_ms
    if event_type == "complete":
        counters["completes"] = int(counters.get("completes", 0)) + 1
    if early:
        counters["early_skips"] = int(counters.get("early_skips", 0)) + 1
    if event_type == "ad_impression":
        counters["ad_impressions"] = int(counters.get("ad_impressions", 0)) + 1
    if event_type == "like":
        counters["likes"] = int(counters.get("likes", 0)) + 1
    counter_key = OPEN_COUNTERS.get(event_type)
    if counter_key:
        counters[counter_key] = int(counters.get(counter_key, 0)) + 1

    affinity = profile.setdefault("topic_affinity", {})
    audio = profile.setdefault("audio_affinity", {})
    if event_type in {"comment_open", "share_open"}:
        pass
    elif event_type == "hashtag_tap":
        tapped = str((event.get("context") or {}).get("hashtag") or "").strip().lower().lstrip("#")
        if tapped and tapped not in SKIP_TAGS:
            affinity[tapped] = min(1.0, float(affinity.get(tapped, 0.0)) + 0.10)
        affinity[category] = min(1.0, float(affinity.get(category, 0.0)) + 0.03)
        audio[audio_id] = min(1.0, float(audio.get(audio_id, 0.0)) + 0.02)
    elif event_type in POSITIVE:
        delta = AFFINITY_DELTA.get(event_type, 0.08)
        affinity[category] = min(1.0, float(affinity.get(category, 0.0)) + delta)
        for tag in tag_list:
            affinity[tag] = min(1.0, float(affinity.get(tag, 0.0)) + delta)
        audio[audio_id] = min(1.0, float(audio.get(audio_id, 0.0)) + 0.05)
    elif early:
        affinity[category] = max(0.0, float(affinity.get(category, 0.0)) - 0.06)
        for tag in tag_list:
            affinity[tag] = max(0.0, float(affinity.get(tag, 0.0)) - 0.06)

    if video_embedding:
        vector = profile.get("interest_vector") or []
        if event_type in POSITIVE or (event_type == "heartbeat" and watch_ms / max(duration_ms, 1) > 0.6):
            lr = LEARNING_RATES.get(event_type, 0.04)
            profile["interest_vector"] = blend(vector, video_embedding, lr)
        elif early:
            profile["interest_vector"] = move_away(vector or video_embedding, video_embedding, LEARNING_RATES["skip"])

    recent = profile.setdefault("recent_video_ids", [])
    video_id = event.get("video_id")
    if video_id:
        recent = [item for item in recent if item != video_id]
        recent.insert(0, video_id)
        profile["recent_video_ids"] = recent[:80]

    if event.get("campaign_id") and event_type.startswith("ad_"):
        camps = profile.setdefault("recent_campaign_ids", [])
        if event["campaign_id"] not in camps:
            camps.insert(0, event["campaign_id"])
        profile["recent_campaign_ids"] = camps[:20]

    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    return profile
