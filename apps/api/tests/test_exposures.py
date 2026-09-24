from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from mongomock_motor import AsyncMongoMockClient
from app.telemetry.exposures import dataset_rows, metrics_for
from app.telemetry.online import online_profile
from app.routers.events import ingest_exposure_event
from app.schemas import EventIn, RegisterIn, CampaignIn
from app.ads.types import AdCandidate, InsertionPolicy
from app.ads.auction import is_targeted, run_auction
from app.recsys.types import UserFeatures
from app.ads.estimates import estimate_click
from app.routers import lab

NOW = datetime(2026, 3, 5, tzinfo=timezone.utc)


def exposure(**kwargs):
    return {"_id": str(uuid4()), "user_id": "u", "video_id": "v", "session_id": "s", "gender": "woman",
            "origin": "real", "duration_ms": 10000, "started_at": NOW-timedelta(days=2),
            "played": True, "watch_ms": 9000, "coverage_ms": 9000, "closed_at": NOW-timedelta(days=2)+timedelta(seconds=9),
            "close_reason": "next", **kwargs}


def test_exposure_labels_unknown_is_not_negative_and_gender_is_historical():
    a = exposure()
    b = exposure(started_at=a["closed_at"]+timedelta(seconds=1), watch_ms=3000, coverage_ms=3000)
    rows = dataset_rows([b, a], NOW)
    assert rows[0]["complete"] == 1 and rows[0]["continue"] == 1
    assert rows[0]["gender"] == "woman"
    incomplete = exposure(played=False, closed_at=None, watch_ms=0, coverage_ms=0)
    row = dataset_rows([incomplete], NOW)[0]
    assert all(row[f"mask_{t}"] == 0 for t in ("complete", "engage", "continue", "click"))


def test_click_masks_continuation_and_organic_does_not_dilute_ctr():
    rows = dataset_rows([exposure(campaign_id="c", clicked=True, close_reason="ad_click"),
                         exposure(session_id="s2")], NOW)
    ad = next(r for r in rows if r["is_ad"])
    assert ad["mask_continue"] == 0 and ad["mask_click"] == 1
    assert metrics_for(rows)["ctr"] == 1
    assert metrics_for([])["ctr"] is None


@pytest.mark.asyncio
async def test_simulated_exposures_are_generated_without_application_data(monkeypatch):
    monkeypatch.setattr(lab, "get_mongo", lambda: (_ for _ in ()).throw(AssertionError("Mongo must not be read")))
    admin = SimpleNamespace(role="admin")
    report = await lab.exposure_metrics(admin, days=7, gender=None, origin="simulated")
    assert report["impressions"] == 60 * 5 * 8
    assert report["users"] == 60
    assert {group["gender"] for group in report["genders"]} == {
        "man", "woman", "other", "prefer_not_to_say", "unspecified"
    }
    assert all(group["impressions"] == 12 * 5 * 8 for group in report["genders"])
    assert all(report[f"{task}_rate"] is not None for task in ("complete", "engage", "continue"))
    response = await lab.export_exposures(admin, origin="simulated")
    csv_bytes = b"".join([chunk async for chunk in response.body_iterator])
    assert csv_bytes.count(b"simulated") == 60 * 5 * 8


@pytest.mark.asyncio
async def test_ingestion_retries_out_of_order_and_profile_replay():
    mongo = AsyncMongoMockClient().test
    await mongo.events.create_index("event_id", unique=True)
    now = datetime.now(timezone.utc)
    e = exposure(started_at=now, closed_at=None, played=False, embedding=[], category="ciencia", audio_id="a", watch_ms=0, coverage_ms=0)
    e.pop("closed_at")
    await mongo.exposures.insert_one(e)
    user = SimpleNamespace(id="u")
    def event(kind, **extra):
        return EventIn(event_id=uuid4(), exposure_id=e["_id"], session_id="s", video_id="v", event_type=kind, **extra)
    play, close, like = event("play"), event("close", watch_ms=9500, coverage_ms=9200, close_reason="next"), event("like")
    await ingest_exposure_event(close, mongo, user)
    await ingest_exposure_event(play, mongo, user)
    await ingest_exposure_event(like, mongo, user)
    await ingest_exposure_event(close, mongo, user)
    await ingest_exposure_event(like, mongo, user)
    # A retry cannot change the original payload.
    close.watch_ms = 99000
    await ingest_exposure_event(close, mongo, user)
    assert await mongo.events.count_documents({}) == 3
    updated = await mongo.exposures.find_one({"_id": e["_id"]})
    assert updated["watch_ms"] == 9500 and updated["gender"] == "woman"
    first = await online_profile(mongo, "u")
    second = await online_profile(mongo, "u")
    assert first["counters_24h"] == second["counters_24h"]
    assert first["counters_24h"]["completes"] == 1
    assert first["counters_24h"]["likes"] == 1
    with pytest.raises(Exception):
        await ingest_exposure_event(play, mongo, SimpleNamespace(id="someone_else"))


def test_gender_targeting_is_an_and_condition_and_absence_is_supported():
    ad = AdCandidate("c", "cr", "v", 100, 5000, 0, [], ["ciencia"], targeting_genders=["woman"])
    user = UserFeatures("u", [], {"ciencia": 1}, {}, gender="man")
    assert not is_targeted(user, ad)
    user.gender = "woman"
    assert is_targeted(user, ad)
    user.gender = "unspecified"
    assert not is_targeted(user, ad)
    ad.targeting_genders = []
    assert is_targeted(user, ad)
    assert run_auction(user, [ad], InsertionPolicy(exploration_rate=0), []).selection_probability == 1


def test_new_campaign_prior_and_unknown_gender_do_not_infer_identity():
    assert estimate_click([], "c", "cr", "woman") == .05
    rows = dataset_rows([exposure(campaign_id="c", creative_id="cr", clicked=True)], NOW)
    assert estimate_click(rows, "c", "cr", "unspecified") == estimate_click(rows, "c", "cr", "prefer_not_to_say")
    assert estimate_click(rows, "c", "cr", "woman") > estimate_click(rows, "c", "cr", "man")


def test_profile_enum_and_destination_validation():
    assert RegisterIn(email="a@b.co", password="12345678", display_name="ab").gender == "unspecified"
    with pytest.raises(ValueError):
        RegisterIn(email="a@b.co", password="12345678", display_name="ab", gender="inferred")
    with pytest.raises(ValueError):
        CampaignIn(name="ad", bid_cents=1, daily_budget_cents=10, video_id="v", landing_url="javascript:alert(1)")
