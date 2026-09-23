"""Build an Orange-compatible early-skip model from Veta interaction events.

Run with the Python interpreter installed with Orange. Evaluation holds out entire
sessions, so repeated events from one session cannot appear in both splits.
"""

from __future__ import annotations

import base64
import json
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
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit


SOURCE = Path(r"C:\Users\lelie\Downloads\veta_interactions.csv")
OUTPUT = Path(__file__).resolve().parent
CATEGORICAL = (
    "user_role",
    "user_region",
    "video_region",
    "category",
    "audio_id",
    "is_ad",
    "tags",
)
NUMERIC = ("duration_s",)
META = ("user_id", "video_id", "session_id")
SEED = 42


def make_table(frame: pd.DataFrame) -> Table:
    variables = []
    columns = []
    for name in CATEGORICAL:
        values = tuple(sorted(frame[name].astype(str).unique()))
        variable = DiscreteVariable(name, values=values)
        codes = pd.Categorical(frame[name].astype(str), categories=values).codes
        variables.append(variable)
        columns.append(codes.astype(float))
    for name in NUMERIC:
        variables.append(ContinuousVariable(name))
        columns.append(frame[name].to_numpy(dtype=float))
    target = DiscreteVariable("early_skip", values=("0", "1"))
    domain = Domain(variables, target, [StringVariable(name) for name in META])
    x = np.column_stack(columns)
    y = frame["early_skip"].to_numpy(dtype=float)
    metas = frame.loc[:, META].astype(str).to_numpy(dtype=object)
    return Table.from_numpy(domain, x, y, metas)


