from copy import deepcopy
from app.telemetry.profile import apply_event, empty_profile


async def online_profile(mongo, user_id):
    """Replay authoritative exposure state: retries cannot increment counters twice.

    The pre-v2 profile is frozen once, preserving existing lab history. The latest
    5000 exposures form the bounded hot history; raw exposures remain exportable.
    """
    base = await mongo.profile_bases.find_one({"_id": user_id})
    if not base:
        legacy = await mongo.user_profiles_online.find_one({"user_id": user_id}) or empty_profile(user_id)
        legacy.pop("_id", None)
        await mongo.profile_bases.update_one({"_id": user_id}, {"$setOnInsert": {"profile": legacy}}, upsert=True)
        base = await mongo.profile_bases.find_one({"_id": user_id})
    profile = deepcopy(base["profile"])
    exposures = await mongo.exposures.find({"user_id": user_id}).sort("started_at", -1).to_list(length=5000)
    for e in reversed(exposures):
        duration = max(e["duration_ms"], 1)
        terminal = "complete" if e.get("coverage_ms", 0) >= .9 * duration else (
            "skip" if e.get("close_reason") == "next" and e.get("watch_ms", 0) < 2000 else "heartbeat")
        types = ([terminal] if e.get("played") else []) + [t for key, t in
            [("liked", "like"), ("shared", "share"), ("commented", "comment"), ("followed", "follow")]
            if e.get(key)]
        for i, kind in enumerate(types):
            event = {"event_type": kind, "video_id": e["video_id"], "campaign_id": e.get("campaign_id"),
                     "duration_ms": duration, "watch_ms": e.get("watch_ms", 0) if i == 0 else 0}
            profile = apply_event(profile, event, e.get("embedding", []), e.get("category", ""), e.get("audio_id", ""), e.get("tags", []))
    return profile
