from app.recsys.scorer import combine_score
from app.recsys.types import PipelineConfig


def test_combine_score_uses_thesis_weights():
    score = combine_score(1, 1, 1, 1, 0)
    assert round(score, 2) == round(0.35 + 0.30 + 0.15 + 0.12, 2)


def test_early_abandon_penalty_when_y5_high():
    cfg = PipelineConfig()
    mild = combine_score(0.8, 0.8, 0.4, 0.3, 0.2, cfg)
    harsh = combine_score(0.8, 0.8, 0.4, 0.3, 0.81, cfg)
    assert harsh < mild
    assert mild - harsh >= cfg.severe_penalty
