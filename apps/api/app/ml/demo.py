"""Explicitly synthetic fixture, never used to promote a serving model."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
import numpy as np
from app.demographics import GENDERS
from app.ml.features import FEATURE_VERSION
from app.telemetry.exposures import dataset_rows, csv_export


def demo_exposures(users=60, days=30, seed=42, campaigns=3, base=None):
    rng = np.random.default_rng(seed)
    base = base or datetime(2026, 1, 1, tzinfo=timezone.utc)
    categories = ("ciencia", "musica", "arte", "deportes")
    exposures = []
    for u in range(users):
        tastes = rng.uniform(.1, .9, 4)
        history = np.zeros(4)
        counts = np.zeros(4)
        for day in range(days):
            start = base + timedelta(days=day, minutes=u*3)
            for slot in range(8):
                c = int(rng.integers(4))
                duration = int(rng.choice([10000, 15000, 20000]))
                ad = slot in (2, 7)
                campaign = f"demo-campaign-{int(rng.integers(campaigns))}" if ad else None
                affinity = (history[c]+.5)/(counts[c]+1)
                p_complete = .15 + .7*tastes[c]
                complete = rng.random() < p_complete
                watch = duration if complete else int(rng.uniform(500, duration*.7))
                click = ad and rng.random() < .05 + .22*tastes[c]
                ident = str(uuid5(NAMESPACE_URL, f"veta-demo-{seed}-{base.date()}-{campaigns}-{u}-{day}-{slot}"))
                gender = GENDERS[u % len(GENDERS)]
                predictive_gender = gender if gender in ("man", "woman", "other") else "unspecified"
                exposures.append({"_id": ident, "user_id": f"demo-user-{u}", "session_id": f"demo-{u}-{day}",
                    "video_id": f"demo-video-{c}-{slot}", "campaign_id": campaign, "creative_id": f"{campaign}-creative" if ad else None,
                    "gender": gender, "origin": "simulated", "duration_ms": duration, "started_at": start,
                    "closed_at": start+timedelta(milliseconds=watch), "close_reason": "ad_click" if click else "ended" if complete else "next",
                    "watch_ms": watch, "coverage_ms": watch, "played": True, "liked": bool(rng.random() < .02+.25*tastes[c]),
                    "shared": bool(rng.random() < .03), "clicked": bool(click), "feature_version": FEATURE_VERSION,
                    "features": {"affinity": affinity, "topic": affinity, "duration_s": duration/1000,
                                 "category": categories[c], "is_ad": int(ad), "gender": predictive_gender,
                                 "new_user": int(day == 0), "same_region": int(rng.random()<.5)}})
                history[c] += int(complete); counts[c] += 1
                start += timedelta(milliseconds=watch+1000)
    return exposures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    args = parser.parse_args()
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(csv_export(dataset_rows(demo_exposures(), datetime(2027, 1, 1, tzinfo=timezone.utc))), encoding="utf-8")
    print(f"Synthetic dataset written to {path}")
