"""Pure exposure reduction shared by analytics, exports and training."""
import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.ml.features import TASKS


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def dataset_rows(exposures, now=None):
    now = now or datetime.now(timezone.utc)
    groups = defaultdict(list)
    for exp in exposures:
        groups[(exp["user_id"], exp["session_id"])].append(exp)
    rows = []
    for sequence in groups.values():
        sequence.sort(key=lambda e: (utc(e["started_at"]), e["_id"]))
        for i, e in enumerate(sequence):
            start = utc(e["started_at"])
            end = utc(e.get("closed_at") or e.get("last_event_at") or e["started_at"])
            mature = now >= end + timedelta(hours=24)
            closed = bool(e.get("closed_at")) and e.get("close_reason") != "error"
            played = bool(e.get("played"))
            next_e = sequence[i + 1] if i + 1 < len(sequence) else None
            next_ok = bool(next_e and 0 <= (utc(next_e["started_at"]) - end).total_seconds() <= 60
                           and next_e.get("watch_ms", 0) >= 2000)
            duration = max(int(e.get("duration_ms", 1)), 1)
            complete = int(e.get("coverage_ms", 0) >= duration * .9)
            row = {
                "exposure_id": e["_id"], "user_id": e["user_id"], "session_id": e["session_id"],
                "video_id": e["video_id"], "campaign_id": e.get("campaign_id") or "",
                "creative_id": e.get("creative_id") or "", "gender": e.get("gender", "unspecified"),
                "started_at": start.isoformat(), "label_end_at": (end + timedelta(hours=24)).isoformat(),
                "origin": e.get("origin", "real"), "is_ad": int(bool(e.get("campaign_id"))),
                "features": e.get("features", {}), "feature_version": e.get("feature_version", ""),
                "complete": complete, "engage": int(bool(e.get("liked") or e.get("shared"))),
                "continue": int(next_ok), "click": int(bool(e.get("clicked"))),
                "mask_complete": int(mature and played and (closed or complete)),
                "mask_engage": int(bool(mature and (closed or e.get("liked") or e.get("shared")))),
                "mask_continue": int(mature and closed and e.get("close_reason") != "ad_click" and not e.get("clicked")),
                "mask_click": int(bool(mature and e.get("campaign_id") and (closed or e.get("clicked")))),
                "watch_ms": int(e.get("watch_ms", 0)),
                "early_skip": int(closed and e.get("close_reason") == "next" and played and e.get("watch_ms", 0) < 2000),
                "observed_close": int(closed), "model_version": e.get("model_version", "heuristic-v1"),
                "selection_probability": e.get("selection_probability", 1),
            }
            rows.append(row)
    return sorted(rows, key=lambda r: (r["started_at"], r["exposure_id"]))


def metrics_for(rows):
    n = len(rows)
    def rate(task):
        observed = [r for r in rows if r[f"mask_{task}"]]
        return sum(r[task] for r in observed) / len(observed) if observed else None
    clicks = sum(r["click"] for r in rows)
    ads = sum(r["is_ad"] for r in rows)
    return {"impressions": n, "users": len({r["user_id"] for r in rows}), "clicks": clicks,
            "ctr": clicks / ads if ads else None, "ad_impressions": ads,
            **{f"{t}_rate": rate(t) for t in TASKS[:3]},
            "mature_exposures": sum(bool(r["mask_complete"]) for r in rows)}


def csv_export(rows):
    output = io.StringIO()
    fields = list(rows[0]) if rows else ["exposure_id", "user_id", "gender", *TASKS]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "features": json.dumps(row["features"], ensure_ascii=False, sort_keys=True)} if "features" in row else row)
    return output.getvalue()
