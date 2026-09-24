import numpy as np


def expanded(features, gender=True):
    return {f"{k}={v}" if isinstance(v, str) else k: 1.0 if isinstance(v, str) else float(v)
            for k, v in features.items() if gender or k != "gender"}


def fit_encoder(features, gender=True):
    records = [expanded(f, gender) for f in features]
    keys = sorted({k for f in records for k in f})
    x = np.array([[f.get(k, 0) for k in keys] for f in records], dtype=np.float32)
    return {"keys": keys, "mean": x.mean(0).tolist(), "scale": np.maximum(x.std(0), 1e-4).tolist(), "gender": gender}


def encode(features, encoder):
    records = [expanded(f, encoder["gender"]) for f in features]
    x = np.array([[f.get(k, 0) for k in encoder["keys"]] for f in records], dtype=np.float32)
    return np.clip((x - encoder["mean"]) / encoder["scale"], -10, 10).astype(np.float32)
