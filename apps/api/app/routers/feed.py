from datetime import datetime, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.ads.insertion import insert_ads
from app.ads.types import AdCandidate
from app.deps import CurrentUser, DbDep
from app.media_util import media_url
from app.models import AdCampaign, Block, Comment, Follow, InboxItem
from app.mongo import get_mongo
from app.recsys.pipeline import rank_organic_feed
from app.recsys.types import PipelineConfig
from app.services.catalog import features_from_profile, load_catalog, to_candidate
from app.telemetry.profile import empty_profile

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("")
async def get_feed(
    db: DbDep,
    current: CurrentUser,
    lane: str = Query(default="foryou"),
) -> dict:
    started = datetime.now(timezone.utc)
    videos = await load_catalog(db)
    catalog = [to_candidate(video) for video in videos]
    video_map = {video.id: video for video in videos}

    mongo = get_mongo()
    try:
        profile_doc = await mongo.user_profiles_online.find_one({"user_id": current.id})
    except Exception:
        profile_doc = None
    profile = profile_doc or empty_profile(current.id)

    blocked_rows = await db.execute(select(Block.blocked_id).where(Block.blocker_id == current.id))
    blocked = list(blocked_rows.scalars())
    user_features = features_from_profile(current, profile, blocked)

    followees = set(
        (await db.execute(select(Follow.followee_id).where(Follow.follower_id == current.id))).scalars()
    )
    if lane in {"following", "friends"}:
        if not followees:
            elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            return {
                "items": [],
                "trace": {"lane": lane, "final": 0, "followees": 0},
                "latency_ms": round(elapsed_ms, 2),
                "new_user": user_features.is_new,
            }
        catalog = [item for item in catalog if item.creator_id in followees]
        videos = [video for video in videos if video.creator_id in followees]
        video_map = {video.id: video for video in videos}

    organic, trace = rank_organic_feed(user_features, catalog, PipelineConfig())
    trace["lane"] = lane

    campaigns = list(
        (
            await db.execute(
                select(AdCampaign).options(selectinload(AdCampaign.creatives)).where(AdCampaign.status == "active")
            )
        ).scalars()
    )
    ads: list[AdCandidate] = []
    for campaign in campaigns:
        for creative in campaign.creatives:
            if creative.status != "active":
                continue
            ads.append(
                AdCandidate(
                    campaign_id=campaign.id,
                    creative_id=creative.id,
                    video_id=creative.video_id,
                    bid_cents=campaign.bid_cents,
                    daily_budget_cents=campaign.daily_budget_cents,
                    spent_today_cents=campaign.spent_today_cents,
                    targeting_tags=list(campaign.targeting_tags or []),
                    targeting_categories=list(campaign.targeting_categories or []),
                )
            )

    if lane == "foryou":
        items = insert_ads(organic, user_features, ads, recent_campaigns=list(profile.get("recent_campaign_ids") or []))
    else:
        items = [
            {
                "kind": "organic",
                "video_id": row.video.id,
                "campaign_id": None,
                "creative_id": None,
                "source": row.source,
                "scores": {
                    "y1": round(row.y1, 4),
                    "y2": round(row.y2, 4),
                    "y3": round(row.y3, 4),
                    "y4": round(row.y4, 4),
                    "y5": round(row.y5, 4),
                    "final": round(row.score, 4),
                },
                "reasons": row.reasons,
            }
            for row in organic
        ]

    comment_rows = await db.execute(select(Comment.video_id, func.count()).group_by(Comment.video_id))
    comment_counts = {video_id: n for video_id, n in comment_rows.all()}
    share_rows = await db.execute(select(InboxItem.video_id, func.count()).group_by(InboxItem.video_id))
    share_counts = {video_id: n for video_id, n in share_rows.all()}

    hydrated = []
    for position, item in enumerate(items):
        video = video_map.get(item["video_id"])
        if video is None:
            continue
        hydrated.append(
            {
                **item,
                "position": position + 1,
                "video": {
                    "id": video.id,
                    "title": video.title,
                    "description": video.description,
                    "category": video.category,
                    "tags": video.tags,
                    "audio_id": video.audio_id,
                    "duration_ms": video.duration_ms,
                    "poster_seed": video.poster_seed,
                    "media_path": video.media_path,
                    "media_url": media_url(video.media_path),
                    "play_count": video.play_count,
                    "creator_id": video.creator_id,
                    "creator_name": video.creator.display_name if video.creator else "",
                    "width": int(getattr(video, "width", None) or 1080),
                    "height": int(getattr(video, "height", None) or 1920),
                    "comment_count": int(comment_counts.get(video.id, 0)),
                    "share_count": int(share_counts.get(video.id, 0)),
                    "followee": video.creator_id in followees,
                },
            }
        )

    elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
    try:
        await mongo.ranking_traces.insert_one(
            {
                "user_id": current.id,
                "ts": datetime.now(timezone.utc),
                "trace": trace,
                "latency_ms": elapsed_ms,
                "item_ids": [row["video_id"] for row in hydrated],
            }
        )
    except Exception:
        pass

    return {
        "items": hydrated,
        "trace": trace,
        "latency_ms": round(elapsed_ms, 2),
        "new_user": user_features.is_new,
    }
