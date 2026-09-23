import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUser, DbDep
from app.models import User, Video
from app.mongo import get_mongo
from app.schemas import SimIn
from app.services.corpus import build_orange_csv, dashboard_slice, with_dimensions
from app.services.simulator import run_simulation

router = APIRouter(prefix="/lab", tags=["lab"])


def _enrich(events: list[dict], users: dict, videos: dict) -> list[dict]:
    rows: list[dict] = []
    for event in events:
        user = users.get(event.get("user_id"))
        video = videos.get(event.get("video_id"))
        rows.append(
            with_dimensions(
                event,
                user_region=(user.region if user else "") or "",
                video_region=(video.region if video else "") or "",
                category=video.category if video else "",
                audio_id=video.audio_id if video else "",
                user_role=user.role if user else "",
                tags=list(video.tags or []) if video is not None else None,
            )
        )
    return rows


@router.get("/metrics")
async def metrics(
    db: DbDep,
    current: CurrentUser,
    region: str = Query(default=""),
    category: str = Query(default=""),
) -> dict:
    mongo = get_mongo()
    since = datetime.now(timezone.utc) - timedelta(days=7)
    cursor = mongo.events.find({"ts": {"$gte": since}}).sort("ts", -1)
    events = await cursor.to_list(length=20_001)
    truncated = len(events) > 20_000
    events = events[:20_000]
    if not events:
        return {**dashboard_slice([], region or None, category=category or None), "window_days": 7, "truncated": False}

    users = {user.id: user for user in (await db.execute(select(User))).scalars()}
    videos = {video.id: video for video in (await db.execute(select(Video))).scalars()}
    traces = await mongo.ranking_traces.find().sort("ts", -1).to_list(length=30)
    return {
        **dashboard_slice(_enrich(events, users, videos), region or None, traces, category=category or None),
        "window_days": 7,
        "truncated": truncated,
    }


@router.post("/sim")
async def simulate(payload: SimIn, db: DbDep, current: CurrentUser) -> dict:
    if current.role not in {"admin", "creator", "advertiser", "viewer"}:
        raise HTTPException(status_code=403, detail="No autorizado")
    return await run_simulation(db, payload.users, payload.days, payload.events_per_user, payload.pass_id)


@router.get("/orange/interactions.csv")
async def orange_interactions(db: DbDep, current: CurrentUser) -> StreamingResponse:
    mongo = get_mongo()
    videos = {video.id: video for video in (await db.execute(select(Video))).scalars()}
    users = {user.id: user for user in (await db.execute(select(User))).scalars()}
    stored = await mongo.events.find().sort("ts", -1).to_list(length=50_000)
    payload = build_orange_csv(_enrich(list(reversed(stored)), users, videos)).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=veta_interactions.csv"},
    )
