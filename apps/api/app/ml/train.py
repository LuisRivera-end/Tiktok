"""python -m app.ml.train exposures.csv --output artifacts/mmoe [--origin simulated]"""
import argparse
import copy
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss, average_precision_score, roc_auc_score, brier_score_loss, ndcg_score
from app.ml.encoding import fit_encoder, encode
from app.ml.features import FEATURE_VERSION, TASKS, legacy_score
from app.ml.readiness import DatasetNotReadyError, assess, partition
from importlib.metadata import version
from app.ml.network import MMoE, masked_loss


def labels(rows):
    return (np.array([[int(r[t]) for t in TASKS] for r in rows], dtype=np.float32).reshape(-1, 4),
            np.array([[int(r[f"mask_{t}"]) for t in TASKS] for r in rows], dtype=np.float32).reshape(-1, 4))


def measurements(y, p):
    result = {"n": len(y), "positives": int(y.sum()), "status": "insufficient"}
    if len(y) < 2 or len(set(y)) < 2:
        return result
    bins = []
    for low in np.arange(0, 1, .1):
        idx = (p >= low) & (p < low + .1)
        if idx.any():
            bins.append({"n": int(idx.sum()), "predicted": float(p[idx].mean()), "observed": float(y[idx].mean())})
    return {**result, "status": "ok" if len(y) >= 100 and min(y.sum(), len(y)-y.sum()) >= 10 else "small_sample",
            "log_loss": float(log_loss(y, p, labels=[0, 1])), "pr_auc": float(average_precision_score(y, p)),
            "roc_auc": float(roc_auc_score(y, p)), "brier": float(brier_score_loss(y, p)), "calibration": bins}


def bootstrap_delta(y, p, baseline, users, seed=42):
    unique = np.unique(users)
    if len(unique) < 10 or len(y) < 100 or min(y.sum(), len(y)-y.sum()) < 10:
        return None
    def loss(q):
        q = np.clip(q, 1e-7, 1-1e-7)
        return -(y * np.log(q) + (1-y) * np.log(1-q))
    delta = loss(p) - loss(baseline)
    by_user = {u: delta[users == u] for u in unique}
    rng = np.random.default_rng(seed)
    samples = [np.concatenate([by_user[u] for u in rng.choice(unique, len(unique), replace=True)]).mean() for _ in range(500)]
    return np.quantile(samples, [.025, .975]).tolist()


