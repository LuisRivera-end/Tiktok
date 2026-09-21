import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUser, DbDep
from app.models import User, Video
from app.mongo import get_mongo
from app.schemas import SimIn
from app.services.simulator import run_simulation

router = APIRouter(prefix="/lab", tags=["lab"])


@router.get("/metrics")
async def metrics(current: CurrentUser) -> dict:
    mongo = get_mongo()
    since = datetime.now(timezone.utc) - timedelta(days=7)
    cursor = mongo.events.find({"ts": {"$gte": since}})
    events = await cursor.to_list(length=20_000)
    if not events:
        return {
            "retention_minutes": 0,
            "completion_rate": 0,
            "early_abandon_rate": 0,
            "new_creator_share": 0,
            "diversity_index": 0,
            "ad_fill_rate": 0,
            "events": 0,
            "comments": 0,
            "shares": 0,
            "follows": 0,
            "hashtag_taps": 0,
            "comment_opens": 0,
            "share_opens": 0,
        }

    users: dict[str, float] = {}
    completes = 0
    early = 0
    plays = 0
    impressions = 0
    ads = 0
    categories: dict[str, int] = {}
    video_ids = {event.get("video_id") for event in events if event.get("video_id")}

    for event in events:
        users[event["user_id"]] = users.get(event["user_id"], 0) + float(event.get("watch_ms") or 0)
        if event["event_type"] in {"play", "heartbeat", "complete", "skip"}:
            plays += 1
        if event["event_type"] == "complete":
            completes += 1
        if event["event_type"] == "skip" or (event.get("watch_ms") or 0) < 2000 and event["event_type"] in {"skip"}:
            early += 1
        if event["event_type"] == "impression":
            impressions += 1
        if event.get("is_ad"):
            ads += 1

    traces = await mongo.ranking_traces.find().sort("ts", -1).to_list(length=30)
    explore = 0
    total_final = 0
    for trace in traces:
        payload = trace.get("trace") or {}
        explore += int(payload.get("explore_in_final") or 0)
        total_final += int(payload.get("final") or 0)

    n_users = max(len(users), 1)
    retention_minutes = (sum(users.values()) / n_users) / 60000
    completion_rate = completes / max(plays, 1)
    early_rate = early / max(plays, 1)
    diversity = 0.0
    # Shannon-ish over event categories is computed in Orange; here a crude unique-video ratio.
    unique_ratio = len(video_ids) / max(len(events), 1)
    return {
        "retention_minutes": round(retention_minutes, 2),
        "completion_rate": round(completion_rate, 4),
        "early_abandon_rate": round(early_rate, 4),
        "new_creator_share": round(explore / max(total_final, 1), 4),
        "diversity_index": round(min(1.0, unique_ratio * 4), 4),
        "ad_fill_rate": round(ads / max(impressions + ads, 1), 4),
        "events": len(events),
        "active_users": len(users),
        "comments": sum(1 for event in events if event.get("event_type") == "comment"),
        "shares": sum(1 for event in events if event.get("event_type") == "share"),
        "follows": sum(1 for event in events if event.get("event_type") == "follow"),
        "hashtag_taps": sum(1 for event in events if event.get("event_type") == "hashtag_tap"),
        "comment_opens": sum(1 for event in events if event.get("event_type") == "comment_open"),
        "share_opens": sum(1 for event in events if event.get("event_type") == "share_open"),
    }


@router.post("/sim")
async def simulate(payload: SimIn, db: DbDep, current: CurrentUser) -> dict:
    if current.role not in {"admin", "creator", "advertiser", "viewer"}:
        raise HTTPException(status_code=403, detail="No autorizado")
    return await run_simulation(db, payload.users, payload.days, payload.events_per_user)


@router.get("/orange/interactions.csv")
async def orange_interactions(db: DbDep, current: CurrentUser) -> StreamingResponse:
    mongo = get_mongo()
    videos = {video.id: video for video in (await db.execute(select(Video))).scalars()}
    users = {user.id: user for user in (await db.execute(select(User))).scalars()}
    events = await mongo.events.find().sort("ts", -1).to_list(length=50_000)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "user_id",
            "user_role",
            "video_id",
            "category",
            "audio_id",
            "event_type",
            "watch_ms",
            "duration_ms",
            "completion_ratio",
            "early_skip",
            "is_ad",
            "campaign_id",
            "session_id",
            "tags",
        ]
    )
    for event in reversed(events):
        video = videos.get(event.get("video_id"))
        user = users.get(event.get("user_id"))
        watch = int(event.get("watch_ms") or 0)
        writer.writerow(
            [
                event.get("user_id"),
                user.role if user else "",
                event.get("video_id"),
                video.category if video else "",
                video.audio_id if video else "",
                event.get("event_type"),
                watch,
                int(event.get("duration_ms") or 0),
                float(event.get("completion_ratio") or 0),
                1 if watch < 2000 and event.get("event_type") in {"skip"} else 0,
                1 if event.get("is_ad") else 0,
                event.get("campaign_id") or "",
                event.get("session_id") or "",
                "|".join(video.tags or []) if video else "",
            ]
        )

    payload = buffer.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=veta_interactions.csv"},
    )