def metrics(y: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    pred = (scores >= threshold).astype(int)
    return {
        "auc": float(roc_auc_score(y, scores)),
        "average_precision": float(average_precision_score(y, scores)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision_1": float(precision_score(y, pred, zero_division=0)),
        "recall_1": float(recall_score(y, pred, zero_division=0)),
        "f1_1": float(f1_score(y, pred, zero_division=0)),
        "confusion_matrix_0_1": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
    }


def oof_scores(learner, data: Table, groups: np.ndarray) -> np.ndarray:
    scores = np.full(len(data), np.nan)
    for train, valid in GroupKFold(n_splits=4).split(np.zeros(len(data)), data.Y, groups):
        fitted = learner(data[train])
        scores[valid] = fitted(data[valid], Model.Probs)[:, 1]
    return scores


def make_workflow(paths: dict[str, Path], model_name: str) -> Path:
    """Write a standard Orange .ows with a held-out-session evaluation branch."""
    scheme = ET.Element(
        "scheme",
        version="2.0",
        title="Veta: predicción de abandono temprano",
        description=(
            "Clasifica skip frente a complete. La prueba contiene sesiones "
            "distintas del entrenamiento. La rama de datos completos entrena "
            "el modelo final."
        ),
    )
    nodes = ET.SubElement(scheme, "nodes")
    node_specs = [
        (0, "File", "Orange.widgets.data.owfile.OWFile", "Entrenamiento (sesiones)", (85, 235)),
        (1, "File", "Orange.widgets.data.owfile.OWFile", "Prueba (sesiones)", (85, 390)),
        (2, "File", "Orange.widgets.data.owfile.OWFile", "Eventos terminales completos", (85, 560)),
        (3, "Random Forest", "Orange.widgets.model.owrandomforest.OWRandomForest", "Bosque aleatorio", (365, 170)),
        (4, "Logistic Regression", "Orange.widgets.model.owlogisticregression.OWLogisticRegression", "Regresión logística", (365, 275)),
        (5, "Test and Score", "Orange.widgets.evaluate.owtestandscore.OWTestAndScore", "Evaluación por sesión", (585, 330)),
        (6, "Confusion Matrix", "Orange.widgets.evaluate.owconfusionmatrix.OWConfusionMatrix", "Matriz de confusión", (820, 265)),
        (7, "ROC Analysis", "Orange.widgets.evaluate.owrocanalysis.OWROCAnalysis", "Curva ROC", (820, 390)),
        (8, "Random Forest", "Orange.widgets.model.owrandomforest.OWRandomForest", "Modelo final", (365, 555)),
        (9, "Save Model", "Orange.widgets.model.owsavemodel.OWSaveModel", "Guardar modelo", (585, 555)),
        (10, "Data Table", "Orange.widgets.data.owtable.OWTable", "Datos terminales", (275, 690)),
    ]
    for node_id, name, qualified, title, (x, y) in node_specs:
        ET.SubElement(
            nodes,
            "node",
            id=str(node_id),
            name=name,
            qualified_name=qualified,
            project_name="Orange3",
            version="",
            title=title,
            position=f"({float(x)}, {float(y)})",
        )

    links = ET.SubElement(scheme, "links")
    link_specs = [
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
    for link_id, (source, sink, source_channel, sink_channel, source_id, sink_id) in enumerate(link_specs):
        ET.SubElement(
            links,
            "link",
            id=str(link_id),
            source_node_id=str(source),
            sink_node_id=str(sink),
            source_channel=source_channel,
            sink_channel=sink_channel,
            enabled="true",
            source_channel_id=source_id,
            sink_channel_id=sink_id,
        )

    ET.SubElement(scheme, "annotations")
    ET.SubElement(scheme, "thumbnail")
    properties = ET.SubElement(scheme, "node_properties")
    for node_id, path_key in ((0, "train"), (1, "test"), (2, "all")):
        settings = {
            "source": 0,
            "recent_paths": [RecentPath(str(paths[path_key]), None, None)],
        }
        encoded = base64.b64encode(pickle.dumps(settings)).decode("ascii")
        ET.SubElement(properties, "properties", node_id=str(node_id), format="pickle").text = encoded
    for node_id in (3, 8):
        settings = {
            "n_estimators": 100,
            "class_weight": model_name == "Random Forest (balanced)",
            "auto_apply": True,
            "__version__": 1,
        }
        ET.SubElement(properties, "properties", node_id=str(node_id), format="literal").text = repr(settings)
    ET.SubElement(properties, "properties", node_id="5", format="literal").text = repr(
        {"resampling": 5, "__version__": 4}
    )
    ET.SubElement(properties, "properties", node_id="9", format="literal").text = repr(
        {"stored_path": str(paths["model"]), "stored_name": paths["model"].name, "auto_save": False}
    )
    ET.SubElement(ET.SubElement(scheme, "session_state"), "window_groups")
    output = OUTPUT / "veta_modelado.ows"
    ET.indent(scheme, space="  ")
    ET.ElementTree(scheme).write(output, encoding="utf-8", xml_declaration=True)
    return output


def main() -> None:
    frame = pd.read_csv(SOURCE)
    terminal = frame.loc[frame["event_type"].isin(("complete", "skip"))].copy()
    if not (terminal["early_skip"].eq(terminal["event_type"].eq("skip").astype(int))).all():
        raise ValueError("early_skip is inconsistent with terminal event types")
    terminal.reset_index(drop=True, inplace=True)
    terminal["duration_s"] = terminal["duration_ms"] / 1000.0
    data = make_table(terminal)
    groups = terminal["session_id"].to_numpy()
    train_indices, test_indices = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(
            np.zeros(len(data)), data.Y, groups
        )
    )
    train, test = data[train_indices], data[test_indices]
    train_groups = groups[train_indices]
    train_y = train.Y.astype(int).ravel()
    test_y = test.Y.astype(int).ravel()

    paths = {
        "all": OUTPUT / "veta_terminal_all.tab",
        "train": OUTPUT / "veta_terminal_train.tab",
        "test": OUTPUT / "veta_terminal_test.tab",
        "model": OUTPUT / "veta_early_skip_model.pkcls",
    }
    data.save(str(paths["all"]))
    train.save(str(paths["train"]))
    test.save(str(paths["test"]))

    learners = {
        "Random Forest": RandomForestLearner(n_estimators=100, random_state=SEED, n_jobs=-1),
        "Random Forest (balanced)": RandomForestLearner(
            n_estimators=100, random_state=SEED, n_jobs=-1, class_weight="balanced"
        ),
        "Logistic Regression": LogisticRegressionLearner(max_iter=1000, random_state=SEED),
        "Logistic Regression (balanced)": LogisticRegressionLearner(
            max_iter=1000, random_state=SEED, class_weight="balanced"
        ),
    }
    evaluations = {}
    for name, learner in learners.items():
        oof = oof_scores(learner, train, train_groups)
        grid = np.linspace(0.05, 0.95, 91)
        threshold = float(max(grid, key=lambda t: f1_score(train_y, oof >= t, zero_division=0)))
        fitted = learner(train)
        test_scores = fitted(test, Model.Probs)[:, 1]
        evaluations[name] = {
            "threshold_from_group_cv": threshold,
            "group_cv": metrics(train_y, oof, threshold),
            "held_out_sessions": metrics(test_y, test_scores, threshold),
        }
        print(name, evaluations[name]["held_out_sessions"], flush=True)

    chosen = max(evaluations, key=lambda name: evaluations[name]["group_cv"]["average_precision"])
    final_model = learners[chosen](data)
    with paths["model"].open("wb") as out:
        pickle.dump(final_model, out)
    workflow = make_workflow(paths, chosen)
    report = {
        "source": str(SOURCE),
        "task": "Predict early_skip for terminal complete/skip watch events",
        "definition": "early_skip=1 for skip events; early_skip=0 for complete events",
        "n_raw_events": int(len(frame)),
        "n_terminal_events": int(len(terminal)),
        "n_train_events": int(len(train)),
        "n_test_events": int(len(test)),
        "n_train_sessions": int(len(set(groups[train_indices]))),
        "n_test_sessions": int(len(set(groups[test_indices]))),
        "positive_rate_train": float(train_y.mean()),
        "positive_rate_test": float(test_y.mean()),
        "features": list(CATEGORICAL + NUMERIC),
        "excluded": ["event_type", "watch_ms", "completion_ratio", "user_id", "video_id", "session_id", "campaign_id", "pass_id"],
        "chosen_model": chosen,
        "chosen_threshold": evaluations[chosen]["threshold_from_group_cv"],
        "evaluation": evaluations,
        "artifacts": {key: str(path) for key, path in paths.items()} | {"workflow": str(workflow)},
        "caveat": "A session-level holdout checks new sessions among the same overall catalog/users. It does not prove performance on new videos or users.",
    }
    (OUTPUT / "veta_early_skip_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("chosen", chosen, "threshold", report["chosen_threshold"], flush=True)


if __name__ == "__main__":
    main()