def run(args):
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    raw = Path(args.input).read_bytes()
    dataset_hash = hashlib.sha256(raw).hexdigest()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    readiness_path = output / "readiness.json"
    readiness_path.write_text(json.dumps({"status": "evaluating", "origin": args.origin,
                                          "dataset_sha256": dataset_hash}), encoding="utf-8")
    with Path(args.input).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows = [r for r in rows if r.get("origin") == args.origin and r.get("feature_version") == FEATURE_VERSION]
    if args.origin == "real":
        readiness = assess(rows, args.seed)
        if readiness["status"] == "collecting":
            readiness_path.write_text(json.dumps({**readiness, "status": "insufficient_data",
                                                  "origin": "real", "dataset_sha256": dataset_hash},
                                                 ensure_ascii=False, indent=2), encoding="utf-8")
            raise DatasetNotReadyError("; ".join(readiness["reasons"]))
    elif len({r["exposure_id"] for r in rows}) != len(rows):
        raise ValueError("exposure_id duplicados")
    for r in rows:
        r["features"] = json.loads(r["features"])
    groups = partition(rows, args.seed)
    reports, artifacts, predictions = {}, {}, {}
    for use_gender in (False, True):
        name = "with_gender" if use_gender else "without_gender"
        encoder = fit_encoder([r["features"] for r in groups["train"]], use_gender)
        xs = {k: encode([r["features"] for r in v], encoder) for k, v in groups.items()}
        ys = {k: labels(v) for k, v in groups.items()}
        if not ys["train"][1].any() or not ys["validation"][1].any():
            raise ValueError("No hay etiquetas observables en entrenamiento o validación")
        torch.manual_seed(args.seed)
        model = MMoE(xs["train"].shape[1])
        optimizer = torch.optim.Adam(model.parameters(), lr=.001)
        best, state, stale = float("inf"), None, 0
        x, y, mask = torch.from_numpy(xs["train"]), torch.from_numpy(ys["train"][0]), torch.from_numpy(ys["train"][1])
        for epoch in range(args.epochs):
            model.train()
            for idx in torch.randperm(len(x)).split(128):
                if not mask[idx].any():
                    continue
                optimizer.zero_grad()
                loss = masked_loss(model(x[idx]), y[idx], mask[idx])
                loss.backward()
                optimizer.step()
            model.eval()
            with torch.no_grad():
                value = float(masked_loss(model(torch.from_numpy(xs["validation"])), torch.from_numpy(ys["validation"][0]), torch.from_numpy(ys["validation"][1])))
            if value < best - 1e-5:
                best, state, stale = value, copy.deepcopy(model.state_dict()), 0
            else:
                stale += 1
            if stale >= 5:
                break
        model.load_state_dict(state)
        with torch.no_grad():
            pred = {k: model(torch.from_numpy(v)).sigmoid().numpy() for k, v in xs.items()}
        baselines, task_reports = {}, {}
        for j, task in enumerate(TASKS):
            observed = ys["train"][1][:, j].astype(bool)
            target = ys["train"][0][observed, j]
            prior = (target.sum() + 1) / (len(target) + 20)
            candidates = {"smoothed": {k: np.full(len(v), prior) for k, v in xs.items()}}
            if len(set(target)) == 2:
                for label, classifier in [("logistic", LogisticRegression(max_iter=500, random_state=args.seed)),
                                          ("forest", RandomForestClassifier(n_estimators=100, min_samples_leaf=10, random_state=args.seed, n_jobs=2))]:
                    classifier.fit(xs["train"][observed], target)
                    candidates[label] = {k: classifier.predict_proba(v)[:, 1] if len(v) else np.array([]) for k, v in xs.items()}
            vm = ys["validation"][1][:, j].astype(bool)
            vy = ys["validation"][0][vm, j]
            winner = min(candidates, key=lambda k: log_loss(vy, candidates[k]["validation"][vm], labels=[0, 1])) if len(vy) else "smoothed"
            baselines[task] = candidates[winner]
            task_reports[task] = {"baseline": winner, "splits": {}}
            for split in ("validation", "test", "unseen_users"):
                valid = ys[split][1][:, j].astype(bool)
                truth, p = ys[split][0][valid, j], pred[split][valid, j]
                base = candidates[winner][split][valid]
                ci = bootstrap_delta(truth, p, base, np.array([r["user_id"] for r in groups[split]])[valid], args.seed)
                measured = measurements(truth, p)
                reference = measurements(truth, base)
                segments = {}
                for field in ("gender", "campaign_id"):
                    for group in sorted({r[field] for r in groups[split]}):
                        idx = valid & np.array([r[field] == group for r in groups[split]], dtype=bool)
                        segments[f"{field}:{group or 'organic'}"] = measurements(ys[split][0][idx, j], pred[split][idx, j])
                for group in (0, 1):
                    idx = valid & np.array([r["features"].get("new_user", 0) == group for r in groups[split]], dtype=bool)
                    segments[f"new_user:{group}"] = measurements(ys[split][0][idx, j], pred[split][idx, j])
                task_reports[task]["splits"][split] = {"mmoe": measured, "baseline": reference,
                    "log_loss_delta_ci95": ci, "segments": segments,
                    "passed": bool(ci and ci[1] < 0 and measured.get("pr_auc", 0) >= reference.get("pr_auc", 1))}
        approved_tasks = {t: all(task_reports[t]["splits"][s]["passed"] for s in ("test", "unseen_users")) for t in TASKS}
        approved = {"content": all(approved_tasks[t] for t in TASKS[:3]), "ads": approved_tasks["click"]}
        if args.origin == "real" and readiness["campaigns"] < 2:
            approved["ads"] = False
        if args.origin != "real":
            approved = {"content": False, "ads": False}
        reports[name] = {"validation_loss": best, "epochs": epoch + 1, "tasks": task_reports, "approved": approved}
        artifacts[name] = {"version": f"mmoe-v1-{dataset_hash[:12]}-{name}", "origin": args.origin,
                           "dataset_sha256": dataset_hash,
                           "feature_version": FEATURE_VERSION, "encoder": encoder, "approved": approved,
                           "weights": {k: v.tolist() for k, v in state.items()}}
        predictions[name] = pred
    # Select only on validation. Test remains untouched for assessment.
    val_y, val_mask = labels(groups["validation"])
    gender_gains = []
    for j, task in enumerate(TASKS):
        valid = val_mask[:, j].astype(bool)
        ci = bootstrap_delta(val_y[valid, j], predictions["with_gender"]["validation"][valid, j], predictions["without_gender"]["validation"][valid, j],
                             np.array([r["user_id"] for r in groups["validation"]])[valid], args.seed)
        gender_gains.append(bool(ci and ci[1] < 0))
    chosen = "with_gender" if any(gender_gains) and reports["with_gender"]["validation_loss"] < reports["without_gender"]["validation_loss"] else "without_gender"
    artifact = artifacts[chosen]
    if chosen == "with_gender":
        for consumer, tasks in (("content", TASKS[:3]), ("ads", ("click",))):
            gender_benefit = True
            for task in tasks:
                j = TASKS.index(task)
                for split in ("test", "unseen_users"):
                    y, mask = labels(groups[split]); valid = mask[:, j].astype(bool)
                    ci = bootstrap_delta(y[valid, j], predictions[chosen][split][valid, j], predictions["without_gender"][split][valid, j],
                                         np.array([r["user_id"] for r in groups[split]])[valid], args.seed)
                    gender_benefit &= bool(ci and ci[1] < 0)
            artifact["approved"][consumer] &= gender_benefit
    ranking = {}
    for split in ("test", "unseen_users"):
        sessions = defaultdict(list)
        for i, row in enumerate(groups[split]):
            if not int(row["is_ad"]) and all(int(row[f"mask_{t}"]) for t in TASKS[:3]):
                sessions[(row["user_id"], row["session_id"])].append(i)
        measured = {"heuristic": [], "mmoe": []}
        for indices in sessions.values():
            if len(indices) < 2:
                continue
            relevance = np.array([sum(w*int(groups[split][i][t]) for w,t in zip((.5,.2,.3),TASKS[:3])) for i in indices])
            if not relevance.any():
                continue
            measured["heuristic"].append(ndcg_score([relevance], [[legacy_score(groups[split][i]["features"]) for i in indices]]))
            measured["mmoe"].append(ndcg_score([relevance], [predictions[chosen][split][indices, :3] @ np.array([.5,.2,.3])]))
        ranking[split] = {"sessions": len(measured["mmoe"]), **{k: float(np.mean(v)) if v else None for k,v in measured.items()}}
    manifest = {"dataset_sha256": dataset_hash, "origin": args.origin, "seed": args.seed,
                "configuration": {"experts":4, "expert_layers":[64,32], "tower_layers":[16,1], "batch_size":128, "learning_rate":.001,
                                  "max_epochs":args.epochs, "patience":5, "bootstrap_samples":500},
                "packages": {p:version(p) for p in ("torch", "numpy", "scikit-learn")},
                "observed_exposure_ndcg": ranking,
                "selected": chosen, "counts": {k: len(v) for k, v in groups.items()}, "variants": reports,
                "approved": artifact["approved"], "interpretation": "Offline predictive evaluation; not causal CTR lift"}
    (output / "model.json").write_text(json.dumps(artifact), encoding="utf-8")
    (output / "report.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for split, data in groups.items():
        with (output / f"{split}_predictions.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["exposure_id", "user_id", "gender", "origin", *TASKS, *[f"mask_{t}" for t in TASKS], *[f"p_{t}" for t in TASKS]])
            writer.writeheader()
            for row, ps in zip(data, predictions[chosen][split]):
                writer.writerow({**{k: row[k] for k in writer.fieldnames if k in row}, **{f"p_{t}": float(p) for t, p in zip(TASKS, ps)}})
    readiness_path.write_text(json.dumps({"status": "evaluated", "origin": args.origin,
                                          "dataset_sha256": dataset_hash, "model_version": artifact["version"],
                                          "approved": artifact["approved"]}, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("counts", "selected", "approved")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output", default="artifacts/mmoe")
    parser.add_argument("--origin", choices=["real", "simulated"], default="real")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=50)
    arguments = parser.parse_args()
    try:
        run(arguments)
    except DatasetNotReadyError as exc:
        destination = Path(arguments.output)
        destination.mkdir(parents=True, exist_ok=True)
        readiness_path = destination / "readiness.json"
        if not readiness_path.exists() or json.loads(readiness_path.read_text(encoding="utf-8")).get("status") != "insufficient_data":
            readiness_path.write_text(json.dumps({"status":"insufficient_data", "reason":str(exc),
                                                  "origin":arguments.origin}, indent=2), encoding="utf-8")
        parser.exit(2, f"Dataset no entrenable: {exc}\n")
