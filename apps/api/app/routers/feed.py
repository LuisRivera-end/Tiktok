from datetime import datetime, timedelta, timezone
from uuid import uuid4

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
from app.services.catalog import (
    catalog_for_lane,
    features_from_profile,
    load_catalog,
    skip_rates_by_video,
    to_candidate,
)
from app.telemetry.profile import empty_profile
from app.telemetry.online import online_profile
from app.telemetry.exposures import dataset_rows
from app.ml.features import features_for, FEATURE_VERSION
from app.ads.estimates import estimate_click
from app.ads.billing import budget_day
from app.ads.auction import is_targeted, passes_filters, session_abandon_risk
from app.ads.types import InsertionPolicy
from app.models import AdDailySpend
from app.recsys.filters import filter_reason

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("")
async def get_feed(
    db: DbDep,
    current: CurrentUser,
    lane: str = Query(default="foryou"),
    session_id: str = Query(default="", max_length=100),
) -> dict:
    started = datetime.now(timezone.utc)
    videos = await load_catalog(db)
    mongo = get_mongo()
    try:
        profile_doc = await online_profile(mongo, current.id)
    except Exception:
        profile_doc = None
    profile = profile_doc or empty_profile(current.id)
    try:
        raw_events = await mongo.events.find(
            {},
            {"video_id": 1, "event_type": 1, "watch_ms": 1},
        ).to_list(length=20_000)
    except Exception:
        raw_events = []
    rates = skip_rates_by_video(raw_events)
    observed = [e async for e in mongo.exposures.find({"started_at": {"$gte": started - timedelta(days=8)}})]
    exposure_rows = dataset_rows(observed)
    for video_id in {r["video_id"] for r in exposure_rows}:
        views = [r for r in exposure_rows if r["video_id"] == video_id and r["observed_close"]]
        if views:
            rates[video_id] = sum(r["early_skip"] for r in views) / len(views)
    ad_rows = [r for r in exposure_rows if datetime.fromisoformat(r["started_at"]) >= started - timedelta(days=7)]
    catalog = [to_candidate(video, skip_rate=rates.get(video.id, 0.0)) for video in videos]
    play_totals = {r["_id"]: r["count"] async for r in mongo.exposures.aggregate([
        {"$match": {"played": True, "origin": "real"}}, {"$group": {"_id": "$video_id", "count": {"$sum": 1}}}])}
    for candidate in catalog:
        candidate.play_count += play_totals.get(candidate.id, 0)

    blocked_rows = await db.execute(select(Block.blocked_id).where(Block.blocker_id == current.id))
    blocked = list(blocked_rows.scalars())
    followees = set(
        (await db.execute(select(Follow.followee_id).where(Follow.follower_id == current.id))).scalars()
    )
    user_features = features_from_profile(current, profile, blocked, followees=list(followees))
    if lane in {"following", "friends"} and not followees:
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        return {
            "items": [],
            "trace": {"lane": lane, "final": 0, "followees": 0},
            "latency_ms": round(elapsed_ms, 2),
            "new_user": user_features.is_new,
        }
    catalog = catalog_for_lane(catalog, followees, lane)
    if lane in {"following", "friends"}:
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
    ad_rejections = []
    candidate_map = {video.id: video for video in catalog}
    recent = [e for e in observed if e["user_id"] == current.id and e.get("session_root", e["session_id"]) == session_id]
    last = max(recent, key=lambda e: e["started_at"], default=None)
    active_session = last["session_id"] if last and started - last.get("last_event_at", last["started_at"]).replace(tzinfo=timezone.utc) < timedelta(minutes=30) else None
    recent_campaigns = {e.get("campaign_id") for e in recent if e["session_id"] == active_session}
    for campaign in campaigns:
        daily_spend = await db.get(AdDailySpend, (campaign.id, budget_day()))
        for creative in campaign.creatives:
            if creative.status != "active":
                continue
            candidate = candidate_map.get(creative.video_id)
            if not candidate or filter_reason(user_features, candidate, allow_seen=True):
                ad_rejections.append({"campaign_id": campaign.id, "reason": "creative_ineligible"})
                continue
            c_rows = [r for r in ad_rows if r["campaign_id"] == campaign.id and r["mask_continue"] and r["origin"] == "real"]
            ad = AdCandidate(
                    campaign_id=campaign.id,
                    creative_id=creative.id,
                    video_id=creative.video_id,
                    bid_cents=campaign.bid_cents,
                    daily_budget_cents=campaign.daily_budget_cents,
                    spent_today_cents=daily_spend.amount_cents if daily_spend else 0,
                    targeting_tags=list(campaign.targeting_tags or []),
                    targeting_categories=list(campaign.targeting_categories or []),
                    targeting_genders=list(campaign.targeting_genders or []),
                    landing_url=creative.landing_url,
                    p_click=estimate_click(ad_rows, campaign.id, creative.id, current.gender),
                    mature_exposures=len(c_rows),
                    p_skip=(sum(r["early_skip"] for r in c_rows) + 4) / (len(c_rows) + 20),
                    p_post_retention=(sum(r["continue"] for r in c_rows) + 14) / (len(c_rows) + 20),
                    impressions_last_hour=sum(e["user_id"] == current.id and e.get("campaign_id") == campaign.id and
                                              (started - e["started_at"].replace(tzinfo=timezone.utc)).total_seconds() < 3600 for e in observed),
                )
            from app.ml.serving import predict as model_predict
            result = model_predict(features_for(user_features, candidate, is_ad=True), "ads")
            if result:
                ad.predictions = result["predictions"]
                ad.model_version = result["version"]
                if result["active"]:
                    ad.p_click = result["predictions"]["p_click"]
            reason = passes_filters(ad, InsertionPolicy(), list(recent_campaigns))
            if not is_targeted(user_features, ad):
                reason = "targeting"
            if ad.mature_exposures >= 100 and session_abandon_risk(ad) > .62:
                reason = "retention"
            if reason:
                ad_rejections.append({"campaign_id": campaign.id, "reason": reason})
            ads.append(ad)

    if lane == "foryou":
        items = insert_ads(organic, user_features, ads, recent_campaigns=list(recent_campaigns))
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
                "predictions": row.predictions,
                "model_version": row.model_version,
            }
            for row in organic
        ]

    comment_rows = await db.execute(select(Comment.video_id, func.count()).group_by(Comment.video_id))
    comment_counts = {video_id: n for video_id, n in comment_rows.all()}
    share_rows = await db.execute(select(InboxItem.video_id, func.count()).group_by(InboxItem.video_id))
    share_counts = {video_id: n for video_id, n in share_rows.all()}

    hydrated = []
    decisions = []
    for position, item in enumerate(items):
        video = video_map.get(item["video_id"])
        if video is None:
            continue
        decision_id = str(uuid4())
        candidate = candidate_map[video.id]
        decisions.append({"_id": decision_id, "user_id": current.id, "video_id": video.id,
                          "campaign_id": item.get("campaign_id"), "creative_id": item.get("creative_id"),
                          "gender": current.gender, "features": features_for(user_features, candidate, is_ad=item["kind"] == "ad"),
                          "feature_version": FEATURE_VERSION, "duration_ms": video.duration_ms,
                          "model_version": item.get("model_version", "heuristic-v1"),
                          "predictions": item.get("predictions", {}), "embedding": candidate.embedding,
                          "category": video.category, "audio_id": video.audio_id, "tags": video.tags,
                          "position": position + 1, "landing_url": item.get("landing_url"),
                          "bid_cents": item.get("bid_cents"), "selection_probability": item.get("selection_probability", 1),
                          "selection_policy": item.get("selection_policy", "organic-deterministic"),
                          "eligible_candidates": item.get("eligible_candidates", trace.get("candidate_ids", [])),
                          "expires_at": started + timedelta(hours=2)})
        hydrated.append(
            {
                **item,
                "decision_id": decision_id,
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
                    "play_count": video.play_count + play_totals.get(video.id, 0),
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

    if decisions:
        await mongo.decisions.insert_many(decisions)
    trace["ad_rejections"] = ad_rejections
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
