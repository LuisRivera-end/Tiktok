"""Data readiness shared by the training command and the laboratory."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from app.ml.features import FEATURE_VERSION, TASKS


class DatasetNotReadyError(ValueError):
    pass


def partition(rows, seed=42):
    users = sorted({r["user_id"] for r in rows})
    np.random.default_rng(seed).shuffle(users)
    held = set(users[:max(1, len(users) // 5)])
    sessions = defaultdict(list)
    for row in rows:
        if row["user_id"] not in held:
            sessions[(row["user_id"], row["session_id"])].append(row)
    ordered = sorted(sessions, key=lambda session: min(r["started_at"] for r in sessions[session]))
    if len(ordered) < 5:
        raise DatasetNotReadyError("Se requieren al menos cinco sesiones fuera de la reserva de usuarios")
    a, b = max(1, int(.7 * len(ordered))), max(2, int(.85 * len(ordered)))
    if b >= len(ordered):
        raise DatasetNotReadyError("Faltan sesiones para la prueba temporal")
    first_val = min(r["started_at"] for s in ordered[a:b] for r in sessions[s])
    first_test = min(r["started_at"] for s in ordered[b:] for r in sessions[s])
    groups = {
        "train": [r for s in ordered[:a] for r in sessions[s] if r["label_end_at"] < first_val],
        "validation": [r for s in ordered[a:b] for r in sessions[s] if r["label_end_at"] < first_test],
        "test": [r for s in ordered[b:] for r in sessions[s]],
        "unseen_users": [r for r in rows if r["user_id"] in held and r["started_at"] >= first_test],
    }
    if any(not groups[k] for k in ("train", "validation", "test", "unseen_users")):
        raise DatasetNotReadyError("Cortes temporales vacíos tras purgar las ventanas de etiquetas; reúne más días")
    return groups


def task_counts(rows):
    result = {}
    for task in TASKS:
        observed = [r for r in rows if int(r[f"mask_{task}"])]
        positives = sum(int(r[task]) for r in observed)
        result[task] = {"observed": len(observed), "positive": positives, "negative": len(observed) - positives}
    return result


def assess(rows, seed=42):
    """Explain whether data support training and an eventual promotion review."""
    rows = [r for r in rows if r.get("origin") == "real" and r.get("feature_version") == FEATURE_VERSION]
    days = sorted({r["started_at"][:10] for r in rows})
    report = {
        "status": "collecting", "feature_version": FEATURE_VERSION,
        "exposures": len(rows), "users": len({r["user_id"] for r in rows}),
        "sessions": len({(r["user_id"], r["session_id"]) for r in rows}),
        "days": len(days), "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
        "campaigns": len({r["campaign_id"] for r in rows if r.get("campaign_id")}),
        "tasks": task_counts(rows), "splits": {}, "reasons": [],
    }
    if len(rows) != len({r["exposure_id"] for r in rows}):
        report["reasons"].append("Hay exposure_id duplicados")
        return report
    if report["users"] < 10:
        report["reasons"].append("Se necesitan al menos diez usuarios para evaluar por usuario")
    if report["days"] < 3:
        report["reasons"].append("Se necesitan exposiciones en varios días para los cortes temporales")
    if report["campaigns"] < 2:
        report["reasons"].append("Se necesitan varias campañas para comparar publicidad entre campañas")
    for task, counts in report["tasks"].items():
        if not counts["observed"]:
            report["reasons"].append(f"{task}: no hay etiquetas maduras observables")
    try:
        groups = partition(rows, seed)
    except DatasetNotReadyError as exc:
        report["reasons"].append(str(exc))
        return report
    report["splits"] = {name: {"exposures": len(group), "users": len({r["user_id"] for r in group}),
                               "tasks": task_counts(group)} for name, group in groups.items()}
    trainable = True
    for split in ("train", "validation"):
        for task, counts in report["splits"][split]["tasks"].items():
            if min(counts["positive"], counts["negative"]) < 1:
                trainable = False
                report["reasons"].append(f"{task}: faltan ambas clases observables en {split}")
    if not trainable:
        return report
    report["status"] = "trainable"
    reviewable = True
    for split in ("test", "unseen_users"):
        if report["splits"][split]["users"] < 10:
            reviewable = False
            report["reasons"].append(f"{split}: menos de diez usuarios")
        for task, counts in report["splits"][split]["tasks"].items():
            if counts["observed"] < 100 or min(counts["positive"], counts["negative"]) < 10:
                reviewable = False
                report["reasons"].append(f"{task}: faltan 100 observaciones y diez de cada clase en {split}")
    if reviewable and report["campaigns"] >= 2:
        report["status"] = "evaluation_ready"
    return report


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico de exposiciones reales para MMoE")
    parser.add_argument("input")
    args = parser.parse_args()
    with Path(args.input).open(encoding="utf-8-sig", newline="") as stream:
        print(json.dumps(assess(list(csv.DictReader(stream))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
