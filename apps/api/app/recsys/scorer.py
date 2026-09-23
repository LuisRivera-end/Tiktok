from __future__ import annotations

import math

from app.recsys.types import (
    PipelineConfig,
    ScoredCandidate,
    UserFeatures,
    VideoCandidate,
    normalized_region,
)
from app.recsys.vector import cosine

# Weak account signals. They stay far below the 0.45 abandon penalty and below
# a real finish-versus-skip gap, so interest still outranks region or a follow.
REGION_MATCH_BONUS = 0.04
FOLLOW_BONUS = 0.03


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def predict_heads(user: UserFeatures, video: VideoCandidate) -> tuple[float, float, float, float, float]:
    affinity = cosine(user.interest_vector, video.embedding) if user.interest_vector else 0.12
    topic = user.topic_affinity.get(video.category, 0.08)
    audio = user.audio_affinity.get(video.audio_id, 0.0)
    skip_prior = video.skip_rate

    y1 = _sigmoid(1.6 * affinity + 1.1 * topic + 0.4 * audio - 0.9 * skip_prior)
    y2 = _clamp(0.25 + 0.55 * affinity + 0.25 * topic - 0.3 * skip_prior)
    y3 = _sigmoid(0.8 * affinity + 1.4 * audio - 0.4)
    y4 = _sigmoid(0.9 * affinity + 0.7 * topic - 0.6)
    y5 = _sigmoid(-1.4 * affinity + 2.2 * skip_prior + 0.3 - 0.6 * topic)
    return y1, y2, y3, y4, y5


def combine_score(
    y1: float,
    y2: float,
    y3: float,
    y4: float,
    y5: float,
    config: PipelineConfig | None = None,
) -> float:
    cfg = config or PipelineConfig()
    w1, w2, w3, w4, w5 = cfg.weights
    score = w1 * y1 + w2 * y2 + w3 * y3 + w4 * y4 - w5 * y5
    if y5 > cfg.early_abandon_threshold:
        score -= cfg.severe_penalty
    return score


def context_adjustment(user: UserFeatures, video: VideoCandidate) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []
    user_region = normalized_region(user.region)
    video_region = normalized_region(video.region)
    if user_region and video_region and user_region == video_region:
        bonus += REGION_MATCH_BONUS
        reasons.append("same_region")
    creator_id = video.creator_id or ""
    if creator_id and creator_id in user.followed_creator_ids:
        bonus += FOLLOW_BONUS
        reasons.append("followed")
    return bonus, reasons


def score_candidate(
    user: UserFeatures, video: VideoCandidate, source: str, config: PipelineConfig
) -> ScoredCandidate:
    y1, y2, y3, y4, y5 = predict_heads(user, video)
    score = combine_score(y1, y2, y3, y4, y5, config)
    extra, extra_reasons = context_adjustment(user, video)
    score += extra
    reasons = [source, *extra_reasons]
    if y5 > config.early_abandon_threshold:
        reasons.append("early_abandon_penalty")
    if source == "explore":
        reasons.append("new_creator")
    return ScoredCandidate(
        video=video,
        y1=y1,
        y2=y2,
        y3=y3,
        y4=y4,
        y5=y5,
        score=score,
        source=source,
        reasons=reasons,
    )
