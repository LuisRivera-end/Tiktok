"""Build reproducible Orange candidate-response models for the Veta lab.

The CSV has no timestamp or feed position. These models score candidate items;
they do not learn an observed next-item sequence. Simulated session suffixes
provide a day number, so organic taste features use strictly earlier days.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import pickle
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from Orange.base import Model
from Orange.classification import LogisticRegressionLearner, RandomForestLearner
from Orange.data import ContinuousVariable, DiscreteVariable, Domain, StringVariable, Table
from Orange.widgets.utils.filedialogs import RecentPath
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit


SOURCE = Path(r"C:\Users\lelie\Downloads\veta_interactions.csv")
ROOT = Path(__file__).resolve().parent
SEED = 42
TARGET = "complete_response"

CATEGORY_CATS = ("user_role", "user_region", "category")
CATEGORY_NUMS = (
    "prior_category_rate", "prior_category_count", "prior_overall_rate", "prior_overall_count"
)
VIDEO_CATS = (
    "user_role", "user_region", "video_region", "category", "audio_id", "tags"
)
VIDEO_NUMS = CATEGORY_NUMS + ("prior_region_rate", "prior_region_count", "duration_s", "same_region")
META = ("user_id", "video_id", "session_id")


def rate(events: pd.DataFrame) -> float:
    # Shrink sparse user histories toward 0.5 rather than asserting a taste
    # from one watch. This is computed only from history available to a row.
    return float((events[TARGET].sum() + 2.0) / (len(events) + 4.0))


def organic_rows(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    sim = raw.loc[
        (raw["is_ad"] == 0)
        & raw["session_id"].astype(str).str.contains("sim-", regex=False)
        & raw["event_type"].isin(("complete", "skip"))
    ].copy()
    sim["day"] = pd.to_numeric(
        sim["session_id"].astype(str).str.extract(r"-(\d+)$")[0], errors="coerce"
    )
    sim = sim.loc[sim["day"].between(0, 4)].copy()
    n_before = len(sim)
    # Older exports repeated the same deterministic simulator events across
    # runs. The CSV has no event ID; collapse indistinguishable observations.
    sim = sim.drop_duplicates(
        subset=("user_id", "day", "video_id", "event_type", "watch_ms", "duration_ms")
    ).copy()
    sim[TARGET] = (sim["event_type"] == "complete").astype(int)
    sim["duration_s"] = sim["duration_ms"] / 1000.0
    sim["same_region"] = (sim["user_region"] == sim["video_region"]).astype(int)
    rows = []
    for user_id, user_rows in sim.groupby("user_id", sort=False):
        for day in range(1, 5):
            prior = user_rows.loc[user_rows["day"] < day]
            current = user_rows.loc[user_rows["day"] == day].copy()
            if current.empty or prior.empty:
                continue
            current["prior_overall_rate"] = rate(prior)
            current["prior_overall_count"] = math.log1p(len(prior))
            by_category = prior.groupby("category", sort=False)
            by_region = prior.groupby("video_region", sort=False)
            category_rate = {key: rate(group) for key, group in by_category}
            category_count = {key: math.log1p(len(group)) for key, group in by_category}
            region_rate = {key: rate(group) for key, group in by_region}
            region_count = {key: math.log1p(len(group)) for key, group in by_region}
            current["prior_category_rate"] = current["category"].map(category_rate).fillna(0.5)
            current["prior_category_count"] = current["category"].map(category_count).fillna(0.0)
            current["prior_region_rate"] = current["video_region"].map(region_rate).fillna(0.5)
            current["prior_region_count"] = current["video_region"].map(region_count).fillna(0.0)
            rows.append(current)
    return pd.concat(rows, ignore_index=True), {
        "eligible_simulated_terminal_rows_before_collapse": n_before,
        "after_indistinguishable_row_collapse": len(sim),
        "target_rows_days_1_to_4": sum(map(len, rows)),
        "users": int(sim["user_id"].nunique()),
        "history_rule": "For day d, only simulated organic complete/skip rows from days < d",
    }


def ad_rows(raw: pd.DataFrame, organic: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    ads = raw.loc[
        (raw["is_ad"] == 1) & raw["event_type"].isin(("complete", "skip"))
    ].copy()
    n_before = len(ads)
    ads = ads.drop_duplicates(
        subset=("user_id", "session_id", "video_id", "event_type", "watch_ms", "duration_ms")
    ).copy()
    ads[TARGET] = (ads["event_type"] == "complete").astype(int)
    ads["duration_s"] = ads["duration_ms"] / 1000.0
    ads["same_region"] = (ads["user_region"] == ads["video_region"]).astype(int)
    # This is a retrospective lab descriptor, not a deployable time-safe
    # feature: the export omits event timestamps, so organic/ad order is unknown.
    base = organic.loc[organic["is_ad"] == 0]
    overall = {uid: (rate(group), math.log1p(len(group))) for uid, group in base.groupby("user_id")}
    cat = {
        (uid, category): (rate(group), math.log1p(len(group)))
        for (uid, category), group in base.groupby(["user_id", "category"])
    }
    ads["organic_overall_rate"] = [overall.get(uid, (0.5, 0.0))[0] for uid in ads["user_id"]]
    ads["organic_overall_count"] = [overall.get(uid, (0.5, 0.0))[1] for uid in ads["user_id"]]
    ads["organic_category_rate"] = [
        cat.get((uid, category), (0.5, 0.0))[0]
        for uid, category in zip(ads["user_id"], ads["category"])
    ]
    ads["organic_category_count"] = [
        cat.get((uid, category), (0.5, 0.0))[1]
        for uid, category in zip(ads["user_id"], ads["category"])
    ]
    return ads.reset_index(drop=True), {
        "ad_terminal_rows_before_collapse": n_before,
        "ad_terminal_rows": len(ads),
        "ad_users": int(ads["user_id"].nunique()),
        "ad_videos": int(ads["video_id"].nunique()),
        "ad_campaigns": int(ads["campaign_id"].nunique(dropna=True)),
        "ad_impressions": int(((raw["is_ad"] == 1) & (raw["event_type"] == "impression")).sum()),
    }


def make_table(frame: pd.DataFrame, cats: tuple[str, ...], nums: tuple[str, ...]) -> Table:
    attrs = []
    columns = []
    for name in cats:
        strings = frame[name].fillna("unknown").astype(str)
        values = tuple(sorted(strings.unique()))
        attrs.append(DiscreteVariable(name, values=values))
        columns.append(pd.Categorical(strings, categories=values).codes.astype(float))
    for name in nums:
        attrs.append(ContinuousVariable(name))
        columns.append(frame[name].to_numpy(dtype=float))
    domain = Domain(attrs, DiscreteVariable(TARGET, values=("0", "1")), [StringVariable(n) for n in META])
    return Table.from_numpy(
        domain,
        np.column_stack(columns),
        frame[TARGET].to_numpy(dtype=float),
        frame.loc[:, META].fillna("").astype(str).to_numpy(dtype=object),
    )


def scores(y: np.ndarray, probs: np.ndarray) -> dict:
    pred = (probs >= 0.5).astype(int)
    result = {
        "n": len(y),
        "positive_rate": float(y.mean()),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1_complete": float(f1_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, probs)),
        "confusion_matrix_0_skip_1_complete": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
    }
    result["auc_roc"] = float(roc_auc_score(y, probs)) if len(np.unique(y)) == 2 else None
    result["average_precision"] = float(average_precision_score(y, probs)) if y.sum() else None
    return result


def workflow(folder: Path, title: str, chosen: str) -> Path:
    scheme = ET.Element("scheme", version="2.0", title=title, description="Prueba con usuarios completos reservados. Clase 1 = reproducción completa.")
    nodes = ET.SubElement(scheme, "nodes")
    specs = [
        (0, "File", "Orange.widgets.data.owfile.OWFile", "Entrenamiento", (80, 210)),
        (1, "File", "Orange.widgets.data.owfile.OWFile", "Prueba: usuarios nuevos", (80, 365)),
        (2, "File", "Orange.widgets.data.owfile.OWFile", "Todos los datos preparados", (80, 565)),
        (3, "Random Forest", "Orange.widgets.model.owrandomforest.OWRandomForest", "Bosque aleatorio", (335, 185)),
        (4, "Logistic Regression", "Orange.widgets.model.owlogisticregression.OWLogisticRegression", "Regresión logística", (335, 295)),
        (5, "Test and Score", "Orange.widgets.evaluate.owtestandscore.OWTestAndScore", "Evaluación", (585, 305)),
        (6, "Confusion Matrix", "Orange.widgets.evaluate.owconfusionmatrix.OWConfusionMatrix", "Matriz de confusión", (830, 235)),
        (7, "ROC Analysis", "Orange.widgets.evaluate.owrocanalysis.OWROCAnalysis", "Curva ROC", (830, 365)),
        (8, "Random Forest" if chosen == "Random Forest" else "Logistic Regression",
         "Orange.widgets.model.owrandomforest.OWRandomForest" if chosen == "Random Forest" else "Orange.widgets.model.owlogisticregression.OWLogisticRegression",
         "Modelo final", (335, 565)),
        (9, "Save Model", "Orange.widgets.model.owsavemodel.OWSaveModel", "Guardar modelo", (585, 565)),
        (10, "Data Table", "Orange.widgets.data.owtable.OWTable", "Datos", (335, 710)),
    ]
    for node_id, name, qualified, label, (x, y) in specs:
        ET.SubElement(nodes, "node", id=str(node_id), name=name, qualified_name=qualified,
                      project_name="Orange3", version="", title=label,
                      position=f"({float(x)}, {float(y)})")
    links = ET.SubElement(scheme, "links")
    pairs = [
        (0, 5, "Data", "Data", "data", "train_data"),
        (1, 5, "Data", "Test Data", "data", "test_data"),
        (3, 5, "Learner", "Learner", "learner", "learner"),
        (4, 5, "Learner", "Learner", "learner", "learner"),
        (5, 6, "Evaluation Results", "Evaluation Results", "evaluations_results", "evaluation_results"),
        (5, 7, "Evaluation Results", "Evaluation Results", "evaluations_results", "evaluation_results"),
        (2, 8, "Data", "Data", "data", "data"),
        (8, 9, "Model", "Model", "model", "model"),
        (2, 10, "Data", "Data", "data", "data"),
    ]
    for link_id, (source, sink, source_channel, sink_channel, source_id, sink_id) in enumerate(pairs):
        ET.SubElement(links, "link", id=str(link_id), source_node_id=str(source), sink_node_id=str(sink),
                      source_channel=source_channel, sink_channel=sink_channel, enabled="true",
                      source_channel_id=source_id, sink_channel_id=sink_id)
    ET.SubElement(scheme, "annotations")
    ET.SubElement(scheme, "thumbnail")
    props = ET.SubElement(scheme, "node_properties")
    for node_id, filename in ((0, "train.tab"), (1, "test.tab"), (2, "all.tab")):
        setting = {"source": 0, "recent_paths": [RecentPath(str(folder / filename), None, None)]}
        encoded = base64.b64encode(pickle.dumps(setting)).decode("ascii")
        ET.SubElement(props, "properties", node_id=str(node_id), format="pickle").text = encoded
    for node_id in (3, 8):
        if node_id == 8 and chosen != "Random Forest":
            continue
        ET.SubElement(props, "properties", node_id=str(node_id), format="literal").text = repr(
            {"n_estimators": 100, "auto_apply": True, "__version__": 1}
        )
    ET.SubElement(props, "properties", node_id="5", format="literal").text = repr(
        {"resampling": 5, "__version__": 4}
    )
    ET.SubElement(props, "properties", node_id="9", format="literal").text = repr(
        {"stored_path": str(folder / "model.pkcls"), "stored_name": "model.pkcls", "auto_save": False}
    )
    ET.SubElement(ET.SubElement(scheme, "session_state"), "window_groups")
    path = folder / "flujo.ows"
    ET.indent(scheme, space="  ")
    ET.ElementTree(scheme).write(path, encoding="utf-8", xml_declaration=True)
    return path


def advertising_workflow(folder: Path) -> Path:
    scheme = ET.Element("scheme", version="2.0", title="Publicidad: afinidad exploratoria",
                        description="Una campaña y dos usuarios con respuesta positiva; sin modelo supervisado validado.")
    nodes = ET.SubElement(scheme, "nodes")
    for node_id, name, qualified, label, x, y in (
        (0, "File", "Orange.widgets.data.owfile.OWFile", "Respuestas y afinidad", 80, 260),
        (1, "Data Table", "Orange.widgets.data.owtable.OWTable", "Datos publicitarios", 335, 200),
        (2, "Distributions", "Orange.widgets.visualize.owdistributions.OWDistributions", "Distribución", 335, 365),
    ):
        ET.SubElement(nodes, "node", id=str(node_id), name=name, qualified_name=qualified,
                      project_name="Orange3", version="", title=label,
                      position=f"({float(x)}, {float(y)})")
    links = ET.SubElement(scheme, "links")
    for link_id, sink in enumerate((1, 2)):
        ET.SubElement(links, "link", id=str(link_id), source_node_id="0", sink_node_id=str(sink),
                      source_channel="Data", sink_channel="Data", enabled="true",
                      source_channel_id="data", sink_channel_id="data")
    ET.SubElement(scheme, "annotations")
    ET.SubElement(scheme, "thumbnail")
    props = ET.SubElement(scheme, "node_properties")
    encoded = base64.b64encode(pickle.dumps({
        "source": 0, "recent_paths": [RecentPath(str(folder / "afinidad.tab"), None, None)]
    })).decode("ascii")
    ET.SubElement(props, "properties", node_id="0", format="pickle").text = encoded
    ET.SubElement(ET.SubElement(scheme, "session_state"), "window_groups")
    path = folder / "flujo.ows"
    ET.indent(scheme, space="  ")
    ET.ElementTree(scheme).write(path, encoding="utf-8", xml_declaration=True)
    return path


def build_ad_exploration(ads: pd.DataFrame, info: dict) -> dict:
    folder = ROOT / "publicidad"
    folder.mkdir(parents=True, exist_ok=True)
    # This is a transparent content-affinity rule, not a fitted ad-response
    # probability. Values are comparable only among candidates for one user.
    ads = ads.copy()
    ads["afinidad_exploratoria"] = (
        0.7 * ads["organic_category_rate"] + 0.3 * ads["organic_overall_rate"]
    )
    attrs = [
        DiscreteVariable(name, values=tuple(sorted(ads[name].fillna("unknown").astype(str).unique())))
        for name in ("user_role", "user_region", "video_region", "category")
    ]
    columns = [
        pd.Categorical(ads[var.name].fillna("unknown").astype(str), categories=var.values).codes.astype(float)
        for var in attrs
    ]
    nums = ("organic_category_rate", "organic_category_count", "organic_overall_rate",
            "organic_overall_count", "afinidad_exploratoria")
    for name in nums:
        attrs.append(ContinuousVariable(name))
        columns.append(ads[name].to_numpy(dtype=float))
    domain = Domain(attrs, DiscreteVariable(TARGET, values=("0", "1")),
                    [StringVariable(name) for name in ("user_id", "video_id", "campaign_id", "session_id")])
    table = Table.from_numpy(
        domain, np.column_stack(columns), ads[TARGET].to_numpy(dtype=float),
        ads.loc[:, ("user_id", "video_id", "campaign_id", "session_id")].fillna("").astype(str).to_numpy(dtype=object)
    )
    table.save(str(folder / "afinidad.tab"))
    advertising_workflow(folder)
    result = {
        **info,
        "positive_users": int(ads.groupby("user_id")[TARGET].max().sum()),
        "complete_rows": int(ads[TARGET].sum()),
        "skip_rows": int((1 - ads[TARGET]).sum()),
        "affinity_formula": "0.7 * smoothed organic category completion rate + 0.3 * smoothed organic overall completion rate",
        "status": "exploratory affinity rule only; no validated ad response model or multi-campaign ranking",
        "limitation": "CSV has no timestamps, so the organic profile cannot be proven to predate each ad impression.",
        "paths": {"flow": str(folder / "flujo.ows"), "data": str(folder / "afinidad.tab")},
    }
    (folder / "resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("publicidad", result["status"], "positive_users", result["positive_users"], flush=True)
    return result


def build_task(name: str, frame: pd.DataFrame, cats: tuple[str, ...], nums: tuple[str, ...],
               *, folds: int) -> dict:
    folder = ROOT / name
    folder.mkdir(parents=True, exist_ok=True)
    table = make_table(frame, cats, nums)
    groups = frame["user_id"].astype(str).to_numpy()
    train_idx, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(
        np.zeros(len(frame)), frame[TARGET], groups
    ))
    train, test = table[train_idx], table[test_idx]
    train_groups = groups[train_idx]
    y_train = train.Y.astype(int).ravel()
    y_test = test.Y.astype(int).ravel()
    assert not (set(groups[train_idx]) & set(groups[test_idx])), "User leakage across holdout"
    assert len(np.unique(y_train)) == len(np.unique(y_test)) == 2, "Both classes required"
    assert np.isfinite(table.X).all(), "Model attributes must be finite"
    for filename, subset in (("all.tab", table), ("train.tab", train), ("test.tab", test)):
        subset.save(str(folder / filename))
    learners = {
        "Logistic Regression": LogisticRegressionLearner(max_iter=1000, random_state=SEED),
        "Random Forest": RandomForestLearner(n_estimators=100, random_state=SEED, n_jobs=-1),
    }
    evaluations = {}
    for learner_name, learner in learners.items():
        oof = np.full(len(train), np.nan)
        for fit_idx, valid_idx in GroupKFold(n_splits=folds).split(np.zeros(len(train)), y_train, train_groups):
            fitted = learner(train[fit_idx])
            oof[valid_idx] = fitted(train[valid_idx], Model.Probs)[:, 1]
        fit = learner(train)
        heldout_probs = fit(test, Model.Probs)[:, 1]
        evaluations[learner_name] = {
            "grouped_train_cv": scores(y_train, oof),
            "held_out_users": scores(y_test, heldout_probs),
        }
    chosen = max(
        evaluations,
        key=lambda label: evaluations[label]["grouped_train_cv"]["auc_roc"] or 0.0,
    )
    final_model = learners[chosen](table)
    with (folder / "model.pkcls").open("wb") as handle:
        pickle.dump(final_model, handle)
    workflow(folder, name.capitalize() + ": respuesta a candidato", chosen)
    result = {
        "task": name,
        "target": "complete_response = 1 for complete, 0 for skip",
        "features_categorical": list(cats),
        "features_numeric": list(nums),
        "excluded_from_features": ["event_type", "watch_ms", "completion_ratio", "early_skip", "user_id", "video_id", "session_id", "campaign_id", "pass_id"],
        "rows": len(frame),
        "train_rows": len(train),
        "test_rows": len(test),
        "train_users": int(len(set(groups[train_idx]))),
        "test_users": int(len(set(groups[test_idx]))),
        "selected_by": f"largest {folds}-fold user-grouped training CV AUC ROC",
        "selected_model": chosen,
        "evaluations": evaluations,
        "majority_accuracy_test": float(max(y_test.mean(), 1 - y_test.mean())),
        "paths": {key: str(folder / key) for key in ("all.tab", "train.tab", "test.tab", "model.pkcls", "flujo.ows")},
    }
    if name == "video":
        result["same_region_rule_test"] = scores(
            y_test, frame.iloc[test_idx]["same_region"].to_numpy(dtype=float)
        )
    (folder / "resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(name, "selected", chosen, "test", evaluations[chosen]["held_out_users"], flush=True)
    return result


def main() -> None:
    raw = pd.read_csv(SOURCE)
    expected = {"user_id", "user_role", "user_region", "video_id", "video_region", "category", "audio_id", "event_type", "watch_ms", "duration_ms", "completion_ratio", "early_skip", "is_ad", "campaign_id", "session_id", "tags", "pass_id"}
    missing = expected - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required CSV columns: {missing}")
    if not raw["is_ad"].isin([0, 1]).all():
        raise ValueError("is_ad must be binary")
    organic, organic_info = organic_rows(raw)
    ads, ad_info = ad_rows(raw, organic)
    results = {
        "categoria": build_task("categoria", organic, CATEGORY_CATS, CATEGORY_NUMS, folds=4),
        "video": build_task("video", organic, VIDEO_CATS, VIDEO_NUMS, folds=4),
        "publicidad": build_ad_exploration(ads, ad_info),
    }
    manifest = {
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "raw_rows": len(raw),
        "raw_exact_duplicate_rows": int(raw.duplicated().sum()),
        "source_has_timestamp": "event_ts" in raw and bool(raw["event_ts"].notna().any()),
        "source_has_feed_position": "feed_position" in raw and bool(raw["feed_position"].notna().any()),
        "organic_preparation": organic_info,
        "advertising_preparation": ad_info,
        "results": results,
        "interpretation": "Candidate completion propensity on observed exposures; not observed next-item prediction or causal ranking lift.",
    }
    (ROOT / "resumen.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
