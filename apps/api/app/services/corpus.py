"""Pure regional corpus: catalog plan, simulated interactions, Orange CSV, and BI.

Postgres and Mongo stay outside this module so tests can run the same functions
the lab routes call.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.recsys.vector import CATEGORIES

REGIONS: tuple[str, ...] = ("México", "Colombia", "Argentina", "Chile", "Perú")

DEMO_REGIONS = {
    "viewer@veta.local": "México",
    "creator@veta.local": "México",
    "advertiser@veta.local": "Colombia",
    "admin@veta.local": "Argentina",
}

VIEWERS_PER_REGION = 14
CREATORS_PER_REGION = 4
CLIPS_PER_CATEGORY = 2

# One lab click: 80 × 5 × 8 = 3200 events, inside SimIn caps.
LAB_SIM_USERS = 80
LAB_SIM_DAYS = 5
LAB_SIM_EVENTS_PER_USER = 8

# Separate Orange pass: 25 × 5 × 8 = 1000 events. Does not replace the 3200 button.
ORANGE_PASS_USERS = 25
ORANGE_PASS_DAYS = 5
ORANGE_PASS_EVENTS_PER_USER = 8
ORANGE_PASS_ID = "orange-1000"

SAME_COMPLETION = {
    "México": 0.92,
    "Colombia": 0.84,
    "Argentina": 0.78,
    "Chile": 0.72,
    "Perú": 0.66,
}
CROSS_HEARTBEAT_RATIO = 0.34

_SLUGS = {
    "México": "mexico",
    "Colombia": "colombia",
    "Argentina": "argentina",
    "Chile": "chile",
    "Perú": "peru",
}

ORANGE_COLUMNS = [
    "user_id",
    "user_role",
    "user_region",
    "video_id",
    "video_region",
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
    "pass_id",
    "event_id",
    "event_ts",
    "feed_position",
    "exposure_id",
    "gender",
    "origin",
]

_SOCIAL_ROTATION = (
    "complete",
    "complete",
    "complete",
    "complete",
    "like",
    "comment",
    "share",
    "follow",
    "hashtag_tap",
    "complete",
)


@dataclass(frozen=True)
class PlannedUser:
    email: str
    display_name: str
    role: str
    age: int
    region: str


@dataclass(frozen=True)
class PlannedClip:
    content_hash: str
    title: str
    category: str
    region: str
    creator_email: str
    audio_id: str
    duration_ms: int
    play_count: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class CorpusActor:
    id: str
    region: str
    role: str


@dataclass(frozen=True)
class CorpusClip:
    id: str
    region: str
    category: str
    duration_ms: int
    creator_id: str
    audio_id: str
    tags: tuple[str, ...] = ()


def injection_plan() -> tuple[list[PlannedUser], list[PlannedClip]]:
    users: list[PlannedUser] = []
    for region in REGIONS:
        slug = _SLUGS[region]
        for index in range(1, CREATORS_PER_REGION + 1):
            users.append(
                PlannedUser(
                    email=f"creator.{slug}.{index:02d}@veta.local",
                    display_name=f"Creador {region} {index:02d}",
                    role="creator",
                    age=22 + index,
                    region=region,
                )
            )
        for index in range(1, VIEWERS_PER_REGION + 1):
            users.append(
                PlannedUser(
                    email=f"viewer.{slug}.{index:02d}@veta.local",
                    display_name=f"Espectador {region} {index:02d}",
                    role="viewer",
                    age=18 + (index % 15),
                    region=region,
                )
            )

    clips: list[PlannedClip] = []
    for region in REGIONS:
        slug = _SLUGS[region]
        creators = [user.email for user in users if user.role == "creator" and user.region == region]
        sequence = 0
        for category in CATEGORIES:
            for copy in range(CLIPS_PER_CATEGORY):
                sequence += 1
                clips.append(
                    PlannedClip(
                        content_hash=f"veta-corpus-{slug}-{category}-{copy}",
                        title=f"{category} · {region} · {copy + 1}",
                        category=category,
                        region=region,
                        creator_email=creators[sequence % len(creators)],
                        audio_id=f"audio-{category}-{copy % 3}",
                        duration_ms=15000,
                        play_count=40 + sequence,
                        tags=(category, "laboratorio", "corto", "veta", slug),
                    )
                )
    return users, clips


def pending_injection(
    existing_emails: set[str],
    existing_hashes: set[str],
) -> tuple[list[PlannedUser], list[PlannedClip]]:
    users, clips = injection_plan()
    fresh_users = [user for user in users if user.email not in existing_emails]
    fresh_clips = [clip for clip in clips if clip.content_hash not in existing_hashes]
    return fresh_users, fresh_clips


def planned_population() -> tuple[list[CorpusActor], list[CorpusClip]]:
    users, clips = injection_plan()
    actors = [CorpusActor(id=user.email, region=user.region, role=user.role) for user in users]
    catalog = [
        CorpusClip(
            id=clip.content_hash,
            region=clip.region,
            category=clip.category,
            duration_ms=clip.duration_ms,
            creator_id=clip.creator_email,
            audio_id=clip.audio_id,
            tags=clip.tags,
        )
        for clip in clips
    ]
    return actors, catalog


def _sample_people(people: list[CorpusActor], limit: int) -> list[CorpusActor]:
    eligible = [person for person in people if person.role in {"viewer", "creator"} and person.region]
    by_region: dict[str, list[CorpusActor]] = {}
    for person in eligible:
        by_region.setdefault(person.region, []).append(person)
    if not by_region or limit <= 0:
        return []
    order = sorted(by_region)
    picked: list[CorpusActor] = []
    cursor = 0
    while len(picked) < limit and any(by_region.values()):
        bucket = by_region[order[cursor % len(order)]]
        if bucket:
            picked.append(bucket.pop(0))
        cursor += 1
        if cursor > limit * len(order) + len(order):
            break
    return picked


def _clips_for(clips: list[CorpusClip], region: str, *, same: bool) -> list[CorpusClip]:
    if same:
        return [clip for clip in clips if clip.region == region]
    return [clip for clip in clips if clip.region and clip.region != region]


def generate_events(
    people: list[CorpusActor],
    clips: list[CorpusClip],
    *,
    users: int = LAB_SIM_USERS,
    days: int = LAB_SIM_DAYS,
    events_per_user: int = LAB_SIM_EVENTS_PER_USER,
    pass_id: str = "",
) -> list[dict]:
    """Seeded interactions. Same-region watches finish; cross-region watches do not."""
    sample = _sample_people(people, users)
    if not sample or not clips:
        return []
    events: list[dict] = []
    for person_index, person in enumerate(sample):
        same_pool = _clips_for(clips, person.region, same=True)
        cross_pool = _clips_for(clips, person.region, same=False)
        if not same_pool and not cross_pool:
            continue
        for day in range(days):
            for step in range(events_per_user):
                wants_same = (step % 5) < 3
                pool = same_pool if wants_same and same_pool else cross_pool or same_pool
                clip = pool[(person_index + day + step) % len(pool)]
                same = bool(person.region) and person.region == clip.region
                duration = max(int(clip.duration_ms or 1), 1)
                context: dict = {}
                if same and (person_index + step) % 17 == 0:
                    event_type = "skip"
                    watch = 600
                elif same:
                    ratio = SAME_COMPLETION.get(clip.region, 0.8)
                    watch = max(1, min(duration, int(round(duration * ratio))))
                    event_type = _SOCIAL_ROTATION[(person_index + day + step) % len(_SOCIAL_ROTATION)]
                    if event_type == "hashtag_tap":
                        context = {"hashtag": clip.tags[0] if clip.tags else clip.category}
                elif (person_index + step) % 2 == 0:
                    event_type = "skip"
                    watch = 500
                else:
                    event_type = "heartbeat"
                    watch = max(1, min(duration, int(round(duration * CROSS_HEARTBEAT_RATIO))))
                events.append(
                    {
                        "user_id": person.id,
                        "user_role": person.role,
                        "user_region": person.region,
                        "session_id": f"sim-{person.id}-{day}",
                        "video_id": clip.id,
                        "video_region": clip.region,
                        "category": clip.category,
                        "audio_id": clip.audio_id,
                        "event_type": event_type,
                        "watch_ms": watch,
                        "duration_ms": duration,
                        "completion_ratio": round(watch / duration, 4),
                        "loop_count": 0,
                        "feed_position": step,
                        "is_ad": False,
                        "campaign_id": "",
                        "tags": list(clip.tags),
                        "context": context,
                        "simulated": True,
                        "pass_id": pass_id,
                    }
                )
    return events


def orange_pass(people: list[CorpusActor], clips: list[CorpusClip]) -> list[dict]:
    """One Orange-sized insertion. Reuses generate_events; it does not write a second generator."""
    return generate_events(
        people,
        clips,
        users=ORANGE_PASS_USERS,
        days=ORANGE_PASS_DAYS,
        events_per_user=ORANGE_PASS_EVENTS_PER_USER,
        pass_id=ORANGE_PASS_ID,
    )


def early_skip_flag(event_type: str, watch_ms: int) -> int:
    return 1 if event_type == "skip" and int(watch_ms) < 2000 else 0


VIEW_EVENTS = {"play", "heartbeat", "complete", "skip"}


def _is_view(event: dict) -> bool:
    # The simulator uses social event names as one synthetic playback each.
    # Real social actions carry watch_ms too, but belong to an existing play.
    return event.get("event_type") in VIEW_EVENTS or (
        bool(event.get("simulated")) and float(event.get("watch_ms") or 0) > 0
    )


def _playbacks(events: list[dict]) -> list[dict]:
    by_exposure: dict[tuple, dict] = {}
    for index, event in enumerate(events):
        if not _is_view(event):
            continue
        session = event.get("session_id")
        key = (
            str(event.get("user_id") or ""),
            str(session),
            str(event.get("video_id") or ""),
            event.get("feed_position"),
            event.get("ts") if event.get("simulated") else None,
        ) if session and event.get("video_id") and event.get("feed_position") is not None else ("event", index)
        current = by_exposure.get(key)
        if current is None or (
            float(event.get("watch_ms") or 0), _completion_ratio(event), event.get("event_type") != "play"
        ) > (
            float(current.get("watch_ms") or 0), _completion_ratio(current), current.get("event_type") != "play"
        ):
            by_exposure[key] = event
    return list(by_exposure.values())


def _completion_ratio(event: dict) -> float:
    ratio = event.get("completion_ratio")
    if ratio is None:
        duration = float(event.get("duration_ms") or 0)
        ratio = float(event.get("watch_ms") or 0) / duration if duration > 0 else 0
    return max(0.0, min(1.0, float(ratio)))


def _view_summary(events: list[dict]) -> dict:
    views = _playbacks(events)
    user_ids = {str(event["user_id"]) for event in views if event.get("user_id")}
    watch_ms = sum(max(0.0, float(event.get("watch_ms") or 0)) for event in views)
    return {
        "views": len(views),
        "completion_rate": round(sum(_completion_ratio(event) for event in views) / len(views), 4) if views else 0,
        "early_abandon_rate": round(
            sum(early_skip_flag(str(event.get("event_type") or ""), int(event.get("watch_ms") or 0)) for event in views)
            / len(views), 4
        ) if views else 0,
        "retention_minutes": round(watch_ms / len(user_ids) / 60000, 2) if user_ids else 0,
    }


def with_dimensions(
    event: dict,
    *,
    user_region: str = "",
    video_region: str = "",
    category: str = "",
    audio_id: str = "",
    user_role: str = "",
    tags: list[str] | None = None,
) -> dict:
    row = dict(event)
    row["user_region"] = user_region or event.get("user_region") or ""
    row["video_region"] = video_region or event.get("video_region") or ""
    row["category"] = category or event.get("category") or ""
    row["audio_id"] = audio_id or event.get("audio_id") or ""
    row["user_role"] = user_role or event.get("user_role") or ""
    if tags is not None:
        row["tags"] = list(tags)
    elif not isinstance(row.get("tags"), list):
        raw = row.get("tags") or []
        row["tags"] = raw.split("|") if isinstance(raw, str) else list(raw)
    return row


def _tag_text(tags: object) -> str:
    if isinstance(tags, str):
        return tags
    if isinstance(tags, list):
        return "|".join(str(tag) for tag in tags)
    return ""


def build_orange_csv(events: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ORANGE_COLUMNS)
    for event in events:
        watch = int(event.get("watch_ms") or 0)
        event_type = str(event.get("event_type") or "")
        timestamp = event.get("ts")
        position = event.get("feed_position")
        writer.writerow(
            [
                event.get("user_id") or "",
                event.get("user_role") or "",
                event.get("user_region") or "",
                event.get("video_id") or "",
                event.get("video_region") or "",
                event.get("category") or "",
                event.get("audio_id") or "",
                event_type,
                watch,
                int(event.get("duration_ms") or 0),
                float(event.get("completion_ratio") or 0),
                early_skip_flag(event_type, watch),
                1 if event.get("is_ad") else 0,
                event.get("campaign_id") or "",
                event.get("session_id") or "",
                _tag_text(event.get("tags")),
                event.get("pass_id") or "",
                str(event.get("event_id") or event.get("_id") or ""),
                timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp or ""),
                "" if position is None else position,
                event.get("exposure_id") or "",
                event.get("gender") or "unspecified",
                event.get("origin") or "legacy",
            ]
        )
    return buffer.getvalue()


def region_breakdown(events: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for event in events:
        region = str(event.get("video_region") or "").strip()
        if not region:
            continue
        buckets.setdefault(region, []).append(event)
    rows: list[dict] = []
    for region in sorted(buckets):
        bucket = buckets[region]
        rows.append(
            {
                "region": region,
                "events": len(bucket),
                **_view_summary(bucket),
            }
        )
    return rows


def empty_metrics() -> dict:
    return {
        "retention_minutes": 0,
        "completion_rate": 0,
        "early_abandon_rate": 0,
        "new_creator_share": 0,
        "diversity_index": 0,
        "ad_fill_rate": 0,
        "events": 0,
        "views": 0,
        "active_users": 0,
        "comments": 0,
        "shares": 0,
        "follows": 0,
        "hashtag_taps": 0,
        "comment_opens": 0,
        "share_opens": 0,
        "regions": [],
        "selected": None,
    }


def metrics_from_events(events: list[dict], traces: list[dict] | None = None) -> dict:
    if not events:
        return empty_metrics()
    summary = _view_summary(events)
    impressions = 0
    ads = 0
    video_ids: set[str] = set()
    for event in events:
        if event.get("video_id"):
            video_ids.add(str(event["video_id"]))
        if event.get("event_type") == "impression":
            impressions += 1
            if event.get("is_ad"):
                ads += 1

    explore = 0
    total_final = 0
    for trace in traces or []:
        payload = trace.get("trace") or {}
        explore += int(payload.get("explore_in_final") or 0)
        total_final += int(payload.get("final") or 0)

    unique_ratio = len(video_ids) / max(len(events), 1)
    return {
        **summary,
        "new_creator_share": round(explore / max(total_final, 1), 4),
        "diversity_index": round(min(1.0, unique_ratio * 4), 4),
        "ad_fill_rate": round(ads / impressions, 4) if impressions else 0,
        "events": len(events),
        "active_users": len({event["user_id"] for event in events if event.get("user_id")}),
        "comments": sum(1 for event in events if event.get("event_type") == "comment"),
        "shares": sum(1 for event in events if event.get("event_type") == "share"),
        "follows": sum(1 for event in events if event.get("event_type") == "follow"),
        "hashtag_taps": sum(1 for event in events if event.get("event_type") == "hashtag_tap"),
        "comment_opens": sum(1 for event in events if event.get("event_type") == "comment_open"),
        "share_opens": sum(1 for event in events if event.get("event_type") == "share_open"),
        "regions": region_breakdown(events),
        "selected": None,
    }


def _same(value: object, chosen: str) -> bool:
    return str(value or "").strip().casefold() == chosen.casefold()


def _narrow(events: list[dict], *, region: str = "", category: str = "") -> list[dict]:
    rows = events
    if region:
        rows = [event for event in rows if _same(event.get("video_region"), region)]
    if category:
        rows = [event for event in rows if _same(event.get("category"), category)]
    return rows


def category_breakdown(events: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for event in events:
        category = str(event.get("category") or "").strip()
        if not category:
            continue
        buckets.setdefault(category, []).append(event)
    rows: list[dict] = []
    for category, bucket in buckets.items():
        rows.append(
            {
                "category": category,
                "events": len(bucket),
                **_view_summary(bucket),
            }
        )
    rows.sort(key=lambda row: (-int(row["events"]), str(row["category"])))
    return rows


def event_type_breakdown(events: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("event_type") or "").strip() or "sin tipo"
        counts[kind] = counts.get(kind, 0) + 1
    rows = [{"event_type": kind, "events": count} for kind, count in counts.items()]
    rows.sort(key=lambda row: (-int(row["events"]), str(row["event_type"])))
    return rows


def daily_breakdown(events: list[dict], *, today: date | None = None, days: int = 8) -> list[dict]:
    """UTC dates touched by a rolling seven-day window, including both partial end days."""
    last_day = today or datetime.now(timezone.utc).date()
    first_day = last_day - timedelta(days=days - 1)
    buckets: dict[date, list[dict]] = {}
    for event in events:
        timestamp = event.get("ts")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
        if not isinstance(timestamp, datetime):
            continue
        stamp = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
        day = stamp.date()
        if first_day <= day <= last_day:
            buckets.setdefault(day, []).append(event)
    return [
        {
            "date": (first_day + timedelta(days=index)).isoformat(),
            "events": len(bucket),
            "views": len(_playbacks(bucket)),
        }
        for index in range(days)
        for bucket in [buckets.get(first_day + timedelta(days=index), [])]
    ]


def _focus(events: list[dict], *, region: str = "", category: str = "") -> dict:
    return {
        "region": region,
        "category": category,
        "events": len(events),
        **_view_summary(events),
    }


def dashboard_slice(
    events: list[dict],
    region: str | None = None,
    traces: list[dict] | None = None,
    *,
    category: str | None = None,
) -> dict:
    """Cross-filtered report. A region slicer does not hide the other regions; a category slicer does not hide the other categories."""
    chosen_region = str(region or "").strip()
    chosen_category = str(category or "").strip()
    report = metrics_from_events(events, traces)
    report["available_regions"] = [row["region"] for row in report["regions"]]
    report["available_categories"] = [row["category"] for row in category_breakdown(events)]
    report["regions"] = region_breakdown(_narrow(events, category=chosen_category))
    report["categories"] = category_breakdown(_narrow(events, region=chosen_region))
    focused = _narrow(events, region=chosen_region, category=chosen_category)
    report["event_types"] = event_type_breakdown(focused)
    report["daily"] = daily_breakdown(focused)
    report["focus"] = _focus(focused, region=chosen_region, category=chosen_category)
    if not chosen_region:
        report["selected"] = None
        return report
    selected = next(
        (row for row in report["regions"] if str(row["region"]).casefold() == chosen_region.casefold()),
        None,
    )
    report["selected"] = selected or {
        "region": chosen_region,
        "events": 0,
        "completion_rate": 0.0,
        "retention_minutes": 0.0,
    }
    return report
