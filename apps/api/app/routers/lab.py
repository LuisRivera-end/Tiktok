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
from app.telemetry.exposures import dataset_rows, metrics_for, csv_export
from app.ml.readiness import assess
from app.ml.demo import demo_exposures
from app.demographics import Gender, GENDERS
from typing import Literal

router = APIRouter(prefix="/lab", tags=["lab"])


def _simulated_exposure_rows(now: datetime) -> list[dict]:
    """Reproducible demo data; never reads or writes application records."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    return dataset_rows(demo_exposures(users=60, days=5, seed=42, base=start), now)


@router.get("/exposures/readiness")
async def exposure_readiness(current: CurrentUser):
    if current.role != "admin":
        raise HTTPException(403, "El diagnóstico de entrenamiento requiere administrador")
    exposures = [e async for e in get_mongo().exposures.find({"origin": "real"})]
    return assess(dataset_rows(exposures))


@router.get("/exposures/metrics")
async def exposure_metrics(current: CurrentUser, days: int = Query(default=7, ge=1, le=365),
                           gender: Gender | None = None, origin: Literal["real", "simulated"] = "real"):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    if origin == "simulated":
        rows = [r for r in _simulated_exposure_rows(now) if datetime.fromisoformat(r["started_at"]) >= since]
    else:
        exposures = [e async for e in get_mongo().exposures.find({"origin": "real", "started_at": {"$gte": since}})]
        rows = dataset_rows(exposures, now)
    if gender:
        rows = [r for r in rows if r["gender"] == gender]
    return {"origin": origin, "days": days, **metrics_for(rows),
            "genders": [{"gender": g, **metrics_for([r for r in rows if r["gender"] == g])} for g in GENDERS]}


@router.get("/orange/exposures.csv")
async def export_exposures(current: CurrentUser, origin: Literal["real", "simulated"] = "real"):
    if current.role != "admin":
        raise HTTPException(403, "La exportación de entrenamiento requiere administrador")
    if origin == "simulated":
        rows = _simulated_exposure_rows(datetime.now(timezone.utc))
    else:
        exposures = [e async for e in get_mongo().exposures.find({"origin": "real"})]
        rows = dataset_rows(exposures)
    content = csv_export(rows).encode("utf-8")
    return StreamingResponse(io.BytesIO(content), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=veta_exposures.csv"})


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
