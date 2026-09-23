"""Offline day-5 ranking example from the Orange models (not the live feed)."""

from __future__ import annotations

import json
import math
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from Orange.base import Model
from Orange.data import DiscreteVariable, Table

from construir_modelos import SOURCE, ROOT, TARGET, rate


def table_for_model(model: Model, rows: pd.DataFrame) -> Table:
    original_domain = model.original_domain
    columns = []
    for var in original_domain.attributes:
        if isinstance(var, DiscreteVariable):
            mapping = {value: index for index, value in enumerate(var.values)}
            columns.append(rows[var.name].fillna("unknown").astype(str).map(mapping).to_numpy(dtype=float))
        else:
            columns.append(rows[var.name].to_numpy(dtype=float))
    metas = rows[["user_id", "video_id", "session_id"]].fillna("").astype(str).to_numpy(dtype=object)
    return Table.from_numpy(original_domain, np.column_stack(columns),
                            np.full(len(rows), np.nan), metas)


def score(model: Model, rows: pd.DataFrame) -> list[float]:
    return [float(value) for value in model(table_for_model(model, rows), Model.Probs)[:, 1]]


def main() -> None:
    raw = pd.read_csv(SOURCE)
    sim = raw.loc[
        (raw["is_ad"] == 0)
        & raw["session_id"].astype(str).str.contains("sim-", regex=False)
        & raw["event_type"].isin(("complete", "skip"))
    ].copy()
    sim["day"] = pd.to_numeric(sim["session_id"].str.extract(r"-(\d+)$")[0], errors="coerce")
    sim = sim.loc[sim["day"].between(0, 4)].drop_duplicates(
        subset=("user_id", "day", "video_id", "event_type", "watch_ms", "duration_ms")
    ).copy()
    sim[TARGET] = (sim["event_type"] == "complete").astype(int)
    user_id = str(sim.groupby("user_id").size().idxmax())
    history = sim.loc[sim["user_id"] == user_id]
    identity = history.iloc[0]
    overall = rate(history)
    overall_count = math.log1p(len(history))
    by_category = {
        key: (rate(group), math.log1p(len(group))) for key, group in history.groupby("category")
    }
    by_region = {
        key: (rate(group), math.log1p(len(group))) for key, group in history.groupby("video_region")
    }

    cat_rows = []
    for category in sorted(raw.loc[raw["is_ad"] == 0, "category"].dropna().unique()):
        category_rate, category_count = by_category.get(category, (0.5, 0.0))
        cat_rows.append({
            "user_id": user_id, "video_id": "", "session_id": "ejemplo-dia-5",
            "user_role": identity["user_role"], "user_region": identity["user_region"],
            "category": category, "prior_category_rate": category_rate,
            "prior_category_count": category_count, "prior_overall_rate": overall,
            "prior_overall_count": overall_count,
        })
    cat_frame = pd.DataFrame(cat_rows)
    with (ROOT / "categoria" / "model.pkcls").open("rb") as handle:
        category_model = pickle.load(handle)
    cat_frame["probabilidad_completar"] = score(category_model, cat_frame)
    cat_frame = cat_frame.sort_values("probabilidad_completar", ascending=False)

    seen = set(raw.loc[raw["user_id"] == user_id, "video_id"].dropna().astype(str))
    catalog = raw.loc[raw["is_ad"] == 0].drop_duplicates("video_id")
    catalog = catalog.loc[~catalog["video_id"].astype(str).isin(seen)].copy()
    catalog = catalog.loc[catalog["video_id"].notna() & catalog["category"].notna()]
    video_rows = []
    for _, candidate in catalog.iterrows():
        category = candidate["category"]
        region = candidate["video_region"]
        category_rate, category_count = by_category.get(category, (0.5, 0.0))
        region_rate, region_count = by_region.get(region, (0.5, 0.0))
        video_rows.append({
            "user_id": user_id, "video_id": str(candidate["video_id"]),
            "session_id": "ejemplo-dia-5", "user_role": identity["user_role"],
            "user_region": identity["user_region"], "video_region": region,
            "category": category, "audio_id": candidate["audio_id"], "tags": candidate["tags"],
            "duration_s": float(candidate["duration_ms"]) / 1000.0,
            "same_region": int(identity["user_region"] == region),
            "prior_category_rate": category_rate, "prior_category_count": category_count,
            "prior_overall_rate": overall, "prior_overall_count": overall_count,
            "prior_region_rate": region_rate, "prior_region_count": region_count,
        })
    video_frame = pd.DataFrame(video_rows)
    with (ROOT / "video" / "model.pkcls").open("rb") as handle:
        video_model = pickle.load(handle)
    video_frame["probabilidad_completar"] = score(video_model, video_frame)
    video_frame = video_frame.sort_values("probabilidad_completar", ascending=False)

    ad_catalog = raw.loc[raw["is_ad"] == 1].drop_duplicates("campaign_id")
    ad_candidates = []
    for _, ad in ad_catalog.iterrows():
        category_rate, category_count = by_category.get(ad["category"], (0.5, 0.0))
        ad_candidates.append({
            "campaign_id": str(ad["campaign_id"]), "video_id": str(ad["video_id"]),
            "category": ad["category"],
            "organic_category_count_log": category_count,
            "afinidad_exploratoria": 0.7 * category_rate + 0.3 * overall,
        })
    ad_candidates.sort(key=lambda row: row["afinidad_exploratoria"], reverse=True)
    result = {
        "example_user_id": user_id,
        "history_terminal_rows_days_0_to_4": len(history),
        "category_candidates": len(cat_frame),
        "video_candidates_unseen_by_this_user": len(video_frame),
        "ad_campaign_candidates": len(ad_candidates),
        "top_categories": cat_frame[["category", "probabilidad_completar"]].head(5).to_dict("records"),
        "top_videos": video_frame[["video_id", "category", "video_region", "probabilidad_completar"]].head(10).to_dict("records"),
        "ad_affinity": ad_candidates,
        "scope": "Offline scores for hypothetical day 5. Does not execute live feed filters, diversity, auction, budget or frequency cap.",
    }
    (ROOT / "ejemplo_ranking.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
