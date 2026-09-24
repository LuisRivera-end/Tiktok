"""Numpy-only inference: training dependencies are never required to serve."""
import json
import logging
from functools import lru_cache
from pathlib import Path
import numpy as np
from app.config import settings
from app.ml.encoding import encode
from app.ml.features import FEATURE_VERSION, TASKS


def forward(x, weights):
    def linear(a, name):
        return a @ np.asarray(weights[name + ".weight"]).T + np.asarray(weights[name + ".bias"])
    relu = lambda a: np.maximum(a, 0)
    experts = np.stack([relu(linear(relu(linear(x, f"experts.{i}.0")), f"experts.{i}.2")) for i in range(4)], axis=1)
    result = []
    for i in range(4):
        logits = linear(x, f"gates.{i}")
        gates = np.exp(logits - logits.max(axis=1, keepdims=True))
        gates /= gates.sum(axis=1, keepdims=True)
        mix = (experts * gates[:, :, None]).sum(axis=1)
        output = linear(relu(linear(mix, f"towers.{i}.0")), f"towers.{i}.2")
        result.append(1 / (1 + np.exp(-np.clip(output, -40, 40))))
    return np.concatenate(result, axis=1)


@lru_cache(maxsize=2)
def load_model(path, modified):
    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if artifact["feature_version"] != FEATURE_VERSION:
        raise ValueError("Incompatible feature schema")
    return artifact


def predict(features, consumer):
    mode = settings.ads_model_mode if consumer == "ads" else settings.content_model_mode
    if mode == "heuristic":
        return None
    try:
        path = Path(settings.mmoe_model_path)
        model = load_model(str(path), path.stat().st_mtime_ns)
        if model["origin"] == "real":
            readiness = json.loads((path.parent / "readiness.json").read_text(encoding="utf-8"))
            if (readiness.get("status") != "evaluated" or readiness.get("origin") != "real"
                    or readiness.get("dataset_sha256") != model.get("dataset_sha256")
                    or readiness.get("model_version") != model.get("version")):
                raise ValueError("Model validation is incomplete or stale")
        probabilities = forward(encode([features], model["encoder"]), model["weights"])[0]
        if len(probabilities) != 4 or not np.isfinite(probabilities).all():
            raise ValueError("Invalid model probabilities")
        active = mode == "mmoe" and model["approved"].get(consumer, False) and model["origin"] == "real"
        if mode == "mmoe" and not active:
            logging.getLogger(__name__).warning("MMoE %s remains in shadow: promotion gate not met", consumer)
        return {"predictions": {f"p_{task}": float(p) for task, p in zip(TASKS, probabilities)},
                "version": model["version"] if active else "shadow:" + model["version"], "active": active}
    except Exception as exc:
        logging.getLogger(__name__).warning("MMoE fallback (%s): %s", consumer, exc)
        return None
