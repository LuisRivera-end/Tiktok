import json
from types import SimpleNamespace
import numpy as np
import pytest
from app.ml.encoding import fit_encoder, encode
from app.ml.features import FEATURE_VERSION
from app.ml.serving import forward, predict
from app.ml.readiness import assess
from app.config import settings


def test_encoder_fits_training_only_and_optional_gender():
    encoder = fit_encoder([{"category": "a", "gender": "woman", "duration_s": 10}], False)
    assert not any(k.startswith("gender") for k in encoder["keys"])
    x = encode([{"category": "never_seen", "gender": "man", "duration_s": 999}], encoder)
    assert np.isfinite(x).all() and np.max(np.abs(x)) <= 10


def test_torch_and_serving_numpy_are_equivalent():
    torch = pytest.importorskip("torch")
    from app.ml.network import MMoE, masked_loss
    torch.manual_seed(42)
    model = MMoE(3).eval()
    x = np.random.default_rng(42).normal(size=(7, 3)).astype(np.float32)
    with torch.no_grad():
        expected = model(torch.from_numpy(x)).sigmoid().numpy()
    weights = {k: v.tolist() for k, v in model.state_dict().items()}
    np.testing.assert_allclose(forward(x, weights), expected, atol=1e-6)
    masks = torch.tensor([[1., 0., 0., 0.]])
    a = masked_loss(torch.zeros(1,4), torch.zeros(1,4), masks)
    b = masked_loss(torch.zeros(1,4), torch.tensor([[0.,1.,1.,1.]]), masks)
    assert a == b


def test_missing_or_incompatible_model_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "content_model_mode", "mmoe")
    monkeypatch.setattr(settings, "mmoe_model_path", str(tmp_path / "absent.json"))
    assert predict({}, "content") is None
    file = tmp_path / "wrong.json"
    file.write_text(json.dumps({"feature_version": "old"}))
    monkeypatch.setattr(settings, "mmoe_model_path", str(file))
    assert predict({}, "content") is None


def test_synthetic_model_can_only_run_in_shadow(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from app.ml.network import MMoE
    encoder = fit_encoder([{"duration_s": 10}])
    network = MMoE(1)
    artifact = {"feature_version": FEATURE_VERSION, "version": "synthetic-test", "origin": "simulated",
                "approved": {"content": True, "ads": True}, "encoder": encoder,
                "weights": {k:v.tolist() for k,v in network.state_dict().items()}}
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(artifact))
    monkeypatch.setattr(settings, "mmoe_model_path", str(path))
    monkeypatch.setattr(settings, "content_model_mode", "mmoe")
    result = predict({"duration_s":10}, "content")
    assert not result["active"] and result["version"].startswith("shadow:")
    assert set(result["predictions"]) == {"p_complete","p_engage","p_continue","p_click"}


def test_real_model_requires_matching_completed_evaluation(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from app.ml.network import MMoE
    encoder = fit_encoder([{"duration_s": 10}])
    network = MMoE(1)
    artifact = {"feature_version": FEATURE_VERSION, "version": "real-test", "origin": "real",
                "dataset_sha256": "dataset-hash", "approved": {"content": True, "ads": True},
                "encoder": encoder, "weights": {k:v.tolist() for k,v in network.state_dict().items()}}
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact))
    monkeypatch.setattr(settings, "mmoe_model_path", str(path))
    monkeypatch.setattr(settings, "content_model_mode", "mmoe")
    assert predict({"duration_s": 10}, "content") is None
    readiness = tmp_path / "readiness.json"
    readiness.write_text(json.dumps({"status": "evaluating", "dataset_sha256": "dataset-hash", "origin": "real",
                                     "model_version": "real-test"}))
    assert predict({"duration_s": 10}, "content") is None
    readiness.write_text(json.dumps({"status": "evaluated", "dataset_sha256": "different", "origin": "real",
                                     "model_version": "real-test"}))
    assert predict({"duration_s": 10}, "content") is None
    readiness.write_text(json.dumps({"status": "evaluated", "dataset_sha256": "dataset-hash", "origin": "real",
                                     "model_version": "real-test"}))
    assert predict({"duration_s": 10}, "content")["active"]


def test_readiness_describes_immature_data_and_temporal_volume():
    from app.ml.demo import demo_exposures
    from app.telemetry.exposures import dataset_rows
    rows = dataset_rows(demo_exposures(users=60, days=30))
    for row in rows:
        row["origin"] = "real"
    assert assess(rows)["status"] == "evaluation_ready"
    immature = rows[:20]
    for row in immature:
        for task in ("complete", "engage", "continue", "click"):
            row[f"mask_{task}"] = 0
    report = assess(immature)
    assert report["status"] == "collecting"
    assert report["tasks"]["complete"]["observed"] == 0
    assert report["reasons"]


def test_temporal_partitions_purge_label_windows_and_hold_users_out():
    pytest.importorskip("torch")
    pytest.importorskip("sklearn")
    from app.ml.train import partition
    from app.ml.demo import demo_exposures
    from app.telemetry.exposures import dataset_rows
    groups = partition(dataset_rows(demo_exposures(users=15, days=30)))
    train_users = {r["user_id"] for r in groups["train"]}
    assert not train_users & {r["user_id"] for r in groups["unseen_users"]}
    assert max(r["label_end_at"] for r in groups["train"]) < min(r["started_at"] for r in groups["validation"])
    assert max(r["label_end_at"] for r in groups["validation"]) < min(r["started_at"] for r in groups["test"])
